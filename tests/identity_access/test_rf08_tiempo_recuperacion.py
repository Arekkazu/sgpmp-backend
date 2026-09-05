"""Regresiones de anti-enumeración temporal para RF-08."""
from __future__ import annotations

import asyncio
from time import monotonic, sleep
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import BackgroundTasks

from src.identity_access.application.use_cases.contrasena.solicitar_recuperacion_use_case import (
    SolicitarRecuperacionUseCase,
)
from src.identity_access.infrastructure.adapters import (
    correo_recuperacion_background_adapter as correo_adapter,
)
from src.identity_access.infrastructure.adapters.correo_recuperacion_background_adapter import (
    CorreoRecuperacionBackgroundAdapter,
)
from src.identity_access.infrastructure.dto.contrasena_dto import (
    SolicitarRecuperacionDTO,
)
from src.shared import notificacion_service as notificacion_module
from src.shared.notificacion_service import NotificacionService

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
    def __init__(self, usuario) -> None:
        self.usuario = usuario

    def obtener_por_correo(self, _correo):
        return self.usuario


class CuentasRepoFake:
    def __init__(self, cuenta, fallar_guardado: bool = False) -> None:
        self.cuenta = cuenta
        self.fallar_guardado = fallar_guardado

    def obtener_por_usuario(self, _id_usuario):
        return self.cuenta

    def guardar(self, _cuenta) -> None:
        if self.fallar_guardado:
            raise RuntimeError("persistencia no disponible")


class EventosRepoFake:
    def __init__(self) -> None:
        self.eventos = []

    def contar_solicitudes_recuperacion_por_ip(self, _ip, _desde):
        return 0

    def registrar(self, **datos) -> None:
        self.eventos.append(datos)


def _ejecutar(usuario, cuenta, tareas: BackgroundTasks):
    db = DbFake()
    caso = SolicitarRecuperacionUseCase(
        usuarios_repo=UsuariosRepoFake(usuario),
        cuentas_repo=CuentasRepoFake(cuenta),
        eventos_repo=EventosRepoFake(),
        db=db,
        correo_recuperacion_port=CorreoRecuperacionBackgroundAdapter(tareas),
    )
    inicio = monotonic()
    mensaje = caso.execute(
        SolicitarRecuperacionDTO(correo_electronico="persona@example.com"),
        "198.51.100.41",
    )
    return (monotonic() - inicio) * 1000, mensaje, db


def test_smtp_lento_no_diferencia_el_request_de_correo_existente(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tareas_existente = BackgroundTasks()
    tareas_inexistente = BackgroundTasks()
    despachos = []

    def smtp_lento(**datos) -> None:
        sleep(0.45)
        despachos.append(datos)

    monkeypatch.setattr(
        correo_adapter,
        "procesar_correo_recuperacion_background",
        smtp_lento,
    )
    usuario = SimpleNamespace(id_usuario=41, nombre="Ana")
    cuenta = MagicMock(id_estado_cuenta=2)
    cuenta.esta_pendiente.return_value = False

    tiempo_existente, mensaje_existente, db = _ejecutar(
        usuario,
        cuenta,
        tareas_existente,
    )
    tiempo_inexistente, mensaje_inexistente, _ = _ejecutar(
        None,
        None,
        tareas_inexistente,
    )

    assert mensaje_existente == mensaje_inexistente == MENSAJE_GENERICO
    assert abs(tiempo_existente - tiempo_inexistente) < 300
    assert tiempo_existente < 300
    assert despachos == []
    assert db.commits == 1
    assert len(tareas_existente.tasks) == 1
    assert len(tareas_inexistente.tasks) == 0

    asyncio.run(tareas_existente())

    assert len(despachos) == 1


def test_cuenta_pendiente_programa_activacion_despues_del_commit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tareas = BackgroundTasks()
    despachos = []
    monkeypatch.setattr(
        correo_adapter,
        "procesar_correo_recuperacion_background",
        lambda **datos: despachos.append(datos),
    )
    usuario = SimpleNamespace(id_usuario=42, nombre="Beto")
    cuenta = MagicMock(id_estado_cuenta=1)
    cuenta.esta_pendiente.return_value = True

    _, mensaje, db = _ejecutar(usuario, cuenta, tareas)

    assert mensaje == MENSAJE_GENERICO
    assert db.commits == 1
    assert despachos == []
    asyncio.run(tareas())
    assert despachos[0]["flujo"] == "activacion"


def test_fallo_de_persistencia_no_programa_correo() -> None:
    tareas = BackgroundTasks()
    usuario = SimpleNamespace(id_usuario=43, nombre="Caro")
    cuenta = MagicMock(id_estado_cuenta=2)
    cuenta.esta_pendiente.return_value = False
    db = DbFake()
    caso = SolicitarRecuperacionUseCase(
        usuarios_repo=UsuariosRepoFake(usuario),
        cuentas_repo=CuentasRepoFake(cuenta, fallar_guardado=True),
        eventos_repo=EventosRepoFake(),
        db=db,
        correo_recuperacion_port=CorreoRecuperacionBackgroundAdapter(tareas),
    )

    with pytest.raises(RuntimeError, match="persistencia no disponible"):
        caso.execute(
            SolicitarRecuperacionDTO(correo_electronico="persona@example.com"),
            "198.51.100.43",
        )

    assert db.commits == 0
    assert db.rollbacks == 1
    assert tareas.tasks == []


@pytest.mark.parametrize(
    ("flujo", "asunto", "contenido_esperado"),
    [
        (
            "recuperacion",
            "Restablece tu contraseña en SGPMP",
            "restablecer-contrasena",
        ),
        ("activacion", "Activa tu cuenta en SGPMP", "activar?token="),
    ],
)
def test_tarea_background_usa_plantilla_y_sesion_independiente(
    flujo: str,
    asunto: str,
    contenido_esperado: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = MagicMock()
    servicio = MagicMock()
    servicio_cls = MagicMock(return_value=servicio)
    monkeypatch.setattr(correo_adapter, "SessionLocal", lambda: db)
    monkeypatch.setattr(
        correo_adapter,
        "SqlAlchemyNotificacionRepository",
        lambda sesion: ("repo", sesion),
    )
    monkeypatch.setattr(correo_adapter, "NotificacionService", servicio_cls)

    correo_adapter.procesar_correo_recuperacion_background(
        correo="persona@example.com",
        nombre="Ana",
        token="token-crudo-041",
        id_usuario=41,
        flujo=flujo,
    )

    servicio_cls.assert_called_once_with(port=("repo", db), db=db)
    datos = servicio.notificar.call_args.kwargs
    assert datos["tipo_evento"] == 7
    assert datos["id_usuario"] == 41
    assert datos["correo_destino"] == "persona@example.com"
    assert datos["asunto_email"] == asunto
    assert contenido_esperado in datos["contenido_html_email"]
    assert "token-crudo-041" in datos["contenido_html_email"]
    assert datos["aplicar_anti_spam_email"] is False
    db.close.assert_called_once_with()


def test_fallo_de_tarea_background_se_registra_y_cierra_la_sesion(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    db = MagicMock()
    monkeypatch.setattr(correo_adapter, "SessionLocal", lambda: db)
    monkeypatch.setattr(
        correo_adapter,
        "SqlAlchemyNotificacionRepository",
        lambda _sesion: MagicMock(),
    )
    monkeypatch.setattr(
        correo_adapter,
        "NotificacionService",
        MagicMock(side_effect=RuntimeError("servicio no disponible")),
    )

    correo_adapter.procesar_correo_recuperacion_background(
        correo="persona@example.com",
        nombre="Ana",
        token="token-crudo-041",
        id_usuario=41,
        flujo="recuperacion",
    )

    assert "No fue posible procesar en segundo plano" in caplog.text
    db.close.assert_called_once_with()


def test_token_nuevo_omite_anti_spam_solo_para_el_email(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    port = MagicMock()
    port.buscar_estado_cuenta.return_value = 2
    port.buscar_ultimo_evento_id.return_value = 77
    port.buscar_fcm_tokens.return_value = []
    port.verificar_anti_spam.return_value = True
    port.registrar.return_value = 88
    enviados = []
    monkeypatch.setattr(
        notificacion_module,
        "send_email",
        lambda **datos: enviados.append(datos),
    )

    NotificacionService(port=port, db=DbFake()).notificar(
        tipo_evento=7,
        id_usuario=41,
        correo_destino="persona@example.com",
        asunto_email="Restablece tu contraseña en SGPMP",
        contenido_html_email="<p>token nuevo</p>",
        aplicar_anti_spam_email=False,
    )

    assert enviados == [
        {
            "to": "persona@example.com",
            "subject": "Restablece tu contraseña en SGPMP",
            "html_body": "<p>token nuevo</p>",
        }
    ]
    assert port.registrar.call_count == 1
    assert port.registrar.call_args.kwargs["id_canal"] == 1
    port.verificar_anti_spam.assert_called_once_with(41, 7, 2, 5)
