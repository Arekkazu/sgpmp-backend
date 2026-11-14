# | Fecha      | Nombre  | Que se hizo |
# |------------|---------|-------------|
# | 2026-10-22 | Leandro | DEV-28 RF-53/62: oraculo, DTO, configuracion y ventanas |
from dataclasses import replace, FrozenInstanceError
from datetime import datetime,timedelta,timezone
from decimal import Decimal,localcontext,ROUND_DOWN
from unittest.mock import Mock

import pytest
from pydantic import ValidationError as ErrorDTO

from src.shared.errors import ServiceUnavailableError,ValidationError
from src.configuration.domain.entities.parametro_mlops import ParametroMLOps
from src.configuration.domain.entities.parametros_vision import PREDETERMINADOS_VISION,vision_configurada
from src.configuration.domain.entities.parametros_heartbeat import COBERTURA
from src.configuration.application.use_cases.configuracion_global.configurar_parametros_mlops_use_case import ConfigurarParametrosMLOpsUseCase
from src.telemetry.domain.entities.calidad_vision import ParametrosCalidadVision,evaluar_calidad_vision
from src.telemetry.domain.entities.secuencia_vision import VentanaVision,ParametrosVentanasVision,ventanas_sin_deteccion
from src.telemetry.infrastructure.adapters.parametros_vision_mlops_adapter import ParametrosVisionMLOpsAdapter
from src.telemetry.infrastructure.dto.observacion_vision_d4_dto import ObservacionVisionD4DTO

D=Decimal


def politica(**cambios):
    p=ParametrosCalidadVision(D('.40'),D('.35'),D('.25'),D(25),5,D('.70'),D(80),D(40),D('.30'))
    return replace(p,**cambios)


def evaluar(**cambios):
    args=dict(cobertura=D('.95'),fps=D(24),perdidos=1,calibracion='CALIBRADO',parametros=politica(),duracion_seg=D(60))
    args.update(cambios)
    return evaluar_calidad_vision(**args)


def sobre(**cambios):
    fin=datetime.now(timezone.utc)-timedelta(minutes=1)
    return dict(serial='CAMARA',area_id=1,tipo_dato='VECTOR_COMPORTAMIENTO',n_individuos_observados=0,
        origen='TIEMPO_REAL',ventana_inicio=fin-timedelta(seconds=60),ventana_fin=fin,
        componentes=dict(densidad_actividad=.5,dispersion_espacial=1,tasa_movimiento=1),
        calidad=dict(cobertura_ventana=.95,n_tracks_perdidos=1,fps_efectivo=24,estado_calibracion='CALIBRADO'),
        version_cascada=dict(detector='1',seguimiento='1',metricas='1',anomalias='1'))|cambios


@pytest.mark.parametrize('estado,indice,clase,apta,confianza',[
    ('CALIBRADO','91.6','OPTIMA',True,False),
    ('EN_CALIBRACION','64.12','DEGRADADA',True,True),
    ('SIN_LINEA_BASE','0','NO_APTA',False,False)])
def test_oraculo_multiplicativo_y_aptitud(estado,indice,clase,apta,confianza):
    r=evaluar(calibracion=estado)
    assert r.indice==D(indice) and r.clase.value==clase
    assert r.apto_para_ia is apta and r.confianza_baja is confianza
    assert r.apto_para_nic41 is False
    with pytest.raises(FrozenInstanceError):r.apto_para_nic41=True


@pytest.mark.parametrize('indice,clase',[('0','NO_APTA'),('39.99','NO_APTA'),('40','DEGRADADA'),
    ('40.01','DEGRADADA'),('79.99','DEGRADADA'),('80','OPTIMA'),('80.01','OPTIMA'),('100','OPTIMA')])
def test_tramos_no_redondean_ni_truncan_antes_de_clasificar(indice,clase):
    r=evaluar(cobertura=D(indice)/100,parametros=politica(w1=D(1),w2=D(0),w3=D(0)))
    assert r.indice==D(indice) and r.clase.value==clase


@pytest.mark.parametrize('fps,perdidos,indice',[(50,0,'98'),(25,5,'73'),(25,50,'73'),(0,0,'63'),(10,2,'67')])
def test_factores_proporcionales_y_limitados(fps,perdidos,indice):
    assert evaluar(fps=D(fps),perdidos=perdidos).indice==D(indice)


def test_calculo_no_depende_del_contexto_decimal_del_llamador():
    esperado=evaluar()
    with localcontext() as c:
        c.prec=3;c.rounding=ROUND_DOWN
        obtenido=evaluar()
    assert obtenido==esperado


def test_sin_linea_base_fuerza_no_apta_aunque_umbral_inferior_sea_cero():
    assert not evaluar(calibracion='SIN_LINEA_BASE',parametros=politica(umbral_degradada=D(0))).apto_para_ia


def test_flags_concurrentes_y_conteos_no_recibidos_no_se_inventan():
    r=evaluar(cobertura=D('.1'),fps=D(2),perdidos=9,calibracion='SIN_LINEA_BASE')
    assert set(r.flags_detectados)=={'cobertura_baja','tracking_inestable','fps_insuficiente','sin_linea_base'}
    assert all(f['activo'] for f in r.flags_detectados.values())
    assert r.flags_detectados['cobertura_baja']['frames_procesados'] is None
    assert D(r.flags_detectados['cobertura_baja']['frames_esperados'])==1500
    assert r.parametros_aplicados['factor_calibracion']=='0'


@pytest.mark.parametrize('cambio',[{'cobertura':D('-0.1')},{'cobertura':D('1.1')},{'fps':D(-1)},
    {'fps':D('NaN')},{'cobertura':D('Infinity')},{'perdidos':-1},{'perdidos':True},
    {'duracion_seg':D(0)},{'calibracion':'CALIBRADA'}])
def test_indicadores_invalidos_no_producen_aptitud(cambio):
    with pytest.raises(ValueError):evaluar(**cambio)


@pytest.mark.parametrize('cambio',[{'fps_configurado':D(0)},{'tracks_perdidos_tolerables':0},
    {'w1':D('.41')},{'w1':D('-0.1')},{'umbral_optima':D(40)},{'factor_en_calibracion':D('1.1')},
    {'cobertura_minima':D('.01')},{'tracks_perdidos_tolerables':51}])
def test_politicas_invalidas_no_ocultan_divisiones_por_cero(cambio):
    with pytest.raises(ValueError):politica(**cambio)


@pytest.mark.parametrize('campo',['tipo_dato','n_individuos_observados','origen'])
def test_campos_normativos_son_obligatorios(campo):
    d=sobre();d.pop(campo)
    with pytest.raises(ErrorDTO):ObservacionVisionD4DTO(**d)


@pytest.mark.parametrize('cambio',[{'tipo_dato':'CRUDO'},{'origen':'OTRO'},{'n_individuos_observados':-1},
    {'n_individuos_observados':True},{'n_individuos_observados':1.5},{'origen':None},{'extra':True},
    {'apto_para_ia':True}])
def test_dto_mantiene_extra_forbid_y_dominios(cambio):
    with pytest.raises(ErrorDTO):ObservacionVisionD4DTO(**sobre(**cambio))


def test_individuos_cero_y_tracks_ausentes_no_se_equiparan():
    d=ObservacionVisionD4DTO(**sobre())
    assert d.n_individuos_observados==0 and d.calidad.n_tracks is None
    datos=sobre();datos['calidad']['n_tracks']=17
    assert ObservacionVisionD4DTO(**datos).calidad.n_tracks==17


def valores(**cambios):
    p=PREDETERMINADOS_VISION|{COBERTURA:.30}|cambios
    return {k:ParametroMLOps(k,v) for k,v in p.items()}


def test_adapter_lee_todos_los_parametros_en_una_consulta_sin_cache():
    repo=Mock();repo.obtener.return_value=valores()
    a=ParametrosVisionMLOpsAdapter(repo)
    assert a.obtener(25).w1==D('.4')
    repo.obtener.assert_called_once()
    repo.obtener.return_value=valores(w1=.5,w2=.25,w3=.25)
    assert a.obtener(25).w1==D('.5')


@pytest.mark.parametrize('fps',[None,0,True,-1])
def test_fps_configurado_ausente_no_se_sustituye_por_uno(fps):
    repo=Mock();repo.obtener.return_value=valores()
    with pytest.raises(ServiceUnavailableError):ParametrosVisionMLOpsAdapter(repo).obtener(fps)


def test_configuracion_ausente_no_usa_defaults_de_siembra():
    with pytest.raises(ServiceUnavailableError):vision_configurada({})


@pytest.mark.parametrize('cambio',[{'w1':.5},{'tracks_perdidos_tolerables':0},
    {'umbral_optima':40},{'w1':True}])
def test_administracion_rechaza_snapshot_inconsistente_sin_persistir(cambio):
    repo,db=Mock(),Mock();repo.obtener.return_value=valores()
    with pytest.raises(ValidationError):ConfigurarParametrosMLOpsUseCase(db,repo).execute(cambio,1)
    repo.guardar.assert_not_called();db.rollback.assert_called_once()


def ventanas(coberturas):
    inicio=datetime(2026,10,22,tzinfo=timezone.utc)
    return [VentanaVision(i+1,1,2,inicio+timedelta(seconds=i*60),inicio+timedelta(seconds=(i+1)*60),D(str(c))) for i,c in enumerate(coberturas)]


@pytest.mark.parametrize('coberturas,esperado',[([.2],False),([.2,.1],False),([.2,.1,.1],True),
    ([.1,.5,.1],False),([.1,.3,.1],False),([.1,.29,.1],True),([.4,.4,.4],False)])
def test_consecutividad_por_cobertura_real(coberturas,esperado):
    assert bool(ventanas_sin_deteccion(ventanas(coberturas),ParametrosVentanasVision(3,D('.30'),60))) is esperado


def test_ventanas_desordenadas_se_ordenan_y_reintento_no_incrementa():
    v=ventanas([.1,.1,.1]);p=ParametrosVentanasVision(3,D('.30'),60)
    assert ventanas_sin_deteccion([v[2],v[0],v[1],v[2]],p)==tuple(v)
    assert ventanas_sin_deteccion([v[0],v[0],v[1]],p)==()


@pytest.mark.parametrize('variante',['faltante','otra_camara','otra_area','solapada','duracion'])
def test_brechas_y_camaras_no_forman_consecutividad(variante):
    v=ventanas([.1,.1,.1])
    if variante=='faltante':v[1]=replace(v[1],inicio=v[1].inicio-timedelta(seconds=60),fin=v[1].fin-timedelta(seconds=60))
    elif variante=='otra_camara':v[1]=replace(v[1],camara=2)
    elif variante=='otra_area':v[1]=replace(v[1],area=3)
    elif variante=='solapada':v[1]=replace(v[1],inicio=v[1].inicio+timedelta(seconds=1),fin=v[1].fin+timedelta(seconds=1))
    else:v[1]=replace(v[1],inicio=v[1].inicio+timedelta(seconds=1))
    assert ventanas_sin_deteccion(v,ParametrosVentanasVision(3,D('.30'),60))==()
