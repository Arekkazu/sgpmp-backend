# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-27 | destroyerban | INC-M03-116-G59 RF-56: consulta del paquete por id con alcance por finca |
"""Router FastAPI para consultar paquetes de inferencia (RF-56).

  GET /iot/paquetes-inferencia/{id_paquete} — Paquete con su trazabilidad y su ciclo de vida

Auth: JWT Bearer + RBAC recurso 39 (bitacora_auditoria_iot), acción R: es una consulta de
trazabilidad técnica (RF-56 CA-8, Postcondición 3 y 5) sobre la misma bitácora RF-63, con
su mismo alcance por finca (M3-14). La bitácora completa de paquetes se consulta en
GET /iot/auditoria?entidad_afectada_tipo=PAQUETE_IA.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session

from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared.database import get_db
from src.shared.rbac import require_permission
from src.shared.schemas import ErrorResponse
from src.telemetry.application.use_cases.inferencia.consultar_paquete_inferencia_use_case import (
    ConsultarPaqueteInferenciaUseCase,
)
from src.telemetry.infrastructure.repositories.bitacora_auditoria_iot_repository import SqlAlchemyBitacoraAuditoriaIotRepository
from src.telemetry.infrastructure.repositories.paquete_inferencia_repository import SqlAlchemyPaqueteInferenciaRepository
from src.telemetry.infrastructure.routers.auditoria_iot_router import _fincas_de_la_bitacora
from src.telemetry.infrastructure.schema.bitacora_auditoria_iot_schema import EventoAuditoriaIotSchema
from src.telemetry.infrastructure.schema.paquete_inferencia_schema import PaqueteInferenciaDetalleSchema

router = APIRouter(prefix="/iot/paquetes-inferencia", tags=["Telemetría IoT - Paquetes de inferencia RF-56"])


@router.get(
    "/{id_paquete}",
    response_model=PaqueteInferenciaDetalleSchema,
    status_code=200,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
    dependencies=[Depends(require_permission(39, 2))],
    summary="Consultar un paquete de inferencia y su ciclo de vida (RF-56)",
)
def obtener_paquete(
    id_paquete: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> PaqueteInferenciaDetalleSchema:
    resultado = ConsultarPaqueteInferenciaUseCase(
        paquete_repo=SqlAlchemyPaqueteInferenciaRepository(db),
        auditoria_repo=SqlAlchemyBitacoraAuditoriaIotRepository(db),
    ).execute(id_paquete, ids_fincas_permitidas=_fincas_de_la_bitacora(db, usuario_actual))
    p = resultado.paquete
    return PaqueteInferenciaDetalleSchema(
        id_paquete_inferencia=p.id_paquetes_inferencia,
        id_sensor=p.id_sensor,
        id_dispositivo_iot=p.id_dispositivo_iot,
        id_evento_edge_computing=p.id_evento_edge_computing,
        id_version_modelo=p.id_version_modelo,
        tipo_variable=p.tipo_variable,
        valor_numerico=p.valor_numerico,
        unidad=p.unidad,
        estado_calidad=p.estado_calidad,
        estado_desviacion=p.estado_desviacion,
        severidad=p.severidad,
        origen=p.origen,
        contexto_incompleto=p.contexto_incompleto,
        contexto_ambiental=p.contexto_ambiental,
        metadatos=p.metadatos,
        estado_paquete=p.estado_paquete,
        intento_envios=p.intento_envios,
        fecha_envio=p.fecha_envio,
        ciclo_vida=[EventoAuditoriaIotSchema.model_validate(e) for e in resultado.ciclo_vida],
    )
