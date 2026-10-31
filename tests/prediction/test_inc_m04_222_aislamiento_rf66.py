# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-30 | Leandro | INC-M04-222-G034 RF-68: reproducir contaminación entre lotes y verificar el cálculo aislado. |
"""Regresiones de aislamiento del factor sanitario por lote."""
from datetime import datetime, timedelta, timezone
import hashlib
import json

import pytest

from src.shared.errors import BusinessRuleError, TooManyRequestsError
from decimal import Decimal as D

from src.prediction.infrastructure.dto.estimar_riesgo_contagio_dto import EstimarRiesgoContagioDTO
from tests.prediction.test_rf68_riesgo_contagio import _use_case


def entrada(ajenas=True):
    instante = datetime.now(timezone.utc).isoformat()
    propias = [dict(id_activo_biologico=854, probabilidad_riesgo_alto='.9' if n < 3 else '.1',
                    fecha_inferencia=instante) for n in range(10)]
    otras = [dict(id_activo_biologico=n, probabilidad_riesgo_alto='.95', fecha_inferencia=instante)
             for n in (878, 852, 836, 830, 823)] if ajenas else []
    return EstimarRiesgoContagioDTO(id_lote=854, total_activos_lote=10, salidas_rf66=propias+otras,
        variables_ambientales=dict(temperatura='30', humedad_relativa='70', fecha_captura=instante),
        densidad_poblacional='6')


def test_salidas_de_otros_lotes_no_cambian_fs_ni_generan_alerta():
    uc, alerta, auditoria = _use_case()
    resultado = uc.execute(entrada(), 1, 3)
    assert resultado.n_enfermos_detectados == 3
    assert resultado.factor_sanitario == D('.3')
    assert resultado.probabilidad_contagio == D('.42')
    assert resultado.nivel_riesgo_contagio == 0
    assert resultado.alerta_id is None and alerta.emitidas == 0
    assert auditoria.eventos == ['RIESGO_CONTAGIO_CALCULADO']

def test_descartes_no_cambian_la_entrada_original_y_quedan_en_auditoria():
    uc, _, _ = _use_case()
    eventos = []
    uc.auditoria_repo.registrar = lambda **kw: eventos.append(kw)
    dto = entrada()
    dto.salidas_rf66.append(dto.salidas_rf66[0].model_copy(update={"id_activo_biologico": None}))
    dto.n_enfermos_detectados = 9
    original = dto.model_dump()
    r = uc.execute(dto, 1, 3)
    assert r.n_enfermos_detectados == 3 and r.factor_sanitario == D('.3')
    assert dto.model_dump() == original
    assert eventos[0]['payload_evento']['aislamiento_rf66'] == dict(
        recibidas=16, conservadas=10, descartadas_otro_lote=5, descartadas_sin_identidad=1)


@pytest.mark.parametrize('identidad', [None, 999])
def test_sin_ninguna_salida_acreditable_no_se_calcula_y_se_audita(identidad):
    uc, alerta, auditoria = _use_case()
    dto = entrada(False)
    dto.salidas_rf66 = [s.model_copy(update={'id_activo_biologico': identidad}) for s in dto.salidas_rf66]
    with pytest.raises(BusinessRuleError) as exc:
        uc.execute(dto, 1, 3)
    assert exc.value.code == 'ERROR_DATOS_INSUFICIENTES' and exc.value.status_code == 422
    assert uc.resultado_repo.guardados == [] and alerta.emitidas == 0
    assert auditoria.eventos == ['ERROR_DATOS_INSUFICIENTES']


@pytest.mark.parametrize('desfase', [120, 1900])
def test_fechas_ajenas_no_afectan_sincronia_ni_frescura(desfase):
    uc, _, _ = _use_case()
    dto = entrada()
    for s in dto.salidas_rf66[10:]:
        s.fecha_inferencia -= timedelta(seconds=desfase)
    r = uc.execute(dto, 1, 3)
    assert r.probabilidad_contagio == D('.42') and not r.confianza_baja


def test_total_omitido_solo_considera_salidas_propias():
    uc, _, _ = _use_case()
    dto = entrada()
    dto.total_activos_lote = None
    r = uc.execute(dto, 1, 3)
    assert r.total_activos_lote == 10 and r.factor_sanitario == D('.3')
    assert r.data_quality_score == D('1')


def test_salidas_ajenas_no_inflan_la_cobertura():
    uc, _, _ = _use_case()
    dto = entrada()
    dto.salidas_rf66 = dto.salidas_rf66[:3]+dto.salidas_rf66[10:]
    r = uc.execute(dto, 1, 3)
    assert r.factor_sanitario is None and r.confianza_baja
    assert 'COBERTURA_RF66_MENOR_AL_50' in r.motivos_degradacion


def test_solo_salidas_propias_con_riesgo_real_siguen_alertando():
    uc, alerta, _ = _use_case()
    dto = entrada(False)
    for s in dto.salidas_rf66[:8]:
        s.probabilidad_riesgo_alto = D('.9')
    r = uc.execute(dto, 1, 3)
    assert r.n_enfermos_detectados == 8 and r.nivel_riesgo_contagio == 2
    assert r.alerta_id == 555 and alerta.emitidas == 1


def test_score_poblacional_se_conserva_sin_inferencias_propias():
    uc, _, _ = _use_case()
    dto = entrada()
    dto.salidas_rf66 = dto.salidas_rf66[10:]
    dto.score_anomalia = D('.3')
    r = uc.execute(dto, 1, 3)
    assert r.factor_sanitario == D('.3') and r.definicion_fs == 'SCORE_POBLACIONAL'


def test_cache_usa_entradas_filtradas_y_no_un_resultado_historico_sin_filtro():
    uc, alerta, _ = _use_case()
    dto = entrada(False)
    primero = uc.execute(dto, 1, 3)
    uc.resultado_repo.anteriores = [primero]
    dto.salidas_rf66.append(dto.salidas_rf66[0].model_copy(update={'id_activo_biologico': 999}))
    assert uc.execute(dto, 1, 3).desde_cache is True
    assert len(uc.resultado_repo.guardados) == 1 and alerta.emitidas == 0
    limpio = dto.model_copy(update={'salidas_rf66':dto.salidas_rf66[:-1]})
    viejo = json.dumps({'dto':limpio.model_dump(mode='json'),'config_version':2},sort_keys=True)
    primero.huella_entradas = hashlib.sha256(viejo.encode()).hexdigest()
    with pytest.raises(TooManyRequestsError):
        uc.execute(dto, 1, 3)


def test_error_de_persistencia_no_se_oculta():
    uc, _, _ = _use_case()
    rollback = []
    uc.db.rollback = lambda: rollback.append(True)
    def fallar(_):
        raise RuntimeError('fallo controlado')
    uc.resultado_repo.guardar = fallar
    with pytest.raises(RuntimeError, match='fallo controlado'):
        uc.execute(entrada(), 1, 3)
    assert rollback == [True]
