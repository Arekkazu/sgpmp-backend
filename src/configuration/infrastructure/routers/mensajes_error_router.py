# | Fecha      | Nombre   | Que se hizo                                                   |
# |------------|----------|---------------------------------------------------------------|
# | 2026-11-18 | Arekkazu | M08 RF-107 RNF-03: catálogo de mensajes de error configurable |
"""Router del catálogo de mensajes de error (`/configuracion/mensajes-error`, RF-107 RNF-03).

  GET    /configuracion/mensajes-error?idioma=        — autenticado (el front lo guarda y traduce los errores)
  PUT    /configuracion/mensajes-error/{clave}        — crea o reemplaza (U sobre ``catalogo_mensajes_error``)
  DELETE /configuracion/mensajes-error/{clave}?idioma= — elimina (D sobre ``catalogo_mensajes_error``)
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Path, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.configuration.application.use_cases.mensajes_error.eliminar_mensaje_error_use_case import (
    EliminarMensajeErrorUseCase,
)
from src.configuration.application.use_cases.mensajes_error.guardar_mensaje_error_use_case import (
    GuardarMensajeErrorUseCase,
)
from src.configuration.application.use_cases.mensajes_error.listar_mensajes_error_use_case import (
    ListarMensajesErrorUseCase,
)
from src.configuration.infrastructure.repositories.catalogo_mensajes_error_repository import (
    SqlAlchemyCatalogoMensajesErrorRepository,
)
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared.base_dto import BaseDTO
from src.shared.database import get_db
from src.shared.rbac import require_permission_sobre
from src.shared.schemas import ErrorResponse

router = APIRouter(prefix="/configuracion/mensajes-error", tags=["Configuración - Mensajes de error (RF-107)"])

Idioma = Literal["es-CO", "en-US"]
_CLAVE = Path(pattern=r"^[A-Z0-9_]{2,80}$", description="Clave del error, por ejemplo PERIODO_NO_CERRADO")


class MensajeErrorDTO(BaseDTO):
    idioma: Idioma = "es-CO"
    mensaje: str = Field(min_length=5, max_length=500)
    texto_accion: Optional[str] = Field(default=None, max_length=80)
    ruta_accion: Optional[str] = Field(default=None, max_length=200,
                                       description="Ruta interna del front, por ejemplo «finanzas»")
    es_activo: bool = True


class MensajeErrorResponse(BaseModel):
    clave: str
    idioma: str
    mensaje: str
    texto_accion: Optional[str] = None
    ruta_accion: Optional[str] = None
    es_activo: bool
    fecha_actualizacion: Optional[datetime] = None


@router.get("", response_model=list[MensajeErrorResponse], responses={401: {"model": ErrorResponse}},
            summary="Catálogo de mensajes de error (RF-107)")
def listar(idioma: Optional[Idioma] = Query(None), db: Session = Depends(get_db),
           _: UsuarioActual = Depends(get_current_user)):
    """**Acceso:** autenticado. Incluye los inactivos (el front solo usa los activos)."""
    return [MensajeErrorResponse(**m.__dict__) for m in
            ListarMensajesErrorUseCase(SqlAlchemyCatalogoMensajesErrorRepository(db)).execute(idioma)]


@router.put("/{clave}", response_model=MensajeErrorResponse,
            dependencies=[Depends(require_permission_sobre("catalogo_mensajes_error", 3))],
            responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
            summary="Crear o editar un mensaje del catálogo (RF-107)")
def guardar(dto: MensajeErrorDTO, clave: str = _CLAVE, db: Session = Depends(get_db),
            usuario_actual: UsuarioActual = Depends(get_current_user)):
    """**Acceso:** `catalogo_mensajes_error` · Actualizar (Administrador). El botón necesita texto y ruta interna
    juntos (400 si falta uno o si la ruta no es del sistema)."""
    m = GuardarMensajeErrorUseCase(db, SqlAlchemyCatalogoMensajesErrorRepository(db)).execute(
        clave, dto.idioma, dto.mensaje, dto.texto_accion, dto.ruta_accion, dto.es_activo, usuario_actual.id_usuario)
    return MensajeErrorResponse(**m.__dict__)


@router.delete("/{clave}", status_code=204,
               dependencies=[Depends(require_permission_sobre("catalogo_mensajes_error", 4))],
               responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
               summary="Eliminar un mensaje del catálogo (RF-107)")
def eliminar(clave: str = _CLAVE, idioma: Idioma = Query("es-CO"), db: Session = Depends(get_db),
             _: UsuarioActual = Depends(get_current_user)):
    """**Acceso:** `catalogo_mensajes_error` · Eliminar (Administrador). No existe → 404."""
    EliminarMensajeErrorUseCase(db, SqlAlchemyCatalogoMensajesErrorRepository(db)).execute(clave, idioma)
    return Response(status_code=204)
