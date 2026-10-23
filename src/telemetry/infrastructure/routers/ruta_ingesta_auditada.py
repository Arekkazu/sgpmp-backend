# | Fecha      | Nombre  | Que se hizo                                      |
# |------------|---------|--------------------------------------------------|
# | 2026-10-21 | Leandro | DEV-40 RF-53: audita estructura individual y lote |
"""Captura Pydantic antes del endpoint, limitada a las dos rutas escalares."""
from uuid import UUID, uuid4
import logging

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from starlette.concurrency import run_in_threadpool

from src.shared.database import SessionLocal, declarar_identidad_sistema
from src.shared.error_handlers import request_validation_error_handler
from src.telemetry.application.use_cases.ingesta.registrar_rechazo_estructura_use_case import RegistrarRechazoEstructuraUseCase
from src.telemetry.infrastructure.dto.ingerir_telemetria_dto import IngerirTelemetriaDTO, IngerirTelemetriaBatchDTO
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


class RutaIngestaAuditada(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()
        if self.path not in _RUTAS or 'POST' not in self.methods:
            return handler

        async def ruta(request: Request):
            try:
                return await handler(request)
            except RequestValidationError as exc:
                if any(error.get('loc', (None,))[0] == 'body' for error in exc.errors()):
                    await run_in_threadpool(_registrar, _contexto(request, exc, self.path))
                return await request_validation_error_handler(request, exc)

        return ruta
