# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-28 | destroyerban | INC-M03-167-G75 RF-57 E16: bordes de la ventana y decisiones de la reevaluación sin BD |
"""INC-M03-167-G75 (RF-57 E16, TC-M03-153/N15/N16): reevaluación por IA sin base de datos.

El reloj se inyecta, así que los bordes de N16 (59:59, 60:00, 60:01) se prueban exactos.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import Mock

import pytest

from src.shared.errors import BusinessRuleError, ConflictError, NotFoundError
from src.telemetry.application.use_cases.alertas.reevaluar_alerta_use_case import (
    ALERTA_GENERADA,
    CONFIRMADA,
    ReevaluarAlertaUseCase,
)
from src.telemetry.domain.entities.alerta import Alerta
from src.telemetry.infrastructure.dto.reevaluar_alerta_dto import ReevaluarAlertaDTO

GENERADA = datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc)


def _original(**cambios):
    datos = dict(id_alerta=496, tipo_alerta="ESTRES_TERMICO", severidad="LEVE", estado_alerta="ACTIVA",
                 origen_evento="EDGE", tipo_variable="TEMPERATURA_AMBIENTAL", fecha_evento=GENERADA,
                 fecha_generacion=GENERADA, tiene_inferencia_no_disponible=True, id_sensor=525,
                 valor=Decimal("31"), unidad="°C")
    datos.update(cambios)
    return Alerta(**datos)


def _caso(original=None, ventana=60, previa=None):
    repo = Mock()
    repo.obtener_por_id.return_value = original if original is not None else _original()
    repo.buscar_reevaluacion.return_value = previa
    repo.guardar.side_effect = lambda a: Alerta(**{**a.__dict__, "id_alerta": 900})
    parametros = Mock()
    parametros.obtener_ventana_reevaluacion_min.return_value = ventana
    return ReevaluarAlertaUseCase(Mock(), repo, parametros, auditoria_repo=None), repo


def _dto(**datos):
    return ReevaluarAlertaDTO(**{"severidad_ia": "MODERADO", **datos})


@pytest.mark.parametrize("transcurrido,acepta", [
    (timedelta(minutes=59, seconds=59), True),
    (timedelta(minutes=60), True),
    (timedelta(minutes=60, milliseconds=1), False),
    (timedelta(minutes=60, seconds=1), False),
])
def test_bordes_de_la_ventana_n16(transcurrido, acepta):
    uc, repo = _caso()
    if acepta:
        assert uc.execute(496, _dto(), ahora=GENERADA + transcurrido).resultado == ALERTA_GENERADA
    else:
        with pytest.raises(BusinessRuleError) as exc:
            uc.execute(496, _dto(), ahora=GENERADA + transcurrido)
        assert exc.value.code == "VENTANA_REEVALUACION_VENCIDA"
        repo.guardar.assert_not_called()


def test_ventana_configurada_se_respeta():
    uc, _ = _caso(ventana=90)
    assert uc.execute(496, _dto(), ahora=GENERADA + timedelta(minutes=89)).resultado == ALERTA_GENERADA


def test_reevaluacion_que_difiere_crea_alerta_vinculada_y_no_toca_la_original():
    original = _original()
    uc, repo = _caso(original)
    r = uc.execute(496, _dto(severidad_ia="CRITICO", probabilidad_ia=Decimal("0.91")),
                   ahora=GENERADA + timedelta(minutes=10))
    assert (r.resultado, r.id_alerta_nueva, r.severidad) == (ALERTA_GENERADA, 900, "CRITICO")
    nueva = repo.guardar.call_args.args[0]
    assert nueva.origen_evento == "IA" and nueva.referencia_alerta_original == 496
    assert nueva.tiene_generada_por_reevaluacion and not nueva.tiene_inferencia_no_disponible
    assert nueva.fecha_evento == original.fecha_evento and nueva.id_sensor == 525
    assert nueva.fecha_vencimiento - nueva.fecha_generacion == timedelta(minutes=5)  # SLA de CRITICO
    assert (original.severidad, original.tiene_inferencia_no_disponible) == ("LEVE", True)
    repo.actualizar_estado.assert_not_called()


def test_tipo_distinto_con_misma_severidad_tambien_es_alerta_nueva():
    uc, repo = _caso()
    r = uc.execute(496, _dto(severidad_ia="LEVE", tipo_alerta_ia="PREDICCION_PATOLOGIA"),
                   ahora=GENERADA + timedelta(minutes=1))
    assert (r.resultado, r.tipo_alerta) == (ALERTA_GENERADA, "PREDICCION_PATOLOGIA")


@pytest.mark.parametrize("tipo", [None, "ESTRES_TERMICO"])
def test_reevaluacion_que_confirma_no_crea_alerta_n15(tipo):
    uc, repo = _caso()
    r = uc.execute(496, _dto(severidad_ia="LEVE", tipo_alerta_ia=tipo), ahora=GENERADA + timedelta(minutes=1))
    assert (r.resultado, r.id_alerta_nueva) == (CONFIRMADA, None)
    repo.guardar.assert_not_called()


@pytest.mark.parametrize("original", [
    _original(tiene_inferencia_no_disponible=False),
    _original(tipo_alerta="TECNICA"),
    _original(tiene_generada_por_reevaluacion=True),
])
def test_alertas_que_no_admiten_reevaluacion(original):
    uc, _ = _caso(original)
    with pytest.raises(BusinessRuleError) as exc:
        uc.execute(496, _dto(), ahora=GENERADA + timedelta(minutes=1))
    assert exc.value.code == "REEVALUACION_NO_APLICA"


def test_segunda_reevaluacion_es_conflicto():
    uc, repo = _caso(previa=_original(id_alerta=900))
    with pytest.raises(ConflictError):
        uc.execute(496, _dto(), ahora=GENERADA + timedelta(minutes=1))
    repo.guardar.assert_not_called()


def test_alerta_inexistente():
    uc, repo = _caso()
    repo.obtener_por_id.return_value = None
    with pytest.raises(NotFoundError):
        uc.execute(1, _dto())


@pytest.mark.parametrize("datos", [{"severidad_ia": "ALTA"}, {"severidad_ia": "LEVE", "tipo_alerta_ia": "TECNICA"},
                                   {"severidad_ia": "LEVE", "probabilidad_ia": 1.5}])
def test_dto_rechaza_valores_fuera_del_catalogo(datos):
    with pytest.raises(ValueError):
        ReevaluarAlertaDTO(**datos)
