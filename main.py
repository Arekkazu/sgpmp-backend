import asyncio
import logging
import os
from contextlib import asynccontextmanager

from audit_sdk.context_fastapi import AuditContextMiddleware
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

from src.biological_assets.infrastructure.routers.activo_biologico_router import router as activo_biologico_router
from src.configuration.infrastructure.routers.ciclo_router import router as ciclo_router
from src.configuration.infrastructure.routers.configuracion_global_router import router as configuracion_global_router
from src.configuration.infrastructure.routers.especie_router import router as especie_router
from src.configuration.infrastructure.routers.finca_router import router as finca_router
from src.configuration.infrastructure.routers.dispositivo_iot_router import router as dispositivo_iot_router
from src.configuration.infrastructure.routers.tipo_dispositivo_iot_router import router as tipo_dispositivo_iot_router
from src.configuration.infrastructure.routers.infraestructura_router import router as infraestructura_router
from src.configuration.infrastructure.routers.sensor_router import router as sensor_router
from src.configuration.infrastructure.routers.contexto_interfaz_router import router as contexto_interfaz_router
from src.configuration.infrastructure.routers.identidad_visual_router import router as identidad_visual_router
from src.configuration.infrastructure.routers.tema_visual_router import router as tema_visual_router
from src.configuration.infrastructure.routers.dashboard_layout_router import router as dashboard_layout_router
from src.configuration.infrastructure.routers.preferencia_idioma_router import router as preferencia_idioma_router
from src.configuration.infrastructure.routers.metrica_router import router as metrica_router
from src.configuration.infrastructure.routers.patologia_router import router as patologia_router
from src.configuration.infrastructure.routers.plantilla_router import router as plantilla_router
from src.configuration.infrastructure.routers.umbral_router import router as umbral_router
from src.identity_access.infrastructure.routers.auditoria_routers import router as auditoria_router
from src.telemetry.infrastructure.routers.telemetria_router import router as telemetria_router
from src.telemetry.infrastructure.routers.evento_edge_router import router as evento_edge_router
from src.telemetry.infrastructure.routers.alerta_router import router as alerta_router
from src.telemetry.infrastructure.routers.monitoreo_router import router as monitoreo_router
from src.telemetry.infrastructure.routers.infraestructura_iot_router import router as infraestructura_iot_router
from src.telemetry.infrastructure.routers.vinculacion_router import router as vinculacion_router
from src.telemetry.infrastructure.routers.calidad_router import router as calidad_router
from src.telemetry.infrastructure.routers.auditoria_iot_router import router as auditoria_iot_router
from src.prediction.infrastructure.routers.patologia_m04_router import router as patologia_m04_router
from src.prediction.infrastructure.routers.motor_ia_router import router as motor_ia_router
from src.prediction.infrastructure.routers.historial_diagnostico_router import router as historial_diagnostico_router
from src.prediction.infrastructure.routers.version_modelo_router import router as version_modelo_router
from src.prediction.infrastructure.routers.ota_router import router as ota_router
from src.prediction.infrastructure.routers.retroalimentacion_clinica_router import router as retroalimentacion_clinica_router
from src.prediction.infrastructure.routers.auditoria_m04_router import router as auditoria_m04_router
from src.supplies.infrastructure.routers.consumo_alimento_router import router as consumo_alimento_router
from src.supplies.infrastructure.routers.medicamento_router import router as medicamento_router
from src.supplies.infrastructure.routers.eficiencia_alimenticia_router import router as eficiencia_alimenticia_router
from src.supplies.infrastructure.routers.batch_ica_router import router as batch_ica_router
from src.supplies.infrastructure.routers.reporte_gastos_router import router as reporte_gastos_router
from src.supplies.infrastructure.routers.batch_reportes_gastos_router import router as batch_reportes_gastos_router
from src.supplies.infrastructure.routers.historial_suministros_router import router as historial_suministros_router
from src.supplies.infrastructure.routers.batch_historial_suministros_router import (
    router as batch_historial_suministros_router,
)
from src.supplies.infrastructure.routers.costeo_suministros_router import router as costeo_suministros_router
from src.supplies.infrastructure.routers.provision_nic41_router import router as provision_nic41_router
from src.supplies.infrastructure.routers.auditoria_suministros_router import router as auditoria_suministros_router
from src.identity_access.infrastructure.routers.agrofusion_integration_router import router as agrofusion_router
from src.identity_access.infrastructure.routers.contrasena_routers import router as contrasena_router
from src.identity_access.infrastructure.routers.roles_routers import router as roles_router
from src.identity_access.infrastructure.routers.sesiones_routers import router as sesiones_router
from src.identity_access.infrastructure.routers.usuarios_routers import router as usuarios_router
from src.identity_access.infrastructure.routers.notificaciones_routers import router as notificaciones_router
from src.shared.error_handlers import register_error_handlers


async def _evaluar_dispositivos_periodicamente() -> None:
    """Tarea periódica RF-60: evalúa estado de dispositivos cada 60 s."""
    from src.shared.database import SessionLocal
    from src.telemetry.application.use_cases.infraestructura.evaluar_estado_dispositivos_use_case import EvaluarEstadoDispositivosUseCase
    from src.telemetry.infrastructure.repositories.alerta_repository import SqlAlchemyAlertaRepository
    from src.telemetry.infrastructure.repositories.estado_dispositivo_iot_repository import SqlAlchemyEstadoDispositivoIoTRepository
    from src.telemetry.infrastructure.repositories.historico_estado_alerta_repository import SqlAlchemyHistoricoEstadoAlertaRepository
    from src.telemetry.infrastructure.repositories.historico_transicion_dispositivo_repository import SqlAlchemyHistoricoTransicionDispositivoRepository
    from src.telemetry.infrastructure.repositories.periodo_inactividad_repository import SqlAlchemyPeriodoInactividadRepository

    while True:
        await asyncio.sleep(60)
        db = SessionLocal()
        try:
            use_case = EvaluarEstadoDispositivosUseCase(
                db=db,
                estado_repo=SqlAlchemyEstadoDispositivoIoTRepository(db),
                transicion_repo=SqlAlchemyHistoricoTransicionDispositivoRepository(db),
                periodo_repo=SqlAlchemyPeriodoInactividadRepository(db),
                alerta_repo=SqlAlchemyAlertaRepository(db),
                historico_alerta_repo=SqlAlchemyHistoricoEstadoAlertaRepository(db),
            )
            n = use_case.execute()
            if n > 0:
                logger.info('EvaluarEstadoDispositivos: %d transiciones registradas.', n)
        except Exception:
            logger.exception('Error en tarea periódica de evaluación de dispositivos.')
        finally:
            db.close()


async def _ejecutar_batch_ica_diario() -> None:
    """Tarea diaria RF-74: ejecuta el motor batch de cálculo ICA a la hora configurada.

    Calcula la espera hasta la próxima ``hora_ejecucion`` (``configuracion_batch_ica``,
    hora local del servidor; 02:00 por defecto), corre el batch y repite cada día.
    """
    from datetime import datetime, time as dtime, timedelta

    from src.shared.database import SessionLocal
    from src.supplies.infrastructure.factories.eficiencia_factory import build_ejecutar_batch_use_case
    from src.supplies.infrastructure.repositories.configuracion_batch_ica_repository import (
        SqlAlchemyConfiguracionBatchICARepository,
    )

    while True:
        hora = dtime(2, 0)
        db = SessionLocal()
        try:
            hora = SqlAlchemyConfiguracionBatchICARepository(db).obtener().hora_ejecucion
        except Exception:
            logger.exception("Batch ICA nocturno: no se pudo leer la configuración; se usa 02:00.")
        finally:
            db.close()

        ahora = datetime.now()
        proximo = ahora.replace(hour=hora.hour, minute=hora.minute, second=0, microsecond=0)
        if proximo <= ahora:
            proximo += timedelta(days=1)
        await asyncio.sleep((proximo - ahora).total_seconds())

        db = SessionLocal()
        try:
            use_case = build_ejecutar_batch_use_case(db)
            ejecucion = await use_case.ejecutar(tipo_disparo="AUTOMATICO")
            logger.info(
                "Batch ICA nocturno: ejecución %s estado %s (procesados %s, fallidos %s).",
                ejecucion.id_ejecucion,
                ejecucion.estado.value,
                ejecucion.cantidad_activos_procesados,
                ejecucion.cantidad_fallidos,
            )
        except Exception:
            logger.exception("Error en el batch ICA nocturno.")
        finally:
            db.close()


async def _revertir_retiros_vencidos_diariamente() -> None:
    """Tarea diaria RF-76 (pasos 11-13): revierte a ACTIVO los activos cuyo retiro venció.

    Corre todos los días a una hora fija del servidor (03:00). A diferencia del
    batch ICA, RF-76 no define un panel de configuración/disparo manual, así
    que la hora queda fija en código.
    """
    from datetime import datetime, time as dtime, timedelta

    from src.shared.database import SessionLocal
    from src.supplies.application.use_cases.suministros.revertir_retiros_vencidos_use_case import (
        RevertirRetirosVencidosUseCase,
    )

    hora = dtime(3, 0)

    while True:
        ahora = datetime.now()
        proximo = ahora.replace(hour=hora.hour, minute=hora.minute, second=0, microsecond=0)
        if proximo <= ahora:
            proximo += timedelta(days=1)
        await asyncio.sleep((proximo - ahora).total_seconds())

        try:
            use_case = RevertirRetirosVencidosUseCase(session_factory=SessionLocal)
            n = await asyncio.to_thread(use_case.ejecutar)
            logger.info("Reversión de retiros vencidos: %d activo(s) revertido(s) a ACTIVO.", n)
        except Exception:
            logger.exception("Error en la tarea diaria de reversión de retiros vencidos.")


async def _archivar_auditoria_diariamente() -> None:
    """Tarea diaria RF-10: archiva eventos con más de 12 meses a las 04:00 UTC."""
    from datetime import datetime, time as dtime, timedelta, timezone

    from src.identity_access.application.use_cases.auditoria.archivar_auditoria_use_case import (
        ArchivarAuditoriaUseCase,
    )
    from src.identity_access.application.use_cases.auditoria.notificar_fallo_archivado_use_case import (
        NotificarFalloArchivadoUseCase,
    )
    from src.identity_access.infrastructure.repositories.evento_repository import (
        SqlAlchemyEventoRepository,
    )
    from src.identity_access.infrastructure.repositories.notificacion_repository import (
        SqlAlchemyNotificacionRepository,
    )
    from src.identity_access.infrastructure.repositories.usuario_repository import (
        SqlAlchemyUsuarioRepository,
    )
    from src.shared.database import SessionLocal

    hora = dtime(4, 0)

    def alertar_fallo(causa: str) -> int:
        """Emite la alerta interna del FA de RF-10 en una sesión limpia.

        La sesión del archivado quedó en rollback, así que la notificación necesita
        una propia.
        """
        db = SessionLocal()
        try:
            return NotificarFalloArchivadoUseCase(
                eventos_repo=SqlAlchemyEventoRepository(db),
                notificaciones_repo=SqlAlchemyNotificacionRepository(db),
                usuarios_repo=SqlAlchemyUsuarioRepository(db),
                db=db,
            ).execute(causa=causa)
        finally:
            db.close()

    while True:
        ahora = datetime.now(timezone.utc)
        proximo = ahora.replace(
            hour=hora.hour,
            minute=hora.minute,
            second=0,
            microsecond=0,
        )
        if proximo <= ahora:
            proximo += timedelta(days=1)
        await asyncio.sleep((proximo - ahora).total_seconds())

        def ejecutar_archivado():
            db = SessionLocal()
            try:
                return ArchivarAuditoriaUseCase(
                    eventos_repo=SqlAlchemyEventoRepository(db),
                    db=db,
                ).execute()
            finally:
                db.close()

        try:
            resultado = await asyncio.to_thread(ejecutar_archivado)
            if not resultado.bloqueo_adquirido:
                logger.info(
                    "Archivado RF-10 omitido: otra réplica tiene el bloqueo del proceso."
                )
                continue
            logger.info(
                "Archivado RF-10 completado: %d evento(s) en %d lote(s), corte=%s.",
                resultado.eventos_archivados,
                resultado.lotes_procesados,
                resultado.fecha_corte.isoformat(),
            )
            if resultado.limite_alcanzado:
                logger.warning(
                    "ALERTA INTERNA RF-10: el archivado alcanzó el límite de lotes; "
                    "el remanente se procesará en la siguiente ejecución."
                )
        except Exception as exc:
            logger.exception(
                "ALERTA INTERNA RF-10: no se pudo completar el archivado automático "
                "de eventos antiguos."
            )
            # El FA de RF-10 exige avisar al administrador, no solo dejar el log.
            # Un fallo de la propia alerta no debe tumbar el bucle diario.
            try:
                avisados = await asyncio.to_thread(alertar_fallo, f"{type(exc).__name__}: {exc}")
                logger.info(
                    "Alerta de fallo de archivado RF-10 notificada a %d administrador(es).",
                    avisados,
                )
            except Exception:
                logger.exception(
                    "ALERTA INTERNA RF-10: tampoco se pudo notificar el fallo del archivado."
                )


async def _procesar_cola_reportes_gastos_periodicamente() -> None:
    """Poller RF-77: procesa la cola de generación async de reportes de gastos.

    A diferencia del batch ICA (cron-like, una vez al día), los reportes se
    encolan en momentos arbitrarios (decisión del usuario en cada request),
    así que este poller corre en un bucle continuo cada
    ``intervalo_poll_segundos`` (configurable en
    ``modulo5.configuracion_batch_reportes_gastos``).
    """
    from src.shared.database import SessionLocal
    from src.supplies.infrastructure.factories.reporte_gastos_factory import (
        build_procesar_cola_reportes_gastos_use_case,
    )
    from src.supplies.infrastructure.repositories.configuracion_batch_reporte_gasto_repository import (
        SqlAlchemyConfiguracionBatchReporteGastoRepository,
    )

    while True:
        db = SessionLocal()
        try:
            intervalo = SqlAlchemyConfiguracionBatchReporteGastoRepository(db).obtener().intervalo_poll_segundos
        except Exception:
            logger.exception("Poller de reportes de gastos: no se pudo leer la configuración; se usan 15s.")
            intervalo = 15
        finally:
            db.close()

        await asyncio.sleep(intervalo)

        db = SessionLocal()
        try:
            use_case = build_procesar_cola_reportes_gastos_use_case(db)
            n = await use_case.ejecutar()
            if n > 0:
                logger.info("Poller de reportes de gastos: %d trabajo(s) procesado(s).", n)
        except Exception:
            logger.exception("Error en el poller de generación de reportes de gastos.")
        finally:
            db.close()


async def _procesar_cola_historial_suministros_periodicamente() -> None:
    """Poller RF-81: procesa la cola de trabajos pesados de historial de suministros
    (``CONSULTA_PESADA`` nivel 3/4 y ``EXPORTACION`` > 10.000 registros). Mismo
    patrón de poller continuo que RF-77."""
    from src.shared.database import SessionLocal
    from src.supplies.infrastructure.factories.historial_suministros_factory import (
        build_procesar_cola_historial_suministros_use_case,
    )
    from src.supplies.infrastructure.repositories.configuracion_batch_historial_repository import (
        SqlAlchemyConfiguracionBatchHistorialRepository,
    )

    while True:
        db = SessionLocal()
        try:
            intervalo = SqlAlchemyConfiguracionBatchHistorialRepository(db).obtener().intervalo_poll_segundos
        except Exception:
            logger.exception("Poller de historial de suministros: no se pudo leer la configuración; se usan 15s.")
            intervalo = 15
        finally:
            db.close()

        await asyncio.sleep(intervalo)

        db = SessionLocal()
        try:
            use_case = build_procesar_cola_historial_suministros_use_case(db)
            n = await use_case.ejecutar()
            if n > 0:
                logger.info("Poller de historial de suministros: %d trabajo(s) procesado(s).", n)
        except Exception:
            logger.exception("Error en el poller de trabajos de historial de suministros.")
        finally:
            db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    tasks = [
        asyncio.create_task(_evaluar_dispositivos_periodicamente()),
        asyncio.create_task(_ejecutar_batch_ica_diario()),
        asyncio.create_task(_revertir_retiros_vencidos_diariamente()),
        asyncio.create_task(_archivar_auditoria_diariamente()),
        asyncio.create_task(_procesar_cola_reportes_gastos_periodicamente()),
        asyncio.create_task(_procesar_cola_historial_suministros_periodicamente()),
    ]
    yield
    for task in tasks:
        task.cancel()
    for task in tasks:
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    lifespan=lifespan,
    root_path=os.getenv("ROOT_PATH", "/api"),
    title="sistema gestion  - Gestión de Usuarios, Roles y Permisos",
    description="Microservicio de gestión de usuarios, roles y permisos dentro del sistema de gestión de maquinaria y nómina.",
    version="1.0.0",
)

# Allowlist explícita, sin depender de que ENV valga literalmente "production"
# (poco confiable en el deploy actual). Agregar un front nuevo (URL de
# Dokploy, dominio propio, etc.) es una env var, nunca un cambio de código.
allowed_origins = [
    origin.strip().rstrip("/")
    for origin in os.getenv("ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    # Localhost siempre permitido para dev local, sin importar ALLOWED_ORIGINS.
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_error_handlers(app)

app.include_router(usuarios_router)
app.include_router(sesiones_router)
app.include_router(contrasena_router)
app.include_router(auditoria_router)
app.include_router(roles_router)
app.include_router(notificaciones_router)
if os.getenv("AGROFUSION_HUB_CLIENT_ID"):
    # Integración M2M con AgroFusion (Mecanismo B) — ni siquiera se expone en
    # un despliegue standalone sin credenciales configuradas.
    app.include_router(agrofusion_router)
app.include_router(activo_biologico_router)
app.include_router(especie_router)
app.include_router(ciclo_router)
app.include_router(patologia_router)
app.include_router(metrica_router)
app.include_router(umbral_router)
app.include_router(plantilla_router)
app.include_router(configuracion_global_router)
app.include_router(finca_router)
app.include_router(infraestructura_router)
app.include_router(dispositivo_iot_router)
app.include_router(tipo_dispositivo_iot_router)
app.include_router(sensor_router)
app.include_router(contexto_interfaz_router)
app.include_router(identidad_visual_router)
app.include_router(tema_visual_router)
app.include_router(dashboard_layout_router)
app.include_router(preferencia_idioma_router)
app.include_router(telemetria_router)
app.include_router(evento_edge_router)
app.include_router(alerta_router)
app.include_router(monitoreo_router)
app.include_router(infraestructura_iot_router)
app.include_router(vinculacion_router)
app.include_router(calidad_router)
app.include_router(auditoria_iot_router)
app.include_router(patologia_m04_router)
app.include_router(motor_ia_router)
app.include_router(historial_diagnostico_router)
app.include_router(version_modelo_router)
app.include_router(ota_router)
app.include_router(retroalimentacion_clinica_router)
app.include_router(auditoria_m04_router)
app.include_router(consumo_alimento_router)
app.include_router(medicamento_router)
app.include_router(eficiencia_alimenticia_router)
app.include_router(batch_ica_router)
app.include_router(reporte_gastos_router)
app.include_router(batch_reportes_gastos_router)
app.include_router(historial_suministros_router)
app.include_router(batch_historial_suministros_router)
app.include_router(costeo_suministros_router)
app.include_router(provision_nic41_router)
app.include_router(auditoria_suministros_router)

@app.get("/", tags=["Health"])
async def index():
    return "hello world!"

@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok", "message": "API funcionando correctamente"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
