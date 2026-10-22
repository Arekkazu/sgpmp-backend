# | Fecha      | Nombre  | Que se hizo                                      |
# |------------|---------|--------------------------------------------------|
# | 2026-10-21 | Leandro | DEV-27 RF-60: conecta adaptadores reales por etapa |
# | 2026-10-22 | Leandro | DEV-42 RF-60: recupera conectividad tras telemetria valida |
"""Composición del procesador B+. No recibe callbacks ni se conecta al broker."""
import asyncio
import logging
import os

from sqlalchemy import text

from src.configuration.infrastructure.repositories.configuracion_global_repository import SqlAlchemyConfiguracionGlobalRepository
from src.prediction.infrastructure.repositories.parametros_mlops_repository import SqlAlchemyParametrosMLOpsRepository
from src.shared.database import engine
from src.telemetry.application.use_cases.calidad.evaluar_calidad_telemetria_use_case import EvaluarCalidadTelemetriaUseCase
from src.telemetry.application.use_cases.infraestructura.recibir_heartbeat_use_case import ProcesarHeartbeatPersistidoUseCase
from src.telemetry.application.use_cases.infraestructura.evaluar_estado_dispositivos_use_case import EvaluarEstadoDispositivosUseCase
from src.telemetry.application.use_cases.infraestructura.evaluar_diagnostico_heartbeat_use_case import EvaluarDiagnosticoHeartbeatUseCase
from src.telemetry.application.use_cases.infraestructura.vincular_lectura_activo_use_case import VincularLecturaActivoUseCase
from src.telemetry.application.use_cases.ingesta.procesar_lectura_confirmada_use_case import ProcesarLecturaConfirmadaUseCase
from src.telemetry.application.use_cases.ingesta.procesar_postcommit_use_case import ProcesarPostcommitUseCase
from src.telemetry.application.use_cases.monitoreo.reclasificar_semaforo_use_case import ReclasificarSemaforoUseCase
from src.telemetry.domain.repositories.postcommit_port import EtapaPostcommit
from src.telemetry.infrastructure.adapters.activo_biologico_m02_adapter import ActivoBiologicoM02Adapter
from src.telemetry.infrastructure.adapters.especie_activo_m02_adapter import EspecieActivoM02Adapter
from src.telemetry.infrastructure.adapters.parametros_calidad_mlops_adapter import ParametrosCalidadMLOpsAdapter
from src.telemetry.infrastructure.adapters.parametros_heartbeat_mlops_adapter import ParametrosHeartbeatMLOpsAdapter, DiagnosticoHeartbeatMLOpsAdapter
from src.telemetry.infrastructure.adapters.umbral_historico_m09_adapter import UmbralHistoricoM09Adapter
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

logger = logging.getLogger(__name__)


def _lectura(db):
    lecturas = SqlAlchemyLecturaPostcommitRepository(db)
    return ProcesarLecturaConfirmadaUseCase(
        lecturas,
        VincularLecturaActivoUseCase(db, SqlAlchemyVinculacionLecturaRepository(db), ActivoBiologicoM02Adapter(db)),
        EvaluarCalidadTelemetriaUseCase(db, lecturas, SqlAlchemyTelemetriaCalidadRepository(db),
                                      ParametrosCalidadMLOpsAdapter(SqlAlchemyParametrosMLOpsRepository(db),
                                                                    SqlAlchemyConfiguracionGlobalRepository(db)),
                                      SqlAlchemyBitacoraAuditoriaIotRepository(db)),
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


def construir_procesador(engine_bd=engine, *, identidad=True, parametros_heartbeat=None, diagnostico_heartbeat=None, limite=50, reintento_seg=60):
    parametros = parametros_heartbeat
    return ProcesarPostcommitUseCase(
        lambda: unidad_postcommit(engine_bd, identidad=identidad),
        {
            EtapaPostcommit.RF61: lambda db, i: _lectura(db).vincular_lectura(i),
            EtapaPostcommit.RF62: lambda db, i: _lectura(db).evaluar_lectura(i),
            EtapaPostcommit.RF17: lambda db, i: _lectura(db).clasificar_lectura(i),
            EtapaPostcommit.RF60: lambda db, i: _recuperar_comunicacion(db, i),
            EtapaPostcommit.HEARTBEAT_ESTADO: lambda db, i: _heartbeat(db, i, False, parametros),
            EtapaPostcommit.HEARTBEAT_ALERTAS: lambda db, i: _heartbeat(db, i, True, parametros),
            EtapaPostcommit.HEARTBEAT_SENSORES: lambda db, i: _diagnostico(db, i, 'sensores', diagnostico_heartbeat),
            EtapaPostcommit.HEARTBEAT_TEMPERATURA: lambda db, i: _diagnostico(db, i, 'temperatura', diagnostico_heartbeat),
            EtapaPostcommit.HEARTBEAT_FIRMWARE: lambda db, i: _diagnostico(db, i, 'firmware', diagnostico_heartbeat),
        }, limite=limite, reintento_seg=reintento_seg,
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
