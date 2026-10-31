# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-30 | Leandro | INC-M04-221-G032 RF-68: validar activación separada del perfil MVP y conservar controles obligatorios. |
# | 2026-10-31 | Arekkazu | INC-M04-221/222 RF-68: salidas con el id del lote (#857 descarta las que no lo traen) |
"""RF-65/RF-68: perfil de cálculo independiente del lugar de ejecución."""
from decimal import Decimal as D
from datetime import datetime, timedelta, timezone

import pytest

from tests.prediction.test_rfc009_taxonomia_paradigma import _configurar
from tests.prediction.test_rf68_riesgo_contagio import _use_case, _config, _dto, _Resultados
from src.shared.errors import BusinessRuleError


def configurar(perfil='MVP',**cambios):
    base=dict(tipo_modelo='MODELO_RIESGO_CONTAGIO',umbral_riesgo_alto=D('.7'),
              umbral_alerta_critica=D('.8'),perfil_calculo_contagio=perfil)
    base.update(cambios)
    return _configurar(**base)


def test_perfil_mvp_se_activa_sin_cambiar_modo_servidor():
    c=configurar()
    assert c.perfil_calculo_contagio=='MVP' and c.modo_ejecucion=='SERVIDOR'
    assert c._snapshot()['perfil_calculo_contagio']=='MVP'


@pytest.mark.parametrize('perfil',['ESTANDAR','MVP'])
def test_perfiles_validos_en_snapshot_y_payload_edge(perfil):
    from src.prediction.application.use_cases.motor_ia.configurar_motor_use_case import payload_config_motor
    c=configurar(perfil)
    assert payload_config_motor(c)['configuracion']['perfil_calculo_contagio']==perfil
    assert payload_config_motor(c)['configuracion']['modo_ejecucion']=='SERVIDOR'


def test_mvp_normaliza_pesos_validos_a_los_predeterminados():
    c=configurar(w_factor_sanitario=D('.2'),w_factor_ambiental=D('.5'),w_factor_densidad=D('.3'))
    assert (c.w_factor_sanitario,c.w_factor_ambiental,c.w_factor_densidad)==(D('.5'),D('.3'),D('.2'))


@pytest.mark.parametrize('cambios,codigo',[
    ({'perfil_calculo_contagio':'OTRO'},'PERFIL_CALCULO_CONTAGIO_INVALIDO'),
    ({'modo_ejecucion':'MVP'},'MODO_EJECUCION_INVALIDO'),
    ({'modo_ejecucion':'EDGE'},'MODO_EDGE_SIN_NODOS'),
    ({'w_factor_sanitario':D('-.1'),'w_factor_ambiental':D('.9')},'PESOS_CONTAGIO_INVALIDOS'),
    ({'w_factor_sanitario':D('.9')},'PESOS_CONTAGIO_INVALIDOS'),
    ({'umbral_riesgo_alto':None},'UMBRALES_REQUERIDOS'),
])
def test_mvp_no_omite_validaciones_de_configuracion(cambios,codigo):
    perfil=cambios.get('perfil_calculo_contagio','MVP')
    cambios={k:v for k,v in cambios.items() if k!='perfil_calculo_contagio'}
    with pytest.raises(BusinessRuleError) as exc:configurar(perfil,**cambios)
    assert exc.value.code==codigo


@pytest.mark.parametrize('tipo',['MODELO_AVES','MODELO_ESPECIES_GRANDES'])
def test_mvp_solo_se_admite_para_contagio(tipo):
    with pytest.raises(BusinessRuleError) as exc:configurar(tipo_modelo=tipo)
    assert exc.value.code=='PERFIL_MVP_NO_APLICA'


AHORA=datetime(2026,10,30,18,tzinfo=timezone.utc)


@pytest.fixture
def reloj(monkeypatch):
    from src.prediction.application.use_cases.riesgo_contagio import estimar_riesgo_contagio_use_case as modulo
    instante=[AHORA]
    class Reloj(datetime):
        @classmethod
        def now(cls,tz=None):return instante[0]
    monkeypatch.setattr(modulo,'datetime',Reloj)
    return instante


def entrada(enfermos=4):
    from src.prediction.infrastructure.dto.estimar_riesgo_contagio_dto import EstimarRiesgoContagioDTO
    return EstimarRiesgoContagioDTO(id_lote=1,total_activos_lote=20,
        salidas_rf66=[dict(id_activo_biologico=1,probabilidad_riesgo_alto='.9' if n<enfermos else '.1',fecha_inferencia=AHORA) for n in range(20)],
        variables_ambientales=dict(temperatura='37.5',humedad_relativa='92.5',fecha_captura=AHORA),densidad_poblacional='8')


def caso(perfil='MVP',**config):
    return _use_case(_Resultados(),config=_config(perfil_calculo_contagio=perfil,**config))


def test_dos_ejecuciones_identicas_mvp_recalculan_a_los_dos_segundos(reloj):
    uc,alerta,auditoria=caso(w_factor_sanitario=D('.1'),w_factor_ambiental=D('.1'),w_factor_densidad=D('.8'))
    primero=uc.execute(entrada(),1,3)
    uc.resultado_repo.anteriores=[primero]
    reloj[0]+=timedelta(seconds=2)
    segundo=uc.execute(entrada(),1,3)
    assert primero.probabilidad_contagio==segundo.probabilidad_contagio==D('.5225')
    assert segundo.pesos_aplicados=={'fs':D('.500'),'fa':D('.300'),'fd':D('.200')}
    assert segundo.id_resultado_contagio!=primero.id_resultado_contagio
    assert not primero.desde_cache and not segundo.desde_cache
    assert segundo.perfil_calculo_contagio=='MVP'
    assert len(uc.resultado_repo.guardados)==2 and auditoria.eventos==['RIESGO_CONTAGIO_CALCULADO']*2
    assert alerta.emitidas==0


def test_estandar_conserva_pesos_personalizados_y_cache(reloj):
    uc,_,auditoria=caso('ESTANDAR',w_factor_sanitario=D('.4'),w_factor_ambiental=D('.4'))
    primero=uc.execute(entrada(),1,3)
    uc.resultado_repo.anteriores=[primero]
    reloj[0]+=timedelta(seconds=2)
    segundo=uc.execute(entrada(),1,3)
    assert segundo.desde_cache and segundo.id_resultado_contagio==primero.id_resultado_contagio
    assert segundo.probabilidad_contagio==D('.5900')
    assert len(auditoria.eventos)==1


def test_cambio_de_perfil_no_reutiliza_cache_del_perfil_anterior(reloj):
    uc,_,_=caso('ESTANDAR')
    primero=uc.execute(entrada(),1,3)
    uc.resultado_repo.anteriores=[primero]
    reloj[0]+=timedelta(seconds=1)
    uc.config_repo.obtener_por_tipo=lambda t:_config(perfil_calculo_contagio='MVP')
    segundo=uc.execute(entrada(),1,3)
    uc.resultado_repo.anteriores=[segundo,primero]
    uc.config_repo.obtener_por_tipo=lambda t:_config(perfil_calculo_contagio='ESTANDAR')
    tercero=uc.execute(entrada(),1,3)
    assert len(uc.resultado_repo.guardados)==3 and not tercero.desde_cache
    assert [r.perfil_calculo_contagio for r in uc.resultado_repo.guardados]==['ESTANDAR','MVP','ESTANDAR']


@pytest.mark.parametrize('defecto',['sensores','inferencias_obsoletas'])
def test_mvp_conserva_rechazo_de_datos_obligatorios_y_audita_perfil(reloj,defecto):
    uc,alerta,auditoria=caso()
    eventos=[]
    auditoria.registrar=lambda **kw:eventos.append(kw)
    dto=entrada()
    if defecto=='sensores':dto.porcentaje_sensores_activos=D('40')
    else:
        for s in dto.salidas_rf66:s.fecha_inferencia=AHORA-timedelta(minutes=31)
    with pytest.raises(BusinessRuleError) as exc:uc.execute(dto,1,3)
    assert exc.value.code=='ERROR_DATOS_INSUFICIENTES'
    assert eventos[0]['payload_evento']['perfil_calculo_contagio']=='MVP'
    assert not uc.resultado_repo.guardados and alerta.emitidas==0


def test_mvp_sin_ambiente_conserva_degradacion_y_ajuste_proporcional(reloj):
    uc,alerta,_=caso()
    dto=entrada(16)
    dto.variables_ambientales=None
    r=uc.execute(dto,1,3)
    assert r.perfil_calculo_contagio=='MVP' and r.confianza_baja and r.modo_ejecucion=='DEGRADADO'
    assert r.factor_ambiental is None and r.pesos_aplicados['fa']==0 and alerta.emitidas==0


def test_mvp_alto_conserva_alertas_y_auditoria_de_pesos(reloj):
    uc,alerta,auditoria=caso()
    ev=[]
    auditoria.registrar=lambda **kw:ev.append(kw)
    r=uc.execute(entrada(16),1,3)
    assert r.nivel_texto=='ALTO' and alerta.emitidas==1
    assert ev[0]['payload_evento']['perfil_calculo_contagio']=='MVP'
    assert ev[0]['payload_evento']['pesos_aplicados']=={'fs':'0.500','fa':'0.300','fd':'0.200'}


def test_default_de_dto_y_entidad_conserva_estandar():
    from src.prediction.infrastructure.dto.configurar_motor_dto import ConfigurarMotorDTO
    c=_configurar(tipo_modelo='MODELO_RIESGO_CONTAGIO',umbral_riesgo_alto=D('.7'),umbral_alerta_critica=D('.8'))
    assert c.perfil_calculo_contagio=='ESTANDAR'
    assert ConfigurarMotorDTO.model_json_schema()['properties']['perfil_calculo_contagio']['default']=='ESTANDAR'
