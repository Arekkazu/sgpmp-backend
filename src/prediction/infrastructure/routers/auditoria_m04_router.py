# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-23 | destroyerban | DEV-37 RF-73: reintentos, respaldo local y sincronización de la bitácora M04 |
# | 2026-10-23 | Arekkazu | PR-667: fechas en UTC y día calendario en la zona del usuario (X-Zona-Horaria) |
# | 2026-10-25 | Arekkazu | USAB-M04 T-18 RF-73: nombre del usuario actor además del id |
# | 2026-10-26 | Arekkazu | INC-M04 G089/G092 RF-73: 422 en parámetros inválidos y filtro correlacion_id |
# | 2026-10-29 | Arekkazu | TC-DIS-195 RF-73: filtro de la bitácora M04 por tipo_modelo del evento |
# | 2026-10-29 | Arekkazu | QA-M04-27-10 CU09 H-04 RF-73: consultar la bitácora no deja evento |
# | 2026-11-02 | Arekkazu | AJF-13 RF-73: filtro por entidad_referencia y nombre legible de la referencia |
# | 2026-11-03 | Arekkazu | QA-M04 ronda 2 CU09 H-05 RF-73: tipo de evento o severidad que no existen responden 4xx, no 500 |
"""Router FastAPI para bitácora de auditoría del módulo de predicción.

RF-73 CU-09 Dev scope:
  GET  /prediccion/auditoria           — Listar bitácora con filtros
  GET  /prediccion/auditoria/exportar  — Exportar CSV/JSON
  GET  /prediccion/auditoria/{id}      — Detalle de evento

Autorización RBAC:
  recurso auditoria_m04 = id_recurso 46
  R=2 (Administrador; Veterinario desde DB-08, DEV-37: RF-73 actores), E=5 (Administrador)
"""
from __future__ import annotations

import uuid
from enum import Enum
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.prediction.application.use_cases.auditoria.consultar_auditoria_m04_use_case import ConsultarAuditoriaM04UseCase
from src.prediction.application.use_cases.auditoria.exportar_auditoria_m04_use_case import ExportarAuditoriaM04UseCase
from src.prediction.domain.services.validacion_auditoria_m04 import TipoEventoM04
from src.prediction.infrastructure.repositories.evento_auditoria_m04_repository import SqlAlchemyEventoAuditoriaM04Repository
from src.prediction.infrastructure.schema.evento_auditoria_m04_schema import AuditoriaM04ListResponse, EventoAuditoriaM04Response
from src.shared.database import get_db
from src.shared.rbac import require_permission
from src.shared.schemas import ErrorResponse
from src.shared.fechas import FechaHoraUtc

router = APIRouter(prefix="/prediccion/auditoria", tags=["Predicción M04 - Auditoría RF-73"])

_RECURSO = 46  # modulo1.recursos: 'auditoria_m04'
# CU09 H-05: un valor fuera del enum de la columna llegaba al SQL y respondía 500.
Severidad = Literal["INFO", "WARNING", "ERROR", "CRITICAL"]


def _con_nombre_usuario(db: Session, eventos: list[EventoAuditoriaM04Response]) -> list[EventoAuditoriaM04Response]:
    """T-18: nombre de quien hizo cada evento, una consulta por página."""
    ids = list({e.id_usuario for e in eventos if e.id_usuario is not None})
    if ids:
        nombres = dict(db.execute(text(
            "SELECT id_usuario, trim(nombre || ' ' || coalesce(apellidos, '')) FROM modulo1.usuarios "
            "WHERE id_usuario = ANY(:ids)"
        ), {"ids": ids}).all())
        for evento in eventos:
            evento.nombre_usuario = nombres.get(evento.id_usuario)
    return eventos


class EntidadReferenciaFiltro(str, Enum):
    """AJF-13: entidades que se pueden elegir por nombre en el filtro "Relacionado con".

    Las de id UUID (resultado de inferencia, retroalimentación) no se filtran: se llega
    a ellas desde el detalle del evento.
    """
    ACTIVO_BIOLOGICO = "activo_biologico"
    VERSION_MODELO = "version_modelo"
    PATOLOGIA = "patologia"
    CONFIGURACION_MOTOR_IA = "configuracion_motor_ia"


# AJF-13: nombre legible de la referencia por entidad; una consulta por entidad y página.
_NOMBRE_REFERENCIA_SQL: dict[str, str] = {
    "activo_biologico": "SELECT id_activo_biologico::text, coalesce(identificador, '#' || id_activo_biologico) "
                        "FROM modulo2.activos_biologicos WHERE id_activo_biologico::text = ANY(:ids)",
    "version_modelo": "SELECT id_version_modelo::text, nombre_version FROM modulo4.versiones_modelos "
                      "WHERE id_version_modelo::text = ANY(:ids)",
    "patologia": "SELECT id_patologia::text, nombre FROM modulo9.patologias WHERE id_patologia::text = ANY(:ids)",
}
_NOMBRE_REFERENCIA_SQL["lote"] = _NOMBRE_REFERENCIA_SQL["activo_biologico"]


def _con_nombre_referencia(db: Session, eventos: list[EventoAuditoriaM04Response]) -> list[EventoAuditoriaM04Response]:
    """AJF-13: "Animal BOV-003" o "Versión porcinos v3" en vez del id crudo."""
    por_entidad: dict[str, set[str]] = {}
    for e in eventos:
        if e.entidad_referencia in _NOMBRE_REFERENCIA_SQL and e.id_referencia:
            por_entidad.setdefault(e.entidad_referencia, set()).add(e.id_referencia)
    nombres: dict[tuple[str, str], str] = {}
    for entidad, ids in por_entidad.items():
        filas = db.execute(text(_NOMBRE_REFERENCIA_SQL[entidad]), {"ids": list(ids)}).all()
        nombres.update({(entidad, str(i)): n for i, n in filas})
    for e in eventos:
        if e.entidad_referencia and e.id_referencia:
            e.nombre_referencia = nombres.get((e.entidad_referencia, e.id_referencia))
    return eventos


@router.get(
    "",
    response_model=AuditoriaM04ListResponse,
    status_code=200,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        422: {"model": ErrorResponse, "description": "Parámetros inválidos (p. ej. por_pagina fuera de 1–200)"},
    },
    # INC-M04-208-G089: el contrato publica 422 para parámetros inválidos; el runtime lo cumple.
    openapi_extra={"x-codigo-validacion": 422},
    summary="Listar bitácora de auditoría M04 con filtros (RF-73)",
)
def listar_auditoria(
    tipo_evento: Optional[TipoEventoM04] = Query(default=None, description="Filtrar por tipo de evento"),
    fecha_desde: Optional[FechaHoraUtc] = Query(default=None),
    fecha_hasta: Optional[FechaHoraUtc] = Query(default=None),
    id_usuario: Optional[int] = Query(default=None, description="Filtrar por id de usuario actor"),
    id_sistema: Optional[str] = Query(default=None, description="Filtrar por sistema actor"),
    id_referencia: Optional[str] = Query(default=None, description="Filtrar por id de entidad referenciada"),
    severidad_evento: Optional[Severidad] = Query(default=None, description="INFO | WARNING | ERROR | CRITICAL"),
    correlacion_id: Optional[uuid.UUID] = Query(
        default=None, description="Cadena completa de un flujo (paquete → inferencia → alerta → retroalimentación)"
    ),
    tipo_modelo: Optional[str] = Query(default=None, description="Filtrar por tipo de modelo del evento (RFC-009)"),
    entidad_referencia: Optional[EntidadReferenciaFiltro] = Query(
        default=None,
        description="Tipo de cosa a la que apunta id_referencia (activo_biologico incluye lotes). "
                    "Sin él, id_referencia mezcla entidades con el mismo id.",
    ),
    pagina: int = Query(default=1, ge=1),
    por_pagina: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> AuditoriaM04ListResponse:
    use_case = ConsultarAuditoriaM04UseCase(repo=SqlAlchemyEventoAuditoriaM04Repository(db))
    items, total = use_case.listar(
        tipo_evento=tipo_evento,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        id_usuario=id_usuario,
        id_sistema=id_sistema,
        id_referencia=id_referencia,
        severidad_evento=severidad_evento,
        correlacion_id=correlacion_id,
        tipo_modelo=tipo_modelo,
        entidad_referencia=entidad_referencia.value if entidad_referencia else None,
        pagina=pagina,
        por_pagina=por_pagina,
    )
    eventos = [EventoAuditoriaM04Response.model_validate(e) for e in items]
    return AuditoriaM04ListResponse(
        total=total,
        pagina=pagina,
        por_pagina=por_pagina,
        items=_con_nombre_referencia(db, _con_nombre_usuario(db, eventos)),
    )


@router.get(
    "/exportar",
    status_code=200,
    dependencies=[Depends(require_permission(_RECURSO, 5))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
    summary="Exportar bitácora de auditoría M04 en CSV o JSON (RF-73)",
)
def exportar_auditoria(
    tipo_evento: Optional[TipoEventoM04] = Query(default=None),
    fecha_desde: Optional[FechaHoraUtc] = Query(default=None),
    fecha_hasta: Optional[FechaHoraUtc] = Query(default=None),
    id_usuario: Optional[int] = Query(default=None),
    id_sistema: Optional[str] = Query(default=None),
    id_referencia: Optional[str] = Query(default=None),
    severidad_evento: Optional[Severidad] = Query(default=None),
    tipo_modelo: Optional[str] = Query(default=None),
    entidad_referencia: Optional[EntidadReferenciaFiltro] = Query(default=None),
    formato: str = Query(default="json", pattern="^(json|csv)$"),
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> StreamingResponse:
    use_case = ExportarAuditoriaM04UseCase(
        db=db,
        repo=SqlAlchemyEventoAuditoriaM04Repository(db),
    )
    contenido, media_type, filename = use_case.exportar(
        tipo_evento=tipo_evento,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        id_usuario=id_usuario,
        id_sistema=id_sistema,
        id_referencia=id_referencia,
        severidad_evento=severidad_evento,
        tipo_modelo=tipo_modelo,
        entidad_referencia=entidad_referencia.value if entidad_referencia else None,
        formato=formato,
        id_usuario_exportador=usuario_actual.id_usuario,
    )
    return StreamingResponse(
        iter([contenido]),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/{id_evento}",
    response_model=EventoAuditoriaM04Response,
    status_code=200,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
    summary="Obtener detalle de evento de auditoría M04 (RF-73)",
)
def obtener_evento(
    id_evento: uuid.UUID,
    db: Session = Depends(get_db),
) -> EventoAuditoriaM04Response:
    use_case = ConsultarAuditoriaM04UseCase(repo=SqlAlchemyEventoAuditoriaM04Repository(db))
    entidad = use_case.obtener_por_id(id_evento)
    return _con_nombre_referencia(db, _con_nombre_usuario(db, [EventoAuditoriaM04Response.model_validate(entidad)]))[0]
