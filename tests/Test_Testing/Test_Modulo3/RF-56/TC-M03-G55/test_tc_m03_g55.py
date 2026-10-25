"""TC-M03-G55 — RF-56 / CU-02.

Subcasos: TC-M03-090, TC-M03-091, TC-M03-092.
No existe POST /inferencia. No se usa el tope 500 de RF-53 (batch telemetría).
MotorObservado(exito=False) no es ACK de M04.
"""
from __future__ import annotations

import inspect
import sys
from datetime import timedelta
from pathlib import Path

import pytest

from src.shared.errors import BusinessRuleError
from src.telemetry.application.use_cases.inferencia.consolidar_paquete_inferencia_use_case import (
    ConsolidarEnviarPaqueteUseCase,
)
from src.telemetry.domain.entities.telemetria import (
    EstadoPaqueteInferencia,
    TipoEventoEdge,
)
from src.telemetry.infrastructure.adapters.motor_inferencia_stub_adapter import (
    MotorInferenciaStubAdapter,
)

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


def _consolidar(motor: MotorObservado, evento=None):
    repo = PaqueteInferenciaRepoMemoria()
    use_case = ConsolidarEnviarPaqueteUseCase(
        db=SesionNula(),
        paquete_repo=repo,
        motor_inferencia_port=motor,
    )
    return use_case.execute(evento or evento_para_consolidar()), repo, motor


def test_tc_m03_090_estructura_paquete_desde_evento_desviacion() -> None:
    paquete, repo, motor = _consolidar(MotorObservado(exito=False))
    assert paquete is not None
    assert paquete.id_paquetes_inferencia is not None
    assert paquete.tipo_variable == "TEMPERATURA_AMBIENTAL"
    assert paquete.estado_desviacion == TipoEventoEdge.DESVIACION_SIMPLE
    tipos = {v["tipo_variable"] for v in paquete.contexto_ambiental["AMBIENTAL"]}
    assert tipos == {"TEMPERATURA_AMBIENTAL", "HUMEDAD_RELATIVA"}
    assert paquete.contexto_incompleto is False
    assert paquete.metadatos["clasificacion_rf55"] == TipoEventoEdge.DESVIACION_SIMPLE
    assert "timestamp_captura" in paquete.metadatos
    assert "timestamp_procesamiento_edge" in paquete.metadatos
    assert paquete.severidad == "MODERADO"
    assert len(repo.guardados) == 1
    assert motor.exito is False
    assert paquete.estado_paquete == EstadoPaqueteInferencia.FALLIDO
    assert paquete.intento_envios == 1
    assert repo.estados == [
        (paquete.id_paquetes_inferencia, EstadoPaqueteInferencia.FALLIDO, 1)
    ]
    assert len(motor.paquetes) == 1


def test_tc_m03_090_normal_no_genera_paquete() -> None:
    paquete, repo, motor = _consolidar(
        MotorObservado(exito=False),
        evento_para_consolidar(clasificacion_rf55=TipoEventoEdge.NORMAL),
    )
    assert paquete is None
    assert repo.guardados == []
    assert motor.paquetes == []


def test_tc_m03_090_desviacion_compuesta_conserva_clasificacion() -> None:
    paquete, repo, motor = _consolidar(
        MotorObservado(exito=False),
        evento_para_consolidar(clasificacion_rf55=TipoEventoEdge.DESVIACION_COMPUESTA),
    )
    assert paquete.estado_desviacion == TipoEventoEdge.DESVIACION_COMPUESTA
    assert paquete.metadatos["clasificacion_rf55"] == TipoEventoEdge.DESVIACION_COMPUESTA
    assert paquete.estado_paquete == EstadoPaqueteInferencia.FALLIDO
    assert len(repo.guardados) == 1
    assert motor.exito is False
    assert len(motor.paquetes) == 1


def test_tc_m03_090_mapeo_puerto_true_es_enviado_del_puerto_no_m04() -> None:
    paquete, repo, motor = _consolidar(MotorObservado(exito=True))
    assert motor.exito is True
    assert paquete.estado_paquete == EstadoPaqueteInferencia.ENVIADO
    assert paquete.intento_envios == 1
    assert repo.estados == [
        (paquete.id_paquetes_inferencia, EstadoPaqueteInferencia.ENVIADO, 1)
    ]
    assert len(motor.paquetes) == 1
    # ENVIADO es el bool del puerto, no un ACK HTTP de M04.


def test_tc_m03_090_error_configuracion_consolida_si_se_invoca_directo() -> None:
    """Consolidar solo omite NORMAL. Recibir no llama a este camino (FA-07 / G59)."""
    paquete, repo, motor = _consolidar(
        MotorObservado(exito=False),
        evento_para_consolidar(clasificacion_rf55=TipoEventoEdge.ERROR_CONFIGURACION),
    )
    assert paquete is not None
    assert paquete.estado_desviacion == TipoEventoEdge.ERROR_CONFIGURACION
    assert paquete.estado_paquete == EstadoPaqueteInferencia.FALLIDO
    assert len(repo.guardados) == 1
    assert len(motor.paquetes) == 1


@pytest.mark.parametrize(
    "variables",
    [
        [],
        [{"tipo_variable": "TEMPERATURA_AMBIENTAL", "valor": None}],
        [{"tipo_variable": "", "valor": "1"}],
    ],
)
def test_tc_m03_090_paquete_inconsistente(variables: list) -> None:
    evento = evento_para_consolidar()
    evento.variables_involucradas = variables
    repo = PaqueteInferenciaRepoMemoria()
    use_case = ConsolidarEnviarPaqueteUseCase(
        db=SesionNula(),
        paquete_repo=repo,
        motor_inferencia_port=MotorObservado(exito=False),
    )
    with pytest.raises(BusinessRuleError) as exc:
        use_case.execute(evento)
    assert exc.value.code == "PAQUETE_INCONSISTENTE"
    assert repo.guardados == []


def test_tc_m03_090_timestamps_delta_mayor_5s() -> None:
    ts = ahora_utc()
    evento = evento_para_consolidar(
        variables=[
            {
                "tipo_variable": "TEMPERATURA_AMBIENTAL",
                "valor": "40.0",
                "unidad": "C",
                "timestamp_captura": ts,
            },
            {
                "tipo_variable": "HUMEDAD_RELATIVA",
                "valor": "80.0",
                "unidad": "%",
                "timestamp_captura": ts + timedelta(seconds=6),
            },
        ]
    )
    repo = PaqueteInferenciaRepoMemoria()
    use_case = ConsolidarEnviarPaqueteUseCase(
        db=SesionNula(),
        paquete_repo=repo,
        motor_inferencia_port=MotorObservado(exito=False),
    )
    with pytest.raises(BusinessRuleError) as exc:
        use_case.execute(evento)
    assert exc.value.code == "PAQUETE_INCONSISTENTE"
    assert repo.guardados == []


def test_tc_m03_091_envio_real_a_m04() -> None:
    pytest.skip(
        "BLOQUEADO TC-M03-091: enviar paquete ≤500 registros a M04 con JWT y "
        "verificar respuesta de recepción. MotorInferenciaStubAdapter.enviar_paquete "
        f"({inspect.getsource(MotorInferenciaStubAdapter.enviar_paquete).strip()!r}) "
        "no abre HTTP. No existe POST /inferencia. "
        "test_tc_m03_090_mapeo_puerto_true_es_enviado_del_puerto_no_m04 solo mapea el bool del puerto."
    )


def test_tc_m03_092_un_evento_un_paquete_sin_partir() -> None:
    paquete, repo, motor = _consolidar(MotorObservado(exito=False))
    assert len(repo.guardados) == 1
    assert len(motor.paquetes) == 1
    assert paquete.id_paquetes_inferencia == repo.guardados[0].id_paquetes_inferencia


def test_tc_m03_092_fragmentacion_501() -> None:
    pytest.skip(
        "BLOQUEADO TC-M03-092: el consolidado arma un paquete por evento, "
        "sin partir 501 registros. max_length=500 de POST /iot/telemetria/batch "
        "es RF-53, no fragmentación RF-56."
    )
