"""RF-16 (#134) — dependencias activas reales al desactivar patología y métrica.

Antes de este fix, `StubDependenciaPatologiaAdapter`/`StubDependenciaMetricaAdapter`
devolvían `False` siempre: `PATCH .../desactivar` nunca se bloqueaba aunque la
patología tuviera predicciones/alertas de M04 activas, o la métrica tuviera
registros productivos activos (FA-04/FA-09 de RF-16), respondiendo 200 en vez de 422.

Estas pruebas insertan datos reales (vía SQL directo — más simple que recorrer los
endpoints completos de M02/M04, que no son objeto de este fix) y verifican contra la
BD real que ahora sí bloquea con 422, y que sin dependencias sigue en 200.

Se salta si falta el schema `modulo9` (mismo guard que el resto de
`tests/integration/test_rf16_*`).
"""
from __future__ import annotations

import random
import string
import uuid
from collections.abc import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

_JWT_SECRET_INTEGRACION = "sgpmp-integration-tests-only"


def _sid() -> int:
    return uuid.uuid4().int % (10**9)


def _letras(n: int = 10) -> str:
    return "".join(random.choices(string.ascii_letters, k=n))


@pytest.fixture
def una_especie(db_session: Session) -> int:
    existe = db_session.execute(
        text("SELECT 1 FROM information_schema.schemata WHERE schema_name = 'modulo9'")
    ).first()
    if existe is None:
        pytest.skip("La base de pruebas no tiene el schema modulo9.")
    fila = db_session.execute(
        text("SELECT id_especie FROM modulo9.especies WHERE es_activo ORDER BY id_especie LIMIT 1")
    ).first()
    if fila is None:
        pytest.skip("Se requiere al menos 1 especie activa en modulo9.especies.")
    return fila[0]


@pytest.fixture
def config_client(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    from src.configuration.infrastructure.routers.metrica_router import router as metrica_router
    from src.configuration.infrastructure.routers.patologia_router import router as patologia_router
    from src.shared import jwt as jwt_module
    from src.shared.database import get_db
    from src.shared.error_handlers import register_error_handlers

    monkeypatch.setattr(jwt_module, "_SECRET_KEY", _JWT_SECRET_INTEGRACION)
    monkeypatch.setattr(jwt_module, "_EXPIRE_HOURS", 8)

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app = FastAPI()
    register_error_handlers(app)
    app.include_router(patologia_router)
    app.include_router(metrica_router)
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, client=("sgpmp-integration-tests", 50000), raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


def _headers_vet(crear_usuario_db, crear_auth_headers) -> dict:
    vet = crear_usuario_db(id_rol=3, estado=2)  # Veterinario: C/R/U/D sobre patologias (18) y metricas (19)
    return crear_auth_headers(vet)


def _crear_activo_biologico(db_session: Session, id_especie: int, id_usuario: int) -> int:
    """Cadena mínima finca -> infraestructura -> activo_biologico (igual que test_rf40)."""
    sid = _sid()
    db_session.execute(text("SET app.usuario_id = :uid"), {"uid": str(id_usuario)})
    db_session.execute(
        text(
            """
            INSERT INTO modulo9.fincas (id_finca, nombre, ubicacion, tamano_h,
                fecha_actualizacion, fecha_creacion, es_activo)
            VALUES (:id_finca, :nombre, '{}', 10, now(), now(), TRUE)
            """
        ),
        {"id_finca": sid, "nombre": f"Finca Integracion {_letras()}"},
    )
    db_session.execute(
        text(
            """
            INSERT INTO modulo9.infraestructuras (id_infraestructura, nombre, id_finca,
                superficie, es_activo, tipo)
            VALUES (:id_infra, :nombre, :id_finca, 100, TRUE, 'Estanque')
            """
        ),
        {"id_infra": sid, "nombre": f"Infra Integracion {_letras()}", "id_finca": sid},
    )
    db_session.execute(
        text(
            """
            INSERT INTO modulo2.estados_activos_biologicos (id_estado_activo_biologico, nombre)
            VALUES (1, 'ACTIVO')
            ON CONFLICT (id_estado_activo_biologico) DO NOTHING
            """
        )
    )
    db_session.execute(
        text(
            """
            INSERT INTO modulo2.activos_biologicos (id_activo_biologico, id_especie,
                identificador, id_infraestructura, tipo, fecha_inicio_ciclo, id_estado,
                descripcion, origen_financiero, costo_adquisicion, atributos_dinamicos,
                id_usuario, fecha_creacion, id_dispositivo_iot, soporte_documental,
                detalles_procedencia)
            VALUES (:id_activo, :id_especie, :identificador, :id_infra, 'INDIVIDUAL',
                current_date, 1, '', 'compra', 100, '{}', :id_usuario,
                now() - interval '1 hour', 0, 'doc', '')
            """
        ),
        {
            "id_activo": sid,
            "id_especie": id_especie,
            "identificador": f"RF16-{sid}",
            "id_infra": sid,
            "id_usuario": id_usuario,
        },
    )
    db_session.flush()
    return sid


# --- Patología (predicciones/alertas de M04 vía vw_rf16_dependencias_patologias) ---


def test_desactivar_patologia_sin_dependencias_permite_200(
    config_client, una_especie, crear_usuario_db, crear_auth_headers
) -> None:
    h = _headers_vet(crear_usuario_db, crear_auth_headers)
    creada = config_client.post(
        "/configuracion/patologias",
        json={"id_especie": una_especie, "nombre": f"Patologia RF16 {_sid()}"},
        headers=h,
    )
    assert creada.status_code == 201, creada.text
    assert creada.json()["id_patologia"] is None  # entidad M09 pura, sin vínculo M04

    resp = config_client.patch(
        f"/configuracion/patologias/{creada.json()['id_especies_patologias']}/desactivar", headers=h
    )
    assert resp.status_code == 200, resp.text


def test_desactivar_patologia_con_prediccion_activa_bloquea_422(
    config_client, una_especie, db_session, crear_usuario_db, crear_auth_headers
) -> None:
    usuario = crear_usuario_db(id_rol=3, estado=2)
    h = crear_auth_headers(usuario)
    sid = _sid()

    id_patologia_catalogo = db_session.execute(
        text("INSERT INTO modulo9.patologias (nombre) VALUES (:nombre) RETURNING id_patologia"),
        {"nombre": f"Patologia Catalogo RF16 {sid}"},
    ).scalar_one()
    id_especies_patologias = db_session.execute(
        text(
            """
            INSERT INTO modulo9.especies_patologias (id_patologia, id_especie, nombre)
            VALUES (:id_patologia, :id_especie, :nombre)
            RETURNING id_especies_patologias
            """
        ),
        {"id_patologia": id_patologia_catalogo, "id_especie": una_especie, "nombre": f"Vinculo RF16 {sid}"},
    ).scalar_one()

    id_activo = _crear_activo_biologico(db_session, una_especie, usuario["id_usuario"])
    id_observacion = db_session.execute(
        text(
            """
            INSERT INTO modulo4.observaciones_clinicas (id_activo_biologico, id_usuario, fecha)
            VALUES (:id_activo, :id_usuario, now())
            RETURNING id_observacion_clinica
            """
        ),
        {"id_activo": id_activo, "id_usuario": usuario["id_usuario"]},
    ).scalar_one()
    id_version_modelo = db_session.execute(
        text(
            "INSERT INTO modulo4.versiones_modelos "
            "(nombre_version, umbral_clasificacion, hash_artecfacto, esta_produccion) "
            "VALUES (:n, 0.7, :hash, TRUE) RETURNING id_version_modelo"
        ),
        {"n": f"Modelo RF16 {sid}", "hash": uuid.uuid4().hex + uuid.uuid4().hex},
    ).scalar_one()
    db_session.execute(
        text(
            """
            INSERT INTO modulo4.predicciones
                (id_prediccion, id_observacion, id_patologia, id_version_modelo, probabilidad_pct,
                 supera_umbral, clase_predicha)
            VALUES (:id_prediccion, :id_observacion, :id_patologia, :id_version_modelo, 80.0, TRUE,
                CAST('POSITIVO' AS modulo4.enum_predicciones_clase))
            """
        ),
        {
            "id_prediccion": sid,
            "id_observacion": id_observacion,
            "id_patologia": id_patologia_catalogo,
            "id_version_modelo": id_version_modelo,
        },
    )
    db_session.flush()

    resp = config_client.patch(f"/configuracion/patologias/{id_especies_patologias}/desactivar", headers=h)
    assert resp.status_code == 422, resp.text
    assert resp.json()["error_code"] == "PATOLOGIA_CON_DEPENDENCIAS"


# --- Métrica (modulo2.eventos_productivos) ---


def test_desactivar_metrica_sin_dependencias_permite_200(
    config_client, una_especie, crear_usuario_db, crear_auth_headers
) -> None:
    h = _headers_vet(crear_usuario_db, crear_auth_headers)
    creada = config_client.post(
        "/configuracion/metricas",
        json={
            "id_especie": una_especie,
            "nombre": f"Metrica RF16 {_sid()}",
            "unidad_medida": "kg",
            "tipo_medicion": "PESO",
        },
        headers=h,
    )
    assert creada.status_code == 201, creada.text

    resp = config_client.patch(
        f"/configuracion/metricas/{creada.json()['id_metrica_produccion']}/desactivar", headers=h
    )
    assert resp.status_code == 200, resp.text


def test_desactivar_metrica_con_registro_productivo_activo_bloquea_422(
    config_client, una_especie, db_session, crear_usuario_db, crear_auth_headers
) -> None:
    usuario = crear_usuario_db(id_rol=3, estado=2)
    h = crear_auth_headers(usuario)
    sid = _sid()

    creada = config_client.post(
        "/configuracion/metricas",
        json={
            "id_especie": una_especie,
            "nombre": f"Metrica RF16 {sid}",
            "unidad_medida": "kg",
            "tipo_medicion": "PESO",
        },
        headers=h,
    )
    assert creada.status_code == 201, creada.text
    id_metrica = creada.json()["id_metrica_produccion"]

    id_activo = _crear_activo_biologico(db_session, una_especie, usuario["id_usuario"])
    id_evento = db_session.execute(
        text(
            """
            INSERT INTO modulo2.eventos_activos (id_activo_biologico, fecha, id_usuario)
            VALUES (:id_activo, now(), :id_usuario)
            RETURNING id_eventos
            """
        ),
        {"id_activo": id_activo, "id_usuario": usuario["id_usuario"]},
    ).scalar_one()
    id_ciclo_productivo = db_session.execute(
        text(
            "INSERT INTO modulo9.ciclos_productivos (nombre, duracion_dias) "
            "VALUES (:n, 90) RETURNING id_ciclo_productivo"
        ),
        {"n": f"Ciclo RF16 {sid}"},
    ).scalar_one()
    db_session.execute(
        text(
            """
            INSERT INTO modulo2.eventos_productivos (id_evento, cantidad, id_metrica_produccion, id_ciclo_productivo)
            VALUES (:id_evento, 1, :id_metrica, :id_ciclo)
            """
        ),
        {"id_evento": id_evento, "id_metrica": id_metrica, "id_ciclo": id_ciclo_productivo},
    )
    db_session.flush()

    resp = config_client.patch(f"/configuracion/metricas/{id_metrica}/desactivar", headers=h)
    assert resp.status_code == 422, resp.text
    assert resp.json()["error_code"] == "METRICA_CON_REGISTROS"
