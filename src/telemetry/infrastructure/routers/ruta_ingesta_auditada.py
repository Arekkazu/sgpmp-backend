# | Fecha      | Nombre  | Que se hizo                                      |
# |------------|---------|--------------------------------------------------|
# | 2026-10-21 | Leandro | DEV-40 RF-53: audita estructura individual y lote |
# | 2026-10-22 | Leandro | DEV-47 RF-63: audita estructura rechazada fuera de transaccion de ingesta |
# | 2026-10-26 | Leandro | INC-M03-125-G12 RF-53/63: respaldar FALLA_PERSISTENCIA con correlación segura sin depender de la BD principal. |
"""Captura Pydantic antes del endpoint, limitada a las dos rutas escalares."""
from uuid import UUID, uuid4
from datetime import datetime, timezone
import hashlib

from src.telemetry.application.use_cases.auditoria.resguardar_falla_persistencia_use_case import ResguardarFallaPersistenciaUseCase
from src.telemetry.infrastructure.adapters.respaldo_auditoria_iot_sqlite_adapter import RespaldoAuditoriaIotSqliteAdapter
import logging

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from starlette.concurrency import run_in_threadpool
from sqlalchemy.exc import SQLAlchemyError
from psycopg2 import Error as PostgreSQLError

from src.shared.database import SessionLocal, declarar_identidad_sistema, sesion_sistema
from src.shared.errors import AppError
from src.shared.error_handlers import request_validation_error_handler
from src.telemetry.application.use_cases.auditoria.evidencia_iot import registrar_evidencia
from src.telemetry.domain.entities.evento_auditoria_iot import ComponenteOrigen, TipoResultado, SeveridadLog
from src.telemetry.application.use_cases.ingesta.registrar_rechazo_estructura_use_case import RegistrarRechazoEstructuraUseCase
from src.telemetry.infrastructure.dto.ingerir_telemetria_dto import IngerirTelemetriaDTO, IngerirTelemetriaBatchDTO
from src.telemetry.infrastructure.repositories.bitacora_auditoria_iot_repository import SqlAlchemyBitacoraAuditoriaIotRepository
from src.telemetry.infrastructure.repositories.bitacora_ingest_repository import SqlAlchemyBitacoraIngestRepository

logger = logging.getLogger(__name__)
_CAMPOS = set(IngerirTelemetriaDTO.model_fields) | set(IngerirTelemetriaBatchDTO.model_fields)
_RUTAS = {'/iot/telemetria', '/iot/telemetria/batch'}


def _identificadores(valor: object) -> dict:
    if not isinstance(valor, dict):
        return {}
    return {
        campo: dato for campo in ('device_id', 'sensor_id')
        if type(dato := valor.get(campo)) is int and 0 < dato <= 2147483647
    }


def _contexto(request: Request, exc: RequestValidationError, ruta: str) -> dict:
    try:
        correlacion = str(UUID(str(getattr(request.state, 'request_id', ''))))
    except ValueError:
        correlacion = str(uuid4())
    # No guardar input, msg ni ctx: pueden contener valores y secretos del body.
    # Las claves extra del cliente tampoco se conservan como nombres de campos.
    errores = []
    for error in exc.errors()[:50]:
        loc = error.get('loc', ())
        if not loc or loc[0] != 'body':
            continue
        campo = [item if item in _CAMPOS else 'campo_no_reconocido'
                 for item in loc[1:] if isinstance(item, str)]
        indices = [item for item in loc[1:] if type(item) is int and 0 <= item < 500]
        errores.append({'campo': '.'.join(campo) or 'body', 'indices': indices, 'tipo': error['type']})
    contexto = {
        'endpoint': ruta, 'operacion': 'POST', 'resultado': 'RECHAZADO',
        'id_correlacion': correlacion, 'errores': errores,
    }
    if ruta == '/iot/telemetria':
        contexto.update(_identificadores(exc.body))
    elif isinstance(exc.body, dict) and isinstance(exc.body.get('registros'), list):
        registros = exc.body['registros']
        contexto['cantidad_registros'] = len(registros)
        contexto['registros'] = [dict(indice=i, **_identificadores(item))
                                 for i, item in enumerate(registros[:20])]
    return contexto


def _registrar(contexto: dict) -> None:
    try:
        with SessionLocal() as db:
            declarar_identidad_sistema(db)
            RegistrarRechazoEstructuraUseCase(db, SqlAlchemyBitacoraIngestRepository(db)).execute(contexto)
    except Exception:
        logger.warning('RF-53: no se pudo abrir la sesión de bitácora de ERROR_ESTRUCTURA.')


def registrar_rechazo_estructural(ruta, cantidad):
    _registrar_error(ruta, 'ERROR_ESTRUCTURA_MENSAJE', {'cantidad_errores': cantidad})


def _registrar_error(ruta, tipo, detalle):
    if tipo == 'FALLA_PERSISTENCIA':
        try:
            ResguardarFallaPersistenciaUseCase(RespaldoAuditoriaIotSqliteAdapter()).execute(ruta, detalle)
        except Exception:
            # Sin segundo medio durable no es posible garantizar la evidencia: hacerlo visible, sin alterar el 503.
            logger.critical('RF-63: FALLA_PERSISTENCIA sin respaldo durable; revisar almacenamiento local.')
        return
    try:
        with sesion_sistema() as db:
            registrar_evidencia(SqlAlchemyBitacoraAuditoriaIotRepository(db),
                tipo, ComponenteOrigen.RF53,
                resultado=TipoResultado.RECHAZADO, severidad=SeveridadLog.WARNING,
                detalle={'endpoint': ruta} | detalle)
            db.commit()
    except Exception:
        logger.error('RF-63: no se pudo persistir el rechazo de ingesta tipo=%s.', tipo)


def _traza_lectura(valor):
    traza = _identificadores(valor)
    if isinstance(valor, dict) and isinstance(valor.get('timestamp_captura'), str):
        ts = valor['timestamp_captura']
        if len(ts) <= 64:
            try:
                fecha = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                traza['timestamp_captura'] = fecha.replace(tzinfo=fecha.tzinfo or timezone.utc).astimezone(timezone.utc).isoformat()
            except (ValueError, OverflowError):
                pass
    return traza


async def _contexto_falla(request: Request, ruta: str) -> dict:
    try:
        correlacion = str(UUID(str(getattr(request.state, 'request_id', ''))))
    except ValueError:
        correlacion = str(uuid4())
    detalle = {'id_correlacion':correlacion}
    try:
        cuerpo = await request.body()
        detalle['hash_solicitud'] = hashlib.sha256(cuerpo).hexdigest()
        valor = await request.json()
    except Exception:
        # La obtención de contexto nunca debe sustituir el error original de persistencia.
        return detalle
    if isinstance(valor, dict) and isinstance(valor.get('registros'), list):
        detalle['cantidad_registros'] = len(valor['registros'])
        detalle['registros'] = [dict(indice=i, **_traza_lectura(v)) for i,v in enumerate(valor['registros'][:500])]
    else:
        detalle.update(_traza_lectura(valor))
    return detalle


class RutaIngestaAuditada(APIRoute):
    def get_route_handler(self):
        original = super().get_route_handler()
        # RF-53 (DEV-40): ERROR_ESTRUCTURA en bitacora_ingest solo para las dos rutas escalares.
        estructura_rf53 = self.path in _RUTAS and 'POST' in self.methods

        async def handler(request: Request):
            try:
                return await original(request)
            except RequestValidationError as exc:
                # RF-63 (DEV-47): evidencia en bitacora_auditoria_iot, fuera de la transacción.
                await run_in_threadpool(registrar_rechazo_estructural, self.path, len(exc.errors()))
                if estructura_rf53 and any(error.get('loc', (None,))[0] == 'body' for error in exc.errors()):
                    await run_in_threadpool(_registrar, _contexto(request, exc, self.path))
                return await request_validation_error_handler(request, exc)
            except Exception as exc:
                origen = getattr(exc, 'original_error', exc)
                if (not isinstance(exc, AppError) or exc.status_code >= 500) and isinstance(origen, (SQLAlchemyError, PostgreSQLError)):
                    await run_in_threadpool(_registrar_error, self.path, 'FALLA_PERSISTENCIA', await _contexto_falla(request, self.path))
                raise

        return handler
