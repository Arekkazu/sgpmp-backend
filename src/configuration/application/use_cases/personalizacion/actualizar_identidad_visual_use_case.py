"""Caso de uso: Actualizar identidad visual de una finca (PATCH RF-26).

Concurrencia optimista con campo ``version`` (entero).
Registra auditoría antes/después de la mutación.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from src.configuration.domain.entities.identidad_visual import IdentidadVisual
from src.configuration.domain.repositories.auditoria_identidad_visual_repository import AuditoriaIdentidadVisualRepository
from src.configuration.domain.repositories.identidad_visual_repository import IdentidadVisualRepository
from src.configuration.domain.value_objects.color_hex import ColorHex
from src.configuration.domain.value_objects.nombre_organizacion import NombreOrganizacion
from src.configuration.infrastructure.dto.actualizar_identidad_visual_dto import ActualizarIdentidadVisualDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.almacen_logos import guardar_logo
from src.shared.errors import NotFoundError, PreconditionFailedError


class ActualizarIdentidadVisualUseCase:

    def __init__(
        self,
        db: Session,
        identidad_repo: IdentidadVisualRepository,
        auditoria_repo: AuditoriaIdentidadVisualRepository,
    ) -> None:
        self.db = db
        self.identidad_repo = identidad_repo
        self.auditoria_repo = auditoria_repo

    def execute(
        self,
        id_finca: int,
        dto: ActualizarIdentidadVisualDTO,
        logo_bytes: Optional[bytes],
        logo_content_type: Optional[str],
        usuario_actual: UsuarioActual,
    ) -> IdentidadVisual:
        entidad = self.identidad_repo.obtener_por_finca(id_finca)
        if entidad is None:
            raise NotFoundError(
                code="IDENTIDAD_VISUAL_NO_ENCONTRADA",
                message=f"No existe identidad visual registrada para la finca {id_finca}.",
            )

        if (entidad.version or 0) != dto.version:
            raise PreconditionFailedError(
                code="CONFLICTO_CONCURRENCIA",
                message="La identidad visual fue modificada por otro usuario. Recarga y reintenta.",
            )

        logo_path = None
        if logo_bytes:
            logo_path = guardar_logo(logo_bytes, logo_content_type)

        snapshot_anterior = entidad._snapshot()

        entidad.actualizar(
            id_usuario=usuario_actual.id_usuario,
            logo_path=logo_path,
            primary_color=ColorHex(dto.primary_color),
            secondary_color=ColorHex(dto.secondary_color),
            org_display_name=NombreOrganizacion(dto.org_display_name),
        )

        try:
            actualizada = self.identidad_repo.actualizar(entidad)
            self.auditoria_repo.registrar(
                id_usuario=usuario_actual.id_usuario,
                valor_anterior=snapshot_anterior,
                valor_nuevo=actualizada._snapshot(),
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return actualizada
