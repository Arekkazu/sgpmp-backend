"""TC-M03-G62 — RF-56 / CU-02.

Subcasos: TC-M03-124 (autenticación access_key), TC-M03-126 (BOLA entre gateways).

Niveles separados:
- DTO: access_key ausente (entrada).
- Use case: puerto None → DISPOSITIVO_NO_AUTORIZADO (no distingue alterada/revocada).
- BOLA: no se ejecuta con DispositivoPortFijo (autoriza cualquier terna) ni con
  inspección SQL. Falta sandbox con dos dispositivos y DispositivoM09Adapter.

Sin JWT. Seriales ficticios. Sin HTTP.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from pydantic import ValidationError as PydanticValidationError

from src.shared.errors import AuthenticationError
from src.telemetry.application.use_cases.inferencia.recibir_evento_edge_use_case import (
    RecibirEventoEdgeUseCase,
)
from src.telemetry.domain.entities.telemetria import DispositivoInfo
from src.telemetry.infrastructure.dto.recibir_evento_edge_dto import RecibirEventoEdgeDTO

_MODULO3 = Path(__file__).resolve().parents[2]
if str(_MODULO3) not in sys.path:
    sys.path.insert(0, str(_MODULO3))
from rf56_dobles import (  # noqa: E402
    DispositivoPortFijo,
    EventoEdgeRepoMemoria,
    MotorObservado,
    PaqueteInferenciaRepoMemoria,
    SesionNula,
    dto_evento_edge,
)


def test_tc_m03_124_dto_sin_access_key() -> None:
    ts = dto_evento_edge().timestamp_captura
    with pytest.raises(PydanticValidationError):
        RecibirEventoEdgeDTO.model_validate(
            {
                "device_id": 1,
                "sensor_id": 1,
                "clasificacion_rf55": "NORMAL",
                "variables_involucradas": [
                    {
                        "tipo_variable": "TEMPERATURA_AMBIENTAL",
                        "valor": "1",
                        "unidad": "C",
                    }
                ],
                "timestamp_captura": ts,
                "timestamp_procesamiento_edge": ts,
                "origen": "TIEMPO_REAL",
                "estado_conectividad": True,
            }
        )


def test_tc_m03_124_puerto_none_rechaza_sin_persistir_ni_enviar() -> None:
    eventos = EventoEdgeRepoMemoria()
    paquetes = PaqueteInferenciaRepoMemoria()
    motor = MotorObservado(exito=False)
    use_case = RecibirEventoEdgeUseCase(
        db=SesionNula(),
        evento_edge_repo=eventos,
        paquete_repo=paquetes,
        dispositivo_port=DispositivoPortFijo(None),
        motor_inferencia_port=motor,
    )
    with pytest.raises(AuthenticationError) as exc:
        use_case.execute(dto_evento_edge(access_key="serial-prueba-no-autorizado"))
    assert exc.value.code == "DISPOSITIVO_NO_AUTORIZADO"
    assert eventos.guardados == []
    assert paquetes.guardados == []
    assert motor.paquetes == []


def test_tc_m03_124_clave_alterada_o_revocada() -> None:
    pytest.skip(
        "BLOQUEADO TC-M03-124 (alterada/revocada): el use case solo distingue "
        "None vs DispositivoInfo. Faltan datos aislados M09 (serial distinto vs "
        "revocado) y DispositivoM09Adapter. No se usa DispositivoPortFijo con "
        "info fija para fingir esos tramos."
    )


def test_tc_m03_126_port_fijo_no_compara_terna() -> None:
    """El doble autoriza cualquier terna. Esto delimita el doble; no es prueba BOLA."""
    eventos = EventoEdgeRepoMemoria()
    paquetes = PaqueteInferenciaRepoMemoria()
    motor = MotorObservado(exito=False)
    info = DispositivoInfo(
        id_dispositivo_iot=7,
        id_sensor=8,
        es_activo_dispositivo=True,
        es_activo_sensor=True,
        id_infraestructura=3,
    )
    puerto = DispositivoPortFijo(info)
    use_case = RecibirEventoEdgeUseCase(
        db=SesionNula(),
        evento_edge_repo=eventos,
        paquete_repo=paquetes,
        dispositivo_port=puerto,
        motor_inferencia_port=motor,
    )
    dto = dto_evento_edge(
        access_key="serial-de-otro-gateway",
        device_id=99,
        sensor_id=88,
        clasificacion_rf55="NORMAL",
    )
    resultado = use_case.execute(dto)
    assert puerto.llamadas == [(99, 88, "serial-de-otro-gateway")]
    assert resultado.paquete_inferencia_estado is None
    assert eventos.guardados[0].id_dispositivo_iot == 7
    assert eventos.guardados[0].id_sensor == 8
    assert eventos.guardados[0].id_dispositivo_iot != dto.device_id
    assert eventos.guardados[0].id_sensor != dto.sensor_id


def test_tc_m03_126_bola_entre_gateways() -> None:
    pytest.skip(
        "BLOQUEADO TC-M03-126: autenticarse como gateway A y enviar sensor_id "
        "de gateway B. DispositivoPortFijo no compara la terna; usarlo haría "
        "pasar un execute que no es BOLA. Inspeccionar el SQL de "
        "DispositivoM09Adapter tampoco ejecuta el escenario. "
        "Falta sandbox con dos dispositivos de prueba aislados. "
        "Fuera de alcance: JWT, flota TEST/DEV, inspección SQL como evidencia."
    )
