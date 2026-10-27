# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-27 | destroyerban | INC-M03-117-G60 RF-56: huella SHA-256 del contenido del paquete para idempotencia |
"""INC-M03-117-G60 (RF-56 restricciones 3 y 10): identidad estable del paquete para el receptor.

Identidad LOCAL del emisor: id_paquetes_inferencia más la huella del contenido. Estas pruebas NO
demuestran la idempotencia en M04: su receptor no existe (ver #658), y TC-M03-119/120 siguen
bloqueados por eso.
"""
from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import Mock

import pytest

from src.telemetry.application.use_cases.inferencia.consolidar_paquete_inferencia_use_case import ConsolidarEnviarPaqueteUseCase
from src.telemetry.domain.entities.telemetria import (
    CLAVE_HUELLA_CONTENIDO,
    EstadoCalidadTelemetria,
    EventoEdgeComputing,
    PaqueteInferencia,
    huella_coincide,
    huella_contenido_paquete,
)
from src.telemetry.domain.repositories.paquete_inferencia_repository import PaqueteInferenciaRepository
from src.telemetry.infrastructure.adapters.motor_inferencia_stub_adapter import MotorInferenciaStubAdapter

_T0 = datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc)


def _paquete(**cambios):
    base = PaqueteInferencia(
        id_paquetes_inferencia=11, id_sensor=3, id_dispositivo_iot=2, id_evento_edge_computing=7,
        tipo_variable="TEMPERATURA_AMBIENTAL", valor_numerico=Decimal("38.5000"), unidad="°C",
        estado_calidad=EstadoCalidadTelemetria.LECTURA_VALIDA, estado_desviacion="DESVIACION_SIMPLE",
        severidad="MODERADO", origen="TIEMPO_REAL",
        contexto_ambiental={"AMBIENTAL": [{"tipo_variable": "TEMPERATURA_AMBIENTAL", "valor": "38.5000"}]},
        contexto_incompleto=True, metadatos={"timestamp_captura": _T0.isoformat(), "clasificacion_rf55": "DESVIACION_SIMPLE"},
        fecha_envio=_T0, estado_paquete="PENDIENTE", intento_envios=0,
    )
    return replace(base, **cambios)


def _como_si_volviera_de_postgresql(p):
    """JSONB pierde el orden de claves; Numeric puede devolver otra escala; los Enum vuelven como str."""
    jsonb = lambda d: json.loads(json.dumps(d, sort_keys=False)) if d is not None else None
    metadatos = dict(reversed(list(jsonb(p.metadatos).items())))
    return replace(p, valor_numerico=Decimal("38.5"), estado_calidad=str(p.estado_calidad.value),
                   contexto_ambiental=jsonb(p.contexto_ambiental), metadatos=metadatos)


def test_huella_es_sha256_determinista():
    h = huella_contenido_paquete(_paquete())
    assert len(h) == 64 and int(h, 16) >= 0
    assert h == huella_contenido_paquete(_paquete())


def test_reintento_conserva_la_huella():
    """Estado, intentos y fecha del intento cambian en cada reintento; la huella no."""
    original = _paquete()
    reintento = replace(original, estado_paquete="FALLIDO", intento_envios=3, fecha_envio=_T0 + timedelta(seconds=50))
    assert huella_contenido_paquete(reintento) == huella_contenido_paquete(original)


def test_huella_sobrevive_al_paso_por_postgresql():
    original = _paquete()
    assert huella_contenido_paquete(_como_si_volviera_de_postgresql(original)) == huella_contenido_paquete(original)


@pytest.mark.parametrize("cambio", [
    {"valor_numerico": Decimal("39.0")},
    {"severidad": "CRITICO"},
    {"id_evento_edge_computing": 8},
    {"contexto_incompleto": False},
    {"metadatos": {"timestamp_captura": (_T0 + timedelta(seconds=1)).isoformat(), "clasificacion_rf55": "DESVIACION_SIMPLE"}},
])
def test_mismo_id_con_contenido_distinto_cambia_la_huella(cambio):
    assert huella_contenido_paquete(_paquete(**cambio)) != huella_contenido_paquete(_paquete())


def test_la_huella_guardada_no_entra_en_su_propio_calculo():
    p = _paquete()
    p.metadatos[CLAVE_HUELLA_CONTENIDO] = huella_contenido_paquete(p)
    assert huella_coincide(p)
    assert huella_contenido_paquete(p) == p.metadatos[CLAVE_HUELLA_CONTENIDO]


def test_huella_coincide_detecta_contenido_alterado_y_ausencia():
    p = _paquete()
    p.metadatos[CLAVE_HUELLA_CONTENIDO] = huella_contenido_paquete(p)
    assert not huella_coincide(replace(p, valor_numerico=Decimal("40")))
    assert not huella_coincide(_paquete())  # paquetes anteriores, sin huella


@pytest.fixture
def evento():
    ts = datetime.now(timezone.utc) - timedelta(minutes=1)
    return EventoEdgeComputing(
        id_evento_edge_computing=7, id_sensor=3, id_dispositivo_iot=2,
        clasificacion_rf55="DESVIACION_SIMPLE", tipo_evento="ALERTA_GENERADA", severidad="MODERADO",
        fecha_captura=ts, fecha_procesamiento=ts, origen_dato="TIEMPO_REAL", estado_conectividad=True,
        variables_involucradas=[{"tipo_variable": "TEMPERATURA_AMBIENTAL", "valor": "38.5", "unidad": "°C"}],
    )


def test_consolidacion_guarda_la_huella_del_paquete_generado(evento):
    repo = Mock(spec=PaqueteInferenciaRepository)
    repo.obtener_por_evento.return_value = None
    repo.guardar.side_effect = lambda p: replace(p, id_paquetes_inferencia=11)
    paquete = ConsolidarEnviarPaqueteUseCase(Mock(), repo, MotorInferenciaStubAdapter()).execute(evento)
    guardado = repo.guardar.call_args.args[0]
    assert guardado.metadatos[CLAVE_HUELLA_CONTENIDO] == huella_contenido_paquete(guardado)
    assert huella_coincide(paquete)


def test_reconsolidar_devuelve_el_mismo_id_y_la_misma_huella(evento):
    existente = _paquete()
    existente.metadatos[CLAVE_HUELLA_CONTENIDO] = huella_contenido_paquete(existente)
    repo = Mock(spec=PaqueteInferenciaRepository)
    repo.obtener_por_evento.return_value = existente
    paquete = ConsolidarEnviarPaqueteUseCase(Mock(), repo, MotorInferenciaStubAdapter()).execute(evento)
    assert paquete.id_paquetes_inferencia == 11
    assert paquete.metadatos[CLAVE_HUELLA_CONTENIDO] == existente.metadatos[CLAVE_HUELLA_CONTENIDO]
    repo.guardar.assert_not_called()
