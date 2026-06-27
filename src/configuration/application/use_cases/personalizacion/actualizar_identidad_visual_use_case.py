"""Caso de uso: Actualizar identidad visual de una finca (PATCH RF-26).

Concurrencia optimista con campo ``version`` (entero).
Registra auditoría antes/después de la mutación.
"""
from __future__ import annotations

import os
import uuid
from typing import Optional

from sqlalchemy.orm import Session

from src.configuration.domain.entities.identidad_visual import IdentidadVisual
from src.configuration.domain.repositories.auditoria_identidad_visual_repository import AuditoriaIdentidadVisualRepository
from src.configuration.domain.repositories.identidad_visual_repository import IdentidadVisualRepository
from src.configuration.domain.value_objects.color_hex import ColorHex
from src.configuration.domain.value_objects.nombre_organizacion import NombreOrganizacion
from src.configuration.infrastructure.dto.actualizar_identidad_visual_dto import ActualizarIdentidadVisualDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import NotFoundError, PreconditionFailedError, ValidationError

_FORMATOS_PERMITIDOS = {"image/png", "image/jpeg", "image/svg+xml"}
_TAMANO_MAX = 2 * 1024 * 1024
_UPLOADS_DIR = "uploads/logos"
_EXT_MAP = {"image/png": ".png", "image/jpeg": ".jpg", "image/svg+xml": ".svg"}


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
            logo_path = self._guardar_logo(logo_bytes, logo_content_type)

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

    @staticmethod
    def _guardar_logo(logo_bytes: bytes, content_type: Optional[str]) -> str:
        if content_type not in _FORMATOS_PERMITIDOS:
            raise ValidationError(
                code="FORMATO_IMAGEN_NO_PERMITIDO",
                message=(
                    f"El logotipo debe estar en formato PNG, JPEG o SVG. "
                    f"Tipo recibido: '{content_type}'."
                ),
                field="logo",
            )
        if len(logo_bytes) > _TAMANO_MAX:
            raise ValidationError(
                code="TAMANO_IMAGEN_EXCEDIDO",
                message=f"El archivo supera el límite de 2 MB ({len(logo_bytes)/(1024*1024):.1f} MB recibidos).",
                field="logo",
            )
        os.makedirs(_UPLOADS_DIR, exist_ok=True)
        ext = _EXT_MAP.get(content_type, ".png")
        filename = f"{uuid.uuid4()}{ext}"
        path = os.path.join(_UPLOADS_DIR, filename)
        with open(path, "wb") as f:
            f.write(logo_bytes)
        return path
