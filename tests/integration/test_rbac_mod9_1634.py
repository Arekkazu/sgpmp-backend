"""Pruebas de integración RBAC para el issue #1634 (RF-15/19/20).

Verifican el ajuste de permisos de módulo 9 decidido con el equipo de análisis:

- RF-15: se **revocó** la edición (U) del Veterinario sobre especies. El Veterinario
  debe recibir 403 al intentar editar; el Ingeniero de Campo conserva la edición.
- RF-19: la lectura (R) del Veterinario sobre fincas se **mantiene** como decisión de
  diseño de RBAC dinámico (debe seguir devolviendo 200).

El RBAC es data-driven (`modulo1.permisos`), por lo que estas pruebas requieren que el
`UPDATE` de revocación esté aplicado en la base `pruebas` (ver
`anotaciones/modulo_9/rf15-19-20-rbac-mod9/resumen_rbac_1634.md`).

Verifican la **compuerta RBAC** (`require_permission`, lo que cambió #1634), no la query
de negocio: la base `pruebas` solo tiene el esquema `modulo1`, no `modulo9`. Por eso un
rol autorizado llega al use case y devuelve algo distinto de 401/403 (el use case puede
fallar aguas abajo por falta de tablas modulo9, pero eso es irrelevante al RBAC), mientras
que un rol sin permiso recibe 403 antes de tocar el use case. Se usa
`raise_server_exceptions=False` para que ese fallo aguas abajo llegue como respuesta 500 y
no como excepción; la aserción `!= 403` sigue siendo válida si algún día `pruebas` tuviera
el esquema modulo9 (devolvería 200/404/412).

El fixture local monta solo los routers de configuración necesarios para no alterar el
`integration_app` compartido (que solo expone identity_access).
"""
from __future__ import annotations

from collections.abc import Generator
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

_JWT_SECRET_INTEGRACION = "sgpmp-integration-tests-only"  # igual que conftest


@pytest.fixture
def config_client(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[TestClient, None, None]:
    from src.configuration.infrastructure.routers.especie_router import router as especie_router
    from src.configuration.infrastructure.routers.finca_router import router as finca_router
    from src.identity_access.infrastructure.routers.usuarios_routers import router as usuarios_router  # noqa: F401  registra modelos identity_access
    from src.shared import jwt as jwt_module
    from src.shared.database import get_db
    from src.shared.error_handlers import register_error_handlers

    monkeypatch.setattr(jwt_module, "_SECRET_KEY", _JWT_SECRET_INTEGRACION)
    monkeypatch.setattr(jwt_module, "_EXPIRE_HOURS", 8)

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app = FastAPI()
    register_error_handlers(app)
    app.include_router(especie_router)
    app.include_router(finca_router)
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(
        app,
        client=("sgpmp-integration-tests", 50000),
        raise_server_exceptions=False,
    ) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _body_especie() -> dict:
    """Body válido para EditarEspecieDTO (evita que un 422 tape el 403)."""
    return {
        "nombre": "Bovino",
        "descripcion": "prueba integracion",
        "fecha_actualizacion": datetime.now(timezone.utc).isoformat(),
    }


def test_veterinario_no_edita_especie(config_client, crear_usuario_db, crear_auth_headers) -> None:
    """RF-15 #1634: la U del Veterinario sobre especies fue revocada → 403."""
    veterinario = crear_usuario_db(id_rol=3, estado=2)

    respuesta = config_client.patch(
        "/configuracion/especies/1",
        json=_body_especie(),
        headers=crear_auth_headers(veterinario),
    )

    assert respuesta.status_code == 403
    assert respuesta.json()["error_code"] == "ACCESO_DENEGADO"


def test_ingeniero_campo_conserva_edicion_especie(config_client, crear_usuario_db, crear_auth_headers) -> None:
    """RF-15: el Ingeniero de Campo sí puede editar → el RBAC no lo bloquea (≠ 403)."""
    ingeniero = crear_usuario_db(id_rol=4, estado=2)

    respuesta = config_client.patch(
        "/configuracion/especies/1",
        json=_body_especie(),
        headers=crear_auth_headers(ingeniero),
    )

    # El permiso pasa; el use case corre aguas abajo. Lo relevante es que el RBAC no lo
    # bloquea: no debe ser 401 (autenticado) ni 403 (over-revoke sería el bug).
    assert respuesta.status_code not in (401, 403)


def test_veterinario_conserva_lectura_fincas(config_client, crear_usuario_db, crear_auth_headers) -> None:
    """RF-19 #1634: la R del Veterinario sobre fincas se mantiene (decisión de diseño) → 200."""
    veterinario = crear_usuario_db(id_rol=3, estado=2)

    respuesta = config_client.get(
        "/configuracion/fincas",
        headers=crear_auth_headers(veterinario),
    )

    # La R del Veterinario sigue activa: el RBAC no bloquea (no 401/403). El listado en sí
    # se ejercita en las pruebas propias de RF-19; aquí solo se guarda la decisión de permisos.
    assert respuesta.status_code not in (401, 403)
