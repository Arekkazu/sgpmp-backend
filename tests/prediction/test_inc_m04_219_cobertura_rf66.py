# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-30 | Leandro | INC-M04-219-G030 RF-68: probar mínimo del 60 %, vigencia, individuos únicos, caché y auditoría de rechazo. |
"""Regresiones de G030 sin base de datos; la integración real vive en tests/integration."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
from types import SimpleNamespace

import pytest

from src.prediction.domain.entities.riesgo_contagio import DatosContagioError, SalidaInferencia
from src.shared.errors import BusinessRuleError
from tests.prediction.test_rf68_riesgo_contagio import AHORA, _calcular, _dto, _use_case, _Resultados


def salidas(cantidad, fecha=AHORA):
    return [SalidaInferencia(D('.9') if n < 4 else D('.1'), fecha, n + 1) for n in range(cantidad)]


@pytest.mark.parametrize('cantidad', [0, 1, 9, 10, 11])
def test_inferencias_menores_al_60_no_ejecutan(cantidad):
    with pytest.raises(DatosContagioError) as exc:
        _calcular(salidas_rf66=salidas(cantidad), total_activos_lote=20)
    assert exc.value.codigo == 'ERROR_DATOS_INSUFICIENTES'
    assert '60%' in exc.value.mensaje


@pytest.mark.parametrize('cantidad,calidad', [(12, '.900'), (13, '.913'), (20, '1.000')])
def test_exactamente_60_y_superior_conservan_formula(cantidad, calidad):
    r = _calcular(salidas_rf66=salidas(cantidad), total_activos_lote=20)
    assert r.factor_sanitario == D('.2')
    assert r.probabilidad_contagio == D('.3500')
    assert not r.confianza_baja and r.modo_ejecucion == 'NORMAL'
    assert r.data_quality_score == D(calidad)


def test_cobertura_no_redondea_59_por_ciento_a_60():
    with pytest.raises(DatosContagioError):
        _calcular(salidas_rf66=salidas(59), total_activos_lote=100)


def test_inferencias_obsoletas_no_completan_el_minimo():
    entradas = salidas(11) + [SalidaInferencia(D('.1'), AHORA - timedelta(minutes=31), 12)]
    with pytest.raises(DatosContagioError):
        _calcular(salidas_rf66=entradas, total_activos_lote=20)


def test_frontera_30_minutos_es_reciente():
    r = _calcular(salidas_rf66=salidas(12, AHORA - timedelta(minutes=30)),
                  total_activos_lote=20, ambiente=None)
    assert r.factor_sanitario == D('.2')


def test_inferencias_futuras_no_completan_la_cobertura():
    with pytest.raises(DatosContagioError):
        _calcular(salidas_rf66=salidas(12, AHORA + timedelta(seconds=1)), total_activos_lote=20)


def test_dos_inferencias_del_mismo_activo_no_cuentan_como_dos_individuos():
    entradas = salidas(11) + [SalidaInferencia(D('.9'), AHORA, 1)]
    with pytest.raises(DatosContagioError):
        _calcular(salidas_rf66=entradas, total_activos_lote=20)


def test_ultima_salida_por_individuo_define_fs_sin_inflarlo():
    entradas = salidas(12) + [SalidaInferencia(D('.9'), AHORA - timedelta(seconds=1), 5)]
    r = _calcular(salidas_rf66=entradas, total_activos_lote=20)
    assert r.factor_sanitario == D('.2')
    assert r.data_quality_score == D('.900')


@pytest.mark.parametrize('score', ['0', '.8'])
def test_score_poblacional_conserva_rfc009(score):
    r = _calcular(salidas_rf66=[], score_anomalia=D(score), total_activos_lote=20)
    assert r.factor_sanitario == D(score) and r.definicion_fs == 'SCORE_POBLACIONAL'
    assert not r.confianza_baja


def test_total_opcional_conserva_contrato_existente():
    r = _calcular(salidas_rf66=salidas(12), total_activos_lote=None)
    assert r.total_activos_lote == 12 and r.factor_sanitario == D('.3333')


@pytest.mark.parametrize('cantidad', [0, 9, 11])
def test_rechazo_audita_sin_resultado_ni_alerta(cantidad):
    uc, alerta, auditoria = _use_case()
    registros = []
    auditoria.registrar = lambda **kw: registros.append(kw)
    commits = []
    uc.db.commit = lambda: commits.append(True)
    with pytest.raises(BusinessRuleError) as exc:
        uc.execute(_dto(probabilidades=['.9'] * cantidad, total_activos_lote=20), 1, 3)
    assert exc.value.status_code == 422 and exc.value.code == 'ERROR_DATOS_INSUFICIENTES'
    assert uc.resultado_repo.guardados == [] and alerta.emitidas == 0
    assert commits == [True]
    evento, = registros
    assert evento['tipo_evento'] == 'ERROR_DATOS_INSUFICIENTES'
    assert evento['resultado_operacion'] == 'FALLIDO' and evento['id_referencia'] == '1'
    assert evento['payload_evento']['inferencias_recientes'] == cantidad
    assert evento['payload_evento']['total_activos_lote'] == 20
    assert D(evento['payload_evento']['cobertura_minima_rf66']) == D('.60')


def test_cache_anterior_no_permite_aceptar_cobertura_insuficiente():
    dto = _dto(probabilidades=['.1'] * 11, total_activos_lote=20)
    uc, alerta, auditoria = _use_case()
    anterior = SimpleNamespace(fecha_calculo=datetime.now(timezone.utc),
                               huella_entradas=uc._huella(dto, 2), desde_cache=False)
    uc.resultado_repo = _Resultados([anterior])
    with pytest.raises(BusinessRuleError) as exc:
        uc.execute(dto, 1, 3)
    assert exc.value.code == 'ERROR_DATOS_INSUFICIENTES'
    assert not anterior.desde_cache and alerta.emitidas == 0
    assert auditoria.eventos == ['ERROR_DATOS_INSUFICIENTES']


def test_fallo_real_de_auditoria_revierte_sin_persistir_resultados():
    uc, alerta, _ = _use_case()
    rollback = []
    uc.db.rollback = lambda: rollback.append(True)
    def fallar(**kw):
        raise RuntimeError('fallo controlado')
    uc.auditoria_repo.registrar = fallar
    with pytest.raises(RuntimeError, match='fallo controlado'):
        uc.execute(_dto(probabilidades=['.1'] * 11, total_activos_lote=20), 1, 3)
    assert rollback == [True] and uc.resultado_repo.guardados == [] and alerta.emitidas == 0


def test_cache_no_reutiliza_inferencias_que_acaban_de_vencer(monkeypatch):
    from src.prediction.application.use_cases.riesgo_contagio import estimar_riesgo_contagio_use_case as modulo_uc
    class Reloj(datetime):
        @classmethod
        def now(cls, tz=None):
            return AHORA
    monkeypatch.setattr(modulo_uc, 'datetime', Reloj)
    dto = _dto(probabilidades=['.1'] * 12, total_activos_lote=20)
    for salida in dto.salidas_rf66:
        salida.fecha_inferencia = AHORA - timedelta(minutes=30, microseconds=1)
    uc, _, auditoria = _use_case()
    anterior = SimpleNamespace(fecha_calculo=AHORA-timedelta(seconds=1),
                               huella_entradas=uc._huella(dto, 2), desde_cache=False)
    uc.resultado_repo = _Resultados([anterior])
    with pytest.raises(BusinessRuleError) as exc:
        uc.execute(dto, 1, 3)
    assert exc.value.code == 'ERROR_DATOS_INSUFICIENTES' and not anterior.desde_cache
    assert auditoria.eventos == ['ERROR_DATOS_INSUFICIENTES']
