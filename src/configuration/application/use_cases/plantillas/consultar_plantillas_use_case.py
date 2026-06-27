"""Caso de uso: Consultar plantillas de configuración e historial de aplicaciones (RF-30)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.configuration.domain.entities.aplicacion_plantilla import AplicacionPlantilla
from src.configuration.domain.entities.plantilla import Plantilla
from src.configuration.domain.repositories.aplicacion_plantilla_repository import AplicacionPlantillaRepository
from src.configuration.domain.repositories.plantilla_repository import PlantillaRepository


class ConsultarPlantillasUseCase:
    """Lista plantillas disponibles y el historial de aplicaciones."""

    def __init__(
        self,
        db: Session,
        plantilla_repo: PlantillaRepository,
        aplicacion_repo: AplicacionPlantillaRepository,
    ) -> None:
        self.db = db
        self.plantilla_repo = plantilla_repo
        self.aplicacion_repo = aplicacion_repo

    def listar_plantillas(self) -> list[Plantilla]:
        return self.plantilla_repo.listar_todas()

    def obtener_plantilla(self, id_plantilla: int) -> Plantilla | None:
        return self.plantilla_repo.obtener_por_id(id_plantilla)

    def listar_historial(self) -> list[AplicacionPlantilla]:
        return self.aplicacion_repo.listar_todas()
