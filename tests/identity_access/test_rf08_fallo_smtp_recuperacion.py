"""Pruebas de resiliencia SMTP para la recuperación de contraseña RF-08."""
from unittest.mock import MagicMock, patch

import pytest

from src.identity_access.application.use_cases.contrasena.solicitar_recuperacion_use_case import (
    ACCION_LEER,
    ID_CANAL_INTERNO,
    RECURSO_AUDITORIA,
    SolicitarRecuperacionUseCase,
)
from src.identity_access.infrastructure.dto.contrasena_dto import SolicitarRecuperacionDTO
from src.shared.errors import ServiceUnavailableError


CORREO = "persona@ejemplo.com"
MENSAJE_GENERICO = (
    "Si el correo está registrado, recibirás instrucciones para recuperar "
    "tu contraseña en unos minutos."
)


class DbFake:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class UsuariosRepoFake:
    def __init__(self, usuario, destinatarios=None) -> None:
        self.usuario = usuario
        self.destinatarios = [10, 20] if destinatarios is None else destinatarios
        self.consultas_permiso = []

    def obtener_por_correo(self, correo):
        return self.usuario

    def listar_ids_con_permiso(self, id_recurso, id_accion):
        self.consultas_permiso.append((id_recurso, id_accion))
        return self.destinatarios


class CuentasRepoFake:
    def __init__(self, cuenta, fallar_guardado: bool = False) -> None:
        self.cuenta = cuenta
        self.fallar_guardado = fallar_guardado
        self.guardadas = 0

    def obtener_por_usuario(self, id_usuario):
        return self.cuenta

    def guardar(self, cuenta):
        if self.fallar_guardado:
            raise RuntimeError("base no disponible")
        self.guardadas += 1


class EventosRepoFake:
    def __init__(self) -> None:
        self.registrados = []

    def contar_solicitudes_recuperacion_por_ip(self, ip, desde):
        return 0

    def registrar(self, tipo_evento, exitoso, id_usuario, detalle, **kwargs):
        self.registrados.append((tipo_evento, exitoso, id_usuario, detalle))


class IntentosAnonimosRepoFake:
    def __init__(self) -> None:
        self.registrados = []

    def registrar(self, tipo, ip):
        self.registrados.append((tipo, ip))

    def contar_por_ip(self, tipo, ip, desde):
        return 1

    def obtener_fecha_mas_antigua_por_ip(self, tipo, ip, desde):
        return None


class NotificacionesRepoFake:
    def __init__(self, id_evento=77, fallar=False) -> None:
        self.id_evento = id_evento
        self.fallar = fallar
        self.registradas = []

    def buscar_ultimo_evento_id(self, id_usuario, tipo_evento):
        return self.id_evento

    def registrar(self, **datos):
        if self.fallar:
            raise RuntimeError("bandeja interna no disponible")
        self.registradas.append(datos)
        return len(self.registradas)


def _error_smtp():
    return ServiceUnavailableError(
        code="EMAIL_NO_DISPONIBLE",
        message="El servicio SMTP no está disponible.",
    )


def _construir_caso(*, pendiente=False, destinatarios=None, fallar_alerta=False, fallar_guardado=False):
    usuario = MagicMock(id_usuario=74, nombre="Ana")
    cuenta = MagicMock(id_estado_cuenta=2)
    cuenta.esta_pendiente.return_value = pendiente
    usuarios = UsuariosRepoFake(usuario, destinatarios)
    cuentas = CuentasRepoFake(cuenta, fallar_guardado=fallar_guardado)
    eventos = EventosRepoFake()
    intentos_anonimos = IntentosAnonimosRepoFake()
    notificaciones = NotificacionesRepoFake(fallar=fallar_alerta)
    servicio_usuario = MagicMock()
    db = DbFake()
    caso = SolicitarRecuperacionUseCase(
        usuarios_repo=usuarios,
        cuentas_repo=cuentas,
        eventos_repo=eventos,
        intentos_anonimos_repo=intentos_anonimos,
        db=db,
        notificacion_service=servicio_usuario,
        notificaciones_repo=notificaciones,
    )
    return caso, usuarios, cuentas, eventos, notificaciones, servicio_usuario, db


@patch(
    "src.identity_access.application.use_cases.contrasena."
    "solicitar_recuperacion_use_case.send_email",
    side_effect=_error_smtp(),
)
def test_fallo_smtp_conserva_202_logico_y_alerta_a_destinatarios_rbac(mock_email) -> None:
    caso, usuarios, cuentas, eventos, notificaciones, servicio_usuario, db = _construir_caso()

    resultado = caso.execute(
        SolicitarRecuperacionDTO(correo_electronico=CORREO),
        ip="203.0.113.10",
    )

    assert resultado == MENSAJE_GENERICO
    assert cuentas.guardadas == 1
    assert len(eventos.registrados) == 1
    assert eventos.registrados[0][1] is True
    assert usuarios.consultas_permiso == [(RECURSO_AUDITORIA, ACCION_LEER)]
    assert [n["id_usuario"] for n in notificaciones.registradas] == [10, 20]
    assert {n["id_evento"] for n in notificaciones.registradas} == {77}
    assert {n["id_canal"] for n in notificaciones.registradas} == {ID_CANAL_INTERNO}
    assert {n["estado"] for n in notificaciones.registradas} == {"enviado"}
    assert all("EMAIL_NO_DISPONIBLE" in n["mensaje"] for n in notificaciones.registradas)
    assert all(CORREO not in n["mensaje"] for n in notificaciones.registradas)
    assert db.commits == 3
    assert db.rollbacks == 0
    servicio_usuario.notificar.assert_not_called()
    mock_email.assert_called_once()


@patch(
    "src.identity_access.application.use_cases.contrasena."
    "solicitar_recuperacion_use_case.send_email",
    side_effect=_error_smtp(),
)
def test_fallo_smtp_en_cuenta_pendiente_tambien_responde_generico_y_alerta(mock_email) -> None:
    caso, _, cuentas, eventos, notificaciones, _, db = _construir_caso(pendiente=True)

    resultado = caso.execute(
        SolicitarRecuperacionDTO(correo_electronico=CORREO),
        ip="203.0.113.11",
    )

    assert resultado == MENSAJE_GENERICO
    assert cuentas.guardadas == 1
    assert eventos.registrados[0][3]["motivo"] == "cuenta_pendiente_token_activacion_rotado"
    assert all("ACTIVACION_CUENTA_PENDIENTE" in n["mensaje"] for n in notificaciones.registradas)
    assert db.commits == 3
    mock_email.assert_called_once()


@patch(
    "src.identity_access.application.use_cases.contrasena."
    "solicitar_recuperacion_use_case.send_email",
    side_effect=_error_smtp(),
)
def test_fallo_de_la_alerta_no_restaura_el_503_ni_revierte_el_token(mock_email) -> None:
    caso, _, cuentas, eventos, _, _, db = _construir_caso(fallar_alerta=True)

    resultado = caso.execute(
        SolicitarRecuperacionDTO(correo_electronico=CORREO),
        ip="203.0.113.12",
    )

    assert resultado == MENSAJE_GENERICO
    assert cuentas.guardadas == 1
    assert len(eventos.registrados) == 1
    assert db.commits == 2
    assert db.rollbacks == 1


@patch(
    "src.identity_access.application.use_cases.contrasena."
    "solicitar_recuperacion_use_case.send_email",
    side_effect=_error_smtp(),
)
def test_sin_destinatarios_registra_el_fallo_en_log_y_mantiene_respuesta(mock_email, caplog) -> None:
    caso, _, _, _, notificaciones, _, db = _construir_caso(destinatarios=[])

    resultado = caso.execute(
        SolicitarRecuperacionDTO(correo_electronico=CORREO),
        ip="203.0.113.13",
    )

    assert resultado == MENSAJE_GENERICO
    assert notificaciones.registradas == []
    assert db.commits == 2
    assert "sin destinatarios RBAC" in caplog.text


@patch(
    "src.identity_access.application.use_cases.contrasena."
    "solicitar_recuperacion_use_case.send_email",
)
def test_smtp_exitoso_conserva_la_notificacion_normal_del_usuario(mock_email) -> None:
    caso, usuarios, _, _, notificaciones, servicio_usuario, db = _construir_caso()

    resultado = caso.execute(
        SolicitarRecuperacionDTO(correo_electronico=CORREO),
        ip="203.0.113.14",
    )

    assert resultado == MENSAJE_GENERICO
    assert usuarios.consultas_permiso == []
    assert notificaciones.registradas == []
    assert db.commits == 2
    servicio_usuario.notificar.assert_called_once()
    mock_email.assert_called_once()


@patch(
    "src.identity_access.application.use_cases.contrasena."
    "solicitar_recuperacion_use_case.send_email",
)
def test_fallo_de_persistencia_se_propaga_y_no_envia_correo(mock_email) -> None:
    caso, _, _, _, notificaciones, _, db = _construir_caso(fallar_guardado=True)

    with pytest.raises(RuntimeError, match="base no disponible"):
        caso.execute(
            SolicitarRecuperacionDTO(correo_electronico=CORREO),
            ip="203.0.113.15",
        )

    assert db.commits == 1
    assert db.rollbacks == 1
    assert notificaciones.registradas == []
    mock_email.assert_not_called()
