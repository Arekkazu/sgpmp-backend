# | Fecha      | Nombre       | Que se hizo                                           |
# |------------|--------------|-------------------------------------------------------|
# | 2026-10-23 | destroyerban | DEV-34 RF-69: códigos HTTP de E2, E3 y E4             |
"""DEV-34 (RF-69 E2/E3/E4, G-03): códigos HTTP del ciclo de vida de versiones de modelo.

E2: metricas_validacion o compatibilidad_variables que no son JSON válido → 422 (antes 500).
E3: una versión registrada como RECHAZADO por métricas → 200 (APROBADO sigue en 201).
E4: activar una versión en estado distinto de APROBADO → 409 (antes 422).
"""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.prediction.domain.entities.version_modelo import VersionModelo
from src.prediction.infrastructure.routers import version_modelo_router as router_module
from src.shared.database import get_db
from src.shared.error_handlers import register_error_handlers
from src.shared.errors import BusinessRuleError, ConflictError

SHA = "a" * 64


def _version(estado: str, notas: str | None = "Validado clínicamente") -> VersionModelo:
    return VersionModelo(
        id_version_modelo=7, nombre_version="v7", tipo_modelo="MODELO_ESPECIES_GRANDES", estado_version=estado,
        formato_artefacto="ONNX", ruta_artefacto="grandes/v7.onnx", tamanio_artefacto_bytes=1024,
        hash_artefacto_sha256=SHA, dataset_entrenamiento_hash=SHA, id_proceso_rf71=uuid.uuid4(),
        version_referencia=None, f1_score=Decimal("0.70"), recall_clase_riesgo_alto=Decimal("0.70"),
        precision_modelo=Decimal("0.70"), accuracy=Decimal("0.70"), roc_auc_score=Decimal("0.70"),
        recall_por_clase={}, matriz_confusion=[[1]], compatibilidad_variables=[], notas_validacion=notas,
        detalle_validacion=None, id_usuario=None, esta_produccion=False, fecha_entrenamiento=None,
        fecha_registro=None, fecha_despliegue=None,
    )


@pytest.fixture
def client(monkeypatch):
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(router_module.router)
    app.dependency_overrides[get_db] = lambda: object()
    return TestClient(app, raise_server_exceptions=False)


def _formulario(**cambios) -> dict:
    datos = {
        "tipo_modelo": "MODELO_ESPECIES_GRANDES",
        "hash_artefacto_sha256": SHA,
        "dataset_entrenamiento_hash": SHA,
        "metricas_validacion": '{"f1_score_global": 0.9}',
        "fecha_entrenamiento": "2026-10-01T00:00:00Z",
        "compatibilidad_variables": "[1, 2]",
        "id_proceso_rf71": str(uuid.uuid4()),
    }
    datos.update(cambios)
    return datos


def _registrar(client, **cambios):
    return client.post(
        "/prediccion/modelos",
        data=_formulario(**cambios),
        files={"archivo_modelo": ("modelo.onnx", b"\x08\x01", "application/octet-stream")},
        headers={"X-RF71-Internal-Key": "clave"},
    )


# --- E2: JSON inválido → 422 ------------------------------------------------------------------

@pytest.mark.parametrize(
    "campo, valor",
    [
        ("metricas_validacion", "{f1: 0.9"),        # no parsea
        ("metricas_validacion", "[0.9, 0.8]"),      # JSON válido pero no es objeto
        ("compatibilidad_variables", "[1, 2"),      # no parsea
        ("compatibilidad_variables", '{"id": 1}'),  # JSON válido pero no es lista
    ],
)
def test_e2_json_invalido_en_el_formulario_es_422(client, campo, valor):
    respuesta = _registrar(client, **{campo: valor})
    assert respuesta.status_code == 422, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["error_code"] == "METADATOS_JSON_INVALIDO"
    assert cuerpo["fields"][0]["field"] == campo
    assert "Los metadatos del modelo son inválidos o incompletos" in cuerpo["message"]


# --- E3: RECHAZADO → 200, APROBADO → 201 ------------------------------------------------------

@pytest.mark.parametrize("estado, http", [("RECHAZADO", 200), ("APROBADO", 201)])
def test_e3_registro_responde_200_si_queda_rechazado(client, monkeypatch, estado, http):
    class _UseCaseFalso:
        def __init__(self, **_): pass
        def execute(self, dto, internal_key): return _version(estado)

    monkeypatch.setattr(router_module, "RegistrarVersionModeloUseCase", _UseCaseFalso)
    respuesta = _registrar(client)
    assert respuesta.status_code == http, respuesta.text
    assert respuesta.json()["estado_version"] == estado


# --- E4: activar una versión no APROBADO → 409 ------------------------------------------------

@pytest.mark.parametrize(
    "estado, codigo",
    [
        ("EN_VALIDACION", "VERSION_NO_APROBADA"),
        ("ACTIVO", "VERSION_NO_APROBADA"),
        ("RECHAZADO", "TRANSICION_ESTADO_INVALIDA"),
        ("DEPRECADO", "TRANSICION_ESTADO_INVALIDA"),
    ],
)
def test_e4_activar_una_version_no_aprobada_es_409(estado, codigo):
    with pytest.raises(ConflictError) as exc:
        _version(estado).activar()
    assert exc.value.code == codigo
    assert exc.value.status_code == 409
    assert estado in exc.value.message


def test_activar_aprobada_sin_notas_sigue_en_422():
    with pytest.raises(BusinessRuleError) as exc:
        _version("APROBADO", notas=None).activar()
    assert exc.value.code == "NOTAS_VALIDACION_REQUERIDAS"
    assert exc.value.status_code == 422


def test_activar_aprobada_con_notas_pasa_a_activo():
    version = _version("APROBADO")
    version.activar()
    assert version.estado_version == "ACTIVO" and version.esta_produccion
