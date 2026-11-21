"""TC-M03-G57 — RF-56 / CU-02.

Subcasos: TC-M03-094, TC-M03-115.
Contrato real: `_evaluar_contexto` y `contexto_incompleto` en el paquete.
No envía HTTP ni ACK de M04. apto_para_IA no está en el consolidado (RF-62).
"""
from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

import pytest

from src.telemetry.application.use_cases.inferencia.consolidar_paquete_inferencia_use_case import (
    ConsolidarEnviarPaqueteUseCase,
    _evaluar_contexto,
)
from src.telemetry.domain.entities.telemetria import EstadoPaqueteInferencia

_MODULO3 = Path(__file__).resolve().parents[2]
if str(_MODULO3) not in sys.path:
    sys.path.insert(0, str(_MODULO3))
from rf56_dobles import (  # noqa: E402
    MotorObservado,
    PaqueteInferenciaRepoMemoria,
    SesionNula,
    ahora_utc,
    evento_para_consolidar,
)


def _var(tipo: str) -> dict:
    return {"tipo_variable": tipo, "valor": Decimal("1.0"), "unidad": "u"}


def _vars(*tipos: str) -> list[dict]:
    ts = ahora_utc()
    unidades = {
        "TEMPERATURA_AMBIENTAL": "C",
        "HUMEDAD_RELATIVA": "%",
        "TEMPERATURA_CORPORAL": "C",
        "TEMP_CORPORAL": "C",
        "FRECUENCIA_CARDIACA": "lpm",
        "PH_AGUA": "pH",
        "OXIGENO_DISUELTO": "mg/L",
        "NH3": "ppm",
    }
    return [
        {
            "tipo_variable": tipo,
            "valor": Decimal("1.0"),
            "unidad": unidades.get(tipo, "u"),
            "timestamp_captura": ts,
        }
        for tipo in tipos
    ]


def _consolidar(variables: list[dict]):
    motor = MotorObservado(exito=False)
    paquete = ConsolidarEnviarPaqueteUseCase(
        db=SesionNula(),
        paquete_repo=PaqueteInferenciaRepoMemoria(),
        motor_inferencia_port=motor,
    ).execute(evento_para_consolidar(variables=variables))
    return paquete, motor


@pytest.mark.parametrize(
    "tipos,incompleto,categorias",
    [
        (("TEMPERATURA_AMBIENTAL", "HUMEDAD_RELATIVA"), False, {"AMBIENTAL"}),
        (("TEMPERATURA_CORPORAL", "FRECUENCIA_CARDIACA"), False, {"ANIMAL"}),
        (("TEMP_CORPORAL", "FRECUENCIA_CARDIACA"), False, {"ANIMAL"}),
        (("PH_AGUA", "OXIGENO_DISUELTO"), False, {"HIDRICA"}),
        (("TEMPERATURA_AMBIENTAL",), True, {"AMBIENTAL"}),
        (("NH3",), True, {"AMBIENTAL"}),
        (("TEMPERATURA_CORPORAL",), True, {"ANIMAL"}),
        (("OXIGENO_DISUELTO",), True, {"HIDRICA"}),
        (("PH_AGUA",), True, {"HIDRICA"}),
    ],
)
def test_tc_m03_115_094_evaluar_contexto(tipos, incompleto: bool, categorias: set) -> None:
    contexto, flag = _evaluar_contexto([_var(t) for t in tipos])
    assert flag is incompleto
    assert set(contexto.keys()) == categorias


def test_tc_m03_115_paquete_ambiental_completo() -> None:
    paquete, motor = _consolidar(_vars("TEMPERATURA_AMBIENTAL", "HUMEDAD_RELATIVA"))
    assert paquete.contexto_incompleto is False
    assert set(paquete.contexto_ambiental.keys()) == {"AMBIENTAL"}
    assert paquete.estado_paquete == EstadoPaqueteInferencia.FALLIDO
    assert motor.exito is False
    assert len(motor.paquetes) == 1


def test_tc_m03_115_paquete_animal_completo() -> None:
    paquete, motor = _consolidar(_vars("TEMPERATURA_CORPORAL", "FRECUENCIA_CARDIACA"))
    assert paquete.contexto_incompleto is False
    assert set(paquete.contexto_ambiental.keys()) == {"ANIMAL"}
    tipos = {v["tipo_variable"] for v in paquete.contexto_ambiental["ANIMAL"]}
    assert tipos == {"TEMPERATURA_CORPORAL", "FRECUENCIA_CARDIACA"}
    assert paquete.estado_paquete == EstadoPaqueteInferencia.FALLIDO
    assert motor.exito is False


def test_tc_m03_115_paquete_animal_alias_temp_corporal() -> None:
    paquete, motor = _consolidar(_vars("TEMP_CORPORAL", "FRECUENCIA_CARDIACA"))
    assert paquete.contexto_incompleto is False
    assert set(paquete.contexto_ambiental.keys()) == {"ANIMAL"}
    assert motor.exito is False


def test_tc_m03_115_paquete_hidrico_completo() -> None:
    paquete, motor = _consolidar(_vars("PH_AGUA", "OXIGENO_DISUELTO"))
    assert paquete.contexto_incompleto is False
    assert set(paquete.contexto_ambiental.keys()) == {"HIDRICA"}
    tipos = {v["tipo_variable"] for v in paquete.contexto_ambiental["HIDRICA"]}
    assert tipos == {"PH_AGUA", "OXIGENO_DISUELTO"}
    assert paquete.estado_paquete == EstadoPaqueteInferencia.FALLIDO
    assert motor.exito is False


def test_tc_m03_094_paquete_ambiental_incompleto() -> None:
    paquete, motor = _consolidar(_vars("TEMPERATURA_AMBIENTAL"))
    assert paquete.contexto_incompleto is True
    assert set(paquete.contexto_ambiental.keys()) == {"AMBIENTAL"}
    assert paquete.estado_paquete == EstadoPaqueteInferencia.FALLIDO
    assert len(motor.paquetes) == 1


def test_tc_m03_094_paquete_animal_incompleto() -> None:
    paquete, motor = _consolidar(_vars("TEMPERATURA_CORPORAL"))
    assert paquete.contexto_incompleto is True
    assert set(paquete.contexto_ambiental.keys()) == {"ANIMAL"}
    assert len(motor.paquetes) == 1


def test_tc_m03_094_paquete_hidrico_incompleto() -> None:
    paquete, motor = _consolidar(_vars("PH_AGUA"))
    assert paquete.contexto_incompleto is True
    assert set(paquete.contexto_ambiental.keys()) == {"HIDRICA"}
    assert len(motor.paquetes) == 1


def test_tc_m03_094_incompleto_no_bloquea_intento_de_puerto() -> None:
    """contexto_incompleto no impide guardar ni llamar al puerto. No es apto_para_IA."""
    paquete, motor = _consolidar(_vars("OXIGENO_DISUELTO"))
    assert paquete.contexto_incompleto is True
    assert paquete.estado_paquete == EstadoPaqueteInferencia.FALLIDO
    assert len(motor.paquetes) == 1


def test_tc_m03_094_no_apto_para_ia() -> None:
    pytest.skip(
        "BLOQUEADO TC-M03-094 (apto_para_IA): PaqueteInferencia no tiene el flag; "
        "ConsolidarEnviarPaqueteUseCase no filtra envío. Ownership RF-62. "
        "El tramo incompleto está en test_tc_m03_094_paquete_*_incompleto."
    )
