"""Caso de uso: Crear una plantilla de configuración reutilizable (RF-31).

Toma los parámetros productivos de una especie origen (proporcionados en el
dto.params_snapshot) y los guarda como un snapshot versionado inmutable.

Esta operación crea plantillas **nuevas**: un nombre ya registrado se rechaza
con `409`, como exigen el FA "Nombre de plantilla duplicado" y el criterio de
aceptación "el sistema rechaza la creación de una plantilla con un nombre ya
existente" de RF-30 y RF-31. Generar la versión siguiente de una plantilla que
ya existe es otra intención y tiene su propio caso de uso
(`VersionarPlantillaUseCase`), para que nadie versione sin querer por repetir
un nombre.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.configuration.domain.entities.plantilla import Plantilla
from src.configuration.domain.esquema_plantilla import (
    SCHEMA_VERSION_ACTUAL,
    claves_fuera_de_alcance,
    validar_rangos_fisicos_umbrales,
)
from src.configuration.domain.repositories.auditoria_plantilla_repository import AuditoriaPlantillaRepository
from src.configuration.domain.repositories.especie_repository import EspecieRepository
from src.configuration.domain.repositories.plantilla_repository import PlantillaRepository
from src.configuration.domain.repositories.variable_ambiental_repository import VariableAmbientalRepository
from src.configuration.infrastructure.dto.registrar_plantilla_dto import RegistrarPlantillaDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import BusinessRuleError, ConflictError, NotFoundError


class RegistrarPlantillaUseCase:
    """Crea una plantilla con versión auto-incrementada para el template_name dado."""

    def __init__(
        self,
        db: Session,
        plantilla_repo: PlantillaRepository,
        especie_repo: EspecieRepository,
        auditoria_repo: AuditoriaPlantillaRepository,
        variable_repo: VariableAmbientalRepository,
    ) -> None:
        self.db = db
        self.plantilla_repo = plantilla_repo
        self.especie_repo = especie_repo
        self.auditoria_repo = auditoria_repo
        self.variable_repo = variable_repo

    def execute(self, dto: RegistrarPlantillaDTO, usuario_actual: UsuarioActual) -> Plantilla:
        # Alcance antes que nada: el RF-30 le da a este caso su propio código
        # (422), distinto del 400 con que se rechaza un fallo de esquema. Por
        # eso no vive en el DTO, que solo puede producir 400.
        fuera_de_alcance = claves_fuera_de_alcance(dto.params_snapshot)
        if fuera_de_alcance:
            raise BusinessRuleError(
                code="ALCANCE_NO_PERMITIDO",
                message=(
                    "Alcance no permitido: las plantillas solo pueden contener parámetros "
                    "productivos y umbrales ambientales. Se han detectado configuraciones "
                    f"de {fuera_de_alcance} que deben ser removidas."
                ),
                field="params_snapshot",
            )

        if self.plantilla_repo.existe_nombre(dto.template_name):
            raise ConflictError(
                code="NOMBRE_PLANTILLA_DUPLICADO",
                message=(
                    f"Nombre no disponible: ya existe una plantilla denominada "
                    f"'{dto.template_name}'. Asigne un nombre único, o genere una nueva "
                    "versión de la plantilla existente."
                ),
                field="template_name",
            )

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

        validar_rangos_fisicos_umbrales(dto.params_snapshot, self.variable_repo)

        snapshot = dict(dto.params_snapshot)
        snapshot['schema_version'] = SCHEMA_VERSION_ACTUAL

        plantilla = Plantilla.crear(
            id_especie=dto.id_especie,
            id_usuario=usuario_actual.id_usuario,
            template_name=dto.template_name,
            params_snapshot=snapshot,
            # Versión inicial que exige el RF-31. El número definitivo lo fija
            # el trigger `trg_fn_plantilla_version_incremental` dentro de la
            # transacción, y `guardar()` lo devuelve tras el refresh: así dos
            # inserts simultáneos no pueden reclamar la misma versión.
            version=1,
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
