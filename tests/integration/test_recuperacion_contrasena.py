"""Flujo HTTP/BD de recuperación y restablecimiento de contraseña."""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone

import bcrypt
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.identity_access.domain.value_objects.token_un_solo_uso import calcular_hash_token

pytestmark = pytest.mark.integration


def test_recuperacion_guarda_hash_y_restablecimiento_consume_token(
    client,
    db_session: Session,
    crear_usuario_db,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.identity_access.application.use_cases.contrasena import (
        solicitar_recuperacion_use_case,
    )
    from src.shared import notificacion_service

    usuario = crear_usuario_db(id_rol=2, estado=2)
    token_crudo = "token-integracion-recuperacion"
    correos: list[dict] = []
    monkeypatch.setattr(
        solicitar_recuperacion_use_case.secrets,
        "token_urlsafe",
        lambda _bytes: token_crudo,
    )
    monkeypatch.setattr(
        solicitar_recuperacion_use_case,
        "send_email",
        lambda **kwargs: correos.append(kwargs),
    )
    monkeypatch.setattr(notificacion_service, "send_email", lambda **_kwargs: None)
    monkeypatch.setattr(notificacion_service, "send_push", lambda **_kwargs: True)

    respuesta = client.post(
        "/contrasena/recuperar",
        json={"correo_electronico": usuario["correo"]},
    )
    assert respuesta.status_code == 202, respuesta.text

    hash_guardado = db_session.execute(
        text(
            """
            SELECT token_activacion_actual
            FROM modulo1.cuentas_usuarios
            WHERE id_usuario = :usuario
            """
        ),
        {"usuario": usuario["id_usuario"]},
    ).scalar_one()
    assert hash_guardado == calcular_hash_token(token_crudo)
    assert hash_guardado != token_crudo
    assert correos and token_crudo in correos[0]["html_body"]

    nueva = "NuevaSegura2!"
    restablecer = client.post(
        "/contrasena/restablecer",
        json={
            "token": token_crudo,
            "nueva_contrasena": nueva,
            "confirmar_contrasena": nueva,
        },
    )
    assert restablecer.status_code == 200, restablecer.text

    resultado = db_session.execute(
        text(
            """
            SELECT u.contrasena_cifrada, c.token_activacion_actual
            FROM modulo1.usuarios u
            JOIN modulo1.cuentas_usuarios c USING (id_usuario)
            WHERE u.id_usuario = :usuario
            """
        ),
        {"usuario": usuario["id_usuario"]},
    ).mappings().one()
    assert resultado["token_activacion_actual"] is None
    assert bcrypt.checkpw(
        nueva.encode("utf-8"),
        resultado["contrasena_cifrada"].encode("utf-8"),
    )
    evento = db_session.execute(
        text(
            """
            SELECT categoria
            FROM modulo1.eventos
            WHERE id_usuario = :usuario AND tipo_evento = 8
            ORDER BY id_evento DESC LIMIT 1
            """
        ),
        {"usuario": usuario["id_usuario"]},
    ).scalar_one()
    assert evento == "AUTENTICACION"


def test_recuperacion_de_cuenta_pendiente_rota_token_y_envia_activacion(
    client,
    db_session: Session,
    crear_usuario_db,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.identity_access.application.use_cases.contrasena import (
        solicitar_recuperacion_use_case,
    )

    usuario = crear_usuario_db(id_rol=2, estado=1)
    token_anterior = "token-activacion-anterior"
    token_nuevo = "token-activacion-renovado"
    db_session.execute(
        text(
            """
            UPDATE modulo1.cuentas_usuarios
            SET token_activacion_actual = :token_hash,
                fecha_cambio_estado = now()
            WHERE id_usuario = :usuario
            """
        ),
        {
            "token_hash": calcular_hash_token(token_anterior),
            "usuario": usuario["id_usuario"],
        },
    )
    correos: list[dict] = []
    monkeypatch.setattr(
        solicitar_recuperacion_use_case.secrets,
        "token_urlsafe",
        lambda _bytes: token_nuevo,
    )
    monkeypatch.setattr(
        solicitar_recuperacion_use_case,
        "send_email",
        lambda **kwargs: correos.append(kwargs),
    )

    respuesta = client.post(
        "/contrasena/recuperar",
        json={"correo_electronico": usuario["correo"]},
    )

    assert respuesta.status_code == 202, respuesta.text
    token_guardado = db_session.execute(
        text(
            """
            SELECT token_activacion_actual
            FROM modulo1.cuentas_usuarios
            WHERE id_usuario = :usuario
            """
        ),
        {"usuario": usuario["id_usuario"]},
    ).scalar_one()
    assert token_guardado == calcular_hash_token(token_nuevo)
    assert token_guardado not in {token_nuevo, calcular_hash_token(token_anterior)}
    assert correos and correos[0]["subject"] == "Activa tu cuenta en SGPMP"
    assert token_nuevo in correos[0]["html_body"]
    assert token_anterior not in correos[0]["html_body"]


def test_reenvio_de_activacion_guarda_hash_y_envia_token_crudo(
    client,
    db_session: Session,
    crear_usuario_db,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.identity_access.application.use_cases.registro import reenviar_token_use_case

    usuario = crear_usuario_db(id_rol=2, estado=1)
    token_crudo = "token-reenvio-integracion"
    correos: list[dict] = []
    monkeypatch.setattr(
        reenviar_token_use_case.secrets,
        "token_urlsafe",
        lambda _bytes: token_crudo,
    )
    monkeypatch.setattr(
        reenviar_token_use_case,
        "send_email",
        lambda **kwargs: correos.append(kwargs),
    )

    respuesta = client.post(
        "/usuarios/activar/reenviar",
        json={"correo_electronico": usuario["correo"]},
    )

    assert respuesta.status_code == 200, respuesta.text
    token_guardado = db_session.execute(
        text(
            """
            SELECT token_activacion_actual
            FROM modulo1.cuentas_usuarios
            WHERE id_usuario = :usuario
            """
        ),
        {"usuario": usuario["id_usuario"]},
    ).scalar_one()
    assert token_guardado == calcular_hash_token(token_crudo)
    assert token_guardado != token_crudo
    assert correos and token_crudo in correos[0]["html_body"]


def _insertar_solicitud_recuperacion(db_session, id_usuario: int, ip: str, hace: timedelta) -> None:
    """Inserta un evento tipo 7 (SOLICITUD_RECUPERACION) con fecha pasada, para
    simular solicitudes previas dentro de la ventana de una hora sin depender
    de tiempo real de ejecución del test."""
    db_session.execute(
        text(
            """
            INSERT INTO modulo1.eventos
                (tipo_evento, fecha_evento, modulo, resultado, detalle, id_usuario, categoria, estado)
            VALUES
                (7, now() - :hace, 'MODULO1', 'exitoso', :detalle, :id_usuario, 'AUTENTICACION', 'PROCESADO')
            """
        ),
        {"hace": hace, "detalle": json.dumps({"ip": ip}), "id_usuario": id_usuario},
    )
    db_session.commit()


def test_recuperacion_excede_limite_responde_429_con_hora_real_de_reintento(
    client,
    db_session: Session,
    crear_usuario_db,
) -> None:
    """INC-M01-07-43 / INC-M01-19-112 / INC-M01-20-112 (RF-08): el límite de 3
    solicitudes/hora por IP debe responder 429 (no 422) y anunciar la hora en
    que la solicitud más antigua de la ventana cumple una hora (no la hora
    actual de la respuesta)."""
    usuario = crear_usuario_db()
    ip = "sgpmp-integration-tests"  # host simulado por el fixture `client` (conftest)
    mas_antigua = timedelta(minutes=50)
    for hace in (mas_antigua, timedelta(minutes=40), timedelta(minutes=30)):
        _insertar_solicitud_recuperacion(db_session, usuario["id_usuario"], ip, hace)

    respuesta = client.post(
        "/contrasena/recuperar",
        json={"correo_electronico": usuario["correo"]},
    )

    assert respuesta.status_code == 429, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["error_code"] == "LIMITE_SOLICITUDES_EXCEDIDO"

    esperado = datetime.now(timezone.utc) - mas_antigua + timedelta(hours=1)
    hora_reportada = re.search(r"(\d{2}:\d{2}):\d{2}", cuerpo["message"]).group(1)
    # Tolerancia de 1 minuto por el tiempo real transcurrido en el test.
    assert hora_reportada in {
        (esperado + timedelta(minutes=d)).strftime("%H:%M") for d in (-1, 0, 1)
    }
    # La hora de reintento NO puede ser "ahora": ese era exactamente el bug.
    ahora = datetime.now(timezone.utc).strftime("%H:%M")
    assert hora_reportada != ahora
