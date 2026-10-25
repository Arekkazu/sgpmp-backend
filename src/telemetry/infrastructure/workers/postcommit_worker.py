# | Fecha      | Nombre  | Que se hizo                                      |
# |------------|---------|--------------------------------------------------|
# | 2026-10-21 | Leandro | DEV-27 RF-60: conecta adaptadores reales por etapa |
# | 2026-10-21 | Leandro | DEV-41 RF-53/57: conecta alerta critica al worker |
# | 2026-10-21 | Leandro | DEV-43 RF-62: integra calidad temporal y alertas tecnicas |
# | 2026-10-22 | Leandro | DEV-42 RF-60: recupera conectividad tras telemetria valida |
# | 2026-10-22 | Leandro | DEV-28 RF-60: conecta diagnostico postcommit de vision |
# | 2026-10-22 | Leandro | DEV-44 RF-61: conecta evidencia y reintento de avisos |
# | 2026-10-22 | Leandro | DEV-47 RF-63: conecta auditoria de HTTP y persistencia MQTT |
# | 2026-10-23 | Arekkazu | INTEG RFC-012..016 RF-61: RF61_AVISOS solo con canal de aviso configurado |
"""Composición del procesador B+. No recibe callbacks ni se conecta al broker."""
import asyncio
import logging
import os

from sqlalchemy import text

from src.configuration.infrastructure.repositories.configuracion_global_repository import SqlAlchemyConfiguracionGlobalRepository
from src.prediction.infrastructure.repositories.parametros_mlops_repository import SqlAlchemyParametrosMLOpsRepository
from src.telemetry.infrastructure.repositories.evidencia_fuentes_iot import auditar_lectura, auditar_ingesta, auditar_heartbeat, auditar_transicion
from src.shared.database import engine
from src.telemetry.application.use_cases.calidad.evaluar_calidad_telemetria_use_case import EvaluarCalidadTelemetriaUseCase
from src.telemetry.application.use_cases.calidad.generar_alerta_calidad_use_case import GenerarAlertaCalidadUseCase
from src.telemetry.infrastructure.adapters.contexto_calidad_m09_rf60_adapter import ContextoCalidadM09RF60Adapter
from src.telemetry.application.use_cases.infraestructura.recibir_heartbeat_use_case import ProcesarHeartbeatPersistidoUseCase
from src.telemetry.application.use_cases.infraestructura.evaluar_estado_dispositivos_use_case import EvaluarEstadoDispositivosUseCase
from src.telemetry.application.use_cases.infraestructura.evaluar_diagnostico_heartbeat_use_case import EvaluarDiagnosticoHeartbeatUseCase
from src.telemetry.application.use_cases.infraestructura.vincular_lectura_activo_use_case import VincularLecturaActivoUseCase
from src.telemetry.application.use_cases.infraestructura.procesar_avisos_vinculacion_use_case import ProcesarAvisosVinculacionUseCase
from src.telemetry.infrastructure.adapters.destinatarios_vinculacion_m01_adapter import DestinatariosVinculacionM01Adapter
from src.telemetry.application.use_cases.ingesta.procesar_lectura_confirmada_use_case import ProcesarLecturaConfirmadaUseCase
from src.telemetry.application.use_cases.ingesta.procesar_postcommit_use_case import ProcesarPostcommitUseCase
from src.telemetry.application.use_cases.monitoreo.reclasificar_semaforo_use_case import ReclasificarSemaforoUseCase
from src.telemetry.application.use_cases.alertas.generar_alerta_use_case import GenararAlertaUseCase
from src.telemetry.application.use_cases.alertas.generar_alerta_telemetria_use_case import GenerarAlertaTelemetriaUseCase
from src.telemetry.domain.repositories.postcommit_port import EtapaPostcommit
from src.telemetry.application.use_cases.calidad.evaluar_ventanas_vision_use_case import EvaluarVentanasVisionUseCase
from src.telemetry.infrastructure.adapters.parametros_vision_mlops_adapter import ParametrosVisionMLOpsAdapter
from src.telemetry.infrastructure.repositories.ventanas_vision_repository import SqlAlchemyVentanasVisionRepository
from src.telemetry.infrastructure.adapters.activo_biologico_m02_adapter import ActivoBiologicoM02Adapter
from src.telemetry.infrastructure.adapters.especie_activo_m02_adapter import EspecieActivoM02Adapter
from src.telemetry.infrastructure.adapters.parametros_calidad_mlops_adapter import ParametrosCalidadMLOpsAdapter
from src.telemetry.infrastructure.adapters.parametros_heartbeat_mlops_adapter import ParametrosHeartbeatMLOpsAdapter, DiagnosticoHeartbeatMLOpsAdapter
from src.telemetry.infrastructure.adapters.umbral_historico_m09_adapter import UmbralHistoricoM09Adapter
from src.telemetry.infrastructure.adapters.parametros_alertas_mlops_adapter import ParametrosAlertasMLOpsAdapter
from src.telemetry.infrastructure.models.heartbeat_model import HeartbeatModel
from src.telemetry.infrastructure.repositories.alerta_repository import SqlAlchemyAlertaRepository
from src.telemetry.infrastructure.repositories.bitacora_auditoria_iot_repository import SqlAlchemyBitacoraAuditoriaIotRepository
from src.telemetry.infrastructure.repositories.estado_dispositivo_iot_repository import SqlAlchemyEstadoDispositivoIoTRepository
from src.telemetry.infrastructure.repositories.heartbeat_repository import SqlAlchemyHeartbeatRepository
from src.telemetry.infrastructure.repositories.lectura_postcommit_repository import SqlAlchemyLecturaPostcommitRepository
from src.telemetry.infrastructure.repositories.monitoreo_repository import SqlAlchemyMonitoreoRepository
from src.telemetry.infrastructure.repositories.postcommit_repository import unidad_postcommit
from src.telemetry.infrastructure.repositories.periodo_inactividad_repository import SqlAlchemyPeriodoInactividadRepository
from src.telemetry.infrastructure.repositories.telemetria_calidad_repository import SqlAlchemyTelemetriaCalidadRepository
from src.telemetry.infrastructure.repositories.vinculacion_lectura_repository import SqlAlchemyVinculacionLecturaRepository
from src.telemetry.infrastructure.repositories.historico_estado_alerta_repository import SqlAlchemyHistoricoEstadoAlertaRepository
from src.telemetry.infrastructure.repositories.regla_alerta_repository import SqlAlchemyReglaAlertaRepository

logger = logging.getLogger(__name__)


def _lectura(db):
    lecturas = SqlAlchemyLecturaPostcommitRepository(db)
    return ProcesarLecturaConfirmadaUseCase(
        lecturas,
        VincularLecturaActivoUseCase(db, SqlAlchemyVinculacionLecturaRepository(db), ActivoBiologicoM02Adapter(db),SqlAlchemyBitacoraAuditoriaIotRepository(db)),
        EvaluarCalidadTelemetriaUseCase(db, lecturas, SqlAlchemyTelemetriaCalidadRepository(db),
                                      ParametrosCalidadMLOpsAdapter(SqlAlchemyParametrosMLOpsRepository(db),
                                                                    SqlAlchemyConfiguracionGlobalRepository(db)),
                                      SqlAlchemyBitacoraAuditoriaIotRepository(db),
                                      contexto_port=ContextoCalidadM09RF60Adapter(db),
                                      alertas_calidad=GenerarAlertaCalidadUseCase(SqlAlchemyAlertaRepository(db))),
        ReclasificarSemaforoUseCase(db, lecturas, EspecieActivoM02Adapter(db),
                                  UmbralHistoricoM09Adapter(db), SqlAlchemyMonitoreoRepository(db)),
    )


def _heartbeat(db, identificador, alertas, parametros):
    heartbeat = SqlAlchemyHeartbeatRepository._a_entidad(db.get(HeartbeatModel, identificador))
    servicio = ProcesarHeartbeatPersistidoUseCase(
        SqlAlchemyEstadoDispositivoIoTRepository(db),
        SqlAlchemyAlertaRepository(db), parametros or ParametrosHeartbeatMLOpsAdapter(db),
        SqlAlchemyPeriodoInactividadRepository(db),
    )
    if alertas:
        infraestructura = SqlAlchemyLecturaPostcommitRepository(db).infraestructura(heartbeat.id_dispositivo_iot)
        servicio.procesar_alertas(heartbeat, infraestructura)
    else:
        ultimo = db.execute(text('''SELECT id_heartbeat FROM modulo3.heartbeats
            WHERE id_dispositivo_iot=:id ORDER BY fecha_recepcion DESC, id_heartbeat DESC LIMIT 1'''),
                            {'id': heartbeat.id_dispositivo_iot}).scalar_one()
        servicio.procesar_estado(heartbeat, ultimo == identificador)


def _recuperar_comunicacion(db, identificador):
    lectura = SqlAlchemyLecturaPostcommitRepository(db).obtener_por_id(identificador)
    if lectura.estado_calidad == 'LECTURA_VALIDA':
        EvaluarEstadoDispositivosUseCase(db, SqlAlchemyEstadoDispositivoIoTRepository(db),
            None, SqlAlchemyPeriodoInactividadRepository(db), SqlAlchemyAlertaRepository(db),
            None, ParametrosHeartbeatMLOpsAdapter(db)).execute(lectura.id_dispositivo_iot, confirmar=False)


def _diagnostico(db, identificador, metodo, politica):
    heartbeat = SqlAlchemyHeartbeatRepository._a_entidad(db.get(HeartbeatModel, identificador))
    infraestructura = SqlAlchemyLecturaPostcommitRepository(db).infraestructura(heartbeat.id_dispositivo_iot)
    servicio = EvaluarDiagnosticoHeartbeatUseCase(SqlAlchemyAlertaRepository(db), politica or DiagnosticoHeartbeatMLOpsAdapter(db))
    getattr(servicio, metodo)(heartbeat, infraestructura)


def _alerta_critica(db, identificador):
    return GenerarAlertaTelemetriaUseCase(
        SqlAlchemyLecturaPostcommitRepository(db), _lectura(db).reclasificar,
        GenararAlertaUseCase(db, SqlAlchemyAlertaRepository(db),
            SqlAlchemyHistoricoEstadoAlertaRepository(db), SqlAlchemyReglaAlertaRepository(db),
            ParametrosAlertasMLOpsAdapter(SqlAlchemyParametrosMLOpsRepository(db))),
    ).execute(identificador)
def _vision(db,identificador):
    EvaluarVentanasVisionUseCase(SqlAlchemyVentanasVisionRepository(db),
        ParametrosVisionMLOpsAdapter(SqlAlchemyParametrosMLOpsRepository(db)),
        SqlAlchemyBitacoraAuditoriaIotRepository(db)).execute(identificador)


def construir_procesador(engine_bd=engine, *, identidad=True, parametros_heartbeat=None, diagnostico_heartbeat=None, avisos_vinculacion=None, limite=50, reintento_seg=60):
    parametros = parametros_heartbeat
    acciones = {
            EtapaPostcommit.RF53_LECTURAS: auditar_lectura,
            EtapaPostcommit.RF53_AUDITORIA: auditar_ingesta,
            EtapaPostcommit.RF60_TRANSICIONES: auditar_transicion,
            EtapaPostcommit.HEARTBEAT_AUDITORIA: auditar_heartbeat,
            EtapaPostcommit.RF61: lambda db, i: _lectura(db).vincular_lectura(i),
            EtapaPostcommit.RF62: lambda db, i: _lectura(db).evaluar_lectura(i),
            EtapaPostcommit.RF17: lambda db, i: _lectura(db).clasificar_lectura(i),
            EtapaPostcommit.RF57: _alerta_critica,
            EtapaPostcommit.RF60: lambda db, i: _recuperar_comunicacion(db, i),
            EtapaPostcommit.VISION_DETECCION: _vision,
            EtapaPostcommit.HEARTBEAT_ESTADO: lambda db, i: _heartbeat(db, i, False, parametros),
            EtapaPostcommit.HEARTBEAT_ALERTAS: lambda db, i: _heartbeat(db, i, True, parametros),
            EtapaPostcommit.HEARTBEAT_SENSORES: lambda db, i: _diagnostico(db, i, 'sensores', diagnostico_heartbeat),
            EtapaPostcommit.HEARTBEAT_TEMPERATURA: lambda db, i: _diagnostico(db, i, 'temperatura', diagnostico_heartbeat),
            EtapaPostcommit.HEARTBEAT_FIRMWARE: lambda db, i: _diagnostico(db, i, 'firmware', diagnostico_heartbeat),
    }
    # RF-61 E3: sin canal de aviso integrado la etapa no corre. Si corriera, cada
    # reintento dejaría un POSTCOMMIT_RF61_AVISOS_FALLIDO en la bitácora inmutable
    # (DB-11) por cada lectura ambigua; queda pendiente y se procesa al conectarlo.
    if avisos_vinculacion is not None:
        acciones[EtapaPostcommit.RF61_AVISOS] = lambda db, i: ProcesarAvisosVinculacionUseCase(
            SqlAlchemyVinculacionLecturaRepository(db), avisos_vinculacion, DestinatariosVinculacionM01Adapter(db)).execute(i)
    return ProcesarPostcommitUseCase(
        lambda: unidad_postcommit(engine_bd, identidad=identidad),
        acciones, limite=limite, reintento_seg=reintento_seg,
    )


async def procesar_postcommit_periodicamente():
    procesador = construir_procesador(
        limite=int(os.getenv('IOT_POSTCOMMIT_LOTE', '50')),
        reintento_seg=int(os.getenv('IOT_POSTCOMMIT_REINTENTO_SEG', '60')),
    )
    intervalo = max(1, int(os.getenv('IOT_POSTCOMMIT_INTERVALO_SEG', '5')))
    while True:
        # Sesiones y conexiones se crean/cierran dentro del hilo. Al apagar se
        # espera su transacción corta antes de finalizar la tarea del lifespan.
        trabajo = asyncio.create_task(asyncio.to_thread(procesador.execute))
        try:
            await asyncio.shield(trabajo)
        except asyncio.CancelledError:
            await trabajo
            raise
        except Exception:
            logger.error('No se pudo consultar el trabajo postcommit; se reintentará.')
        await asyncio.sleep(intervalo)
