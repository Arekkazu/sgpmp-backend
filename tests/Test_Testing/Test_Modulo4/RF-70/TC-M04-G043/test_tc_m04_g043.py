"""TC-M04-G043 — RF-70 / CU-06.

Subcasos: TC-M04-010, TC-M04-011 (también TC-M04-179, TC-M04-180).

Ambigüedad de gate: RF-70 pide APROBADO; RF-69 propaga solo ACTIVO;
CU-M04-06/FA-01 menciona ACTIVO o aprobada.
Dev no expone POST de inicio OTA. ActivarVersionModeloUseCase exige APROBADO
para pasar a ACTIVO (RF-69), que no es la distribución OTA.
"""
from __future__ import annotations

import inspect

import pytest

from src.prediction.application.use_cases.versiones_modelo.activar_version_modelo_use_case import (
    ActivarVersionModeloUseCase,
)
from src.prediction.domain.entities.version_modelo import VersionModelo
from src.prediction.infrastructure.routers import ota_router
from src.shared.errors import BusinessRuleError


def test_tc_m04_010_011_ambiguedad_gate_aprobado_vs_activo() -> None:
    pytest.skip(
        "PENDING_SPEC TC-M04-010/011: el resultado esperado OTA no puede fijarse. "
        "RF-70 exige estado APROBADO; RF-69 indica que solo ACTIVO se propaga a RF-70; "
        "CU-M04-06/FA-01 rechaza si 'no está en estado ACTIVO o no ha sido aprobada'. "
        "No hay use case de inicio de distribución en src/prediction/application/use_cases/ota/ "
        "(solo ConsultarOtaStatusUseCase y ListarDesplieguesUseCase). "
        "IoT/IA escribe modulo4.despliegues_ota. No se elige APROBADO ni ACTIVO de forma arbitraria."
    )


def test_tc_m04_010_router_ota_solo_lectura() -> None:
    metodos = set()
    for ruta in ota_router.router.routes:
        metodos |= set(getattr(ruta, "methods", set()) or [])
    assert metodos == {"GET"}
    fuentes = inspect.getsource(ota_router)
    assert "POST" not in fuentes or fuentes.count("@router.get") >= 2


def test_tc_m04_011_activar_version_exige_aprobado_rf69_no_es_ota() -> None:
    """RF-69: activar() solo desde APROBADO. No inicia OTA."""
    import uuid
    from datetime import datetime, timezone
    from decimal import Decimal

    v = VersionModelo.crear(
        tipo_modelo="MODELO_ESPECIES_GRANDES",
        formato_artefacto="ONNX",
        ruta_artefacto="/tmp/x",
        tamanio_artefacto_bytes=10,
        hash_artefacto_sha256="a" * 64,
        dataset_entrenamiento_hash="b" * 64,
        id_proceso_rf71=uuid.uuid4(),
        f1_score=Decimal("0.9"),
        recall_clase_riesgo_alto=Decimal("0.9"),
        precision_modelo=None,
        accuracy=None,
        roc_auc_score=None,
        recall_por_clase=None,
        matriz_confusion=None,
        compatibilidad_variables=[],
        fecha_entrenamiento=datetime(2026, 10, 1, tzinfo=timezone.utc),
    )
    assert v.estado_version == "EN_VALIDACION"
    with pytest.raises(BusinessRuleError) as exc:
        v.activar()
    assert exc.value.code == "VERSION_NO_APROBADA"
    assert "despliegue" not in inspect.getsource(ActivarVersionModeloUseCase.execute).lower()
