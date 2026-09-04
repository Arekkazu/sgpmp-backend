"""Caso de uso: Generar la versión siguiente de una plantilla (RF-30, RF-31).

Las plantillas son inmutables: el RF resuelve la actualización creando una
versión nueva con número incremental, nunca sobrescribiendo la anterior. Este
caso de uso es esa operación, separada de la creación para que un nombre
repetido en `RegistrarPlantillaUseCase` pueda rechazarse con `409` sin que el
usuario pierda la forma de versionar.

La versión nueva hereda nombre y especie de la anterior; lo único que cambia
son los parámetros.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.configuration.domain.entities.plantilla import Plantilla
from src.configuration.domain.esquema_plantilla import SCHEMA_VERSION_ACTUAL, claves_fuera_de_alcance
from src.configuration.domain.repositories.auditoria_plantilla_repository import AuditoriaPlantillaRepository
from src.configuration.domain.repositories.especie_repository import EspecieRepository
from src.configuration.domain.repositories.plantilla_repository import PlantillaRepository
from src.configuration.infrastructure.dto.versionar_plantilla_dto import VersionarPlantillaDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import BusinessRuleError, NotFoundError


class VersionarPlantillaUseCase:
    """Crea la versión N+1 de una plantilla existente."""

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

    def execute(
        self, id_plantilla: int, dto: VersionarPlantillaDTO, usuario_actual: UsuarioActual
    ) -> Plantilla:
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

        base = self.plantilla_repo.obtener_por_id(id_plantilla)
        if base is None:
            raise NotFoundError(
                code="PLANTILLA_NO_ENCONTRADA",
                message=f"No existe la plantilla con id {id_plantilla}.",
            )

        # La especie pudo desactivarse entre una versión y la siguiente.
        especie = self.especie_repo.obtener_por_id(base.id_especie)
        if especie is None or not especie.es_activo:
            raise BusinessRuleError(
                code="ESPECIE_INACTIVA",
                message=(
                    "No se puede versionar una plantilla cuya especie asociada "
                    "no está disponible o fue desactivada."
                ),
                field="id_especie",
            )

        snapshot = dict(dto.params_snapshot)
        snapshot['schema_version'] = SCHEMA_VERSION_ACTUAL

        nueva = Plantilla.crear(
            id_especie=base.id_especie,
            id_usuario=usuario_actual.id_usuario,
            template_name=base.template_name,
            params_snapshot=snapshot,
            # Intención; el número definitivo lo fija el trigger
            # `trg_fn_plantilla_version_incremental` dentro de la transacción,
            # así dos versionados simultáneos no reclaman el mismo número.
            version=base.version + 1,
            fecha_creacion=datetime.now(timezone.utc),
        )

        try:
            guardada = self.plantilla_repo.guardar(nueva)
            self.auditoria_repo.registrar(
                id_plantilla=guardada.id_plantilla,
                id_usuario=usuario_actual.id_usuario,
                tipo_operacion="CREATE",
                valores_nuevos=guardada._snapshot(),
                valores_anteriores=base._snapshot(),
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return guardada
