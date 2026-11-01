# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-29 | Arekkazu | QA-M04-27-10 CU09 H-02/H-03 RF-73: NOTAS_REGISTRADAS e id_version_deprecada contra BD real |
# | 2026-10-31 | Arekkazu | RFC-010 RF-69: versión por animal y SOMBRA contra BD real |
"""RF-69 de punta a punta contra Postgres real, con los triggers de M04 activos.

Fija cuatro defectos que hacían imposible registrar una versión desde RF-71:
  - `umbral_clasificacion` (numeric(5,4)) tenía default 70.00 → overflow en todo INSERT
    (migración 78f6f579b5ba);
  - el trigger `hash_obligatorio` exige la columna legada `hash_artecfacto`, que la
    app no llenaba;
  - el schema tipaba `matriz_confusion` como dict → 500 después del commit;
  - los eventos RF-73 de la versión no cumplían sus campos mínimos.
Y la regla de RFC-009: una versión ACTIVO por (tipo_modelo, componente), que RFC-010
extiende con el animal: una ACTIVO y una SOMBRA por (tipo_modelo, componente, id_activo_biologico).
"""
from __future__ import annotations

import hashlib
import json
import os
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.prediction.application.use_cases.versiones_modelo.activar_version_modelo_use_case import ActivarVersionModeloUseCase
from src.prediction.application.use_cases.versiones_modelo.registrar_notas_version_use_case import RegistrarNotasVersionUseCase
from src.prediction.infrastructure.dto.registrar_notas_version_dto import RegistrarNotasVersionDTO
from src.prediction.infrastructure.repositories.evento_auditoria_m04_repository import SqlAlchemyEventoAuditoriaM04Repository
from src.prediction.infrastructure.repositories.version_modelo_repository import SqlAlchemyVersionModeloRepository
from src.prediction.infrastructure.routers.version_modelo_router import router as version_modelo_router
from src.shared.database import get_db
from src.shared.error_handlers import register_error_handlers
from tests.integration.test_control_acceso_f4_aislamiento import _finca_con_activo

CLAVE_RF71 = "clave-rf71-integracion"
POBLACIONALES = {"calibracion_completada": True, "tasa_falsos_positivos_rutina": 0.04, "tasa_deteccion_eventos_clinicos": 0.9}
SUPERVISADAS = {
    "f1_score_global": 0.85, "recall_clase_riesgo_alto": 0.9, "precision_global": 0.8, "accuracy": 0.9,
    "roc_auc_score": 0.9, "recall_por_clase": {"0": 0.9, "1": 0.9}, "matriz_confusion": [[90, 10], [12, 88]],
}


@pytest.fixture
def cliente(db_session: Session, monkeypatch: pytest.MonkeyPatch, tmp_path) -> TestClient:
    monkeypatch.setenv("RF71_INTERNAL_KEY", CLAVE_RF71)
    monkeypatch.setenv("MODELOS_STORAGE_PATH", str(tmp_path))
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(version_modelo_router)
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def activos(db_session: Session, crear_usuario_db) -> list[int]:
    """Dos animales para los modelos INDIVIDUAL (RFC-010: uno por animal)."""
    dueno = crear_usuario_db(id_rol=3)
    db_session.execute(text("SET LOCAL session_replication_role = replica"))
    ids = [_finca_con_activo(db_session, dueno["id_usuario"])[2] for _ in range(2)]
    db_session.execute(text("SET LOCAL session_replication_role = origin"))
    return ids


def _registrar(
    cliente: TestClient, tipo: str, metricas: dict, componente: str | None = None,
    id_activo: int | None = None, fuente: str | None = None, estado_http: int = 201,
) -> dict:
    artefacto = b"\x08" + os.urandom(32)
    datos = {
        "tipo_modelo": tipo,
        "hash_artefacto_sha256": hashlib.sha256(artefacto).hexdigest(),
        "dataset_entrenamiento_hash": "b" * 64,
        "metricas_validacion": json.dumps(metricas),
        "fecha_entrenamiento": "2026-10-01T08:00:00Z",
        "compatibilidad_variables": "[]",
        "id_proceso_rf71": str(uuid.uuid4()),
        **({"componente": componente} if componente else {}),
        **({"id_activo_biologico": str(id_activo)} if id_activo else {}),
        **({"fuente_datos": fuente} if fuente else {}),
    }
    respuesta = cliente.post(
        "/prediccion/modelos", headers={"X-RF71-Internal-Key": CLAVE_RF71},
        data=datos, files={"archivo_modelo": ("modelo.onnx", artefacto)},
    )
    assert respuesta.status_code == estado_http, respuesta.text
    return respuesta.json()


def _eventos(db: Session, id_version: int) -> list[str]:
    return list(db.execute(
        text("SELECT tipo_evento::text FROM modulo4.eventos_auditoria_m04 WHERE id_referencia = :id ORDER BY 1"),
        {"id": str(id_version)},
    ).scalars())


def test_registra_versiones_de_ambos_paradigmas_con_eventos_rf73_validos(cliente, db_session, activos):
    poblacional = _registrar(cliente, "MODELO_PORCINOS", POBLACIONALES, "DETECTOR")
    individual = _registrar(cliente, "MODELO_ESPECIES_MEDIANAS", SUPERVISADAS, id_activo=activos[0])

    assert (poblacional["estado_version"], poblacional["paradigma"], poblacional["componente"]) == ("APROBADO", "POBLACIONAL", "DETECTOR")
    assert (individual["estado_version"], individual["paradigma"]) == ("APROBADO", "INDIVIDUAL")
    assert individual["matriz_confusion"] == [[90, 10], [12, 88]]
    for version in (poblacional, individual):
        assert _eventos(db_session, version["id_version_modelo"]) == ["VERSION_APROBADA", "VERSION_REGISTRADA"]
        fila = db_session.execute(
            text("SELECT hash_artecfacto = hash_artefacto_sha256, umbral_clasificacion FROM modulo4.versiones_modelos WHERE id_version_modelo = :id"),
            {"id": version["id_version_modelo"]},
        ).one()
        assert fila[0] is True and 0 <= fila[1] <= 1


def test_activar_solo_deprecia_la_version_activa_del_mismo_componente(cliente, db_session):
    ids = [
        _registrar(cliente, "MODELO_ACUICULTURA", POBLACIONALES, componente)["id_version_modelo"]
        for componente in ("DETECTOR", "DETECTOR", "SEGUIMIENTO")
    ]
    repo, auditoria = SqlAlchemyVersionModeloRepository(db_session), SqlAlchemyEventoAuditoriaM04Repository(db_session)
    for id_version in ids:
        RegistrarNotasVersionUseCase(db=db_session, repo=repo, auditoria_repo=auditoria).execute(
            id_version, RegistrarNotasVersionDTO(notas_validacion="Validada en campo"), 1,
        )
        ActivarVersionModeloUseCase(db=db_session, repo=repo, auditoria_repo=auditoria).execute(id_version, id_usuario=1)

    estados = dict(db_session.execute(
        text("SELECT id_version_modelo, estado_version::text FROM modulo4.versiones_modelos WHERE id_version_modelo = ANY(:ids)"),
        {"ids": ids},
    ).all())
    assert [estados[i] for i in ids] == ["DEPRECADO", "ACTIVO", "ACTIVO"]
    assert "AUDITORIA_EVENTO_INVALIDO" not in _eventos(db_session, ids[0])
    # QA-M04-27-10 CU09 H-02/H-03: las notas tienen su propio tipo y la activación dice
    # qué versión deprecó; ninguno de los dos queda como evento inválido.
    assert _eventos(db_session, ids[1]) == [
        "NOTAS_REGISTRADAS", "VERSION_ACTIVADA", "VERSION_APROBADA", "VERSION_REGISTRADA",
    ]
    deprecada = db_session.execute(
        text("SELECT payload_evento ->> 'id_version_deprecada' FROM modulo4.eventos_auditoria_m04 "
             "WHERE tipo_evento = 'VERSION_ACTIVADA' AND id_referencia = :id"),
        {"id": str(ids[1])},
    ).scalar_one()
    assert deprecada == str(ids[0])


# ── RFC-010: versión por animal y SOMBRA ──────────────────────────────────

def _notas_y(db: Session, id_version: int, en_sombra: bool = False):
    repo, auditoria = SqlAlchemyVersionModeloRepository(db), SqlAlchemyEventoAuditoriaM04Repository(db)
    if not en_sombra:
        RegistrarNotasVersionUseCase(db=db, repo=repo, auditoria_repo=auditoria).execute(
            id_version, RegistrarNotasVersionDTO(notas_validacion="Validada en campo"), 1,
        )
    ActivarVersionModeloUseCase(db=db, repo=repo, auditoria_repo=auditoria).execute(
        id_version, id_usuario=1, en_sombra=en_sombra,
    )


def _estados(db: Session, ids: list[int]) -> list[str]:
    estados = dict(db.execute(
        text("SELECT id_version_modelo, estado_version::text FROM modulo4.versiones_modelos WHERE id_version_modelo = ANY(:ids)"),
        {"ids": ids},
    ).all())
    return [estados[i] for i in ids]


def test_rfc010_cada_animal_tiene_su_version_activa(cliente, db_session, activos):
    a885, a886, a885_nueva = (
        _registrar(cliente, "MODELO_ESPECIES_GRANDES", SUPERVISADAS, id_activo=a)["id_version_modelo"]
        for a in (activos[0], activos[1], activos[0])
    )
    for id_version in (a885, a886, a885_nueva):
        _notas_y(db_session, id_version)

    # Antes de RFC-010 activar el segundo animal deprecaba al primero.
    assert _estados(db_session, [a885, a886, a885_nueva]) == ["DEPRECADO", "ACTIVO", "ACTIVO"]
    produccion = db_session.execute(
        text("SELECT bool_and(esta_produccion) FROM modulo4.versiones_modelos WHERE id_version_modelo = ANY(:ids)"),
        {"ids": [a886, a885_nueva]},
    ).scalar_one()
    assert produccion is True


def test_rfc010_sintetico_corre_en_sombra_junto_al_activo(cliente, db_session, activos):
    real = _registrar(cliente, "MODELO_ESPECIES_GRANDES", SUPERVISADAS, id_activo=activos[0])["id_version_modelo"]
    sombra_1, sombra_2 = (
        _registrar(cliente, "MODELO_ESPECIES_GRANDES", SUPERVISADAS, id_activo=activos[0], fuente="SINTETICA")
        for _ in range(2)
    )
    assert sombra_1["fuente_datos"] == "SINTETICA" and sombra_1["id_activo_biologico"] == activos[0]
    _notas_y(db_session, real)
    _notas_y(db_session, sombra_1["id_version_modelo"], en_sombra=True)
    _notas_y(db_session, sombra_2["id_version_modelo"], en_sombra=True)

    assert _estados(db_session, [real, sombra_1["id_version_modelo"], sombra_2["id_version_modelo"]]) == [
        "ACTIVO", "DEPRECADO", "SOMBRA",
    ]
    assert "VERSION_EN_SOMBRA" in _eventos(db_session, sombra_2["id_version_modelo"])
    assert "AUDITORIA_EVENTO_INVALIDO" not in _eventos(db_session, sombra_2["id_version_modelo"])


def test_rfc010_reglas_de_llave_en_el_registro(cliente, activos):
    sin_animal = _registrar(cliente, "MODELO_ESPECIES_GRANDES", SUPERVISADAS, estado_http=422)
    assert sin_animal["error_code"] == "ACTIVO_BIOLOGICO_REQUERIDO"
    poblacional = _registrar(cliente, "MODELO_AVES", POBLACIONALES, "DETECTOR", id_activo=activos[0], estado_http=422)
    assert poblacional["error_code"] == "ACTIVO_BIOLOGICO_NO_APLICA"
    fuente = _registrar(cliente, "MODELO_ESPECIES_GRANDES", SUPERVISADAS, id_activo=activos[0], fuente="OTRA", estado_http=422)
    assert fuente["error_code"] == "FUENTE_DATOS_INVALIDA"
    inexistente = _registrar(cliente, "MODELO_ESPECIES_GRANDES", SUPERVISADAS, id_activo=2_000_000_000, estado_http=400)
    assert inexistente["error_code"] == "REFERENCIA_INVALIDA"
