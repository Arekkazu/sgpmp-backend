"""TC-M03-G58 — RF-56 / CU-02.

Subcasos: TC-M03-114 (DTO Dev vs E5 M04), TC-M03-121 (versión de modelo).
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError as PydanticValidationError

from src.telemetry.application.use_cases.inferencia.consolidar_paquete_inferencia_use_case import (
    ConsolidarEnviarPaqueteUseCase,
)
from src.telemetry.infrastructure.dto.recibir_evento_edge_dto import RecibirEventoEdgeDTO

_MODULO3 = Path(__file__).resolve().parents[2]
if str(_MODULO3) not in sys.path:
    sys.path.insert(0, str(_MODULO3))
from rf56_dobles import (  # noqa: E402
    MotorObservado,
    PaqueteInferenciaRepoMemoria,
    SesionNula,
    evento_para_consolidar,
)


def _base(**overrides):
    ts = datetime.now(timezone.utc)
    data = {
        "device_id": 1,
        "sensor_id": 1,
        "access_key": "k",
        "clasificacion_rf55": "DESVIACION_SIMPLE",
        "severidad": "LEVE",
        "variables_involucradas": [
            {
                "tipo_variable": "TEMPERATURA_AMBIENTAL",
                "valor": Decimal("20"),
                "unidad": "C",
                "timestamp_captura": ts,
            }
        ],
        "timestamp_captura": ts,
        "timestamp_procesamiento_edge": ts,
        "origen": "TIEMPO_REAL",
        "estado_conectividad": True,
    }
    data.update(overrides)
    return data


@pytest.mark.parametrize(
    "overrides",
    [
        {"clasificacion_rf55": "OTRO"},
        {"severidad": "GRAVE"},
        {"origen": "MQTT"},
    ],
)
def test_tc_m03_114_dto_rechaza_enum_invalido(overrides: dict) -> None:
    with pytest.raises(PydanticValidationError):
        RecibirEventoEdgeDTO.model_validate(_base(**overrides))


def test_tc_m03_114_dto_rechaza_valor_no_numerico() -> None:
    payload = _base()
    payload["variables_involucradas"] = [
        {
            "tipo_variable": "TEMPERATURA_AMBIENTAL",
            "valor": "no-es-numero",
            "unidad": "C",
            "timestamp_captura": datetime.now(timezone.utc),
        }
    ]
    with pytest.raises(PydanticValidationError):
        RecibirEventoEdgeDTO.model_validate(payload)


@pytest.mark.parametrize(
    "clasificacion",
    ["NORMAL", "DESVIACION_SIMPLE", "DESVIACION_COMPUESTA", "ERROR_CONFIGURACION"],
)
def test_tc_m03_114_dto_acepta_clasificaciones_del_contrato(clasificacion: str) -> None:
    dto = RecibirEventoEdgeDTO.model_validate(_base(clasificacion_rf55=clasificacion, severidad=None))
    assert dto.clasificacion_rf55 == clasificacion


def test_tc_m03_114_rechazo_esquema_por_m04() -> None:
    pytest.skip(
        "BLOQUEADO TC-M03-114 (E5/M04): M04 rechaza esquema, paquete FALLIDO sin "
        "reintento de conectividad. No hay cliente ni mock de M04. El DTO Dev no es E5."
    )


def test_tc_m03_121_campo_existe_y_consolidado_no_lo_aplica() -> None:
    dto = RecibirEventoEdgeDTO.model_validate(_base(version_modelo_objetivo="v-no-vigente"))
    assert dto.version_modelo_objetivo == "v-no-vigente"
    motor = MotorObservado(exito=False)
    paquete = ConsolidarEnviarPaqueteUseCase(
        db=SesionNula(),
        paquete_repo=PaqueteInferenciaRepoMemoria(),
        motor_inferencia_port=motor,
    ).execute(evento_para_consolidar())
    assert paquete.id_version_modelo is None
    assert "version_modelo_objetivo" not in (paquete.metadatos or {})
    assert motor.exito is False


def test_tc_m03_121_politica_ajuste_enrutamiento_o_rechazo() -> None:
    pytest.skip(
        "BLOQUEADO TC-M03-121: ni ajuste, ni pipeline compatible, ni rechazo por "
        "version_modelo_objetivo. Falta decisión E8."
    )
