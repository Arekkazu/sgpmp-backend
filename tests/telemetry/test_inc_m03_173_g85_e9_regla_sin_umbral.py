# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-28 | destroyerban | INC-M03-173-G85 RF-57 E9: decisión del caso de uso sin BD |
"""INC-M03-173-G85: E9 en GenararAlertaUseCase con el puerto de umbrales simulado."""
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import Mock

import pytest

from src.telemetry.application.use_cases.alertas.generar_alerta_use_case import GenararAlertaUseCase
from src.telemetry.domain.entities.alerta import Alerta
from src.telemetry.domain.repositories.umbral_configurado_port import UmbralConfigurado
from src.telemetry.infrastructure.dto.procesar_evento_alerta_dto import ProcesarEventoAlertaDTO


def _caso(configurado, existente=None):
    repo = Mock()
    repo.buscar_activa_duplicada.return_value = existente
    repo.guardar.side_effect = lambda a: Alerta(**{**a.__dict__, "id_alerta": 7})
    puerto = Mock()
    puerto.consultar.return_value = UmbralConfigurado(configurado, 11, (3,), None if configurado else "SIN_UMBRAL_PARA_LAS_ESPECIES")
    return GenararAlertaUseCase(Mock(), repo, Mock(), Mock(), Mock(), umbral_port=puerto), repo, puerto


def _dto(origen="EDGE"):
    return ProcesarEventoAlertaDTO(device_id=1, sensor_id=2, serial="S", tipo_variable="NH3", valor=Decimal("25"),
                                   unidad="ppm", timestamp_evento=datetime.now(timezone.utc),
                                   estado_dato="LECTURA_VALIDA", severidad_edge="LEVE", origen_evento=origen,
                                   id_telemetria=1, tipo_alerta_ia="PREDICCION_PATOLOGIA" if origen == "IA" else None,
                                   severidad_ia="LEVE" if origen == "IA" else None,
                                   probabilidad_ia=Decimal("0.9") if origen == "IA" else None)


def test_sin_umbral_crea_tecnica_pendiente_y_no_operativa():
    uc, repo, puerto = _caso(False)
    r = uc.execute(_dto(), id_infraestructura=5)
    tecnica = repo.guardar.call_args.args[0]
    assert (tecnica.tipo_alerta, tecnica.tipo_variable) == ("TECNICA", "ERROR_CONFIGURACION_REGLA")
    assert tecnica.metadato_evento["evento_pendiente"]["estado_evaluacion"] == "PENDIENTE_EVALUACION"
    assert r.tipo_alerta == "TECNICA" and "PENDIENTE_EVALUACION" in r.motivo_descarte
    puerto.consultar.assert_called_once_with("NH3", 5)


def test_con_umbral_sigue_el_flujo_normal():
    uc, repo, _ = _caso(True)
    r = uc.execute(_dto(), id_infraestructura=5)
    assert r.tipo_alerta == "SINDROME_RESPIRATORIO"
    assert repo.guardar.call_args.args[0].tipo_alerta == "SINDROME_RESPIRATORIO"


def test_tecnica_abierta_del_sensor_se_consolida():
    abierta = Alerta(id_alerta=3, tipo_alerta="TECNICA", severidad="MODERADO", estado_alerta="ACTIVA",
                     origen_evento="EDGE", tipo_variable="ERROR_CONFIGURACION_REGLA",
                     fecha_evento=datetime.now(timezone.utc), fecha_generacion=datetime.now(timezone.utc))
    uc, repo, _ = _caso(False, existente=abierta)
    r = uc.execute(_dto(), id_infraestructura=5)
    assert r.es_duplicado and r.alerta_existente_id == 3
    repo.guardar.assert_not_called()
    repo.actualizar_deduplicacion.assert_called_once()


@pytest.mark.parametrize("origen", ["IA"])
def test_predicciones_de_ia_no_dependen_de_umbrales(origen):
    uc, _, puerto = _caso(False)
    uc.execute(_dto(origen), id_infraestructura=5)
    puerto.consultar.assert_not_called()
