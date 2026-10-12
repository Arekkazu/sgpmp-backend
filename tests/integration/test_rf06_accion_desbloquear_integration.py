"""RF-06 de punta a punta: 'desbloquear' persiste en la bitácora (enum_accion_cuenta)."""
from __future__ import annotations

import pytest
from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared.database import declarar_identidad, get_db

pytestmark = pytest.mark.integration


@pytest.fixture
def como_admin(integration_app, crear_usuario_db):
    admin = crear_usuario_db(id_rol=1)

    def actual(db: Session = Depends(get_db)) -> UsuarioActual:
        declarar_identidad(db, admin["id_usuario"], "Administrador")
        return UsuarioActual(id_usuario=admin["id_usuario"], id_token=1, id_rol=1, id_estado_cuenta=2)

    integration_app.dependency_overrides[get_current_user] = actual
    yield admin
    integration_app.dependency_overrides.pop(get_current_user, None)


def test_desbloquear_reactiva_la_cuenta_y_registra_la_accion(
    client, db_session: Session, crear_usuario_db, como_admin
) -> None:
    usuario = crear_usuario_db(id_rol=2, estado=4)

    respuesta = client.post(
        f"/usuarios/{usuario['id_usuario']}/gestionar",
        json={"accion_cuenta": "desbloquear", "motivo_accion": "Revisión de soporte"},
    )

    assert respuesta.status_code == 200, respuesta.text
    estado = db_session.execute(
        text("SELECT id_estado_cuenta FROM modulo1.cuentas_usuarios WHERE id_usuario = :i"),
        {"i": usuario["id_usuario"]},
    ).scalar_one()
    assert estado == 2
    accion = db_session.execute(
        text(
            'SELECT g."accion_cuenta "::text FROM modulo1.gestiones_cuenta g '
            "WHERE g.id_cuenta_usuario = :c ORDER BY g.id_gestion_cuenta DESC LIMIT 1"
        ),
        {"c": usuario["id_cuenta_usuario"]},
    ).scalar_one()
    assert accion == "desbloquear"


def test_desbloquear_una_cuenta_activa_responde_400(
    client, crear_usuario_db, como_admin
) -> None:
    usuario = crear_usuario_db(id_rol=2, estado=2)

    respuesta = client.post(
        f"/usuarios/{usuario['id_usuario']}/gestionar",
        json={"accion_cuenta": "desbloquear"},
    )

    assert respuesta.status_code == 400, respuesta.text
    assert respuesta.json()["error_code"] == "ACCION_INCONSISTENTE_ESTADO"
    assert "ya se encuentra ACTIVO" in respuesta.json()["message"]
