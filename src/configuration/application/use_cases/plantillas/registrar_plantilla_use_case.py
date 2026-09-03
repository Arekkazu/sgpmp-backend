"""Caso de uso: Crear una plantilla de configuración reutilizable (RF-31).

Toma los parámetros productivos de una especie origen (proporcionados en el
dto.params_snapshot) y los guarda como un snapshot versionado inmutable.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.configuration.domain.entities.plantilla import Plantilla
from src.configuration.domain.esquema_plantilla import SCHEMA_VERSION_ACTUAL
from src.configuration.domain.repositories.auditoria_plantilla_repository import AuditoriaPlantillaRepository
from src.configuration.domain.repositories.especie_repository import EspecieRepository
from src.configuration.domain.repositories.plantilla_repository import PlantillaRepository
from src.configuration.infrastructure.dto.registrar_plantilla_dto import RegistrarPlantillaDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import BusinessRuleError, NotFoundError


class RegistrarPlantillaUseCase:
    """Crea una plantilla con versión auto-incrementada para el template_name dado."""

    def __init__(
        self,
        db: Session,
        plantilla_repo: PlantillaRepository,
        especie_repo: EspecieRepository,
        auditoria_repo: AuditoriaPlantillaRepository,
    ) -> None:
        self.db = db
        self.plantilla_repo = plantilla_repo
        self.especie_repo = especie_repo
        self.auditoria_repo = auditoria_repo

    def execute(self, dto: RegistrarPlantillaDTO, usuario_actual: UsuarioActual) -> Plantilla:
        especie = self.especie_repo.obtener_por_id(dto.id_especie)
        if especie is None:
            raise NotFoundError(
                code="ESPECIE_NO_ENCONTRADA",
                message=f"No existe la especie con id {dto.id_especie}.",
            )
        if not especie.es_activo:
            raise BusinessRuleError(
                code="ESPECIE_INACTIVA",
                message="No se puede crear una plantilla a partir de una especie inactiva.",
                field="id_especie",
            )

        snapshot = dict(dto.params_snapshot)
        snapshot['schema_version'] = SCHEMA_VERSION_ACTUAL

        version_max = self.plantilla_repo.obtener_version_maxima(dto.template_name)
        version = (version_max or 0) + 1

        plantilla = Plantilla.crear(
            id_especie=dto.id_especie,
            id_usuario=usuario_actual.id_usuario,
            template_name=dto.template_name,
            params_snapshot=snapshot,
            version=version,
            fecha_creacion=datetime.now(timezone.utc),
        )

        try:
            guardada = self.plantilla_repo.guardar(plantilla)
            self.auditoria_repo.registrar(
                id_plantilla=guardada.id_plantilla,
                id_usuario=usuario_actual.id_usuario,
                tipo_operacion="CREATE",
                valores_nuevos=guardada._snapshot(),
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return guardada
