"""RF-32 / INC-M09-03-122 (#317) — el sistema permitía aplicar una versión

superada (no vigente) de una plantilla exactamente igual que la vigente, sin
ninguna restricción. El versionado (RF-31: "una actualización genera una
nueva versión, no sobreescribe la original") solo cumple su propósito de
control de cambios si la versión anterior deja de poder aplicarse.
"""
from __future__ import annotations

import random
import string
from collections.abc import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

_JWT_SECRET_INTEGRACION = "sgpmp-integration-tests-only"

_SNAPSHOT_V1 = {"ciclos_biologicos": [{"nombre": "Engorde", "duracion_dias": 45, "descripcion": None}]}
_SNAPSHOT_V2 = {"ciclos_biologicos": [{"nombre": "Engorde ajustado", "duracion_dias": 50, "descripcion": None}]}


def _sufijo_letras(largo: int = 6) -> str:
    return "".join(random.choices(string.ascii_uppercase, k=largo))


@pytest.fixture
def especie_activa(db_session: Session) -> dict:
    existe = db_session.execute(
        text("SELECT 1 FROM information_schema.schemata WHERE schema_name = 'modulo9'")
    ).first()
    if existe is None:
        pytest.skip("La base de pruebas no tiene el schema modulo9.")
    fila = db_session.execute(
        text(
            "SELECT id_especie, fecha_actualizacion FROM modulo9.especies "
            "WHERE es_activo ORDER BY id_especie LIMIT 1"
        )
    ).mappings().first()
    if fila is None:
        pytest.skip("Se requiere al menos una especie activa en modulo9.especies.")
    return {"id_especie": fila["id_especie"], "fecha_actualizacion": fila["fecha_actualizacion"]}


@pytest.fixture
def config_client(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    from src.configuration.infrastructure.routers.plantilla_router import router as plantilla_router
    from src.shared import jwt as jwt_module
    from src.shared.database import get_db
    from src.shared.error_handlers import register_error_handlers

    monkeypatch.setattr(jwt_module, "_SECRET_KEY", _JWT_SECRET_INTEGRACION)
    monkeypatch.setattr(jwt_module, "_EXPIRE_HOURS", 8)

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app = FastAPI()
    register_error_handlers(app)
    app.include_router(plantilla_router)
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, client=("sgpmp-integration-tests", 50000), raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


def test_aplicar_version_superada_responde_422_y_aplicar_vigente_funciona(
    config_client, crear_usuario_db, crear_auth_headers, especie_activa: dict
) -> None:
    admin = crear_usuario_db(id_rol=1, estado=2)
    headers = crear_auth_headers(admin)
    id_especie = especie_activa["id_especie"]
    fecha_actualizacion = especie_activa["fecha_actualizacion"]
    nombre = f"Plantilla Version {_sufijo_letras()}"

    v1 = config_client.post(
        "/configuracion/plantillas",
        json={"template_name": nombre, "id_especie": id_especie, "params_snapshot": _SNAPSHOT_V1},
        headers=headers,
    )
    assert v1.status_code == 201, v1.text
    id_v1 = v1.json()["id_plantilla"]

    v2 = config_client.post(
        f"/configuracion/plantillas/{id_v1}/versiones",
        json={"params_snapshot": _SNAPSHOT_V2},
        headers=headers,
    )
    assert v2.status_code == 201, v2.text
    id_v2 = v2.json()["id_plantilla"]
    assert v2.json()["version"] == 2

    # Aplicar la versión superada (v1) debe rechazarse: ya no es vigente.
    aplicar_v1 = config_client.post(
        f"/configuracion/plantillas/{id_v1}/aplicar",
        json={
            "id_especie_destino": id_especie,
            "fecha_actualizacion_especie_destino": (
                fecha_actualizacion.isoformat() if fecha_actualizacion else None
            ),
        },
        headers=headers,
    )
    assert aplicar_v1.status_code == 422, aplicar_v1.text
    assert aplicar_v1.json()["error_code"] == "PLANTILLA_VERSION_NO_VIGENTE"

    # Aplicar la versión vigente (v2) sí debe funcionar.
    aplicar_v2 = config_client.post(
        f"/configuracion/plantillas/{id_v2}/aplicar",
        json={
            "id_especie_destino": id_especie,
            "fecha_actualizacion_especie_destino": (
                fecha_actualizacion.isoformat() if fecha_actualizacion else None
            ),
        },
        headers=headers,
    )
    assert aplicar_v2.status_code == 200, aplicar_v2.text
    assert aplicar_v2.json()["after_snapshot"]["ciclos_biologicos"] == [
        {"nombre": "Engorde ajustado", "duracion_dias": 50, "descripcion": None}
    ]
