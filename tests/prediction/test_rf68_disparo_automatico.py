# | Fecha      | Nombre   | Que se hizo                                                     |
# |------------|----------|-----------------------------------------------------------------|
# | 2026-11-02 | Arekkazu | RF-68: disparo automático tras RF-66 y sin alerta con insumos en sombra |
"""RF-68 disparado por cada resultado nuevo de RF-66."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.prediction.application.use_cases.riesgo_contagio.disparar_riesgo_contagio_use_case import (
    ID_SISTEMA_DISPARO,
    DispararRiesgoContagioUseCase,
)
from src.prediction.domain.entities.resultado_inferencia import ResultadoInferencia
from src.prediction.domain.repositories.contexto_contagio_port import AmbienteArea, ContextoContagio
from src.shared.errors import BusinessRuleError
from tests.prediction.test_rf68_riesgo_contagio import _dto, _use_case

AHORA = datetime.now(timezone.utc)


def _resultado(sombra=False, p_alto=0.94):
    return ResultadoInferencia(
        id_resultado_inferencia=uuid.uuid4(), id_activo_biologico=2, tipo_modelo="MODELO_ESPECIES_GRANDES",
        id_version_modelo=1, nivel_riesgo=3, probabilidad_riesgo={"0": 0.01, "2": 0.05, "3": p_alto},
        probabilidad_enfermedad={"13": p_alto}, confianza_global=Decimal("0.94"), contexto_incompleto=False,
        modo_ejecucion="SERVIDOR", modo_sombra=sombra, fecha_inferencia=AHORA,
    )


def _disparo(contexto, estimar=None):
    estimar = estimar or Mock()
    port = SimpleNamespace(obtener=lambda id_activo, instante: contexto)
    return DispararRiesgoContagioUseCase(contexto_port=port, estimar=estimar), estimar


def _contexto(ambiente_desfase_s=10):
    ambiente = AmbienteArea(Decimal("31.4"), Decimal("60.5"), AHORA - timedelta(seconds=ambiente_desfase_s))
    return ContextoContagio(Decimal("0.01"), Decimal("100.00"), ambiente)


@pytest.mark.parametrize(("sombra", "alertar"), [(False, True), (True, False)])
def test_arma_el_calculo_del_lote_y_solo_alerta_sin_sombra(sombra, alertar):
    uc, estimar = _disparo(_contexto())
    uc.execute(_resultado(sombra=sombra))
    dto = estimar.execute_sistema.call_args.args[0]
    assert estimar.execute_sistema.call_args.kwargs == {"id_sistema": ID_SISTEMA_DISPARO, "alertar": alertar}
    assert dto.id_lote == 2
    assert [(s.id_activo_biologico, s.probabilidad_riesgo_alto) for s in dto.salidas_rf66] == [(2, Decimal("0.94"))]
    assert (dto.densidad_poblacional, dto.porcentaje_sensores_activos) == (Decimal("0.01"), Decimal("100.00"))
    assert dto.variables_ambientales.temperatura == Decimal("31.4")


def test_ambiente_fuera_de_sincronia_no_se_envia():
    uc, estimar = _disparo(_contexto(ambiente_desfase_s=36))
    uc.execute(_resultado())
    assert estimar.execute_sistema.call_args.args[0].variables_ambientales is None


def test_sin_lote_no_calcula_y_un_rechazo_de_rf68_no_se_propaga():
    uc, estimar = _disparo(None)
    assert uc.execute(_resultado()) is None
    estimar.execute_sistema.assert_not_called()

    rechazo = Mock()
    rechazo.execute_sistema.side_effect = BusinessRuleError(code="ERROR_DATOS_INSUFICIENTES", message="x")
    uc, _ = _disparo(_contexto(), rechazo)
    assert uc.execute(_resultado()) is None


class _AuditoriaActor:
    def __init__(self):
        self.eventos = []

    def registrar(self, **kw):
        self.eventos.append(kw)


def test_como_sistema_no_valida_alcance_audita_sistema_y_en_sombra_no_alerta():
    uc, alerta, _ = _use_case(accesible=False)
    uc.auditoria_repo = auditoria = _AuditoriaActor()
    r = uc.execute_sistema(_dto(), id_sistema=ID_SISTEMA_DISPARO, alertar=False)
    assert r.nivel_texto == "ALTO" and not r.confianza_baja
    assert r.alerta_id is None and alerta.emitidas == 0
    [evento] = auditoria.eventos
    assert (evento["tipo_actor"], evento["id_sistema"], "id_usuario" in evento) == ("SISTEMA", ID_SISTEMA_DISPARO, False)
    assert evento["payload_evento"]["alerta_suprimida"] == "INSUMOS_RF66_EN_SOMBRA"


def test_como_sistema_sin_sombra_alerta_igual_que_el_post_manual():
    uc, alerta, _ = _use_case(accesible=False)
    r = uc.execute_sistema(_dto(), id_sistema=ID_SISTEMA_DISPARO, alertar=True)
    assert r.alerta_id == 555 and alerta.emitidas == 1
