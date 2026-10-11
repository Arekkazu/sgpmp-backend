"""RF-69 de punta a punta contra Postgres real, con los triggers de M04 activos.

Fija cuatro defectos que hacían imposible registrar una versión desde RF-71:
  - `umbral_clasificacion` (numeric(5,4)) tenía default 70.00 → overflow en todo INSERT
    (migración 78f6f579b5ba);
  - el trigger `hash_obligatorio` exige la columna legada `hash_artecfacto`, que la
    app no llenaba;
  - el schema tipaba `matriz_confusion` como dict → 500 después del commit;
  - los eventos RF-73 de la versión no cumplían sus campos mínimos.
Y la regla de RFC-009: una versión ACTIVO por (tipo_modelo, componente).
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


def _registrar(cliente: TestClient, tipo: str, metricas: dict, componente: str | None = None) -> dict:
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
    }
    respuesta = cliente.post(
        "/prediccion/modelos", headers={"X-RF71-Internal-Key": CLAVE_RF71},
        data=datos, files={"archivo_modelo": ("modelo.onnx", artefacto)},
    )
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def _eventos(db: Session, id_version: int) -> list[str]:
    return list(db.execute(
        text("SELECT tipo_evento::text FROM modulo4.eventos_auditoria_m04 WHERE id_referencia = :id ORDER BY 1"),
        {"id": str(id_version)},
    ).scalars())


def test_registra_versiones_de_ambos_paradigmas_con_eventos_rf73_validos(cliente, db_session):
    poblacional = _registrar(cliente, "MODELO_PORCINOS", POBLACIONALES, "DETECTOR")
    individual = _registrar(cliente, "MODELO_ESPECIES_MEDIANAS", SUPERVISADAS)

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
