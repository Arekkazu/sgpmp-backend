"""Regresión INC-M01-18-092 (RF-14): bloqueo/inactivación de cuenta debe notificar
al usuario afectado.

Dos causas raíz distintas, cada una con su propia prueba:

1. `GestionarCuentaUseCase` registraba el evento de auditoría bajo el
   `id_usuario` del ADMINISTRADOR actor en vez del usuario afectado, así que
   `NotificacionService` nunca encontraba el evento a notificar (busca por
   `id_usuario` = destinatario) y omitía el envío siempre, sin importar la
   acción.
2. `NotificacionService` suprimía sin excepción cualquier notificación a una
   cuenta ya INACTIVA — pero para cuando se llama a `notificar()` (después del
   commit del cambio de estado), la cuenta YA está en ese estado, así que la
   propia notificación de "tu cuenta fue inactivada" se autosuprimía.
"""
from __future__ import annotations

from types import SimpleNamespace

from src.identity_access.application.use_cases.cuentas.gestionar_cuenta_use_case import (
    TIPO_CAMBIO_ESTADO,
    GestionarCuentaUseCase,
)
from src.identity_access.domain.entities.cuenta import Cuenta
from src.identity_access.infrastructure.dto.gestion_cuenta_dto import GestionarCuentaDTO
from src.shared.notificacion_service import ESTADO_BLOQUEADO, ESTADO_INACTIVO, NotificacionService


class _DbFake:
    def __init__(self) -> None:
        self.commits = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:  # pragma: no cover - no se ejercita en estos casos
        pass


class _UsuariosRepoFake:
    def obtener_por_id(self, id_usuario: int):
        return SimpleNamespace(id_usuario=id_usuario, id_rol=2, correo="afectado@example.com")


class _CuentasRepoFake:
    def __init__(self, estado_inicial: int) -> None:
        self.estado_inicial = estado_inicial
        self.guardada: Cuenta | None = None

    def obtener_por_usuario(self, id_usuario: int) -> Cuenta:
        return Cuenta(
            id_cuenta_usuario=8,
            id_usuario=id_usuario,
            id_estado_cuenta=self.estado_inicial,
        )

    def guardar(self, cuenta: Cuenta) -> Cuenta:
        self.guardada = cuenta
        return cuenta

    def registrar_gestion(self, **_kwargs) -> None:
        pass

    def contar_usuarios_activos_por_rol(self, _id_rol: int) -> int:
        return 5  # nunca es el último admin en estas pruebas


class _RolesRepoFake:
    def obtener_por_id(self, id_rol: int):
        return SimpleNamespace(id_rol=id_rol, es_protegido=False)


class _EventosRepoFake:
    def __init__(self) -> None:
        self.registros: list[dict] = []

    def registrar(self, **kwargs) -> None:
        self.registros.append(kwargs)


def _ejecutar_gestion(accion: str, estado_inicial: int) -> tuple[_EventosRepoFake, int]:
    eventos = _EventosRepoFake()
    use_case = GestionarCuentaUseCase(
        usuarios_repo=_UsuariosRepoFake(),
        cuentas_repo=_CuentasRepoFake(estado_inicial),
        eventos_repo=eventos,
        sesiones_repo=SimpleNamespace(invalidar_todas_sesiones=lambda *_a, **_k: None),
        roles_repo=_RolesRepoFake(),
        db=_DbFake(),
    )
    id_usuario_afectado = 55
    use_case.execute(
        id_usuario=id_usuario_afectado,
        dto=GestionarCuentaDTO(accion_cuenta=accion, motivo_accion="Justificación de prueba"),
        usuario_actual=SimpleNamespace(id_usuario=1, id_rol=1),
    )
    return eventos, id_usuario_afectado


def test_bloquear_registra_el_evento_bajo_el_usuario_afectado_no_el_actor() -> None:
    eventos, id_usuario_afectado = _ejecutar_gestion("bloquear", Cuenta.ESTADO_ACTIVO)

    assert len(eventos.registros) == 1
    evento = eventos.registros[0]
    assert evento["id_usuario"] == id_usuario_afectado
    assert evento["tipo_evento"] == TIPO_CAMBIO_ESTADO
    assert evento["detalle"]["id_usuario_responsable"] == 1


def test_inactivar_registra_el_evento_bajo_el_usuario_afectado_no_el_actor() -> None:
    eventos, id_usuario_afectado = _ejecutar_gestion("inactivar", Cuenta.ESTADO_ACTIVO)

    assert eventos.registros[0]["id_usuario"] == id_usuario_afectado


class _PortNotificacionFake:
    """Sustituye el evento real por uno cuyo id_usuario coincide con el que
    `GestionarCuentaUseCase` ya registró (post-fix), simulando lo que vería
    `NotificacionService` en producción tras el fix del evento."""

    def __init__(self, estado_cuenta: int) -> None:
        self.estado_cuenta = estado_cuenta
        self.enviados: list[dict] = []

    def buscar_estado_cuenta(self, _id_usuario):
        return self.estado_cuenta

    def buscar_ultimo_evento_id(self, _id_usuario, _tipo_evento):
        return 999  # el evento SÍ existe, porque ahora se registra bajo el afectado

    def buscar_correo_usuario(self, _id_usuario):
        return "afectado@example.com"

    def buscar_fcm_tokens(self, _id_usuario):
        return []

    def verificar_anti_spam(self, *_a, **_k):
        return False

    def registrar(self, **datos) -> int:
        self.enviados.append(datos)
        return len(self.enviados)

    def actualizar_estado(self, _id_notificacion, _estado) -> None:
        pass


def test_notificacion_no_se_autosuprime_para_cuenta_recien_inactivada(monkeypatch) -> None:
    from src.shared import notificacion_service as modulo

    monkeypatch.setattr(modulo, "send_email", lambda **_k: None)
    port = _PortNotificacionFake(estado_cuenta=ESTADO_INACTIVO)
    servicio = NotificacionService(port=port, db=_DbFake())

    servicio.notificar(tipo_evento=TIPO_CAMBIO_ESTADO, id_usuario=55, correo_destino="afectado@example.com")

    assert len(port.enviados) == 2  # email + interno


def test_notificacion_no_se_autosuprime_para_cuenta_recien_bloqueada(monkeypatch) -> None:
    from src.shared import notificacion_service as modulo

    monkeypatch.setattr(modulo, "send_email", lambda **_k: None)
    port = _PortNotificacionFake(estado_cuenta=ESTADO_BLOQUEADO)
    servicio = NotificacionService(port=port, db=_DbFake())

    servicio.notificar(tipo_evento=TIPO_CAMBIO_ESTADO, id_usuario=55, correo_destino="afectado@example.com")

    assert len(port.enviados) == 2


def test_notificacion_no_relacionada_con_seguridad_sigue_suprimida_si_esta_inactiva(monkeypatch) -> None:
    """La excepción es solo para eventos de seguridad: una cuenta inactiva
    sigue sin recibir, por ejemplo, un aviso de 'perfil actualizado' (tipo 9)."""
    from src.shared import notificacion_service as modulo

    monkeypatch.setattr(modulo, "send_email", lambda **_k: None)
    port = _PortNotificacionFake(estado_cuenta=ESTADO_INACTIVO)
    servicio = NotificacionService(port=port, db=_DbFake())

    servicio.notificar(tipo_evento=9, id_usuario=55, correo_destino="afectado@example.com")

    assert port.enviados == []
