"""Pruebas de resiliencia SMTP para la recuperación de contraseña RF-08.

El envío de correo y la alerta administrativa por fallo SMTP (INC-M01-14-044)
viven en ``correo_recuperacion_background_adapter`` desde INC-M01-21-041 (el
correo se despacha en segundo plano para evitar el canal lateral de tiempo,
ver ``test_rf08_tiempo_recuperacion.py``). Antes vivían dentro de
``SolicitarRecuperacionUseCase``; se movieron aquí sin perder cobertura.
"""
from unittest.mock import MagicMock

import pytest

from src.identity_access.infrastructure.adapters import (
    correo_recuperacion_background_adapter as correo_adapter,
)
from src.shared import notificacion_service as notificacion_module
from src.shared.notificacion_service import NotificacionService

CORREO = "persona@ejemplo.com"


class DbFake:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0
        self.cerrada = False

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def close(self) -> None:
        self.cerrada = True


class NotificacionRepoFake:
    def __init__(self, id_evento=77) -> None:
        self.id_evento = id_evento
        self.registradas = []
        self.fallar_para: set[int] = set()

    def buscar_estado_cuenta(self, _id_usuario):
        return 2  # ACTIVO

    def buscar_ultimo_evento_id(self, id_usuario, tipo_evento):
        return self.id_evento

    def buscar_correo_usuario(self, _id_usuario):
        return CORREO

    def buscar_fcm_tokens(self, _id_usuario):
        return []

    def verificar_anti_spam(self, _id_usuario, _tipo_evento, _id_canal, _ventana):
        return False

    def registrar(self, id_evento, id_usuario, id_canal, mensaje, estado):
        if id_usuario in self.fallar_para:
            raise RuntimeError("bandeja interna no disponible")
        self.registradas.append(
            {
                "id_evento": id_evento,
                "id_usuario": id_usuario,
                "id_canal": id_canal,
                "mensaje": mensaje,
                "estado": estado,
            }
        )
        return len(self.registradas)

    def actualizar_estado(self, _id_notificacion, _estado):
        pass


class UsuariosRepoFake:
    def __init__(self, destinatarios=(10, 20)) -> None:
        self.destinatarios = list(destinatarios)
        self.consultas_permiso = []

    def listar_ids_con_permiso(self, id_recurso, id_accion):
        self.consultas_permiso.append((id_recurso, id_accion))
        return self.destinatarios


def _preparar(monkeypatch, *, destinatarios=(10, 20), fallar_registro=False):
    db = DbFake()
    notificaciones = NotificacionRepoFake()
    if fallar_registro:
        notificaciones.fallar_para = set(destinatarios)
    usuarios = UsuariosRepoFake(destinatarios)
    monkeypatch.setattr(correo_adapter, "SessionLocal", lambda: db)
    monkeypatch.setattr(
        correo_adapter, "SqlAlchemyNotificacionRepository", lambda _db: notificaciones
    )
    monkeypatch.setattr(
        correo_adapter, "SqlAlchemyUsuarioRepository", lambda _db: usuarios
    )
    return db, notificaciones, usuarios


def test_fallo_smtp_alerta_a_destinatarios_rbac(monkeypatch, caplog) -> None:
    db, notificaciones, usuarios = _preparar(monkeypatch)
    monkeypatch.setattr(
        notificacion_module,
        "send_email",
        MagicMock(side_effect=RuntimeError("EMAIL_NO_DISPONIBLE")),
    )

    correo_adapter.procesar_correo_recuperacion_background(
        correo=CORREO,
        nombre="Ana",
        token="token-crudo",
        id_usuario=74,
        flujo="recuperacion",
    )

    # notificar() también registra las filas EMAIL/INTERNO propias del usuario
    # que pidió la recuperación (id_usuario=74); la alerta administrativa se
    # distingue por ir dirigida a los destinatarios RBAC (10, 20).
    alertas = [n for n in notificaciones.registradas if n["id_usuario"] in (10, 20)]

    assert usuarios.consultas_permiso == [
        (correo_adapter.RECURSO_AUDITORIA, correo_adapter.ACCION_LEER)
    ]
    assert [n["id_usuario"] for n in alertas] == [10, 20]
    assert {n["id_evento"] for n in alertas} == {77}
    assert {n["id_canal"] for n in alertas} == {correo_adapter.ID_CANAL_INTERNO}
    assert {n["estado"] for n in alertas} == {"enviado"}
    assert all("Usuario relacionado: 74" in n["mensaje"] for n in alertas)
    assert db.commits >= 1
    assert db.cerrada is True


def test_fallo_smtp_en_activacion_tambien_alerta(monkeypatch) -> None:
    _, notificaciones, _ = _preparar(monkeypatch)
    monkeypatch.setattr(
        notificacion_module,
        "send_email",
        MagicMock(side_effect=RuntimeError("EMAIL_NO_DISPONIBLE")),
    )

    correo_adapter.procesar_correo_recuperacion_background(
        correo=CORREO,
        nombre="Ana",
        token="token-crudo",
        id_usuario=74,
        flujo="activacion",
    )

    alertas = [n for n in notificaciones.registradas if n["id_usuario"] in (10, 20)]
    assert alertas
    assert all("Flujo: activacion" in n["mensaje"] for n in alertas)


def test_fallo_de_la_alerta_no_interrumpe_el_procesamiento(monkeypatch, caplog) -> None:
    db, _, _ = _preparar(monkeypatch, fallar_registro=True)
    monkeypatch.setattr(
        notificacion_module,
        "send_email",
        MagicMock(side_effect=RuntimeError("EMAIL_NO_DISPONIBLE")),
    )

    correo_adapter.procesar_correo_recuperacion_background(
        correo=CORREO,
        nombre="Ana",
        token="token-crudo",
        id_usuario=74,
        flujo="recuperacion",
    )

    assert "No se pudo persistir la alerta interna" in caplog.text
    assert db.cerrada is True


def test_sin_destinatarios_registra_el_fallo_en_log(monkeypatch, caplog) -> None:
    _, notificaciones, _ = _preparar(monkeypatch, destinatarios=())
    monkeypatch.setattr(
        notificacion_module,
        "send_email",
        MagicMock(side_effect=RuntimeError("EMAIL_NO_DISPONIBLE")),
    )

    correo_adapter.procesar_correo_recuperacion_background(
        correo=CORREO,
        nombre="Ana",
        token="token-crudo",
        id_usuario=74,
        flujo="recuperacion",
    )

    assert [n for n in notificaciones.registradas if n["id_usuario"] != 74] == []
    assert "sin destinatarios RBAC" in caplog.text


def test_smtp_exitoso_no_dispara_alerta(monkeypatch) -> None:
    _, notificaciones, usuarios = _preparar(monkeypatch)
    monkeypatch.setattr(notificacion_module, "send_email", MagicMock())

    correo_adapter.procesar_correo_recuperacion_background(
        correo=CORREO,
        nombre="Ana",
        token="token-crudo",
        id_usuario=74,
        flujo="recuperacion",
    )

    assert usuarios.consultas_permiso == []
    assert [n for n in notificaciones.registradas if n["id_usuario"] != 74] == []


def test_notificacion_service_reporta_fallo_de_email_al_llamador(monkeypatch) -> None:
    """La pieza que permite alertar: notificar() debe exponer si EMAIL falló."""
    port = NotificacionRepoFake()
    monkeypatch.setattr(
        notificacion_module,
        "send_email",
        MagicMock(side_effect=RuntimeError("EMAIL_NO_DISPONIBLE")),
    )

    resultado = NotificacionService(port=port, db=DbFake()).notificar(
        tipo_evento=7,
        id_usuario=74,
        correo_destino=CORREO,
        asunto_email="Restablece tu contraseña en SGPMP",
        contenido_html_email="<p>token</p>",
        aplicar_anti_spam_email=False,
    )

    assert resultado is False


def test_notificacion_service_reporta_exito_de_email_al_llamador(monkeypatch) -> None:
    port = NotificacionRepoFake()
    monkeypatch.setattr(notificacion_module, "send_email", MagicMock())

    resultado = NotificacionService(port=port, db=DbFake()).notificar(
        tipo_evento=7,
        id_usuario=74,
        correo_destino=CORREO,
        asunto_email="Restablece tu contraseña en SGPMP",
        contenido_html_email="<p>token</p>",
        aplicar_anti_spam_email=False,
    )

    assert resultado is True
