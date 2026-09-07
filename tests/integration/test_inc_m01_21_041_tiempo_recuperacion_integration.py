"""Integración HTTP/BD de anti-enumeración temporal de RF-08."""
from __future__ import annotations

from time import monotonic

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

MENSAJE_GENERICO = (
    "Si el correo está registrado, recibirás instrucciones para recuperar "
    "tu contraseña en unos minutos."
)


def test_existente_e_inexistente_responden_202_igual_y_en_tiempo_comparable(
    integration_app,
    db_session: Session,
    crear_usuario_db,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.identity_access.infrastructure.adapters import (
        correo_recuperacion_background_adapter,
    )

    usuario = crear_usuario_db(id_rol=2, estado=2)
    tareas = []
    monkeypatch.setattr(
        correo_recuperacion_background_adapter,
        "procesar_correo_recuperacion_background",
        lambda **datos: tareas.append(datos),
    )

    from src.shared.database import get_db

    def override_get_db():
        yield db_session

    integration_app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(
            integration_app,
            client=("tc-m01-041-local", 50041),
        ) as client:
            inicio = monotonic()
            existente = client.post(
                "/contrasena/recuperar",
                json={"correo_electronico": usuario["correo"]},
            )
            tiempo_existente = (monotonic() - inicio) * 1000

            inicio = monotonic()
            inexistente = client.post(
                "/contrasena/recuperar",
                json={"correo_electronico": "inexistente-041@example.com"},
            )
            tiempo_inexistente = (monotonic() - inicio) * 1000
    finally:
        integration_app.dependency_overrides.clear()

    assert existente.status_code == inexistente.status_code == 202
    assert existente.json() == inexistente.json() == {"message": MENSAJE_GENERICO}
    assert abs(tiempo_existente - tiempo_inexistente) < 300
    assert tareas[0]["id_usuario"] == usuario["id_usuario"]

    evento = db_session.execute(
        text(
            """
            SELECT detalle ->> 'motivo'
            FROM modulo1.eventos
            WHERE id_usuario = :usuario AND tipo_evento = 7
            ORDER BY id_evento DESC
            LIMIT 1
            """
        ),
        {"usuario": usuario["id_usuario"]},
    ).scalar_one()
    assert evento == "token_generado"
