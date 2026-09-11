"""Caso de uso: Desactivar tipo de área del catálogo (RF-20).

Solo el Administrador puede desactivar. Desactivar solo oculta el tipo de las
nuevas áreas a registrar; las áreas ya existentes conservan su ``tipo`` como
texto congelado, sin ningún guard de dependencias (a diferencia de las áreas
productivas, RF-20 no exige bloquear la desactivación del tipo).
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.configuration.domain.entities.tipo_area import TipoArea
from src.configuration.domain.repositories.tipo_area_repository import TipoAreaRepository
from src.shared.errors import BusinessRuleError, NotFoundError


class DesactivarTipoAreaUseCase:
    """Realiza la baja lógica de un tipo de área activo."""

    def __init__(self, db: Session, tipo_area_repo: TipoAreaRepository) -> None:
        self.db = db
        self.tipo_area_repo = tipo_area_repo

    def execute(self, id_tipo_area: int) -> TipoArea:
        tipo_area = self.tipo_area_repo.obtener_por_id(id_tipo_area)
        if tipo_area is None:
            raise NotFoundError(
                code="TIPO_AREA_NO_ENCONTRADO",
                message=f"No existe un tipo de área con ID {id_tipo_area}.",
            )

        if not tipo_area.es_activo:
            raise BusinessRuleError(
                code="TIPO_AREA_YA_INACTIVO",
                message="El tipo de área ya se encuentra inactivo.",
            )

        tipo_area.desactivar()
        tipo_area.fecha_actualizacion = datetime.now(timezone.utc)

        try:
            tipo_area_actualizado = self.tipo_area_repo.actualizar(tipo_area)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return tipo_area_actualizado
