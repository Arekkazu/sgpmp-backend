"""Pruebas de integración para tokens de un solo uso almacenados como hash."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.identity_access.domain.value_objects.token_un_solo_uso import (
    calcular_hash_token,
)

pytestmark = pytest.mark.integration


def _registro(numero: str, correo: str) -> dict:
    """Construye los datos mínimos para registrar un usuario."""
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
    }


def test_registro_guarda_hash_y_activacion_consume_token(
    client,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El registro persiste solo el hash y la activación consume el token."""

    from src.identity_access.application.use_cases.registro import (
        crear_usuario_use_case,
    )
    from src.shared import notificacion_service

    token_crudo = "token-integracion-registro"

    # Forzar un token conocido para poder comprobar qué se guarda en BD.
    monkeypatch.setattr(
        crear_usuario_use_case.secrets,
        "token_urlsafe",
        lambda _bytes: token_crudo,
    )

    # Evitar envío real de correo durante la prueba.
    monkeypatch.setattr(notificacion_service, "send_email", lambda **_kwargs: None)

    correo = "registro-hash-integracion@example.com"

    respuesta = client.post(
        "/usuarios/",
        json=_registro("900000000001", correo),
    )

    assert respuesta.status_code == 201, respuesta.text

    # Comprobar qué quedó realmente almacenado.
    fila = db_session.execute(
        text(
            """
            SELECT
                u.id_usuario,
                c.id_estado_cuenta,
                c.token_activacion_actual
            FROM modulo1.usuarios u
            JOIN modulo1.cuentas_usuarios c USING (id_usuario)
            WHERE u.correo_electronico = :correo
            """
        ),
        {"correo": correo},
    ).mappings().one()

    hash_esperado = calcular_hash_token(token_crudo)

    # Debe persistirse SHA-256.
    assert fila["token_activacion_actual"] == hash_esperado

    # El token crudo nunca debe quedar almacenado.
    assert fila["token_activacion_actual"] != token_crudo

    # La cuenta recién registrada debe permanecer pendiente.
    assert fila["id_estado_cuenta"] == 1

    # El usuario presenta el token CRUDO.
    # El caso de uso debe calcular su hash para realizar la búsqueda.
    activacion = client.get(
        f"/usuarios/activar/{token_crudo}"
    )

    assert activacion.status_code == 200, activacion.text

    # Después de usarlo, el hash debe consumirse.
    cuenta_activada = db_session.execute(
        text(
            """
            SELECT
                id_estado_cuenta,
                tiene_correo_verificado,
                token_activacion_actual
            FROM modulo1.cuentas_usuarios
            WHERE id_usuario = :usuario
            """
        ),
        {"usuario": fila["id_usuario"]},
    ).mappings().one()

    assert cuenta_activada["id_estado_cuenta"] == 2
    assert cuenta_activada["tiene_correo_verificado"] is True

    # El token es de un solo uso: después de activar no debe existir hash.
    assert cuenta_activada["token_activacion_actual"] is None
