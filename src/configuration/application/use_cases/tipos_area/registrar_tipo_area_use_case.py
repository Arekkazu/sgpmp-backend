"""Caso de uso: Registrar nuevo tipo de área en el catálogo (RF-20).

Solo el Administrador puede registrar tipos de área nuevos.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.configuration.domain.entities.tipo_area import TipoArea
from src.configuration.domain.repositories.tipo_area_repository import TipoAreaRepository
from src.configuration.infrastructure.dto.registrar_tipo_area_dto import RegistrarTipoAreaDTO
from src.shared.errors import ConflictError


class RegistrarTipoAreaUseCase:
    """Registra un tipo de área nuevo en el catálogo."""

    def __init__(self, db: Session, tipo_area_repo: TipoAreaRepository) -> None:
        self.db = db
        self.tipo_area_repo = tipo_area_repo

    def execute(self, dto: RegistrarTipoAreaDTO) -> TipoArea:
        existente = self.tipo_area_repo.obtener_por_nombre(dto.nombre)
        if existente is not None:
            raise ConflictError(
                code="TIPO_AREA_DUPLICADO",
                message=f"El tipo de área '{dto.nombre}' ya se encuentra registrado en el catálogo.",
                field="nombre",
            )

        tipo_area = TipoArea.crear(nombre=dto.nombre, fecha_creacion=datetime.now(timezone.utc))

        try:
            tipo_area_guardado = self.tipo_area_repo.guardar(tipo_area)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return tipo_area_guardado
