"""TC-M03-G56 — RF-56 / RF-54 / CU-02.

Subcasos: TC-M03-093, TC-M03-112, TC-M03-113, TC-M03-116.
Contrato actual en src: un intento síncrono; False o excepción → FALLIDO, intento_envios=1.
No hay backoff 0/5/15/30/60 s ni cola RF-54 de dispositivo.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from src.telemetry.application.use_cases.inferencia.consolidar_paquete_inferencia_use_case import (
    ConsolidarEnviarPaqueteUseCase,
)
from src.telemetry.domain.entities.telemetria import EstadoPaqueteInferencia, PaqueteInferencia
from src.telemetry.domain.repositories.motor_inferencia_port import MotorInferenciaPort

_MODULO3 = Path(__file__).resolve().parents[2]
if str(_MODULO3) not in sys.path:
    sys.path.insert(0, str(_MODULO3))
from rf56_dobles import (  # noqa: E402
    MotorObservado,
    PaqueteInferenciaRepoMemoria,
    SesionNula,
    evento_para_consolidar,
)

_BACKOFF_MATRIZ_S = (0, 5, 15, 30, 60)


class MotorQueLanza(MotorInferenciaPort):
    def enviar_paquete(self, paquete: PaqueteInferencia) -> bool:
        raise RuntimeError("fallo simulado del puerto; no es M04")


def _ejecutar(motor):
    repo = PaqueteInferenciaRepoMemoria()
    use_case = ConsolidarEnviarPaqueteUseCase(
        db=SesionNula(),
        paquete_repo=repo,
        motor_inferencia_port=motor,
    )
    paquete = use_case.execute(evento_para_consolidar())
    return paquete, repo, motor


@pytest.mark.parametrize("motor_factory", [lambda: MotorObservado(exito=False), MotorQueLanza])
def test_tc_m03_093_contrato_actual_un_intento_falla(motor_factory) -> None:
    motor = motor_factory()
    paquete, repo, motor = _ejecutar(motor)
    assert paquete.intento_envios == 1
    assert paquete.estado_paquete == EstadoPaqueteInferencia.FALLIDO
    assert repo.estados == [
        (paquete.id_paquetes_inferencia, EstadoPaqueteInferencia.FALLIDO, 1)
    ]
    if isinstance(motor, MotorObservado):
        assert len(motor.paquetes) == 1
        assert motor.exito is False


def test_tc_m03_093_cinco_reintentos_y_buffer_rf54() -> None:
    pytest.skip(
        "BLOQUEADO TC-M03-093: no hay 5 reintentos ni SYNC_FAILURE ni buffer "
        "local RF-54. El contrato actual está en "
        "test_tc_m03_093_contrato_actual_un_intento_falla."
    )


def test_tc_m03_112_pendiente_sin_primer_intento() -> None:
    pytest.skip(
        "BLOQUEADO TC-M03-112: el use case llama enviar_paquete de inmediato; "
        "no deja PENDIENTE por M04 caído antes del primer intento."
    )


def test_tc_m03_113_intervalos_backoff() -> None:
    pytest.skip(
        f"BLOQUEADO TC-M03-113: no hay temporizadores {_BACKOFF_MATRIZ_S} s que medir.",
    )


def test_tc_m03_116_reenvio_cronologico() -> None:
    pytest.skip(
        "BLOQUEADO TC-M03-116: no hay cola de paquetes ni reenvío al recuperar M04.",
    )
