"""RF-32 (#128, #129) — reaplicar una plantilla sobre la especie que la originó.

Causa raíz: `AplicarPlantillaUseCase` desactiva (`es_activo=false`) las filas
vigentes e inserta las nuevas, pero las reglas de unicidad de `modulo9`
(triggers de ciclo/métrica + constraint de umbral) comparaban contra TODAS las
filas, activas o no. Reaplicar una plantilla sobre la especie que ya tenía
esos nombres/variable (el caso normal de uso, ej. plantilla creada a partir de
la config actual de esa misma especie) chocaba con la fila recién desactivada
y el endpoint respondía 500 en vez de aplicar. Este test reproduce exactamente
ese escenario contra Postgres real, con las 3 categorías a la vez (igual que
el issue #129).
"""
from __future__ import annotations

import uuid
from collections.abc import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

_JWT_SECRET_INTEGRACION = "sgpmp-integration-tests-only"


def _sid() -> str:
    return uuid.uuid4().hex[:8]


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
def variable_ambiental_activa(db_session: Session) -> dict:
    id_variable = db_session.execute(
        text(
            """
            INSERT INTO modulo9.variables_ambientales
                (nombre, unidad, valor_fisico_min, valor_fisico_max, es_activo)
            VALUES (:nombre, '°C', 0, 45, TRUE)
            RETURNING id_variable_ambiental
            """
        ),
        {"nombre": f"Temperatura RF32 {_sid()}"},
    ).scalar_one()
    db_session.flush()
    return {"id_variable_ambiental": id_variable}


@pytest.fixture
def config_client(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    from src.configuration.infrastructure.routers.ciclo_router import router as ciclo_router
    from src.configuration.infrastructure.routers.metrica_router import router as metrica_router
    from src.configuration.infrastructure.routers.plantilla_router import router as plantilla_router
    from src.configuration.infrastructure.routers.umbral_router import router as umbral_router
    from src.shared import jwt as jwt_module
    from src.shared.database import get_db
    from src.shared.error_handlers import register_error_handlers

    monkeypatch.setattr(jwt_module, "_SECRET_KEY", _JWT_SECRET_INTEGRACION)
    monkeypatch.setattr(jwt_module, "_EXPIRE_HOURS", 8)

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app = FastAPI()
    register_error_handlers(app)
    app.include_router(ciclo_router)
    app.include_router(metrica_router)
    app.include_router(umbral_router)
    app.include_router(plantilla_router)
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, client=("sgpmp-integration-tests", 50000), raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


def _headers_admin(crear_usuario_db, crear_auth_headers) -> dict:
    admin = crear_usuario_db(id_rol=1, estado=2)
    return crear_auth_headers(admin)


def test_reaplicar_plantilla_con_mismos_nombres_ya_no_da_500(
    config_client, especie_activa: dict, variable_ambiental_activa: dict, crear_usuario_db, crear_auth_headers
) -> None:
    headers = _headers_admin(crear_usuario_db, crear_auth_headers)
    id_especie = especie_activa["id_especie"]
    sufijo = _sid()
    nombre_ciclo = f"Engorde RF32 {sufijo}"
    nombre_metrica = f"Peso RF32 {sufijo}"

    # Config vigente de la especie: mismos nombres/variable que la plantilla usará.
    r_ciclo = config_client.post(
        "/configuracion/ciclos",
        json={"id_especie": id_especie, "nombre": nombre_ciclo, "duracion_dias": 90},
        headers=headers,
    )
    assert r_ciclo.status_code == 201, r_ciclo.text

    r_metrica = config_client.post(
        "/configuracion/metricas",
        json={
            "id_especie": id_especie, "nombre": nombre_metrica,
            "unidad_medida": "kg", "tipo_medicion": "PESO",
        },
        headers=headers,
    )
    assert r_metrica.status_code == 201, r_metrica.text

    r_umbral = config_client.post(
        "/configuracion/umbrales",
        json={
            "id_especie": id_especie,
            "id_variable_ambiental": variable_ambiental_activa["id_variable_ambiental"],
            "valor_min": "15.0", "valor_max": "30.0",
            "niveles": [
                {"nivel": "normal", "limite_inferior": "15.0", "limite_superior": "25.0"},
                {"nivel": "precaucion", "limite_inferior": "25.0", "limite_superior": "28.0"},
                {"nivel": "critico", "limite_inferior": "28.0", "limite_superior": "30.0"},
            ],
        },
        headers=headers,
    )
    assert r_umbral.status_code == 201, r_umbral.text

    # Plantilla con exactamente los mismos nombres/variable (ej. capturada
    # desde la config actual de esta misma especie, el caso normal de uso).
    r_plantilla = config_client.post(
        "/configuracion/plantillas",
        json={
            "template_name": f"Plantilla Reaplicacion {sufijo}",
            "id_especie": id_especie,
            "params_snapshot": {
                "ciclos_biologicos": [{"nombre": nombre_ciclo, "duracion_dias": 90}],
                "metricas_produccion": [{
                    "nombre": nombre_metrica, "unidad_medida": "kg",
                    "tipo_medicion": "PESO", "aplica_a_tipo_activo": "AMBOS",
                }],
                "umbrales_ambientales": [{
                    "id_variable_ambiental": variable_ambiental_activa["id_variable_ambiental"],
                    "unidad_medida": "°C", "valor_min": "18.0", "valor_max": "28.0",
                    "niveles": [
                        {"nivel": "normal", "limite_inferior": "18.0", "limite_superior": "23.0"},
                        {"nivel": "precaucion", "limite_inferior": "23.0", "limite_superior": "26.0"},
                        {"nivel": "critico", "limite_inferior": "26.0", "limite_superior": "28.0"},
                    ],
                }],
            },
        },
        headers=headers,
    )
    assert r_plantilla.status_code == 201, r_plantilla.text
    id_plantilla = r_plantilla.json()["id_plantilla"]

    fecha_actualizacion = especie_activa["fecha_actualizacion"]

    def _aplicar() -> dict:
        resp = config_client.post(
            f"/configuracion/plantillas/{id_plantilla}/aplicar",
            json={
                "id_especie_destino": id_especie,
                "fecha_actualizacion_especie_destino": (
                    fecha_actualizacion.isoformat() if fecha_actualizacion else None
                ),
            },
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        return resp.json()

    # Antes del fix: 500 (P0104/P0109/UniqueViolation por chocar con la fila
    # recién desactivada). Ahora: 200 y las 3 categorías quedan aplicadas.
    resultado = _aplicar()
    assert resultado["after_snapshot"]["ciclos_biologicos"] == [
        {"nombre": nombre_ciclo, "duracion_dias": 90, "descripcion": None}
    ]
    assert [m["nombre"] for m in resultado["after_snapshot"]["metricas_produccion"]] == [nombre_metrica]
    assert [
        u["id_variable_ambiental"] for u in resultado["after_snapshot"]["umbrales_ambientales"]
    ] == [variable_ambiental_activa["id_variable_ambiental"]]

    # Reaplicar una segunda vez tampoco debe chocar.
    _aplicar()

    activos_ciclo = config_client.get(
        f"/configuracion/ciclos?id_especie={id_especie}&solo_activas=true", headers=headers
    ).json()["items"]
    coincidencias = [c for c in activos_ciclo if c["nombre"] == nombre_ciclo]
    assert len(coincidencias) == 1 and coincidencias[0]["es_activo"] is True
