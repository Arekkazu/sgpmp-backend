"""Regresion e2e (TestClient real contra el router, sin fakes) para
INC-M02-29-g36 / issue #411, RF-38/RF-45: cubre POST .../eventos/baja para
INDIVIDUAL y para POBLACIONAL en baja TOTAL (cantidad_actual -> 0, dispara
el mismo camino de cierre de fase que INDIVIDUAL), y POST .../cierre
(RF-38) el mismo dia UTC de creacion del activo. Los tests unitarios de
`registrar_evento_baja_use_case.py` y `cerrar_ciclo_use_case.py` usan
repositorios falsos; este archivo ejercita los triggers reales de Postgres
(`trg_fn_evento_fecha_coherente`, `trg_fn_sincronizar_estado_activo`,
`trg_fn_estado_activo_transicion_valida`, etc.) que esos fakes no pueden
reproducir.
"""
from __future__ import annotations

import random
import string
import uuid
from collections.abc import Generator
from datetime import date, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

_JWT_SECRET_INTEGRACION = "sgpmp-integration-tests-only"


def _id_temporal() -> int:
    return uuid.uuid4().int % (10**9)


def _nombre_temporal(prefijo: str) -> str:
    return prefijo + " " + "".join(random.choices(string.ascii_letters, k=10))


@pytest.fixture(autouse=True)
def catalogo_estados_activo(db_session: Session) -> None:
    db_session.execute(
        text(
            """
            INSERT INTO modulo2.estados_activos_biologicos (id_estado_activo_biologico, nombre)
            VALUES (1,'ACTIVO'),(2,'INACTIVO'),(3,'EN_TRATAMIENTO'),(4,'AISLADO'),(5,'CERRADO'),(6,'BAJA')
            ON CONFLICT (id_estado_activo_biologico) DO NOTHING
            """
        )
    )
    db_session.flush()


def _crear_finca_infra(db_session: Session, id_usuario_dueno: int) -> int:
    sid = _id_temporal()
    db_session.execute(text("SET LOCAL app.usuario_id = :uid"), {"uid": id_usuario_dueno})
    db_session.execute(
        text(
            """
            INSERT INTO modulo9.fincas (
                id_finca, nombre, ubicacion, tamano_h, fecha_actualizacion, fecha_creacion, es_activo, id_usuario
            ) VALUES (:id, :nombre, '{}', 10, now(), now(), true, :id_usuario)
            """
        ),
        {"id": sid, "nombre": _nombre_temporal("Finca Verificacion Baja"), "id_usuario": id_usuario_dueno},
    )
    db_session.execute(
        text(
            """
            INSERT INTO modulo9.infraestructuras (
                id_infraestructura, nombre, id_finca, superficie, es_activo, tipo
            ) VALUES (:id, :nombre, :id, 100, true, 'Corral')
            """
        ),
        {"id": sid, "nombre": _nombre_temporal("Infra Verificacion Baja")},
    )
    db_session.flush()
    return sid


def _crear_activo(db_session: Session, sid: int, id_usuario: int, tipo: str, cantidad_inicial: int | None = None) -> int:
    id_activo = _id_temporal()
    db_session.execute(
        text(
            """
            INSERT INTO modulo2.activos_biologicos (
                id_activo_biologico, id_especie, identificador,
                id_infraestructura, tipo, fecha_inicio_ciclo, id_estado,
                descripcion, origen_financiero, costo_adquisicion,
                atributos_dinamicos, id_usuario, fecha_creacion,
                soporte_documental, detalles_procedencia
            ) VALUES (
                :id_activo, 2, :identificador, :id_infra, :tipo,
                current_date, 1, 'Integración INC-M02-29-G36', 'compra', 100,
                '{}', :id_usuario, now() - interval '3 days', 'doc', ''
            )
            """
        ),
        {
            "id_activo": id_activo,
            "identificador": f"G36-{id_activo}" if tipo == "INDIVIDUAL" else None,
            "id_infra": sid,
            "id_usuario": id_usuario,
            "tipo": tipo,
        },
    )
    if tipo == "POBLACIONAL":
        db_session.execute(
            text(
                """
                INSERT INTO modulo2.detalles_activos_biologicos_poblacionales (
                    id_detalle_activo_biologico_poblacional, id_activo_biologico, cantidad_inicial, cantidad_actual
                ) VALUES (:id, :id_activo, :cant, :cant)
                """
            ),
            {"id": _id_temporal(), "id_activo": id_activo, "cant": cantidad_inicial},
        )
    db_session.flush()
    return id_activo


@pytest.fixture
def m02_client(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[TestClient, None, None]:
    from src.biological_assets.infrastructure.routers.activo_biologico_router import router as activo_router
    from src.identity_access.infrastructure.routers.usuarios_routers import router as usuarios_router  # noqa: F401
    from src.shared import jwt as jwt_module
    from src.shared.database import get_db
    from src.shared.error_handlers import register_error_handlers

    monkeypatch.setattr(jwt_module, "_SECRET_KEY", _JWT_SECRET_INTEGRACION)
    monkeypatch.setattr(jwt_module, "_EXPIRE_HOURS", 8)

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app = FastAPI()
    register_error_handlers(app)
    app.include_router(activo_router)
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(
        app,
        client=("sgpmp-integration-tests", 50000),
        raise_server_exceptions=False,
    ) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_baja_individual_e2e(m02_client, db_session, crear_usuario_db, crear_auth_headers) -> None:
    productor = crear_usuario_db(id_rol=2, estado=2)
    sid = _crear_finca_infra(db_session, productor["id_usuario"])
    id_activo = _crear_activo(db_session, sid, productor["id_usuario"], "INDIVIDUAL")

    ayer = (date.today() - timedelta(days=1)).isoformat()
    respuesta = m02_client.post(
        f"/activos-biologicos/{id_activo}/eventos/baja",
        json={"tipo_baja": "venta", "fecha_baja": ayer, "motivo_baja": "verificacion e2e individual"},
        headers=crear_auth_headers(productor),
    )
    assert respuesta.status_code == 201, respuesta.text


def test_baja_poblacional_total_e2e(m02_client, db_session, crear_usuario_db, crear_auth_headers) -> None:
    productor = crear_usuario_db(id_rol=2, estado=2)
    sid = _crear_finca_infra(db_session, productor["id_usuario"])
    id_activo = _crear_activo(db_session, sid, productor["id_usuario"], "POBLACIONAL", cantidad_inicial=3)

    ayer = (date.today() - timedelta(days=1)).isoformat()
    respuesta = m02_client.post(
        f"/activos-biologicos/{id_activo}/eventos/baja",
        json={
            "tipo_baja": "venta", "fecha_baja": ayer,
            "motivo_baja": "verificacion e2e poblacional total", "cantidad_afectada": 3,
        },
        headers=crear_auth_headers(productor),
    )
    assert respuesta.status_code == 201, respuesta.text


def test_cierre_ciclo_mismo_dia_utc_e2e(m02_client, db_session, crear_usuario_db, crear_auth_headers) -> None:
    """RF-38, endpoint POST /{id_activo}/cierre -- mismo escenario que #412
    (mismo dia UTC de creacion del activo) pero para RF-38 en vez de RF-45."""
    productor = crear_usuario_db(id_rol=2, estado=2)
    sid = _crear_finca_infra(db_session, productor["id_usuario"])
    id_activo = _crear_activo(db_session, sid, productor["id_usuario"], "INDIVIDUAL")
    db_session.execute(
        text(
            """
            INSERT INTO modulo2.gestiones_fases (
                id_gestion_fases, id_activo_biologico, id_ciclo_productiva,
                fecha_inicio, es_activa, id_usuario
            ) VALUES (:id, :id_activo, 1, now() - interval '3 days', true, :id_usuario)
            """
        ),
        {"id": _id_temporal(), "id_activo": id_activo, "id_usuario": productor["id_usuario"]},
    )
    db_session.flush()

    hoy = date.today().isoformat()
    respuesta = m02_client.post(
        f"/activos-biologicos/{id_activo}/cierre",
        json={"fecha_cierre": hoy, "motivo_cierre": "venta"},
        headers=crear_auth_headers(productor),
    )
    assert respuesta.status_code == 200, respuesta.text
