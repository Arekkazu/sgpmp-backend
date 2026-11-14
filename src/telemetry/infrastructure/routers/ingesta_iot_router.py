# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-02 | Arekkazu | AJF-07 RF-53: GET /iot/ingesta y /iot/ingesta/indicadores (solo lectura) |
"""Monitor de ingesta (RF-53), solo lectura.

  GET /iot/ingesta              — Eventos de la bitácora de ingesta, paginados (24 h por defecto, máx. 31 días)
  GET /iot/ingesta/indicadores  — Lecturas de hoy: total, válidas, fuera de rango, errores

Mismo permiso que la pestaña Flujo IoT: recurso 36 (alertas técnicas IoT), Leer.
Respeta las fincas del usuario.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared.alcance_finca_adapter import AlcanceFincaAdapter
from src.shared.database import get_db
from src.shared.fechas import FechaHoraUtc
from src.shared.rbac import require_permission
from src.shared.schemas import ErrorResponse
from src.telemetry.application.use_cases.ingesta.consultar_ingesta_use_case import ConsultarIngestaUseCase
from src.telemetry.infrastructure.repositories.ingesta_repository import SqlAlchemyIngestaRepository
from src.telemetry.infrastructure.schema.lectura_ingesta_schema import (
    IndicadoresIngestaSchema, LecturaIngestaSchema, ListaIngestaSchema,
)

router = APIRouter(prefix="/iot/ingesta", tags=["Telemetría IoT - Ingesta"])

_RECURSO = 36  # modulo1.recursos: alertas técnicas IoT (operación de equipos)


@router.get(
    "",
    response_model=ListaIngestaSchema,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
    summary="Eventos de la bitácora de ingesta, paginados (RF-53)",
)
def listar_ingesta(
    desde: Optional[FechaHoraUtc] = Query(default=None, description="Por defecto, 24 h antes de `hasta`."),
    hasta: Optional[FechaHoraUtc] = Query(default=None, description="Por defecto, ahora. Rango máximo: 31 días."),
    estado_calidad: Optional[str] = Query(default=None),
    origen: Optional[str] = Query(default=None, description="TIEMPO_REAL | BUFFER_LOCAL | EDGE_AGREGADO"),
    id_dispositivo_iot: Optional[int] = Query(default=None, gt=0),
    id_sensor: Optional[int] = Query(default=None, gt=0),
    pagina: int = Query(default=1),
    por_pagina: int = Query(default=50),
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> ListaIngestaSchema:
    fincas = AlcanceFincaAdapter(db).listar_ids_fincas_permitidas(usuario_actual.id_usuario, usuario_actual.id_rol)
    items, total, f = ConsultarIngestaUseCase(SqlAlchemyIngestaRepository(db)).listar(
        ids_fincas=fincas, desde=desde, hasta=hasta, estado_calidad=estado_calidad, origen=origen,
        id_dispositivo_iot=id_dispositivo_iot, id_sensor=id_sensor, pagina=pagina, por_pagina=por_pagina,
    )
    return ListaIngestaSchema(
        items=[LecturaIngestaSchema.model_validate(i) for i in items], total=total,
        pagina=f.pagina, por_pagina=f.por_pagina, desde=f.desde, hasta=f.hasta,
    )


@router.get(
    "/indicadores",
    response_model=IndicadoresIngestaSchema,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
    summary="Indicadores de la ingesta de hoy (RF-53)",
)
def indicadores_ingesta(
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> IndicadoresIngestaSchema:
    fincas = AlcanceFincaAdapter(db).listar_ids_fincas_permitidas(usuario_actual.id_usuario, usuario_actual.id_rol)
    return IndicadoresIngestaSchema.model_validate(
        ConsultarIngestaUseCase(SqlAlchemyIngestaRepository(db)).indicadores_de_hoy(fincas))
