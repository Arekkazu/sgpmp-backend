"""Pruebas de integración de auditoría para registro y activación de cuentas."""
from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration


def _registro(numero: str, correo: str) -> dict[str, Any]:
    return {
        "correo_electronico": correo,
        "telefono": "3001234567",
        "tipo_identificacion": "CC",
        "numero_identificacion": numero,
        "nombre": "Registro",
        "apellidos": "Integracion",
        "fecha_nacimiento": "1990-01-01",
        "genero": "M",
        "contrasena": "Segura1!",
        "confirmar_contrasena": "Segura1!",
        "direccion": "Direccion Integracion",
        "captcha_token": "captcha-prueba-valido",
    }


def test_registro_y_activacion_generan_auditoria(
    client,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.identity_access.application.use_cases.registro import (
        crear_usuario_use_case,
    )
    from src.shared import notificacion_service

    token_crudo = "token-integracion-auditoria"

    # Evita enviar correo real y permite conocer el token para activar la cuenta.
    monkeypatch.setattr(
        crear_usuario_use_case.secrets,
        "token_urlsafe",
        lambda _bytes: token_crudo,
    )
    monkeypatch.setattr(notificacion_service, "send_email", lambda **_kwargs: None)

    correo = "auditoria-registro@example.com"
    numero_identificacion = "900000000001"
    contrasena = "Segura1!"

    headers = {
        "user-agent": "rf01-rf10-integration",
    }

    # Registro
    respuesta = client.post(
        "/usuarios/",
        json=_registro(numero_identificacion, correo),
        headers=headers,
    )

    assert respuesta.status_code == 201, respuesta.text

    cuenta = db_session.execute(
        text(
            """
            SELECT u.id_usuario, c.id_estado_cuenta
            FROM modulo1.usuarios u
            JOIN modulo1.cuentas_usuarios c USING (id_usuario)
            WHERE u.correo_electronico = :correo
            """
        ),
        {"correo": correo},
    ).mappings().one()

    assert cuenta["id_estado_cuenta"] == 1

    evento_registro = db_session.execute(
        text(
            """
            SELECT categoria, detalle
            FROM modulo1.eventos
            WHERE id_usuario = :usuario
              AND tipo_evento = 1
            ORDER BY id_evento DESC
            LIMIT 1
            """
        ),
        {"usuario": cuenta["id_usuario"]},
    ).mappings().one()

    assert evento_registro["categoria"] == "AUTENTICACION"

    detalle_registro = str(evento_registro["detalle"])

    assert "registro_usuario" in detalle_registro
    assert "rf01-rf10-integration" in detalle_registro

    assert token_crudo not in detalle_registro
    assert contrasena not in detalle_registro
    assert numero_identificacion not in detalle_registro

    # Activación
    activacion = client.get(
        f"/usuarios/activar/{token_crudo}",
        headers=headers,
    )

    assert activacion.status_code == 200, activacion.text

    cuenta_activada = db_session.execute(
        text(
            """
            SELECT id_estado_cuenta, tiene_correo_verificado
            FROM modulo1.cuentas_usuarios
            WHERE id_usuario = :usuario
            """
        ),
        {"usuario": cuenta["id_usuario"]},
    ).mappings().one()

    assert cuenta_activada["id_estado_cuenta"] == 2
    assert cuenta_activada["tiene_correo_verificado"] is True

    evento_activacion = db_session.execute(
        text(
            """
            SELECT categoria, detalle
            FROM modulo1.eventos
            WHERE id_usuario = :usuario
              AND tipo_evento = 2
            ORDER BY id_evento DESC
            LIMIT 1
            """
        ),
        {"usuario": cuenta["id_usuario"]},
    ).mappings().one()

    assert evento_activacion["categoria"] == "AUTENTICACION"

    detalle_activacion = str(evento_activacion["detalle"])

    assert "activacion_cuenta" in detalle_activacion
    assert "rf01-rf10-integration" in detalle_activacion

    assert token_crudo not in detalle_activacion
    assert contrasena not in detalle_activacion
    assert numero_identificacion not in detalle_activacion
