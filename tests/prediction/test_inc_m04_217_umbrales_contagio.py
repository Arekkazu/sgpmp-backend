# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-30 | Leandro | INC-M04-217-G026 RF-68: verificar umbrales y flujo en entorno aislado. |
"""Regresiones de #852: configuración RF-65 aplicada al cálculo RF-68."""
from datetime import timedelta
from decimal import Decimal

import pytest

from tests.prediction.test_rf68_riesgo_contagio import _config, _dto, _use_case

D = Decimal


def test_configuracion_version_dos_corrige_el_caso_reportado_por_qa():
    config = _config(umbral_riesgo_alto=D('0.90'), umbral_alerta_critica=D('0.95'))
    uc, alerta, auditoria = _use_case(config=config)
    dto = _dto(probabilidades=('0.9',) * 12 + ('0.1',) * 8,
               total_activos_lote=20, densidad_poblacional='10')
    dto.variables_ambientales.temperatura = D('40')
    dto.variables_ambientales.humedad_relativa = D('100')
    r = uc.execute(dto, 1, 3)
    assert r.factor_sanitario == D('0.6')
    assert r.probabilidad_contagio == D('0.8')
    assert r.nivel_texto == 'MEDIO'
    assert r.config_version == 2
    assert r.alerta_id is None and alerta.emitidas == 0
    assert auditoria.eventos == ['RIESGO_CONTAGIO_CALCULADO']


@pytest.mark.parametrize('probabilidad,nivel', [
    ('0.4999', 'BAJO'), ('0.50', 'MEDIO'), ('0.8999', 'MEDIO'),
    ('0.90', 'ALTO'), ('0.9001', 'ALTO'),
])
def test_corte_alto_configurado_y_corte_medio_conservado(probabilidad, nivel):
    config = _config(umbral_riesgo_alto=D('0.90'), umbral_alerta_critica=D('0.95'),
                     w_factor_sanitario=D('1'), w_factor_ambiental=D('0'), w_factor_densidad=D('0'))
    uc, _, _ = _use_case(config=config)
    r = uc.execute(_dto(salidas_rf66=[], score_anomalia=probabilidad), 1, 3)
    assert r.probabilidad_contagio == D(probabilidad)
    assert r.nivel_texto == nivel


def test_el_cambio_de_version_no_reutiliza_el_resultado_de_la_configuracion_anterior():
    config = _config(umbral_riesgo_alto=D('0.70'), umbral_alerta_critica=D('0.70'))
    uc, _, _ = _use_case(config=config)
    dto = _dto(probabilidades=('0.9',) * 3 + ('0.1',) * 2,
               total_activos_lote=5, densidad_poblacional='10')
    dto.variables_ambientales.temperatura = D('40')
    dto.variables_ambientales.humedad_relativa = D('100')
    antes = uc.execute(dto, 1, 3)
    assert antes.nivel_texto == 'ALTO'
    antes.fecha_calculo -= timedelta(seconds=6)
    uc.resultado_repo.anteriores = [antes]
    config.config_version += 1
    config.umbral_riesgo_alto = D('0.90')
    config.umbral_alerta_critica = D('0.95')
    despues = uc.execute(dto, 1, 3)
    assert despues.nivel_texto == 'MEDIO' and despues.alerta_id is None
    assert despues.huella_entradas != antes.huella_entradas and not despues.desde_cache
    assert antes.nivel_texto == 'ALTO' and antes.config_version == 2
    assert despues.config_version == 3


@pytest.mark.parametrize('probabilidad,alertas', [('0.9499', 0), ('0.95', 1), ('0.9501', 1)])
def test_alerta_critica_respeta_su_umbral_inclusivo(probabilidad, alertas):
    config = _config(umbral_riesgo_alto=D('0.90'), umbral_alerta_critica=D('0.95'),
                     w_factor_sanitario=D('1'), w_factor_ambiental=D('0'), w_factor_densidad=D('0'))
    uc, alerta, auditoria = _use_case(config=config)
    r = uc.execute(_dto(salidas_rf66=[], score_anomalia=probabilidad), 1, 3)
    assert r.nivel_texto == 'ALTO' and not r.confianza_baja
    assert alerta.emitidas == alertas
    assert ('ALERTA_CONTAGIO_GENERADA' in auditoria.eventos) is bool(alertas)
    assert (r.alerta_id is not None) is bool(alertas)
    assert r.umbrales_aplicados == {'umbral_riesgo_alto': D('0.90'), 'umbral_alerta_critica': D('0.95')}


def test_umbral_alto_minimo_es_inclusivo_y_no_inventa_una_banda_media():
    config = _config(umbral_riesgo_alto=D('0.50'), umbral_alerta_critica=D('0.75'))
    uc, alerta, _ = _use_case(config=config)
    dto = _dto(probabilidades=('0.1',) * 5, densidad_poblacional='10')
    dto.variables_ambientales.temperatura = D('40')
    dto.variables_ambientales.humedad_relativa = D('100')
    r = uc.execute(dto, 1, 3)
    assert r.probabilidad_contagio == D('0.5') and r.nivel_texto == 'ALTO'
    assert r.alerta_id is None and alerta.emitidas == 0


def test_prevalencia_sanitaria_obligatoria_no_se_confunde_con_umbral_configurable():
    config = _config(umbral_riesgo_alto=D('0.90'), umbral_alerta_critica=D('0.95'))
    uc, alerta, _ = _use_case(config=config)
    dto = _dto(probabilidades=('0.9',) * 4 + ('0.1',), total_activos_lote=5,
               densidad_poblacional='0')
    dto.variables_ambientales.temperatura = D('20')
    dto.variables_ambientales.humedad_relativa = D('40')
    r = uc.execute(dto, 1, 3)
    assert r.factor_sanitario == D('0.8') and r.probabilidad_contagio == D('0.4')
    assert r.nivel_texto == 'ALTO'  # RF-68 obliga ALTO con más del 70 % enfermo.
    assert alerta.emitidas == 0  # La alerta crítica sigue su umbral independiente.


def test_confianza_baja_sigue_impidiendo_alerta_aunque_se_supere_el_umbral():
    config = _config(umbral_riesgo_alto=D('0.90'), umbral_alerta_critica=D('0.95'))
    uc, alerta, _ = _use_case(config=config)
    r = uc.execute(_dto(salidas_rf66=[], score_anomalia='1', densidad_poblacional='10',
                        variables_ambientales=None), 1, 3)
    assert r.probabilidad_contagio == D('1') and r.nivel_texto == 'ALTO' and r.confianza_baja
    assert r.alerta_id is None and alerta.emitidas == 0
