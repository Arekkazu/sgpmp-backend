# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-30 | Leandro | INC-M04-220-G032 RF-68: validar recálculo inmediato, ventana de caché, errores y efectos transaccionales. |
"""G032: orquestación con fakes; no acredita persistencia PostgreSQL."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D

import pytest

from src.prediction.application.use_cases.riesgo_contagio import estimar_riesgo_contagio_use_case as modulo_uc
from src.prediction.infrastructure.dto.estimar_riesgo_contagio_dto import EstimarRiesgoContagioDTO
from src.shared.errors import BusinessRuleError, NotFoundError
from tests.prediction.test_rf68_riesgo_contagio import _use_case, _Resultados, _config

AHORA = datetime(2026, 10, 30, 18, tzinfo=timezone.utc)


@pytest.fixture
def reloj(monkeypatch):
    instante = [AHORA]
    class Reloj(datetime):
        @classmethod
        def now(cls, tz=None):
            return instante[0]
    monkeypatch.setattr(modulo_uc, 'datetime', Reloj)
    return instante


def entrada(enfermos=4):
    return EstimarRiesgoContagioDTO(
        id_lote=1, total_activos_lote=20,
        salidas_rf66=[dict(id_activo_biologico=n+1,probabilidad_riesgo_alto='.9' if n<enfermos else '.1',
                          fecha_inferencia=AHORA) for n in range(20)],
        densidad_poblacional='8',
        variables_ambientales=dict(temperatura='37.5',humedad_relativa='92.5',fecha_captura=AHORA))


def iniciar(reloj):
    resultados = _Resultados()
    uc, alerta, auditoria = _use_case(resultados, config=_config())
    primero = uc.execute(entrada(),1,3)
    resultados.anteriores = [primero]
    reloj[0] += timedelta(seconds=2)
    return uc, alerta, auditoria, primero


def test_caso_qa_fs_cambia_a_los_dos_segundos_recalcula(reloj):
    uc, alerta, auditoria, primero = iniciar(reloj)
    nuevo = uc.execute(entrada(9),1,3)
    assert primero.factor_sanitario==D('.2') and primero.probabilidad_contagio==D('.5225')
    assert nuevo.factor_sanitario==D('.45') and nuevo.probabilidad_contagio==D('.6475')
    assert nuevo.id_resultado_contagio!=primero.id_resultado_contagio and not nuevo.desde_cache
    assert len(uc.resultado_repo.guardados)==2 and alerta.emitidas==0
    assert auditoria.eventos==['RIESGO_CONTAGIO_CALCULADO']*2


@pytest.mark.parametrize('cambio', ['ambiente','densidad','configuracion','score_poblacional','conteo_sanitario'])
def test_otra_entrada_relevante_cambiante_recalcula_antes_de_5_s(reloj,cambio):
    uc, _, _, primero = iniciar(reloj)
    dto = entrada()
    if cambio=='ambiente':
        dto.variables_ambientales.temperatura=D('30')
    elif cambio=='densidad':
        dto.densidad_poblacional=D('1')
    elif cambio=='configuracion':
        uc.config_repo.obtener_por_tipo=lambda t:_config(config_version=3,w_factor_sanitario=D('.4'),w_factor_ambiental=D('.4'))
    elif cambio=='score_poblacional':
        dto.score_anomalia=D('.45')
    else:
        dto.n_enfermos_detectados=9
    nuevo=uc.execute(dto,1,3)
    assert not nuevo.desde_cache and nuevo.id_resultado_contagio!=primero.id_resultado_contagio
    assert len(uc.resultado_repo.guardados)==2
    if cambio=='configuracion':
        assert nuevo.config_version==3 and nuevo.probabilidad_contagio==D('.5900')


@pytest.mark.parametrize('segundos,cache', [(0,True),(4.999,True),(5,False),(6,False)])
def test_limites_de_cinco_segundos_solo_controlan_cache(reloj,segundos,cache):
    uc, _, auditoria, primero=iniciar(reloj)
    reloj[0]=AHORA+timedelta(seconds=segundos)
    salida=uc.execute(entrada(),1,3)
    assert salida.desde_cache is cache
    assert len(uc.resultado_repo.guardados)==(1 if cache else 2)
    assert len(auditoria.eventos)==(1 if cache else 2)


def test_cache_del_nuevo_resultado_no_repite_persistencia_ni_auditoria(reloj):
    uc, alerta, auditoria, primero=iniciar(reloj)
    nuevo=uc.execute(entrada(9),1,3)
    uc.resultado_repo.anteriores=[nuevo,primero]
    repetido=uc.execute(entrada(9),1,3)
    assert repetido.desde_cache and repetido.id_resultado_contagio==nuevo.id_resultado_contagio
    assert len(uc.resultado_repo.guardados)==2 and len(auditoria.eventos)==2 and alerta.emitidas==0


def test_entradas_cambiantes_no_quedan_limitadas_a_12_por_minuto(reloj):
    uc, _, _, _=iniciar(reloj)
    for n in range(13):
        dto=entrada()
        dto.densidad_poblacional=D('1')+D(n)/100
        nuevo=uc.execute(dto,1,3)
        assert not nuevo.desde_cache
        uc.resultado_repo.anteriores=[nuevo]
        reloj[0]+=timedelta(milliseconds=100)
    assert len(uc.resultado_repo.guardados)==14


def test_cambio_invalido_sigue_rechazado_y_auditado(reloj):
    uc, alerta, auditoria, _=iniciar(reloj)
    dto=entrada(9)
    dto.porcentaje_sensores_activos=D('40')
    with pytest.raises(BusinessRuleError) as exc:
        uc.execute(dto,1,3)
    assert exc.value.code=='ERROR_DATOS_INSUFICIENTES'
    assert len(uc.resultado_repo.guardados)==1 and alerta.emitidas==0
    assert auditoria.eventos[-1]=='ERROR_DATOS_INSUFICIENTES'


def test_cambio_a_alto_conserva_generacion_de_alerta_y_cache_no_la_repite(reloj):
    uc, alerta, auditoria, primero=iniciar(reloj)
    nuevo=uc.execute(entrada(16),1,3)
    assert nuevo.nivel_texto=='ALTO' and nuevo.alerta_id==555 and alerta.emitidas==1
    assert auditoria.eventos[-2:]==['RIESGO_CONTAGIO_CALCULADO','ALERTA_CONTAGIO_GENERADA']
    uc.resultado_repo.anteriores=[nuevo,primero]
    assert uc.execute(entrada(16),1,3).desde_cache
    assert alerta.emitidas==1


def test_recambio_con_confianza_baja_no_emite_alerta(reloj):
    uc, alerta, _, _=iniciar(reloj)
    dto=entrada(16)
    dto.variables_ambientales=None
    nuevo=uc.execute(dto,1,3)
    assert nuevo.confianza_baja and nuevo.alerta_id is None and alerta.emitidas==0


def test_fallo_de_escritura_no_invalida_el_resultado_previo(reloj):
    uc, alerta, _, primero=iniciar(reloj)
    revertidos=[]
    uc.db.rollback=lambda:revertidos.append(True)
    def fallar(resultado):
        raise RuntimeError('fallo controlado')
    uc.resultado_repo.guardar=fallar
    with pytest.raises(RuntimeError,match='fallo controlado'):
        uc.execute(entrada(9),1,3)
    assert revertidos==[True] and alerta.emitidas==0
    assert primero.probabilidad_contagio==D('.5225') and not primero.desde_cache


def test_acceso_al_lote_se_valida_antes_de_cache(reloj):
    uc, _, _, _=iniciar(reloj)
    uc.activo_port.activo_existe_y_accesible=lambda *args:False
    with pytest.raises(NotFoundError):
        uc.execute(entrada(),1,3)
