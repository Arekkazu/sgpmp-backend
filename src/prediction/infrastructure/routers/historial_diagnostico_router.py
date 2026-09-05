"""Router FastAPI para el historial diagnóstico M04 (`/prediccion/historial`).

RF-67 CU-04: consulta paginada por cursor del historial diagnóstico de un activo biológico.
  GET /prediccion/historial/{id_activo_biologico}

Autorización RBAC:
  recurso historial_diagnostico = id_recurso 42
  R=2 (Administrador, Veterinario, Productor)
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.prediction.application.use_cases.historial_diagnostico.consultar_historial_use_case import ConsultarHistorialUseCase
from src.prediction.infrastructure.adapters.activo_biologico_stub_adapter import ActivoBiologicoStubAdapter
from src.prediction.infrastructure.repositories.evento_auditoria_m04_repository import SqlAlchemyEventoAuditoriaM04Repository
from src.prediction.infrastructure.repositories.historial_diagnostico_repository import SqlAlchemyHistorialDiagnosticoRepository
from src.prediction.infrastructure.schema.historial_diagnostico_schema import HistorialDiagnosticoResponse
from src.shared.database import get_db
from src.shared.rbac import require_permission
from src.shared.schemas import ErrorResponse

router = APIRouter(prefix="/prediccion/historial", tags=["Predicción M04 - Historial Diagnóstico"])

_RECURSO = 42


@router.get(
    "/{id_activo_biologico}",
    response_model=HistorialDiagnosticoResponse,
    dependencies=[Depends(require_permission(_RECURSO, 2))],
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
    summary="Consultar historial diagnóstico de un activo biológico (RF-67)",
)
def consultar_historial(
    id_activo_biologico: int,
    fecha_inicio: date = Query(..., description="Límite inferior del rango de consulta (YYYY-MM-DD)."),
    fecha_fin: date = Query(..., description="Límite superior del rango de consulta (YYYY-MM-DD)."),
    nivel_riesgo: Optional[int] = Query(None, ge=0, le=3, description="Filtrar por nivel de riesgo (0-3)."),
    id_patologia: Optional[int] = Query(None, description="Filtrar por ID de patología del catálogo."),
    incluir_alertas: bool = Query(False, description="Si true, superpone alertas correlacionadas por id_resultado_inferencia."),
    cursor_paginacion: Optional[str] = Query(None, description="Token de paginación basado en (fecha_inferencia, id_resultado_inferencia)."),
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> HistorialDiagnosticoResponse:
    use_case = ConsultarHistorialUseCase(
        db=db,
        repo=SqlAlchemyHistorialDiagnosticoRepository(db),
        auditoria_repo=SqlAlchemyEventoAuditoriaM04Repository(db),
        activo_port=ActivoBiologicoStubAdapter(),
    )
    pagina = use_case.execute(
        id_activo_biologico=id_activo_biologico,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        nivel_riesgo=nivel_riesgo,
        id_patologia=id_patologia,
        incluir_alertas=incluir_alertas,
        cursor_paginacion=cursor_paginacion,
        id_usuario=usuario_actual.id_usuario,
        id_rol=usuario_actual.id_rol,
    )
    return HistorialDiagnosticoResponse.from_pagina(pagina)
