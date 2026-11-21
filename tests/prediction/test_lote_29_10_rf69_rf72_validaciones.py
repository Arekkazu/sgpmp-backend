# | Fecha      | Nombre   | Que se hizo                                                        |
# |------------|----------|--------------------------------------------------------------------|
# | 2026-10-29 | Arekkazu | INC-M04-213/214/215/216 RF-69/RF-72: 422 y formato SavedModel      |
"""Lote QA 29-10 (M04).

INC-M04-213 (#819): un SavedModel empieza con 0x08 igual que ONNX; se distingue por estructura.
INC-M04-214 (#820): fecha futura, tipo_modelo vacío y hashes ausentes responden 422.
INC-M04-215/216 (#844/#845): fuente inválida y más de 3 patologías responden 422.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.identity_access.infrastructure.dependencies import get_current_user
from src.prediction.application.use_cases.versiones_modelo.registrar_version_modelo_use_case import (
    RegistrarVersionModeloUseCase,
    _es_saved_model,
)
from src.prediction.domain.entities.retroalimentacion_clinica import RetroalimentacionClinica
from src.prediction.infrastructure.routers import retroalimentacion_clinica_router, version_modelo_router
from src.shared.database import get_db, get_db_sistema
from src.shared.error_handlers import register_error_handlers
from src.shared.errors import BusinessRuleError

SHA = "a" * 64
# SavedModel real: schema_version=1, meta_graphs{meta_info_def{...}}
SAVED_MODEL = b"\x08\x01\x12\x06\x0a\x04\x0a\x02tf"
# ONNX real: ir_version=8, producer_name="pytorch", graph{...}, opset_import{...}
ONNX = b"\x08\x08\x12\x07pytorch\x3a\x02\x0a\x00\x42\x02\x10\x11"


@pytest.mark.parametrize("datos, esperado", [
    (SAVED_MODEL, "TENSORFLOW_SAVED_MODEL"),
    (ONNX, "ONNX"),
    (b"\x08\x01", "ONNX"),               # fixtures previos: solo ir_version
    (b"\x08\x01modelo-onnx", "ONNX"),
])
def test_formato_por_estructura_y_no_por_primer_byte(datos, esperado):
    assert RegistrarVersionModeloUseCase._detectar_formato(None, datos) == esperado


def test_saved_model_sin_meta_graphs_no_se_toma_como_saved_model():
    assert not _es_saved_model(b"\x08\x01")
    assert not _es_saved_model(b"\x08\x01\x12\x02ab")  # campo 2 no es un MetaGraphDef


def test_fecha_entrenamiento_futura_es_422_antes_de_guardar():
    futura = datetime.now(timezone.utc) + timedelta(days=1)
    with pytest.raises(BusinessRuleError) as exc:
        RegistrarVersionModeloUseCase._validar_fecha_entrenamiento(None, futura)
    assert exc.value.status_code == 422
    assert exc.value.field == "fecha_entrenamiento"


def _app(router) -> TestClient:
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: object()
    app.dependency_overrides[get_db_sistema] = lambda: object()
    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.parametrize("omitidos", [
    ("hash_artefacto_sha256",), ("dataset_entrenamiento_hash",),
    ("hash_artefacto_sha256", "dataset_entrenamiento_hash"),
])
def test_hashes_omitidos_responden_422(omitidos):
    datos = {
        "tipo_modelo": "MODELO_ESPECIES_GRANDES", "hash_artefacto_sha256": SHA,
        "dataset_entrenamiento_hash": SHA, "metricas_validacion": "{}",
        "fecha_entrenamiento": "2026-10-01T00:00:00Z", "compatibilidad_variables": "[]",
        "id_proceso_rf71": str(uuid.uuid4()),
    }
    for campo in omitidos:
        datos.pop(campo)
    respuesta = _app(version_modelo_router.router).post(
        "/prediccion/modelos", data=datos,
        files={"archivo_modelo": ("m.onnx", ONNX, "application/octet-stream")},
    )
    assert respuesta.status_code == 422, respuesta.text
    assert {f["field"] for f in respuesta.json()["fields"]} >= set(omitidos)


def test_mas_de_tres_patologias_responde_422():
    cliente = _app(retroalimentacion_clinica_router.router)
    cliente.app.dependency_overrides.update({
        dep.dependency: (lambda: None)
        for ruta in retroalimentacion_clinica_router.router.routes for dep in ruta.dependencies
    })
    cliente.app.dependency_overrides[get_current_user] = lambda: None
    respuesta = cliente.post("/prediccion/retroalimentacion", json={
        "id_resultado_inferencia": str(uuid.uuid4()), "id_activo_biologico": 1,
        "estado_retroalimentacion": "INCORRECTO", "diagnosticos_reales": [7, 8, 9, 10],
    })
    assert respuesta.status_code == 422, respuesta.text
    assert respuesta.json()["fields"][0]["field"] == "diagnosticos_reales"


@pytest.mark.parametrize("cambios, campo", [
    ({"fuente_diagnostico": "RESONANCIA_MAGNETICA"}, "fuente_diagnostico"),
    ({"diagnosticos_reales": [1, 2, 3, 4]}, "diagnosticos_reales"),
])
def test_entidad_rechaza_con_422(cambios, campo):
    datos = dict(
        id_resultado_inferencia=uuid.uuid4(), id_activo_biologico=1, estado_retroalimentacion="INCORRECTO",
        diagnosticos_reales=[1], fuente_diagnostico=None, observaciones_clinicas=None, id_usuario_veterinario=1,
    )
    datos.update(cambios)
    with pytest.raises(BusinessRuleError) as exc:
        RetroalimentacionClinica.crear(**datos)
    assert exc.value.status_code == 422
    assert exc.value.field == campo
    if campo == "fuente_diagnostico":
        assert "OBSERVACION_DIRECTA, LABORATORIO, HISTORIAL_CLINICO, OTRO" in exc.value.message
