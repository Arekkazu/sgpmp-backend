from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from pydantic import ValidationError as ErrorDTO

from src.shared.errors import AppError
from src.telemetry.application.use_cases.ingesta.ingerir_observaciones_vision_use_case import IngerirObservacionesVisionUseCase
from src.telemetry.infrastructure.dto.observacion_vision_d4_dto import ObservacionVisionD4DTO


def sobre(**cambios):
    fin=datetime.now(timezone.utc)-timedelta(minutes=1)
    return dict(serial='CAM-D4',area_id=2,ventana_inicio=(fin-timedelta(minutes=1)).isoformat(),ventana_fin=fin.isoformat(),
        componentes=dict(densidad_actividad=.65,dispersion_espacial=2.4,tasa_movimiento=1.8),
        calidad=dict(cobertura_ventana=.95,n_tracks=19,n_tracks_perdidos=1,fps_efectivo=24,estado_calibracion='CALIBRADA'),
        version_cascada=dict(detector='v-detector',seguimiento='v-seguimiento',metricas='v-metricas',anomalias='v-anomalias'))|cambios


def construir(**camara):
    identidad=Mock()
    identidad.obtener_camara_por_serial.return_value=SimpleNamespace(**(dict(id_dispositivo_iot=12,id_infraestructura=2,es_activo=True,es_camara=True,fps_nominal=25)|camara))
    repo=Mock();repo.fechas_existentes.return_value=set()
    def guardar(o):o.id_observacion_vision=1;return o
    repo.guardar.side_effect=guardar
    return IngerirObservacionesVisionUseCase(Mock(),repo,identidad)


@pytest.mark.parametrize('campo',['serial','area_id','ventana_inicio','ventana_fin','componentes','calidad','version_cascada'])
def test_sobre_incompleto_no_se_completa_por_defecto(campo):
    datos=sobre();datos.pop(campo)
    with pytest.raises(ErrorDTO):ObservacionVisionD4DTO(**datos)


@pytest.mark.parametrize('campo,valor',[('densidad_actividad',-0.0001),('densidad_actividad',1.0001),
    ('dispersion_espacial',-1),('tasa_movimiento',-1),('tasa_movimiento',float('nan')),
    ('dispersion_espacial',float('inf'))])
def test_componentes_fuera_de_dominio_se_rechazan(campo,valor):
    datos=sobre();datos['componentes'][campo]=valor
    with pytest.raises(ErrorDTO):ObservacionVisionD4DTO(**datos)


@pytest.mark.parametrize('campo',['densidad_actividad','dispersion_espacial','tasa_movimiento'])
def test_todos_los_componentes_son_obligatorios(campo):
    datos=sobre();datos['componentes'].pop(campo)
    with pytest.raises(ErrorDTO):ObservacionVisionD4DTO(**datos)


@pytest.mark.parametrize('bloque,campo,valor',[
    ('calidad','n_tracks',True),('calidad','n_tracks',1.5),('calidad','n_tracks_perdidos',-1),
    ('calidad','fps_efectivo',-1),('calidad','cobertura_ventana',1.1),
    ('calidad','estado_calibracion','OTRO'),('version_cascada','detector',''),
    ('calidad','apto_para_ia',True),('componentes','otro',1),('version_cascada','otro','v1')])
def test_estructura_calidad_y_versiones_no_admite_decisiones_del_cliente(bloque,campo,valor):
    datos=sobre();datos[bloque][campo]=valor
    with pytest.raises(ErrorDTO):ObservacionVisionD4DTO(**datos)


@pytest.mark.parametrize('campo',['apto_para_ia','es_apto_para_ia','indice_calidad','clasificacion_calidad','n_individuos_observados','origen','tipo_dato'])
def test_campos_no_soportados_no_se_ignoran_silenciosamente(campo):
    with pytest.raises(ErrorDTO):ObservacionVisionD4DTO(**sobre(**{campo:True}))


@pytest.mark.parametrize('cambio',['sin-zona','igual','invertido'])
def test_ventana_requiere_zona_y_orden(cambio):
    datos=sobre()
    if cambio=='sin-zona':datos['ventana_inicio']=datetime.now().isoformat()
    elif cambio=='igual':datos['ventana_inicio']=datos['ventana_fin']
    else:datos['ventana_inicio']=(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()
    with pytest.raises(ErrorDTO):ObservacionVisionD4DTO(**datos)


def test_aliases_equivalentes_se_documentan_sin_completar_otro_sobre():
    datos=sobre();datos['dispositivo_serial']=datos.pop('serial');datos['indicadores_calidad']=datos.pop('calidad')
    assert ObservacionVisionD4DTO(**datos).serial=='CAM-D4'


def test_aliases_contradictorios_se_rechazan():
    with pytest.raises(ErrorDTO):ObservacionVisionD4DTO(**sobre(dispositivo_serial='OTRA'))


def test_d4_conserva_ventana_versiones_y_calculo_backend_heredado():
    dto=ObservacionVisionD4DTO(**sobre());uc=construir()
    r=uc.execute(dto);o=r.observaciones[0]
    assert r.total==1 and r.duplicados==0
    assert o.fecha_observacion==dto.ventana_fin and o.fecha_inicio_ventana==dto.ventana_inicio
    assert o.version_cascada==dto.version_cascada.model_dump()
    assert o.vector=={'densidad_actividad':.65,'dispersion_espacial':2.4,'tasa_movimiento':1.8}
    assert o.indice_calidad==97 and o.es_apto_para_ia and not o.es_apto_para_nic41
    uc.dispositivo_port.obtener_camara_por_serial.assert_called_once_with('CAM-D4')


def test_baja_calidad_no_se_vuelve_apta_por_recibir_el_sobre():
    datos=sobre();datos['calidad'].update(cobertura_ventana=0,n_tracks=0,n_tracks_perdidos=5,fps_efectivo=0,estado_calibracion='SIN_DETECCION')
    o=construir().execute(ObservacionVisionD4DTO(**datos)).observaciones[0]
    assert o.indice_calidad==0 and not o.es_apto_para_ia


@pytest.mark.parametrize('camara,codigo',[(dict(es_activo=False),'ERROR_AUTENTICACION'),
    (dict(es_camara=False),'DISPOSITIVO_NO_ES_CAMARA'),(dict(id_infraestructura=7),'AREA_NO_COINCIDE')])
def test_identidad_y_area_rechazan_antes_de_persistir(camara,codigo):
    uc=construir(**camara)
    with pytest.raises(AppError) as e:uc.execute(ObservacionVisionD4DTO(**sobre()))
    assert e.value.code==codigo;uc.repo.guardar.assert_not_called()


def test_ventana_fin_futura_rechaza_sin_persistir():
    uc=construir();datos=sobre(ventana_fin=(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat())
    with pytest.raises(AppError) as e:uc.execute(ObservacionVisionD4DTO(**datos))
    assert e.value.code=='ERROR_TIEMPO' and e.value.field=='ventana_fin'
    uc.repo.guardar.assert_not_called()


def test_duplicado_concurrente_del_repositorio_no_se_cuenta_aceptado():
    uc=construir();uc.repo.guardar.side_effect=None;uc.repo.guardar.return_value=None
    r=uc.execute(ObservacionVisionD4DTO(**sobre()))
    assert r.duplicados==1 and r.observaciones==[]


def test_error_de_persistencia_revierte_y_no_confirma():
    uc=construir();uc.repo.guardar.side_effect=RuntimeError('fallo')
    with pytest.raises(RuntimeError):uc.execute(ObservacionVisionD4DTO(**sobre()))
    uc.db.rollback.assert_called_once();uc.db.commit.assert_not_called()
