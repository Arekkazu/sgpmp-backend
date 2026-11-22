# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-28 | destroyerban | INC-M03-169-G77 RF-57 Fase 3: el caso de uso usa el contexto resuelto sin BD |
"""INC-M03-169-G77: la alerta toma el activo y el contexto del puerto, y marca el incompleto con su motivo."""
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import Mock

from src.telemetry.application.use_cases.alertas.generar_alerta_use_case import GenararAlertaUseCase
from src.telemetry.domain.entities.alerta import Alerta
from src.telemetry.domain.repositories.contexto_activo_alerta_port import ContextoActivoAlerta
from src.telemetry.infrastructure.dto.procesar_evento_alerta_dto import ProcesarEventoAlertaDTO


def _ejecutar(resuelto, **kwargs):
    repo = Mock()
    repo.buscar_activa_duplicada.return_value = None
    repo.guardar.side_effect = lambda a: Alerta(**{**a.__dict__, "id_alerta": 1})
    puerto = Mock()
    puerto.resolver.return_value = resuelto
    uc = GenararAlertaUseCase(db=Mock(), alerta_repo=repo, historico_repo=Mock(), regla_repo=Mock(),
                              parametros_port=Mock(), contexto_port=puerto)
    dto = ProcesarEventoAlertaDTO(
        device_id=1, sensor_id=3, serial="S", tipo_variable="OXIGENO_DISUELTO", valor=Decimal("4"), unidad="mg/L",
        timestamp_evento=datetime.now(timezone.utc), estado_dato="LECTURA_VALIDA", severidad_edge="LEVE",
        origen_evento="EDGE", id_telemetria=9, metadata_evento={"x": 1})
    uc.execute(dto, id_infraestructura=1, **kwargs)
    return repo.guardar.call_args.args[0], puerto


def test_activo_resuelto_completa_el_contexto():
    contexto = {"id_activo_biologico": 768, "especie": "Tilapia"}
    alerta, puerto = _ejecutar(ContextoActivoAlerta(768, contexto, "ASOCIACION_SENSOR"))
    assert (alerta.id_activo_biologico, alerta.contexto_activo_biologico, alerta.tiene_contexto_incompleto) == (
        768, contexto, False)
    assert puerto.resolver.call_args.args[0] == 3 and puerto.resolver.call_args.args[3] == 9
    assert alerta.metadato_evento == {"x": 1}


def test_sin_activo_queda_incompleto_con_motivo():
    alerta, _ = _ejecutar(ContextoActivoAlerta(None, None, "ASOCIACION_AMBIENTAL", "VARIOS_ACTIVOS_CANDIDATOS"))
    assert alerta.tiene_contexto_incompleto is True and alerta.id_activo_biologico is None
    assert alerta.metadato_evento == {"x": 1, "contexto_incompleto": {"motivo": "VARIOS_ACTIVOS_CANDIDATOS",
                                                                      "fuente": "ASOCIACION_AMBIENTAL"}}


def test_activo_dado_por_quien_llama_no_se_vuelve_a_resolver():
    alerta, puerto = _ejecutar(ContextoActivoAlerta(1, {}, "X"), id_activo_biologico=55,
                               contexto_activo_biologico={"dado": True})
    puerto.resolver.assert_not_called()
    assert (alerta.id_activo_biologico, alerta.contexto_activo_biologico) == (55, {"dado": True})
