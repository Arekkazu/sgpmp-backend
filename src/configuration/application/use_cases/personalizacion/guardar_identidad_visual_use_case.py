"""Caso de uso: Crear identidad visual institucional de una finca (POST RF-26).

Valida que no exista ya una identidad para la finca (409 si ya existe).
Guarda el logo en disco si se proporciona.
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
from src.configuration.infrastructure.dto.guardar_identidad_visual_dto import GuardarIdentidadVisualDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import ConflictError, ValidationError

_FORMATOS_PERMITIDOS = {"image/png", "image/jpeg", "image/svg+xml"}
_TAMANO_MAX = 2 * 1024 * 1024  # 2 MB
_UPLOADS_DIR = "uploads/logos"

_EXT_MAP = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/svg+xml": ".svg",
}


class GuardarIdentidadVisualUseCase:

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
        dto: GuardarIdentidadVisualDTO,
        logo_bytes: Optional[bytes],
        logo_content_type: Optional[str],
        usuario_actual: UsuarioActual,
    ) -> IdentidadVisual:
        existente = self.identidad_repo.obtener_por_finca(dto.id_finca)
        if existente is not None:
            raise ConflictError(
                code="IDENTIDAD_VISUAL_EXISTENTE",
                message=(
                    "Ya existe una identidad visual para esta finca. "
                    "Utilice el método de actualización para modificar los valores vigentes."
                ),
            )

        logo_path = self._guardar_logo(logo_bytes, logo_content_type) if logo_bytes else None

        entidad = IdentidadVisual.crear(
            id_finca=dto.id_finca,
            id_usuario=usuario_actual.id_usuario,
            logo_path=logo_path,
            primary_color=ColorHex(dto.primary_color),
            secondary_color=ColorHex(dto.secondary_color),
            org_display_name=NombreOrganizacion(dto.org_display_name),
        )

        try:
            guardada = self.identidad_repo.guardar(entidad)
            self.auditoria_repo.registrar(
                id_usuario=usuario_actual.id_usuario,
                valor_anterior={},
                valor_nuevo=guardada._snapshot(),
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return guardada

    @staticmethod
    def _guardar_logo(logo_bytes: bytes, content_type: Optional[str]) -> str:
        if content_type not in _FORMATOS_PERMITIDOS:
            raise ValidationError(
                code="FORMATO_IMAGEN_NO_PERMITIDO",
                message=(
                    f"Archivo no admitido. El logotipo debe estar en formato PNG, JPEG o SVG. "
                    f"Tipo recibido: '{content_type}'."
                ),
                field="logo",
            )
        if len(logo_bytes) > _TAMANO_MAX:
            raise ValidationError(
                code="TAMANO_IMAGEN_EXCEDIDO",
                message=(
                    f"El archivo de imagen supera el límite de 2 MB "
                    f"({len(logo_bytes) / (1024*1024):.1f} MB recibidos)."
                ),
                field="logo",
            )
        os.makedirs(_UPLOADS_DIR, exist_ok=True)
        ext = _EXT_MAP.get(content_type, ".png")
        filename = f"{uuid.uuid4()}{ext}"
        path = os.path.join(_UPLOADS_DIR, filename)
        with open(path, "wb") as f:
            f.write(logo_bytes)
        return path
