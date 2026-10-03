"""RF-32 / INC-M09-04-124 (#316) — un intento fallido de aplicación de

plantilla (con rollback) no quedaba registrado en ningún lugar consultable:
ni en /configuracion/plantillas/historial ni en auditoría. El rollback de
datos en sí funcionaba bien; el problema era exclusivamente de trazabilidad.

Ya resuelto por el mecanismo agregado en INC-M09-01-109 (#319):
AplicarPlantillaUseCase.execute() audita cualquier fallo (tipo_operacion=APPLY,
resultado=FALLIDO) en una transacción propia antes de relanzar. Esta prueba
solo confirma el comportamiento contra Postgres real.
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

_SNAPSHOT_VALIDO = {"ciclos_biologicos": [{"nombre": "Engorde", "duracion_dias": 45, "descripcion": None}]}


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


def test_aplicacion_fallida_por_conflicto_de_concurrencia_queda_auditada_y_sin_rastro_en_historial(
    config_client, crear_usuario_db, crear_auth_headers, especie_activa: dict
) -> None:
    admin = crear_usuario_db(id_rol=1, estado=2)
    headers = crear_auth_headers(admin)
    id_especie = especie_activa["id_especie"]
    nombre = f"Plantilla Aplicacion Fallida {_sufijo_letras()}"

    creada = config_client.post(
        "/configuracion/plantillas",
        json={"template_name": nombre, "id_especie": id_especie, "params_snapshot": _SNAPSHOT_VALIDO},
        headers=headers,
    )
    assert creada.status_code == 201, creada.text
    id_plantilla = creada.json()["id_plantilla"]

    # fecha_actualizacion deliberadamente desincronizada -> 412 CONFLICTO_CONCURRENCIA,
    # el use case falla antes de escribir ningún cambio en la especie destino.
    resp = config_client.post(
        f"/configuracion/plantillas/{id_plantilla}/aplicar",
        json={
            "id_especie_destino": id_especie,
            "fecha_actualizacion_especie_destino": "2000-01-01T00:00:00Z",
        },
        headers=headers,
    )
    assert resp.status_code == 412, resp.text

    # No debe haber quedado ningún registro de esta aplicación fallida en el
    # historial de aplicaciones (solo audita filas EXITOSAS de antemano).
    historial = config_client.get("/configuracion/plantillas/historial", headers=headers)
    assert not any(
        item["id_plantilla"] == id_plantilla for item in historial.json()["items"]
    )

    # Pero sí debe quedar auditado como intento fallido, consultable.
    auditoria = config_client.get("/configuracion/plantillas/auditoria", headers=headers)
    fallidos = [
        item for item in auditoria.json()["items"]
        if item["id_plantilla"] == id_plantilla
        and item["tipo_operacion"] == "APPLY"
        and item["resultado"] == "FALLIDO"
    ]
    assert len(fallidos) == 1
    assert fallidos[0]["valores_nuevos"]["id_especie_destino"] == id_especie
