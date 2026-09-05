"""Caso de uso: Registrar patología por especie (Flujo E — RF-16).

La patología se crea como entidad **propia de M09** en `especies_patologias`, con
nombre único por especie (case-insensitive). No se escribe el catálogo clínico
M04 (`modulo9.patologias`): el vínculo ``id_patologia`` queda en ``None``.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.configuration.domain.entities.especie_patologia import EspeciePatologia
from src.configuration.domain.repositories.auditoria_patologia_repository import AuditoriaPatologiaRepository
from src.configuration.domain.repositories.especie_patologia_repository import EspeciePatologiaRepository
from src.configuration.domain.repositories.especie_repository import EspecieRepository
from src.configuration.domain.value_objects.nombre_patologia import NombrePatologia
from src.configuration.infrastructure.dto.registrar_patologia_dto import RegistrarPatologiaDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import BusinessRuleError, ConflictError, NotFoundError


class RegistrarPatologiaUseCase:

    def __init__(
        self,
        db: Session,
        especie_patologia_repo: EspeciePatologiaRepository,
        especies_repo: EspecieRepository,
        auditoria_repo: AuditoriaPatologiaRepository,
    ) -> None:
        self.db = db
        self.especie_patologia_repo = especie_patologia_repo
        self.especies_repo = especies_repo
        self.auditoria_repo = auditoria_repo

    def execute(self, dto: RegistrarPatologiaDTO, usuario_actual: UsuarioActual) -> EspeciePatologia:
        especie = self.especies_repo.obtener_por_id(dto.id_especie)
        if especie is None:
            raise NotFoundError(
                code="ESPECIE_NO_ENCONTRADA",
                message=f"No existe una especie con ID {dto.id_especie}.",
            )
        if not especie.es_activo:
            raise BusinessRuleError(
                code="ESPECIE_INACTIVA",
                message=f"La especie con ID {dto.id_especie} está inactiva.",
            )

        nombre = NombrePatologia(dto.nombre)
        if self.especie_patologia_repo.obtener_por_especie_y_nombre(dto.id_especie, nombre) is not None:
            raise ConflictError(
                code="PATOLOGIA_DUPLICADA_EN_ESPECIE",
                message=f"Ya existe una patología con el nombre '{nombre.valor}' para esta especie.",
                field="nombre",
            )

        entidad = EspeciePatologia.crear(
            id_especie=dto.id_especie,
            nombre=nombre,
            descripcion=dto.descripcion,
        )

        try:
            guardada = self.especie_patologia_repo.guardar(entidad)
            self.auditoria_repo.registrar(
                id_especies_patologias=guardada.id_especies_patologias,
                id_usuario=usuario_actual.id_usuario,
                tipo_operacion="CREATE",
                valores_nuevos=guardada._snapshot(),
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return guardada
