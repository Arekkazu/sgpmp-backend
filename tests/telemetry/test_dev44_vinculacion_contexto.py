# | Fecha      | Nombre  | Que se hizo |
# |------------|---------|-------------|
# | 2026-10-22 | Leandro | DEV-44 RF-61: estados, causas, avisos y rollback |
from datetime import datetime,timezone,timedelta
from unittest.mock import Mock
import pytest

from src.shared.errors import BusinessRuleError,ServiceUnavailableError
from src.telemetry.domain.entities.vinculacion_lectura import VinculacionLectura
from src.telemetry.domain.repositories.activo_biologico_dependency_port import ActivoBiologicoInfo
from src.telemetry.application.use_cases.infraestructura.vincular_lectura_activo_use_case import VincularLecturaActivoUseCase
from src.telemetry.application.use_cases.infraestructura.procesar_avisos_vinculacion_use_case import ProcesarAvisosVinculacionUseCase
from src.telemetry.application.use_cases.infraestructura.evidencia_vinculacion import registrar_evidencia
from src.telemetry.domain.entities.evento_auditoria_iot import ClasificacionRegistro


def vinculo(**cambios):
    datos=dict(id_vinculacion_lectura=4,id_telemetria=8,modelo_manejo='INDIVIDUAL',id_activo_biologico=None,
        id_infraestructura=3,fecha_inicio_vinculacion=datetime.now(timezone.utc)-timedelta(minutes=2),
        fecha_fin_vinculacion=None,mecanismo_vinculacion='AUTOMATICA',estado_vinculacion='PENDIENTE_REVISION',
        id_usuario=None,motivo_correccion=None,id_vinculacion_reemplazada=None,fecha_creacion=datetime.now(timezone.utc),
        contexto_activo={'candidatos':[2,3]})
    return VinculacionLectura(**(datos|cambios))


def construir(activos,areas=(3,),directos=()):
    db,repo,port=Mock(),Mock(),Mock()
    repo.vigente.return_value=None
    repo.ultima.return_value=None
    repo.contexto_lectura.return_value={'areas':list(areas),'activos_directos':list(directos),'id_sensor':1,'id_dispositivo_iot':2}
    repo.guardar.side_effect=lambda v:v
    port.obtener_activos_en_momento.return_value=activos
    port.obtener_contexto.return_value={'edad_dias':10,'peso_referencia':None}
    port.historial_inconsistente.return_value=False
    return VincularLecturaActivoUseCase(db,repo,port)


@pytest.mark.parametrize('modelo',['INDIVIDUAL','POBLACIONAL'])
def test_candidato_unico_confirmado_con_snapshot(modelo):
    uc=construir([ActivoBiologicoInfo(9,modelo)])
    captura=datetime.now(timezone.utc)
    v=uc.execute(8,3,captura)
    assert (v.estado_vinculacion,v.id_activo_biologico,v.modelo_manejo)==('CONFIRMADA',9,modelo)
    assert v.contexto_activo['edad_dias']==10 and v.causa is None
    uc.activo_port.obtener_contexto.assert_called_once_with(9,captura)


@pytest.mark.parametrize('areas,causa',[((),'CONFIGURACION_INCOMPLETA'),((3,),'SIN_ACTIVOS_EN_ESTRUCTURA'),((3,4),'CONFIGURACION_INCOMPLETA')])
def test_causas_no_se_confunden(areas,causa):
    uc=construir([],areas=areas)
    v=uc.execute(8,3,datetime.now(timezone.utc))
    assert v.estado_vinculacion=='SIN_VINCULAR' and v.causa==causa
    if causa=='CONFIGURACION_INCOMPLETA':uc.activo_port.obtener_activos_en_momento.assert_not_called()


def test_ambiguedad_no_se_resuelve_por_orden():
    uc=construir([ActivoBiologicoInfo(9,'INDIVIDUAL'),ActivoBiologicoInfo(2,'INDIVIDUAL')])
    v=uc.execute(8,3,datetime.now(timezone.utc))
    assert v.estado_vinculacion=='PENDIENTE_REVISION' and v.id_activo_biologico is None
    assert v.contexto_activo['candidatos']==[9,2]


def test_asociacion_directa_resuelve_solo_si_el_candidato_es_elegible():
    uc=construir([ActivoBiologicoInfo(9,'INDIVIDUAL'),ActivoBiologicoInfo(2,'INDIVIDUAL')],directos=[2])
    assert uc.execute(8,3,datetime.now(timezone.utc)).id_activo_biologico==2


def test_modelos_distintos_no_usan_el_primero():
    uc=construir([ActivoBiologicoInfo(9,'INDIVIDUAL'),ActivoBiologicoInfo(2,'POBLACIONAL')])
    with pytest.raises(ServiceUnavailableError):uc.execute(8,3,datetime.now(timezone.utc))
    uc.vinculacion_repo.guardar.assert_not_called()
    uc.db.rollback.assert_called_once()


def test_reintento_no_crea_otro_vinculo():
    uc=construir([]);previo=vinculo()
    uc.vinculacion_repo.ultima.return_value=previo
    assert uc.execute(8,3,datetime.now(timezone.utc)) is previo
    uc.vinculacion_repo.guardar.assert_not_called()
    uc.activo_port.obtener_activos_en_momento.assert_not_called()


def test_error_tecnico_no_se_convierte_en_causa():
    uc=construir([]);uc.activo_port.obtener_activos_en_momento.side_effect=RuntimeError('BD no disponible')
    with pytest.raises(RuntimeError):uc.execute(8,3,datetime.now(timezone.utc))
    uc.vinculacion_repo.guardar.assert_not_called()
    uc.db.rollback.assert_called_once()


def test_falta_total_de_estructura_no_inventa_fk():
    uc=construir([],areas=())
    with pytest.raises(ServiceUnavailableError):uc.execute(8,None,datetime.now(timezone.utc))
    uc.vinculacion_repo.guardar.assert_not_called()


@pytest.mark.parametrize('estado',['AMBIGUA','SIN_VINCULAR','PENDIENTE_REVISION'])
def test_pendientes_resolubles(estado):
    v=vinculo(estado_vinculacion=estado,causa='CONFIGURACION_INCOMPLETA')
    v.resolver(3,7)
    assert v.estado_vinculacion=='CONFIRMADA' and v.causa is None


@pytest.mark.parametrize('estado',['CONFIRMADA','SUPERADA','VINCULADA','CORREGIDA'])
def test_no_resuelve_terminal_ni_estado_heredado(estado):
    with pytest.raises(BusinessRuleError):vinculo(estado_vinculacion=estado).resolver(3,7)


def test_periodo_cerrado_no_se_resuelve():
    with pytest.raises(BusinessRuleError):vinculo(fecha_fin_vinculacion=datetime.now(timezone.utc)).resolver(3,7)


@pytest.mark.parametrize('causa,estado,metodo,administradores',[
    ('CONFIGURACION_INCOMPLETA','SIN_VINCULAR','configuracion_incompleta',True),
    (None,'PENDIENTE_REVISION','ambiguedad',False)])
def test_aviso_clave_estable_y_destinatarios(causa,estado,metodo,administradores):
    repo,avisos,dest=Mock(),Mock(),Mock()
    repo.vigente.return_value=vinculo(causa=causa,estado_vinculacion=estado)
    dest.obtener.return_value=[7]
    getattr(avisos,metodo).return_value=True
    uc=ProcesarAvisosVinculacionUseCase(repo,avisos,dest)
    uc.execute(8);uc.execute(8)
    llamadas=getattr(avisos,metodo).call_args_list
    assert llamadas[0].kwargs==llamadas[1].kwargs and llamadas[0].kwargs['destinatarios']==[7]
    dest.obtener.assert_called_with(3,administradores=administradores)


@pytest.mark.parametrize('resultado',[False,None,1])
def test_canal_sin_confirmacion_no_simula_entrega(resultado):
    repo,avisos,dest=Mock(),Mock(),Mock()
    repo.vigente.return_value=vinculo();dest.obtener.return_value=[7]
    avisos.ambiguedad.return_value=resultado
    with pytest.raises(ServiceUnavailableError):ProcesarAvisosVinculacionUseCase(repo,avisos,dest).execute(8)


def test_sin_contrato_de_avisos_permanece_pendiente():
    repo=Mock();repo.vigente.return_value=vinculo()
    with pytest.raises(ServiceUnavailableError) as error:ProcesarAvisosVinculacionUseCase(repo).execute(8)
    assert error.value.code=='AVISO_VINCULACION_NO_DISPONIBLE'


def test_sin_destinatarios_no_se_envia():
    repo,avisos,dest=Mock(),Mock(),Mock()
    repo.vigente.return_value=vinculo();dest.obtener.return_value=[]
    with pytest.raises(ServiceUnavailableError):ProcesarAvisosVinculacionUseCase(repo,avisos,dest).execute(8)
    avisos.ambiguedad.assert_not_called()


@pytest.mark.parametrize('v',[None,vinculo(estado_vinculacion='CONFIRMADA'),vinculo(estado_vinculacion='SIN_VINCULAR',causa='SIN_ACTIVOS_EN_ESTRUCTURA')])
def test_no_notifica_cuando_no_corresponde(v):
    repo=Mock();repo.vigente.return_value=v
    ProcesarAvisosVinculacionUseCase(repo).execute(8)


def test_evidencia_rf61_nic41_y_fallo_no_silenciado():
    repo=Mock();repo.registrar.side_effect=lambda e:e
    with pytest.raises(RuntimeError):registrar_evidencia(repo,'SIN_VINCULAR',4,{'causa':'CONFIGURACION_INCOMPLETA'})
    evento=repo.registrar.call_args.args[0]
    assert evento.hash_integridad and evento.clasificacion_registro==ClasificacionRegistro.NIC41


@pytest.mark.parametrize('nombre',['resolver','corregir'])
def test_mutacion_sin_fuente_historica_falla_sin_actualizar(nombre):
    from importlib import import_module
    modulo=import_module(f'src.telemetry.application.use_cases.infraestructura.{nombre}_vinculacion_use_case')
    dto_modulo=import_module(f'src.telemetry.infrastructure.dto.{nombre}_vinculacion_dto')
    clase=getattr(modulo,nombre.capitalize()+'VinculacionUseCase')
    dto_clase=getattr(dto_modulo,nombre.capitalize()+'VinculacionDTO')
    db,repo=Mock(),Mock()
    repo.obtener_por_id.return_value=vinculo()
    datos={'id_activo_biologico':3,'modelo_manejo':'INDIVIDUAL'}
    if nombre=='corregir':datos['motivo']='Correccion DEV44'
    with pytest.raises(ServiceUnavailableError):clase(db,repo).execute(4,dto_clase(**datos),7)
    repo.actualizar.assert_not_called();repo.guardar.assert_not_called();db.rollback.assert_called_once()


def test_clasificacion_historica_no_reabre_periodo_superado():
    from src.telemetry.application.use_cases.ingesta.procesar_lectura_confirmada_use_case import ProcesarLecturaConfirmadaUseCase
    from types import SimpleNamespace
    lecturas=Mock();lecturas.vinculacion.return_value=None
    lecturas.vinculacion_historica.return_value={'id_activo_biologico':9}
    lecturas.ultima_lectura_valida.return_value=SimpleNamespace(id_telemetria=8)
    reclasificar=Mock()
    ProcesarLecturaConfirmadaUseCase(lecturas,Mock(),Mock(),reclasificar).clasificar_lectura(8)
    reclasificar.execute.assert_called_once_with(8,9)
    lecturas.vinculacion_historica.assert_called_once_with(8)
