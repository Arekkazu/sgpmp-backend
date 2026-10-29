# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-27 | Leandro | INC-M03-127-G27 RF-54/60: validar prioridad del buffer, vaciado confirmado y fuente vigente compartida. |
from datetime import datetime,timedelta,timezone
from types import SimpleNamespace
from unittest.mock import Mock
import pytest

from src.telemetry.domain.entities.estado_dispositivo_iot import EstadoDispositivoIoT
from src.telemetry.domain.repositories.parametros_heartbeat_port import ParametrosComunicacionHeartbeat
from src.telemetry.application.use_cases.infraestructura.evaluar_estado_dispositivos_use_case import EvaluarEstadoDispositivosUseCase
from src.telemetry.application.use_cases.infraestructura.recibir_heartbeat_use_case import ProcesarHeartbeatPersistidoUseCase
from src.telemetry.infrastructure.adapters.parametros_heartbeat_mlops_adapter import ParametrosHeartbeatMLOpsAdapter
from src.configuration.domain.entities.parametro_mlops import ParametroMLOps
from src.configuration.domain.entities.parametros_heartbeat import INTERVALOS_TIPO,MARGEN,INACTIVIDAD


def estado(actual='BUFFER_ACTIVO'):
    ahora=datetime.now(timezone.utc)
    return EstadoDispositivoIoT(1,1,actual,ahora-timedelta(seconds=3),1,0,None,None,ahora,None)


def parametros(buffer='A',pendientes=37):
    return ParametrosComunicacionHeartbeat(60,600,300,3600,buffer,datos_pendientes_buffer=pendientes)


def test_buffer_reportado_no_se_libera_por_contacto_reciente():
    assert estado().evaluar_transicion(3,'A',600,900,4500) is None


@pytest.mark.parametrize('tiempo',[0,3,600,601,901,4501,99999])
@pytest.mark.parametrize('buffer',['A','L'])
def test_pendientes_priorizan_buffer_en_todos_los_intervalos(tiempo,buffer):
    assert estado().evaluar_transicion(tiempo,buffer,600,900,4500,datos_pendientes_buffer=37) is None
    assert estado('ACTIVO').evaluar_transicion(tiempo,buffer,600,900,4500,datos_pendientes_buffer=37)=='BUFFER_ACTIVO'


@pytest.mark.parametrize('buffer',['I','A','L',None])
def test_reporte_cero_confirma_vaciado_y_permite_activo(buffer):
    assert estado().evaluar_transicion(3,buffer,600,900,4500,datos_pendientes_buffer=0)=='ACTIVO'


def test_sin_cantidad_no_se_inventa_vaciado():
    assert estado().evaluar_transicion(3,None,600,900,4500) is None


def test_desactivar_flag_sin_vaciar_no_libera_un_buffer_pendiente():
    assert estado().evaluar_transicion(3,'I',600,900,4500,datos_pendientes_buffer=37) is None


@pytest.mark.parametrize('tiempo,esperado',[(3,'ACTIVO'),(600,'ACTIVO'),(900,None),(901,'SIN_SEÑAL'),(4501,'INACTIVO')])
def test_sin_buffer_se_conservan_umbrales_y_tolerancia(tiempo,esperado):
    assert estado('DESCONOCIDO').evaluar_transicion(tiempo,'I',600,900,4500,datos_pendientes_buffer=0)==esperado


def test_mantenimiento_tiene_prioridad_sobre_cualquier_reporte():
    assert estado('EN_MANTENIMIENTO').evaluar_transicion(3,'A',600,900,4500,datos_pendientes_buffer=37) is None


def test_ciclos_periodicos_sin_mensaje_no_crean_transiciones_ni_cierre():
    e=estado();db,repo,alertas,periodos,politica=Mock(),Mock(),Mock(),Mock(),Mock()
    repo.obtener_por_dispositivo.return_value=e;repo.bloquear_por_dispositivo.return_value=e
    politica.obtener_comunicacion.return_value=parametros()
    uc=EvaluarEstadoDispositivosUseCase(db,repo,None,periodos,alertas,None,politica)
    assert [uc.execute(1) for _ in range(3)]==[0,0,0]
    assert e.estado_actual=='BUFFER_ACTIVO'
    repo.actualizar.assert_not_called();periodos.cerrar.assert_not_called();alertas.guardar.assert_not_called()


def test_nuevo_reporte_vacio_produce_una_sola_transicion():
    e=estado();db,repo,alertas,periodos,politica=Mock(),Mock(),Mock(),Mock(),Mock()
    repo.obtener_por_dispositivo.return_value=e;repo.bloquear_por_dispositivo.return_value=e
    politica.obtener_comunicacion.return_value=parametros('I',0)
    periodos.obtener_abierto_por_dispositivo.return_value=None
    alertas.listar_conectividad_abierta.return_value=[]
    uc=EvaluarEstadoDispositivosUseCase(db,repo,None,periodos,alertas,None,politica)
    assert [uc.execute(1),uc.execute(1)]==[1,0]
    assert e.estado_actual=='ACTIVO'
    repo.actualizar.assert_called_once()


def test_postcommit_revalida_ultimo_reporte_bajo_bloqueo():
    e=estado('ACTIVO');repo,alertas,periodos,politica=Mock(),Mock(),Mock(),Mock()
    repo.bloquear_por_dispositivo.return_value=e
    politica.obtener_comunicacion.return_value=parametros('A',37)
    uc=ProcesarHeartbeatPersistidoUseCase(repo,alertas,politica,periodos)
    anterior=SimpleNamespace(id_dispositivo_iot=1,estado_local_buffer='I',datos_pendientes_buffer=0)
    uc.procesar_estado(anterior,True)
    assert e.estado_actual=='BUFFER_ACTIVO'
    repo.actualizar.assert_called_once()
    periodos.cerrar.assert_not_called()


def test_heartbeat_historico_no_escribe_estado_actual():
    repo,alertas,periodos,politica=Mock(),Mock(),Mock(),Mock()
    ProcesarHeartbeatPersistidoUseCase(repo,alertas,politica,periodos).procesar_estado(SimpleNamespace(),False)
    repo.bloquear_por_dispositivo.assert_not_called()


def test_adapter_transporta_cantidad_del_ultimo_reporte():
    db=Mock()
    db.execute.return_value.mappings.return_value.one_or_none.return_value=dict(categoria='SENSOR',
        id_infraestructura=9,ultimo_heartbeat=None,ultima_telemetria=None,primera_telemetria=None,
        buffer='A',datos_pendientes_buffer=37)
    adapter=ParametrosHeartbeatMLOpsAdapter(db)
    adapter.configuracion_repo=Mock()
    adapter.configuracion_repo.obtener_activo.return_value=SimpleNamespace(
        frecuencia_muestreo=SimpleNamespace(valor=10),heartbeat=SimpleNamespace(valor=20))
    adapter.parametros_repo=Mock()
    adapter.parametros_repo.obtener.return_value={n:ParametroMLOps(n,v) for n,v in
        [(INTERVALOS_TIPO,{'SENSOR':60}),(MARGEN,300),(INACTIVIDAD,3600)]}
    p=adapter.obtener_comunicacion(1)
    assert p.estado_local_buffer=='A' and p.datos_pendientes_buffer==37


@pytest.mark.parametrize('fincas',[[],[99]])
def test_estado_fuera_de_finca_no_lee_estado_ni_historial(fincas):
    from src.shared.errors import NotFoundError
    from src.telemetry.application.use_cases.infraestructura.obtener_estado_dispositivo_use_case import ObtenerEstadoDispositivoUseCase
    repo,historial=Mock(),Mock()
    repo.pertenece_a_fincas.return_value=False
    uc=ObtenerEstadoDispositivoUseCase(Mock(),repo,historial)
    with pytest.raises(NotFoundError) as fallo:uc.execute(1,ids_fincas_permitidas=fincas)
    assert fallo.value.code=='ESTADO_DISPOSITIVO_NO_ENCONTRADO'
    repo.obtener_por_dispositivo.assert_not_called();historial.listar_por_dispositivo.assert_not_called()


def test_estado_global_conserva_el_contrato_de_lectura():
    from src.telemetry.application.use_cases.infraestructura.obtener_estado_dispositivo_use_case import ObtenerEstadoDispositivoUseCase
    repo,historial=Mock(),Mock()
    repo.obtener_por_dispositivo.return_value=estado()
    historial.listar_por_dispositivo.return_value=[]
    resultado=ObtenerEstadoDispositivoUseCase(Mock(),repo,historial).execute(1,ids_fincas_permitidas=None)
    assert resultado.estado.estado_actual=='BUFFER_ACTIVO' and resultado.historial==[]
    repo.pertenece_a_fincas.assert_not_called()
