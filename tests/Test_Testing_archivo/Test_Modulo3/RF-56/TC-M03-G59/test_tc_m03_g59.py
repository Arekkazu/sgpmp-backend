"""TC-M03-G59 — RF-56 / CU-02.

Subcasos: TC-M03-117, TC-M03-118.
Memoria + SesionNula: no es PostgreSQL ni sandbox X-Test-Run-Id.
MotorObservado(exito=False): FALLIDO del puerto, no ACK de M04.
"""
from __future__ import annotations

import sys
from datetime import timedelta
from pathlib import Path

import pytest

from src.shared.errors import ValidationError
from src.telemetry.domain.entities.telemetria import (
    EstadoPaqueteInferencia,
    TipoEventoEdge,
)

_MODULO3 = Path(__file__).resolve().parents[2]
if str(_MODULO3) not in sys.path:
    sys.path.insert(0, str(_MODULO3))
from rf56_dobles import ahora_utc, dto_evento_edge, recibir_use_case  # noqa: E402


def test_tc_m03_117_evento_normal_queda_en_repositorio() -> None:
    use_case, eventos, paquetes, motor, _ = recibir_use_case()
    resultado = use_case.execute(dto_evento_edge(clasificacion_rf55=TipoEventoEdge.NORMAL))
    assert len(eventos.guardados) == 1
    guardado = eventos.guardados[0]
    assert guardado.id_dispositivo_iot == 7
    assert guardado.id_sensor == 8
    assert guardado.clasificacion_rf55 == TipoEventoEdge.NORMAL
    assert resultado.id_evento_edge_computing == guardado.id_evento_edge_computing
    assert resultado.paquete_inferencia_estado is None
    assert paquetes.guardados == []
    assert motor.paquetes == []


def test_tc_m03_117_desviacion_enlaza_evento_y_paquete_via_puerto() -> None:
    use_case, eventos, paquetes, motor, _ = recibir_use_case()
    resultado = use_case.execute(
        dto_evento_edge(
            clasificacion_rf55=TipoEventoEdge.DESVIACION_SIMPLE,
            severidad="LEVE",
        )
    )
    evento = eventos.guardados[0]
    paquete = paquetes.guardados[0]
    assert paquete.id_evento_edge_computing == evento.id_evento_edge_computing
    assert paquete.id_sensor == evento.id_sensor
    assert paquete.id_dispositivo_iot == evento.id_dispositivo_iot
    assert paquete.estado_desviacion == TipoEventoEdge.DESVIACION_SIMPLE
    assert paquete.estado_paquete == EstadoPaqueteInferencia.FALLIDO
    assert resultado.paquete_inferencia_estado == EstadoPaqueteInferencia.FALLIDO
    assert len(motor.paquetes) == 1
    assert paquetes.estados == [
        (paquete.id_paquetes_inferencia, EstadoPaqueteInferencia.FALLIDO, 1)
    ]


def test_tc_m03_117_error_configuracion_guarda_evento_sin_paquete() -> None:
    use_case, eventos, paquetes, motor, _ = recibir_use_case()
    resultado = use_case.execute(
        dto_evento_edge(clasificacion_rf55=TipoEventoEdge.ERROR_CONFIGURACION)
    )
    assert eventos.guardados[0].clasificacion_rf55 == TipoEventoEdge.ERROR_CONFIGURACION
    assert resultado.paquete_inferencia_estado is None
    assert paquetes.guardados == []
    assert motor.paquetes == []


def test_tc_m03_117_desviacion_compuesta_enlaza_ids() -> None:
    use_case, eventos, paquetes, motor, _ = recibir_use_case()
    resultado = use_case.execute(
        dto_evento_edge(
            clasificacion_rf55=TipoEventoEdge.DESVIACION_COMPUESTA,
            severidad="CRITICO",
        )
    )
    assert paquetes.guardados[0].id_evento_edge_computing == eventos.guardados[0].id_evento_edge_computing
    assert paquetes.guardados[0].estado_desviacion == TipoEventoEdge.DESVIACION_COMPUESTA
    assert resultado.paquete_inferencia_estado == EstadoPaqueteInferencia.FALLIDO
    assert motor.exito is False


def test_tc_m03_117_copia_severidad_metadata_y_conectividad() -> None:
    dto = dto_evento_edge(
        clasificacion_rf55=TipoEventoEdge.DESVIACION_SIMPLE,
        severidad="MODERADO",
        estado_conectividad=False,
    )
    dto.metadata_edge = {"origen_prueba": "g59"}
    use_case, eventos, paquetes, motor, _ = recibir_use_case()
    resultado = use_case.execute(dto)
    assert eventos.guardados[0].severidad == "MODERADO"
    assert eventos.guardados[0].estado_conectividad is False
    assert eventos.guardados[0].metadatos.get("origen_prueba") == "g59"
    assert resultado.severidad == "MODERADO"
    assert paquetes.guardados[0].severidad == "MODERADO"
    assert motor.exito is False


def test_tc_m03_117_timestamp_futuro_no_persiste() -> None:
    dto = dto_evento_edge(clasificacion_rf55=TipoEventoEdge.NORMAL)
    dto.timestamp_captura = ahora_utc() + timedelta(seconds=31)
    dto.timestamp_procesamiento_edge = dto.timestamp_captura
    use_case, eventos, _, _, _ = recibir_use_case()
    with pytest.raises(ValidationError) as exc:
        use_case.execute(dto)
    assert exc.value.code == "TIMESTAMP_FUTURO"
    assert eventos.guardados == []


def test_tc_m03_117_repos_aislados_entre_instancias() -> None:
    uc_a, ev_a, pq_a, motor_a, _ = recibir_use_case()
    uc_b, ev_b, pq_b, motor_b, _ = recibir_use_case()
    uc_a.execute(dto_evento_edge(clasificacion_rf55=TipoEventoEdge.NORMAL))
    assert len(ev_a.guardados) == 1
    assert ev_b.guardados == []
    assert pq_a.guardados == []
    assert pq_b.guardados == []
    assert motor_a.paquetes == []
    assert motor_b.paquetes == []
    uc_b.execute(
        dto_evento_edge(
            clasificacion_rf55=TipoEventoEdge.DESVIACION_SIMPLE,
            severidad="LEVE",
        )
    )
    assert len(ev_b.guardados) == 1
    assert len(pq_b.guardados) == 1
    assert pq_a.guardados == []
    assert ev_a.guardados[0].id_evento_edge_computing != ev_b.guardados[0].id_evento_edge_computing
    assert motor_a.paquetes == []
    assert len(motor_b.paquetes) == 1


def test_tc_m03_117_buffer_expirado_no_persiste() -> None:
    dto = dto_evento_edge(clasificacion_rf55=TipoEventoEdge.NORMAL)
    dto.origen = "BUFFER_LOCAL"
    dto.timestamp_captura = ahora_utc() - timedelta(hours=73)
    dto.timestamp_procesamiento_edge = dto.timestamp_captura
    use_case, eventos, _, _, _ = recibir_use_case()
    with pytest.raises(ValidationError) as exc:
        use_case.execute(dto)
    assert exc.value.code == "TIMESTAMP_EXPIRADO"
    assert eventos.guardados == []


def test_tc_m03_117_consulta_http_por_id_paquete() -> None:
    pytest.skip(
        "BLOQUEADO TC-M03-117 (tramo GET): no existen GET /inferencia/paquetes/{id} "
        "ni vista HTTP sensor→M04. La relación en memoria está en "
        "test_tc_m03_117_desviacion_enlaza_evento_y_paquete_via_puerto."
    )


def test_tc_m03_118_intento_en_memoria_no_es_bitacora() -> None:
    """actualizar_estado en memoria: un FALLIDO. No hay tabla de bitácora ni CA-8."""
    use_case, _, paquetes, motor, _ = recibir_use_case()
    use_case.execute(
        dto_evento_edge(
            clasificacion_rf55=TipoEventoEdge.DESVIACION_SIMPLE,
            severidad="LEVE",
        )
    )
    assert len(paquetes.estados) == 1
    assert paquetes.estados == [
        (paquetes.guardados[0].id_paquetes_inferencia, EstadoPaqueteInferencia.FALLIDO, 1)
    ]
    assert motor.exito is False
    assert paquetes.guardados[0].intento_envios == 1


def test_tc_m03_118_bitacora_ciclo_vida() -> None:
    pytest.skip(
        "BLOQUEADO TC-M03-118: no hay GET /inferencia/bitacora ni registro de "
        "generación/validación/envío/reintento por id_paquete. "
        "intento_envios=1 en memoria no cubre éxito, fallo y reintento (CA-8)."
    )
