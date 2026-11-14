# | Fecha      | Nombre  | Que se hizo                                      |
# |------------|---------|--------------------------------------------------|
# | 2026-10-21 | Leandro | DEV-27 RF-60: prueba politica dinamica y cadena    |
# | 2026-10-22 | Leandro | DEV-42 RF-60: configura lectura bloqueada en doble de prueba |
# | 2026-10-25 | Arekkazu | USAB-M03 M3-12 RF-60: firmware con prefijo v y "pi-test" no comparable |
# | 2026-10-26 | Arekkazu | FW-06 RF-60: casos SemVer 2.0 y hash de commit no comparable |
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.configuration.domain.entities.parametro_mlops import ParametroMLOps
from src.configuration.domain.entities.parametros_heartbeat import (
    BATERIA_AVISO, BATERIA_CRITICA, COBERTURA, DURACION, FIRMWARE, INACTIVIDAD,
    INTERVALO_CAMARA, INTERVALOS_TIPO, LATENCIA, MARGEN, RSSI, SNR,
    TEMPERATURA_CRITICA, TEMPERATURA_MAXIMA, VENTANAS, validar_heartbeat_configurado,
)
from src.configuration.application.use_cases.configuracion_global.configurar_parametros_mlops_use_case import ConfigurarParametrosMLOpsUseCase
from src.configuration.application.use_cases.configuracion.validar_cadena_heartbeat import validar_cadena_heartbeat
from src.shared.errors import BusinessRuleError, ServiceUnavailableError, ValidationError
from src.telemetry.application.use_cases.infraestructura.evaluar_estado_dispositivos_use_case import EvaluarEstadoDispositivosUseCase
from src.telemetry.application.use_cases.infraestructura.recibir_heartbeat_use_case import ProcesarHeartbeatPersistidoUseCase
from src.telemetry.domain.entities.estado_dispositivo_iot import EstadoDispositivoIoT
from src.telemetry.domain.repositories.parametros_heartbeat_port import ParametrosComunicacionHeartbeat
from src.telemetry.infrastructure.adapters.parametros_heartbeat_mlops_adapter import ParametrosHeartbeatMLOpsAdapter, DiagnosticoHeartbeatMLOpsAdapter


def valores(**cambios):
    # Valores exclusivamente de prueba; no son defaults normativos.
    datos = {INTERVALO_CAMARA: 120, INTERVALOS_TIPO: {'SENSOR': 60}, MARGEN: 300, INACTIVIDAD: 3600,
        BATERIA_AVISO: 30, BATERIA_CRITICA: 10, RSSI: -100, SNR: -10,
        FIRMWARE: '1.9.0', TEMPERATURA_MAXIMA: 40, TEMPERATURA_CRITICA: 50,
        VENTANAS: 3, COBERTURA: .30, DURACION: 60, LATENCIA: 80}
    datos.update(cambios)
    return {nombre: ParametroMLOps(nombre, valor) for nombre, valor in datos.items()}


def repo(datos):
    r = Mock()
    r.obtener.side_effect = lambda nombres: {n: datos[n] for n in nombres if n in datos}
    return r


def configuracion():
    return SimpleNamespace(obtener_activo=lambda: SimpleNamespace(
        frecuencia_muestreo=SimpleNamespace(valor=10), heartbeat=SimpleNamespace(valor=20)))


@pytest.mark.parametrize('clave,valor', [(INTERVALO_CAMARA,29), (INTERVALO_CAMARA,601),
    (VENTANAS,0),(VENTANAS,21),(VENTANAS,1.5),(COBERTURA,.04),(COBERTURA,.91),
    (DURACION,9),(DURACION,301),(LATENCIA,49),(LATENCIA,96), (MARGEN,0),
    (INACTIVIDAD,0),(RSSI,float('inf')),(BATERIA_AVISO,True),(BATERIA_CRITICA,-1),
    (TEMPERATURA_CRITICA,39), (BATERIA_CRITICA,31), (INTERVALOS_TIPO,{'SENSOR': False}),
    (FIRMWARE,''), (FIRMWARE,{'version':'1.0'})])
def test_parametros_invalidos_se_rechazan_antes_de_guardar(clave, valor):
    r, db = repo(valores()), Mock()
    uc = ConfigurarParametrosMLOpsUseCase(db, r, configuracion())
    with pytest.raises(ValidationError):
        uc.execute({clave: valor}, 1)
    r.guardar.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_called_once()


@pytest.mark.parametrize('frecuencia,umbral,margen', [(3,10,300),(10,9,300),(10,20,299)])
def test_cadena_invalida_es_400_en_validacion_rf18(frecuencia, umbral, margen):
    with pytest.raises(ValidationError) as error:
        validar_cadena_heartbeat(repo(valores(**{MARGEN:margen})), frecuencia, umbral)
    assert error.value.status_code == 400 and error.value.code == 'CADENA_HEARTBEAT_INVALIDA'


def test_cadena_admite_igualdad_y_respeta_minutos_y_segundos():
    validar_cadena_heartbeat(repo(valores()), 4, 4)
    assert validar_heartbeat_configurado(valores(), 10, 20)[MARGEN] == 300


@pytest.mark.parametrize('tiempo,buffer,esperado', [(600,None,'ACTIVO'), (601,'A','BUFFER_ACTIVO'),
    (900,None,None),(901,None,'SIN_SEÑAL'), (4500,None,'SIN_SEÑAL'),
    (4501,None,'INACTIVO'), (99999,'A','BUFFER_ACTIVO')])
def test_algoritmo_respeta_orden_tolerancia_y_limites(tiempo, buffer, esperado):
    estado = EstadoDispositivoIoT(1,1,'DESCONOCIDO',None,None,None,None,None,datetime.now(timezone.utc),None)
    resultado=estado.evaluar_transicion(tiempo,buffer,600,900,4500)
    assert resultado==esperado


def test_mantenimiento_no_es_sobrescrito_por_evaluacion():
    estado=EstadoDispositivoIoT(1,1,'EN_MANTENIMIENTO',None,None,None,None,None,datetime.now(timezone.utc),None)
    assert estado.evaluar_transicion(99999,None,600,900,4500) is None


def test_umbrales_derivan_de_los_valores_y_no_de_constantes():
    p=ParametrosComunicacionHeartbeat(120,600,300,3600,None)
    assert (p.umbral_activo,p.umbral_sin_senal,p.umbral_inactivo)==(600,900,4500)


def test_bateria_y_snr_usan_parametros_releidos():
    datos=valores()
    adapter=ParametrosHeartbeatMLOpsAdapter(Mock())
    adapter.parametros_repo=repo(datos)
    alertas=Mock()
    alertas.buscar_tecnica_activa_dispositivo.return_value=None
    uc=ProcesarHeartbeatPersistidoUseCase(Mock(),alertas,adapter,Mock())
    h=SimpleNamespace(id_heartbeat=1,id_dispositivo_iot=1,nivel_bateria_pct=Decimal(20),
        calidad_senal_rssi=None,calidad_senal_snr=Decimal(-15),fecha_registro=datetime.now(timezone.utc),fecha_recepcion=datetime.now(timezone.utc))
    uc.procesar_alertas(h,1)
    assert {c.args[0].tipo_variable for c in alertas.guardar.call_args_list}=={'BATERIA_BAJA','SEÑAL_DEGRADADA'}
    datos[BATERIA_CRITICA]=ParametroMLOps(BATERIA_CRITICA,25)
    alertas.guardar.reset_mock()
    uc.procesar_alertas(h,1)
    assert ('BATERIA_CRITICA','CRITICO') in [(c.args[0].tipo_variable,c.args[0].severidad) for c in alertas.guardar.call_args_list]


@pytest.mark.parametrize('instalada,minima,anterior',[('1.10.0','1.9.0',False),('1.9.0','1.10.0',True),
    ('1.0','1.0.0',False),('1.0.0','1.0.0',False),
    # M3-12: el prefijo "v" de los tags no impide comparar.
    ('v2.0.1','0.1.0',False),('v0.0.9','0.1.0',True),('V1.0','v1.0.1',True),
    # FW-06: SemVer 2.0; prerelease antes de la versión final y "+metadato" ignorado.
    ('v0.2.0-rc.1','0.2.0',True),('v0.2.0','0.2.0-rc.1',False),('0.2.0-rc.2','0.2.0-rc.10',True),
    ('1.0.0-alpha','1.0.0-alpha.1',True),('1.0.0-alpha.1','1.0.0-alpha.beta',True),('1.0.0-beta.11','1.0.0-rc.1',True),
    ('v0.2.0+3.gabc1234','0.2.0',False),('v0.2.0+dirty','0.2.1',True),('v0.2.0+3.gabc1234','v0.2.0+9.gfff0000',False)])
def test_firmware_numerico_se_compara_por_segmentos(instalada,minima,anterior):
    adapter=DiagnosticoHeartbeatMLOpsAdapter(Mock())
    adapter.parametros_repo=repo(valores(**{FIRMWARE:minima}))
    assert adapter.comparar_firmware(1,instalada).es_anterior is anterior


def test_formato_firmware_no_confirmado_no_produce_comparacion_ficticia():
    adapter=DiagnosticoHeartbeatMLOpsAdapter(Mock())
    adapter.parametros_repo=repo(valores())
    with pytest.raises(BusinessRuleError,match='convención'):
        adapter.comparar_firmware(1,'release-inventada')
    with pytest.raises(BusinessRuleError,match='convención'):
        adapter.comparar_firmware(1,'pi-test')
    # Hash de commit sin tag: no tiene orden.
    with pytest.raises(BusinessRuleError,match='convención'):
        adapter.comparar_firmware(1,'f889231')


def test_parametro_ausente_no_tiene_fallback():
    adapter=ParametrosHeartbeatMLOpsAdapter(Mock())
    adapter.parametros_repo=repo({})
    with pytest.raises(ServiceUnavailableError,match='configurado'):
        adapter.obtener()


def test_inactivo_genera_critico_aunque_exista_periodo_previo():
    db,estados,alertas,politica=Mock(),Mock(),Mock(),Mock()
    ahora=datetime.now(timezone.utc)
    estado=EstadoDispositivoIoT(1,1,'SIN_SEÑAL',ahora-timedelta(hours=3),None,None,None,None,ahora,None)
    estados.listar_activos.return_value=[estado]
    estados.bloquear_por_dispositivo.return_value=estado
    alertas.buscar_tecnica_activa_dispositivo.return_value=None
    politica.obtener_comunicacion.return_value=ParametrosComunicacionHeartbeat(120,600,300,3600,None)
    historial,periodos,hist_alertas=Mock(),Mock(),Mock()
    uc=EvaluarEstadoDispositivosUseCase(db,estados,historial,periodos,alertas,hist_alertas,politica)
    assert uc.execute()==1
    alerta=alertas.guardar.call_args.args[0]
    assert alerta.tipo_variable=='DISPOSITIVO_INACTIVO' and alerta.severidad=='CRITICO'
    historial.registrar.assert_not_called()
    hist_alertas.registrar.assert_not_called()


def test_siembra_conserva_existentes_y_no_guarda_sin_aplicar():
    datos=valores()
    r,db=repo(datos),Mock()
    uc=ConfigurarParametrosMLOpsUseCase(db,r,configuracion())
    assert uc.sembrar({INTERVALO_CAMARA:130},1)=={INTERVALO_CAMARA:'conservado'}
    r.guardar.assert_not_called()
    db.rollback.assert_called_once()


def test_siembra_solo_actualiza_nombres_explicitamente_autorizados():
    r,db=repo(valores()),Mock()
    uc=ConfigurarParametrosMLOpsUseCase(db,r,configuracion())
    acciones=uc.sembrar({INTERVALO_CAMARA:130,VENTANAS:4},1,aplicar=True,actualizar_existentes={VENTANAS})
    assert acciones=={INTERVALO_CAMARA:'conservado',VENTANAS:'actualizado'}
    assert [p.nombre for p in r.guardar.call_args.args[0]]==[VENTANAS]
