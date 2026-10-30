# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-26 | Arekkazu | INC-M04-196-G026 RF-68: modelo de estimación de riesgo de contagio |
# | 2026-10-30 | Leandro | INC-M04-217-G026 RF-68: mantener regresiones con umbrales explícitos de configuración. |
"""RF-68: fórmula, discretización, consistencia, datos incompletos y orquestación."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest

from src.prediction.application.use_cases.riesgo_contagio.estimar_riesgo_contagio_use_case import (
    EstimarRiesgoContagioUseCase,
)
from src.prediction.domain.entities.riesgo_contagio import (
    DatosContagioError,
    LecturaAmbiental,
    ParametrosContagio,
    SalidaInferencia,
    calcular_riesgo_contagio,
    discretizar,
)
from src.prediction.infrastructure.dto.estimar_riesgo_contagio_dto import EstimarRiesgoContagioDTO
from src.shared.errors import BusinessRuleError, NotFoundError, TooManyRequestsError

AHORA = datetime(2026, 10, 26, 12, tzinfo=timezone.utc)
D = Decimal


def _parametros(**cambios):
    base = dict(w_fs=D("0.5"), w_fa=D("0.3"), w_fd=D("0.2"), temp_min=D("20"), temp_max=D("40"),
                hr_min=D("40"), hr_max=D("100"), densidad_maxima=D("10"), umbral_riesgo_alto=D("0.70"))
    base.update(cambios)
    return ParametrosContagio(**base)


def _salidas(probabilidades, desfase_s=0):
    return [SalidaInferencia(D(p), AHORA - timedelta(seconds=desfase_s)) for p in probabilidades]


def _calcular(**cambios):
    base = dict(id_lote=1, parametros=_parametros(), ahora=AHORA,
                salidas_rf66=_salidas(["0.9", "0.1", "0.2", "0.3"]), total_activos_lote=4,
                ambiente=LecturaAmbiental(D("30"), D("70"), AHORA), densidad_poblacional=D("5"))
    base.update(cambios)
    return calcular_riesgo_contagio(**base)


def test_formula_ponderada_ca9():
    r = _calcular()
    # Fs = 1/4 = 0.25 ; Fa = (0.5 + 0.5)/2 = 0.5 ; Fd = 5/10 = 0.5
    assert (r.factor_sanitario, r.factor_ambiental, r.factor_densidad) == (D("0.25"), D("0.5"), D("0.5"))
    assert r.probabilidad_contagio == D("0.3750") and r.nivel_texto == "BAJO"
    assert not r.confianza_baja and r.definicion_fs == "CONTEO_INDIVIDUAL"


@pytest.mark.parametrize("p, nivel", [("0.4999", 0), ("0.50", 1), ("0.6999", 1), ("0.70", 2), ("1", 2)])
def test_discretizacion_en_las_fronteras(p, nivel):
    assert discretizar(D(p), D("0.70")) == nivel


def test_acotamiento_de_temperatura_y_humedad():
    r = _calcular(ambiente=LecturaAmbiental(D("80"), D("5"), AHORA))
    assert r.factor_ambiental == D("0.5")  # T_norm = 1 (saturado), HR_norm = 0 (saturado)


def test_mas_del_50_por_ciento_enfermo_no_puede_ser_bajo_y_mas_del_70_es_alto():
    alto = _calcular(salidas_rf66=_salidas(["0.9", "0.9", "0.9", "0.1"]), densidad_poblacional=D("0"),
                      ambiente=LecturaAmbiental(D("20"), D("40"), AHORA))
    assert alto.factor_sanitario == D("0.75") and alto.nivel_texto == "ALTO"
    minimo = _calcular(salidas_rf66=_salidas(["0.9", "0.9", "0.9", "0.1", "0.1"]), total_activos_lote=5,
                       densidad_poblacional=D("0"), ambiente=LecturaAmbiental(D("20"), D("40"), AHORA))
    assert minimo.probabilidad_contagio < D("0.5") and minimo.nivel_texto == "MEDIO"


def test_sin_factor_ambiental_recalcula_pesos_y_baja_la_confianza():
    r = _calcular(ambiente=None)
    assert r.factores_ausentes == ["fa"] and r.confianza_baja
    assert r.pesos_aplicados == {"fs": D("0.714"), "fa": D("0.000"), "fd": D("0.286")}


def test_ambiente_de_mas_de_10_minutos_se_ignora():
    r = _calcular(ambiente=LecturaAmbiental(D("30"), D("70"), AHORA - timedelta(minutes=11)))
    assert "fa" in r.factores_ausentes and "DATOS_AMBIENTALES_DESACTUALIZADOS" in r.motivos_degradacion


def test_densidad_nula_asume_capacidad_maxima():
    r = _calcular(densidad_poblacional=None)
    assert r.factor_densidad == D("1") and r.densidad_asumida


def test_pesos_invalidos_no_ejecutan():
    with pytest.raises(DatosContagioError) as exc:
        _calcular(parametros=_parametros(w_fs=D("0.6")))
    assert exc.value.codigo == "ERROR_CONFIGURACION_PESOS"


@pytest.mark.parametrize("desfase, degradado", [(30, False), (33, True)])
def test_sincronizacion_30_y_jitter_35(desfase, degradado):
    salidas = _salidas(["0.1"]) + [SalidaInferencia(D("0.1"), AHORA - timedelta(seconds=desfase))]
    r = _calcular(salidas_rf66=salidas, total_activos_lote=2)
    assert ("DATOS_NO_SINCRONIZADOS" in r.motivos_degradacion) is degradado


def test_mas_de_35_segundos_no_se_ejecuta():
    salidas = _salidas(["0.1"]) + [SalidaInferencia(D("0.1"), AHORA - timedelta(seconds=36))]
    with pytest.raises(DatosContagioError) as exc:
        _calcular(salidas_rf66=salidas, total_activos_lote=2)
    assert exc.value.codigo == "ERROR_DATOS_DESINCRONIZADOS"


def test_menos_del_60_por_ciento_de_sensores_no_se_ejecuta():
    with pytest.raises(DatosContagioError) as exc:
        _calcular(porcentaje_sensores_activos=D("59.9"))
    assert exc.value.codigo == "ERROR_DATOS_INSUFICIENTES"


def test_inferencias_de_mas_de_30_minutos_no_se_usan():
    with pytest.raises(DatosContagioError):
        _calcular(salidas_rf66=_salidas(["0.9"], desfase_s=31 * 60), ambiente=None)


def test_cobertura_rf66_menor_al_50_calcula_sin_fs_e1():
    r = _calcular(salidas_rf66=_salidas(["0.9"]), total_activos_lote=4)
    assert "fs" in r.factores_ausentes and r.confianza_baja and "COBERTURA_RF66_MENOR_AL_50" in r.motivos_degradacion


def test_score_poblacional_como_fs():
    r = _calcular(salidas_rf66=[], score_anomalia=D("0.8"), total_activos_lote=None)
    assert r.factor_sanitario == D("0.8") and r.definicion_fs == "SCORE_POBLACIONAL"


# ---------------------------------------------------------------------------
# Caso de uso
# ---------------------------------------------------------------------------

class _Resultados:
    def __init__(self, anteriores=()):
        self.anteriores, self.guardados, self.alertas = list(anteriores), [], {}

    def guardar(self, r):
        r.id_resultado_contagio = 100 + len(self.guardados)
        self.guardados.append(r)
        return r

    def ultimos_por_lote(self, id_lote, cantidad):
        return self.anteriores[:cantidad]

    def asociar_alerta(self, id_resultado, id_alerta):
        self.alertas[id_resultado] = id_alerta


class _Auditoria:
    def __init__(self):
        self.eventos = []

    def registrar(self, **kw):
        self.eventos.append(kw["tipo_evento"])


class _Alerta:
    def __init__(self):
        self.emitidas = 0

    def area_del_lote(self, id_lote):
        return 7

    def emitir(self, resultado):
        self.emitidas += 1
        return 555


def _config(**cambios):
    base = dict(umbral_riesgo_alto=D("0.70"), umbral_alerta_critica=D("0.70"), es_activa=True, id_configuracion_motor=3, config_version=2, w_factor_sanitario=D("0.5"),
                w_factor_ambiental=D("0.3"), w_factor_densidad=D("0.2"), temp_min_config=D("20"),
                temp_max_config=D("40"), hr_min_config=D("40"), hr_max_config=D("100"), densidad_maxima_config=D("10"))
    base.update(cambios)
    return SimpleNamespace(**base)


def _use_case(resultados=None, config=_config(), accesible=True):
    alerta, auditoria = _Alerta(), _Auditoria()
    uc = EstimarRiesgoContagioUseCase(
        db=SimpleNamespace(commit=lambda: None, rollback=lambda: None),
        config_repo=SimpleNamespace(obtener_por_tipo=lambda t: config),
        resultado_repo=resultados or _Resultados(),
        activo_port=SimpleNamespace(activo_existe_y_accesible=lambda *a: accesible),
        alerta_port=alerta, auditoria_repo=auditoria,
    )
    return uc, alerta, auditoria


def _dto(probabilidades=("0.9", "0.9", "0.9", "0.9"), **cambios):
    ahora = datetime.now(timezone.utc).isoformat()
    base = dict(id_lote=1, salidas_rf66=[{"probabilidad_riesgo_alto": p, "fecha_inferencia": ahora} for p in probabilidades],
                densidad_poblacional="8", variables_ambientales={"temperatura": "38", "humedad_relativa": "95",
                                                                 "fecha_captura": ahora})
    base.update(cambios)
    return EstimarRiesgoContagioDTO(**base)


def test_riesgo_alto_con_confianza_normal_genera_alerta_rf57():
    uc, alerta, auditoria = _use_case()
    r = uc.execute(_dto(), id_usuario=1, id_rol=3)
    assert r.nivel_texto == "ALTO" and not r.confianza_baja and r.alerta_id == 555 and alerta.emitidas == 1
    assert auditoria.eventos == ["RIESGO_CONTAGIO_CALCULADO", "ALERTA_CONTAGIO_GENERADA"]
    assert r.id_area_productiva == 7 and r.config_version == 2


def test_confianza_baja_no_genera_alerta():
    uc, alerta, _ = _use_case()
    r = uc.execute(_dto(variables_ambientales=None), id_usuario=1, id_rol=3)
    assert r.nivel_texto == "ALTO" and r.confianza_baja and r.alerta_id is None and alerta.emitidas == 0


def test_mismas_entradas_en_menos_de_5_s_usa_el_resultado_anterior_y_distintas_dan_429():
    resultados = _Resultados()
    uc, _, _ = _use_case(resultados)
    dto = _dto()
    primero = uc.execute(dto, 1, 3)
    resultados.anteriores = [primero]
    assert uc.execute(dto, 1, 3).desde_cache
    with pytest.raises(TooManyRequestsError):
        uc.execute(_dto(densidad_poblacional="1"), 1, 3)


def test_lote_inaccesible_es_404_y_sin_configuracion_422():
    with pytest.raises(NotFoundError):
        _use_case(accesible=False)[0].execute(_dto(), 1, 2)
    with pytest.raises(BusinessRuleError) as exc:
        _use_case(config=None)[0].execute(_dto(), 1, 3)
    assert exc.value.code == "CONFIGURACION_CONTAGIO_NO_DEFINIDA"


def test_datos_insuficientes_se_registran_y_responden_422():
    uc, _, auditoria = _use_case()
    with pytest.raises(BusinessRuleError) as exc:
        uc.execute(_dto(porcentaje_sensores_activos="40"), 1, 3)
    assert exc.value.code == "ERROR_DATOS_INSUFICIENTES" and exc.value.status_code == 422
    assert auditoria.eventos == ["ERROR_DATOS_INSUFICIENTES"]


def test_mas_de_5_ejecuciones_degradadas_seguidas_emiten_alerta_de_calidad():
    viejo = SimpleNamespace(confianza_baja=True, fecha_calculo=datetime.now(timezone.utc) - timedelta(minutes=1),
                            huella_entradas="x")
    uc, _, auditoria = _use_case(_Resultados([viejo] * 5))
    uc.execute(_dto(variables_ambientales=None), 1, 3)
    assert "ALERTA_CALIDAD_DATOS" in auditoria.eventos
