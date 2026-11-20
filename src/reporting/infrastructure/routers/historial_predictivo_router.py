# | Fecha      | Nombre   | Que se hizo                                                  |
# |------------|----------|--------------------------------------------------------------|
# | 2026-11-18 | Arekkazu | M08 RF-106: endpoint del historial clínico predictivo        |
"""Router FastAPI del historial clínico predictivo (`/historial-predictivo`, RF-106).

  GET /historial-predictivo/{id_activo_biologico} — predicciones, eventos sanitarios, retroalimentaciones, TVCO,
      correspondencias, colisiones y pendientes de evaluar.

RBAC: recurso ``historial_clinico_predictivo`` · Leer (Veterinario y Administrador; 403 para los demás, CA-6).
"""
from __future__ import annotations

from datetime import date
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.reporting.application.use_cases.historial.consultar_historial_predictivo_use_case import (
    ConsultarHistorialPredictivoUseCase,
)
from src.reporting.infrastructure.adapters.instantanea_reportes import abrir_instantanea
from src.reporting.infrastructure.adapters.solicitante_reportes import construir_solicitante
from src.shared.database import get_db
from src.shared.fechas import nombre_zona_usuario
from src.shared.errors import ValidationError
from src.shared.rbac import require_permission_sobre
from src.shared.schemas import ErrorResponse

router = APIRouter(prefix="/historial-predictivo", tags=["Historial clínico predictivo (RF-106)"])


@router.get(
    "/{id_activo_biologico}",
    dependencies=[Depends(require_permission_sobre("historial_clinico_predictivo", 2))],
    responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 403: {"model": ErrorResponse},
               404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
    summary="Historial clínico predictivo de un animal (RF-106)",
)
def historial_predictivo(
    id_activo_biologico: int,
    fecha_inicio: Optional[date] = Query(None, description="Por defecto: 12 meses antes de la fecha de fin"),
    fecha_fin: Optional[date] = Query(None, description="Por defecto: hoy"),
    nivel_riesgo: Optional[list[int]] = Query(None, description="0 Ninguno, 1 Bajo, 2 Medio, 3 Alto"),
    modo_visualizacion: Literal["LINEAL", "AGRUPADO"] = Query("LINEAL"),
    incluir_eventos_sanitarios: bool = Query(True),
    incluir_retroalimentacion: bool = Query(True),
    pagina_pendientes: int = Query(1, ge=1),
    db: Session = Depends(get_db),
    usuario_actual: UsuarioActual = Depends(get_current_user),
) -> dict[str, Any]:
    """Rango máximo de 24 meses (400). Animal de otra finca → 403; inexistente → 404; dado de baja → 422.
    Si una de las tres fuentes falla, responde con las demás y la nombra en `fuentes_no_disponibles`."""
    if nivel_riesgo and any(n not in (0, 1, 2, 3) for n in nivel_riesgo):
        raise ValidationError(code="VAL_ENTRADA", field="nivel_riesgo",
                              message="El nivel de riesgo debe ser 0 (ninguno), 1 (bajo), 2 (medio) o 3 (alto).")
    solicitante = construir_solicitante(db, usuario_actual.id_usuario, usuario_actual.id_rol, nombre_zona_usuario())
    resultado = ConsultarHistorialPredictivoUseCase(abrir_instantanea).execute(
        id_activo_biologico, solicitante, fecha_inicio=fecha_inicio, fecha_fin=fecha_fin, niveles=nivel_riesgo,
        incluir_eventos=incluir_eventos_sanitarios, incluir_retroalimentacion=incluir_retroalimentacion,
        pagina=pagina_pendientes)
    return {**resultado, "modo_visualizacion": modo_visualizacion}
