# | Fecha      | Nombre  | Que se hizo |
# |------------|---------|-------------|
# | 2026-10-22 | Leandro | DEV-47 RF-63: GET de integridad protegido y POST compatible |
# | 2026-10-23 | Arekkazu | PR-667: fechas en UTC y día calendario en la zona del usuario (X-Zona-Horaria) |
# | 2026-10-25 | Arekkazu | INC-M03-135/136/137 RF-63: filtros de la ficha y verificación con rango obligatorio |
# | 2026-10-25 | Arekkazu | USAB-M03 M3-14 RF-63: bitácora limitada a las fincas del usuario salvo para el auditor |
"""Router FastAPI para bitácora de auditoría IoT.

RF-63 — CU06 Dev scope:
  GET  /iot/auditoria                       — Listar bitácora con filtros
  GET  /iot/auditoria/{id_evento}           — Detalle de evento
  GET  /iot/auditoria/exportar              — Exportar JSON/CSV
  GET/POST /iot/auditoria/verificar-integridad — Verificar hashes SHA-256

Auth: JWT Bearer + RBAC recurso 39 (bitacora_auditoria_iot).
componente_origen no se expone en respuestas (campo interno).
"""
from __future__ import annotations

from dataclasses import asdict
from src.telemetry.infrastructure.adapters.aviso_integridad_m01_adapter import AvisoIntegridadM01Adapter

import csv
import io
import json
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from src.shared.database import get_db
from src.shared.alcance_finca_adapter import AlcanceFincaAdapter
from src.shared.rbac import require_permission, tiene_permiso
from src.shared.schemas import ErrorResponse
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.telemetry.application.use_cases.auditoria.consultar_bitacora_iot_use_case import ConsultarBitacoraIotUseCase
from src.telemetry.application.use_cases.auditoria.verificar_integridad_bitacora_use_case import VerificarIntegridadBitacoraUseCase
from src.telemetry.domain.entities.evento_auditoria_iot import ComponenteOrigen
from src.telemetry.infrastructure.repositories.bitacora_auditoria_iot_repository import SqlAlchemyBitacoraAuditoriaIotRepository
from src.telemetry.infrastructure.schema.bitacora_auditoria_iot_schema import (
    EventoAuditoriaIotSchema,
    ListaAuditoriaIotSchema,
    VerificacionIntegridadSchema,
)
from src.shared.fechas import FechaHoraUtc

router = APIRouter(prefix="/iot/auditoria", tags=["Telemetría IoT - Auditoría RF-63"])


def _fincas_de_la_bitacora(db: Session, usuario_actual: UsuarioActual) -> Optional[list[int]]:
    """M3-14: quien puede verificar la integridad (39, E) audita toda la bitácora.

    Hoy son el Administrador y el Contador, que no tiene finca. El resto (el
    Ingeniero de campo) veía 2,2 M eventos de todas las fincas; ahora solo los de
    los equipos de sus fincas. Se decide por permiso, no por id_rol.
    """
    if tiene_permiso(db, usuario_actual.id_rol, 39, 5):
        return None
    return AlcanceFincaAdapter(db).listar_ids_fincas_permitidas(usuario_actual.id_usuario, usuario_actual.id_rol)


@router.get(
    "",
    response_model=ListaAuditoriaIotSchema,
    status_code=200,
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
    dependencies=[Depends(require_permission(39, 2))],
    summary="Listar bitácora de auditoría IoT (RF-63)",
)
def listar_auditoria(
    fecha_desde: Optional[FechaHoraUtc] = Query(default=None),
    fecha_hasta: Optional[FechaHoraUtc] = Query(default=None),
    tipo_evento: Optional[str] = Query(default=None),
    severidad_log: Optional[str] = Query(default=None),
    clasificacion_registro: Optional[str] = Query(default=None),
    entidad_afectada_id: Optional[str] = Query(default=None),
    resultado: Optional[str] = Query(default=None),
    id_usuario: Optional[int] = Query(default=None, description="Usuario que originó el evento."),
    rf_origen: Optional[ComponenteOrigen] = Query(default=None, description="RF emisor (RF53–RF62...)."),
    registro_incompleto: Optional[bool] = Query(
        default=None, description="true: solo eventos registrados con campos faltantes (CA-13)."),
    pagina: int = Query(default=1, ge=1),
    por_pagina: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> ListaAuditoriaIotSchema:
    use_case = ConsultarBitacoraIotUseCase(
        auditoria_repo=SqlAlchemyBitacoraAuditoriaIotRepository(db),
    )
    items, total = use_case.listar(
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        tipo_evento=tipo_evento,
        severidad_log=severidad_log,
        clasificacion_registro=clasificacion_registro,
        entidad_afectada_id=entidad_afectada_id,
        resultado=resultado,
        pagina=pagina,
        por_pagina=por_pagina,
        id_usuario=id_usuario,
        rf_origen=rf_origen.value if rf_origen else None,
        registro_incompleto=registro_incompleto,
        ids_fincas_permitidas=_fincas_de_la_bitacora(db, usuario_actual),
    )
    return ListaAuditoriaIotSchema(
        total=total,
        pagina=pagina,
        por_pagina=por_pagina,
        items=[EventoAuditoriaIotSchema.model_validate(e) for e in items],
    )


@router.get(
    "/exportar",
    status_code=200,
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
    dependencies=[Depends(require_permission(39, 5))],
    summary="Exportar bitácora de auditoría IoT (RF-63)",
)
def exportar_auditoria(
    fecha_desde: Optional[FechaHoraUtc] = Query(default=None),
    fecha_hasta: Optional[FechaHoraUtc] = Query(default=None),
    tipo_evento: Optional[str] = Query(default=None),
    clasificacion_registro: Optional[str] = Query(default=None),
    formato: str = Query(default='json', pattern='^(json|csv)$'),
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> StreamingResponse:
    use_case = ConsultarBitacoraIotUseCase(
        auditoria_repo=SqlAlchemyBitacoraAuditoriaIotRepository(db),
    )
    items, _ = use_case.listar(
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        tipo_evento=tipo_evento,
        clasificacion_registro=clasificacion_registro,
        pagina=1,
        por_pagina=10000,
    )
    schemas = [EventoAuditoriaIotSchema.model_validate(e) for e in items]

    if formato == 'csv':
        output = io.StringIO()
        if schemas:
            writer = csv.DictWriter(output, fieldnames=schemas[0].model_fields.keys())
            writer.writeheader()
            for s in schemas:
                writer.writerow(s.model_dump())
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type='text/csv',
            headers={'Content-Disposition': 'attachment; filename="auditoria_iot.csv"'},
        )

    data = json.dumps([s.model_dump(mode='json') for s in schemas], default=str)
    return StreamingResponse(
        iter([data]),
        media_type='application/json',
        headers={'Content-Disposition': 'attachment; filename="auditoria_iot.json"'},
    )


@router.api_route(
    "/verificar-integridad",
    methods=["GET", "POST"],
    response_model=VerificacionIntegridadSchema,
    status_code=200,
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 403: {"model": ErrorResponse},
               422: {"model": ErrorResponse}},
    dependencies=[Depends(require_permission(39, 5))],
    summary="Verificar integridad SHA-256 de la bitácora (RF-63 FA-11)",
)
def verificar_integridad(
    fecha_desde: FechaHoraUtc = Query(..., description="Inicio de la ventana a verificar (obligatorio)."),
    fecha_hasta: FechaHoraUtc = Query(..., description="Fin de la ventana a verificar (obligatorio)."),
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> VerificacionIntegridadSchema:
    """Recalcula el SHA-256 de los eventos de la ventana (RF-63 FA-11).

    La ventana es obligatoria (sin ella, 400) y no puede superar ``AUDITORIA_IOT_MAX_VERIFICACION``
    eventos (50 000 por defecto): sin límite, una sola llamada recalculaba toda la
    bitácora y dejaba el servicio sin responder (INC-M03-135-G177). Rangos más
    grandes se verifican por ventanas: 422 ``RANGO_VERIFICACION_EXCEDIDO``.
    """
    use_case = VerificarIntegridadBitacoraUseCase(
        db=db, avisos=AvisoIntegridadM01Adapter(db),
        auditoria_repo=SqlAlchemyBitacoraAuditoriaIotRepository(db),
    )
    resultado = use_case.execute(fecha_desde=fecha_desde, fecha_hasta=fecha_hasta)
    return VerificacionIntegridadSchema(**asdict(resultado))


@router.get(
    "/{id_evento}",
    response_model=EventoAuditoriaIotSchema,
    status_code=200,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
    dependencies=[Depends(require_permission(39, 2))],
    summary="Obtener detalle de evento de auditoría (RF-63)",
)
def obtener_evento(
    id_evento: UUID,
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> EventoAuditoriaIotSchema:
    use_case = ConsultarBitacoraIotUseCase(
        auditoria_repo=SqlAlchemyBitacoraAuditoriaIotRepository(db),
    )
    return EventoAuditoriaIotSchema.model_validate(
        use_case.get(id_evento, ids_fincas_permitidas=_fincas_de_la_bitacora(db, usuario_actual)))
