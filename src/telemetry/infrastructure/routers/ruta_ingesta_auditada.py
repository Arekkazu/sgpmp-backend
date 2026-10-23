# | Fecha      | Nombre  | Que se hizo |
# |------------|---------|-------------|
# | 2026-10-22 | Leandro | DEV-47 RF-63: audita estructura rechazada fuera de transaccion de ingesta |
"""Solo los endpoints de ingesta; no altera el handler HTTP global."""
import logging

from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from starlette.concurrency import run_in_threadpool
from sqlalchemy.exc import SQLAlchemyError
from psycopg2 import Error as PostgreSQLError

from src.shared.database import sesion_sistema
from src.shared.errors import AppError
from src.telemetry.application.use_cases.auditoria.evidencia_iot import registrar_evidencia
from src.telemetry.domain.entities.evento_auditoria_iot import ComponenteOrigen, TipoResultado, SeveridadLog
from src.telemetry.infrastructure.repositories.bitacora_auditoria_iot_repository import SqlAlchemyBitacoraAuditoriaIotRepository

logger = logging.getLogger(__name__)


def registrar_rechazo_estructural(ruta, cantidad):
    _registrar_error(ruta, 'ERROR_ESTRUCTURA_MENSAJE', {'cantidad_errores': cantidad})


def _registrar_error(ruta, tipo, detalle):
    try:
        with sesion_sistema() as db:
            registrar_evidencia(SqlAlchemyBitacoraAuditoriaIotRepository(db),
                tipo, ComponenteOrigen.RF53,
                resultado=TipoResultado.RECHAZADO, severidad=SeveridadLog.WARNING,
                detalle={'endpoint': ruta} | detalle)
            db.commit()
    except Exception:
        logger.error('RF-63: no se pudo persistir el rechazo de ingesta tipo=%s.', tipo)


class RutaIngestaAuditada(APIRoute):
    def get_route_handler(self):
        original = super().get_route_handler()

        async def handler(request):
            try:
                return await original(request)
            except RequestValidationError as exc:
                await run_in_threadpool(registrar_rechazo_estructural, self.path, len(exc.errors()))
                raise
            except Exception as exc:
                origen = getattr(exc, 'original_error', exc)
                if (not isinstance(exc, AppError) or exc.status_code >= 500) and isinstance(origen, (SQLAlchemyError, PostgreSQLError)):
                    await run_in_threadpool(_registrar_error, self.path, 'FALLA_PERSISTENCIA', {})
                raise

        return handler
