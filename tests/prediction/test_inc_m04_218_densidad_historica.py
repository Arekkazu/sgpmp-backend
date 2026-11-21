# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-30 | Leandro | INC-M04-218-G029 RF-68: probar recuperación de densidad negativa con histórico real. |
from src.prediction.infrastructure.dto.estimar_riesgo_contagio_dto import EstimarRiesgoContagioDTO


def test_densidad_negativa_llega_al_caso_de_uso_para_aplicar_e2():
    dto = EstimarRiesgoContagioDTO(id_lote=1, densidad_poblacional='-5')
    assert str(dto.densidad_poblacional) == '-5'


from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from pydantic import ValidationError as PydanticValidationError

from src.prediction.domain.entities.ocupacion_lote import MuestraOcupacion, promediar_ocupacion, VENTANA_OCUPACION
from tests.prediction.test_rf68_riesgo_contagio import AHORA, _calcular, _dto, _parametros, _use_case
from src.shared.errors import NotFoundError, ServiceUnavailableError

D = Decimal


def muestra(dias, densidad, id_registro):
    return MuestraOcupacion(id_registro, AHORA - timedelta(days=dias), D(densidad) if densidad is not None else None)


def test_promedio_temporal_8_y_11_durante_15_dias_cada_uno_es_9_5():
    r = promediar_ocupacion([muestra(30, '8', 1), muestra(15, '11', 2)], hasta=AHORA)
    assert r.densidad_promedio == D('9.5')
    assert r.segundos_cubiertos == D(30 * 86400)
    assert r.registros_utilizados == (1, 2)
    assert r.snapshot()['muestras_utilizadas'] == 2


def test_frecuencia_de_modificaciones_no_sesga_el_promedio():
    muestras = [muestra(30, '8', 1), muestra(15, '11', 2), muestra(14, '11', 3), muestra(1, '11', 4)]
    assert promediar_ocupacion(muestras, hasta=AHORA).densidad_promedio == D('9.5')


def test_el_ultimo_estado_previo_cubre_el_inicio_y_el_futuro_no_se_usa():
    r = promediar_ocupacion([muestra(60, '999', 1), muestra(31, '8', 2),
                             muestra(15, '11', 3), muestra(-1, '1000', 4)], hasta=AHORA)
    assert r.densidad_promedio == D('9.5') and r.registros_utilizados == (2, 3)


def test_historial_parcial_no_inventa_dias_anteriores_al_primer_registro():
    r = promediar_ocupacion([muestra(10, '9.5', 1)], hasta=AHORA)
    assert r.densidad_promedio == D('9.5') and r.segundos_cubiertos == D(10 * 86400)


@pytest.mark.parametrize('invalida', [None, '-1', 'NaN', 'Infinity'])
def test_estado_invalido_interrumpe_cobertura_sin_prolongar_el_anterior(invalida):
    r = promediar_ocupacion([muestra(30, '8', 1), muestra(20, invalida, 2), muestra(10, '11', 3)], hasta=AHORA)
    assert r.densidad_promedio == D('9.5') and r.segundos_cubiertos == D(20 * 86400)
    assert r.registros_utilizados == (1, 3)


def test_mismo_instante_prevalece_id_mayor_y_el_registro_al_final_no_tiene_duracion():
    r = promediar_ocupacion([muestra(30, '100', 1), muestra(30, '8', 2),
                             muestra(15, '11', 3), muestra(0, '1000', 4)], hasta=AHORA)
    assert r.densidad_promedio == D('9.5') and r.registros_utilizados == (2, 3)


def test_precision_de_microsegundos_no_se_pierde():
    t = AHORA - timedelta(microseconds=2)
    r = promediar_ocupacion([MuestraOcupacion(1, t, D('8')),
                             MuestraOcupacion(2, t + timedelta(microseconds=1), D('11'))], hasta=AHORA)
    assert r.densidad_promedio == D('9.5') and r.segundos_cubiertos == D('0.000002')


@pytest.mark.parametrize('muestras', [[], [muestra(0, '8', 1)], [muestra(30, None, 1)]])
def test_sin_cobertura_util_no_se_inventa_promedio(muestras):
    r = promediar_ocupacion(muestras, hasta=AHORA)
    assert r.densidad_promedio is None and r.segundos_cubiertos == 0


def test_error_de_sensor_usa_densidad_historica_y_conserva_normalizacion():
    r = _calcular(parametros=_parametros(densidad_maxima=D('15')), densidad_poblacional=D('-5'),
                  muestras_ocupacion=[muestra(30, '8', 1), muestra(15, '11', 2)])
    assert r.factor_densidad == D('0.6333')
    assert not r.densidad_asumida and not r.confianza_baja
    assert r.contexto_densidad['fuente'] == 'HISTORICO_OCUPACION_M02'
    assert r.contexto_densidad['densidad_solicitada'] == '-5'
    assert r.contexto_densidad['densidad_aplicada'] == '9.5'


@pytest.mark.parametrize('densidad,esperado', [('0', '0'), ('30', '1')])
def test_promedio_cero_es_valido_y_por_encima_del_maximo_satura(densidad, esperado):
    r = _calcular(parametros=_parametros(densidad_maxima=D('15')), densidad_poblacional=D('-5'),
                  muestras_ocupacion=[muestra(30, densidad, 1)])
    assert r.factor_densidad == D(esperado) and not r.densidad_asumida


def test_error_de_sensor_sin_historico_es_preventivo_y_degradado():
    r = _calcular(densidad_poblacional=D('-5'))
    assert r.factor_densidad == D('1') and r.densidad_asumida and r.confianza_baja
    assert 'SIN_HISTORICO_OCUPACION' in r.motivos_degradacion
    assert r.contexto_densidad['fuente'] == 'CAPACIDAD_MAXIMA_SIN_HISTORICO'


@pytest.mark.parametrize('densidad', [None, '0', '5'])
def test_densidad_nula_o_valida_no_consulta_el_historico(densidad):
    uc, _, _ = _use_case()
    uc.ocupacion_port = SimpleNamespace(obtener_muestras=lambda *a, **kw: pytest.fail('No corresponde histórico'))
    r = uc.execute(_dto(densidad_poblacional=densidad), 1, 3)
    assert r.densidad_asumida is (densidad is None)
    assert 'SIN_HISTORICO_OCUPACION' not in r.motivos_degradacion


def test_caso_de_uso_consulta_mismo_lote_y_ventana_y_cache_no_reconsulta():
    uc, _, _ = _use_case()
    consultas = []

    def obtener(id_lote, *, desde, hasta):
        consultas.append((id_lote, desde, hasta))
        return [MuestraOcupacion(1, desde, D('8')), MuestraOcupacion(2, desde + timedelta(days=15), D('11'))]

    uc.ocupacion_port = SimpleNamespace(obtener_muestras=obtener)
    dto = _dto(densidad_poblacional='-5')
    r = uc.execute(dto, 1, 3)
    assert consultas[0][0] == dto.id_lote and consultas[0][2] - consultas[0][1] == VENTANA_OCUPACION
    assert r.contexto_densidad['densidad_aplicada'] == '9.5'
    uc.resultado_repo.anteriores = [r]
    assert uc.execute(dto, 1, 3).desde_cache and len(consultas) == 1


def test_lote_ajeno_se_rechaza_antes_de_leer_historial():
    uc, _, _ = _use_case(accesible=False)
    uc.ocupacion_port = SimpleNamespace(obtener_muestras=lambda *a, **kw: pytest.fail('No debe acceder'))
    with pytest.raises(NotFoundError):
        uc.execute(_dto(densidad_poblacional='-5'), 1, 3)


def test_fallo_de_infraestructura_no_se_disfraza_de_historial_ausente():
    uc, _, _ = _use_case()

    def fallar(*a, **kw):
        raise ServiceUnavailableError(code='BD_NO_DISPONIBLE', message='Fallo controlado')

    uc.ocupacion_port = SimpleNamespace(obtener_muestras=fallar)
    with pytest.raises(ServiceUnavailableError):
        uc.execute(_dto(densidad_poblacional='-5'), 1, 3)
    assert uc.resultado_repo.guardados == []


def test_sin_historico_no_emite_alerta_aunque_el_riesgo_sea_alto():
    uc, alerta, _ = _use_case()
    r = uc.execute(_dto(densidad_poblacional='-5'), 1, 3)
    assert r.nivel_texto == 'ALTO' and r.confianza_baja and alerta.emitidas == 0


@pytest.mark.parametrize('valor', ['NaN', 'Infinity', '-Infinity', 'texto', {}, True])
def test_errores_de_formato_siguen_siendo_rechazados(valor):
    with pytest.raises(PydanticValidationError):
        EstimarRiesgoContagioDTO(id_lote=1, densidad_poblacional=valor)
