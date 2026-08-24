"""Caso de uso: Editar patología por especie (Flujo F — RF-16).

Edita la entidad M09 en `especies_patologias` (nombre/descripción de esa especie).
Concurrencia optimista mediante ``fecha_actualizacion`` (FA-07). Unicidad de
nombre por especie (case-insensitive).
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.configuration.domain.entities.especie_patologia import EspeciePatologia
from src.configuration.domain.repositories.auditoria_patologia_repository import AuditoriaPatologiaRepository
from src.configuration.domain.repositories.especie_patologia_repository import EspeciePatologiaRepository
from src.configuration.domain.value_objects.nombre_patologia import NombrePatologia
from src.configuration.infrastructure.dto.editar_patologia_dto import EditarPatologiaDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import BusinessRuleError, ConflictError, NotFoundError, PreconditionFailedError


class EditarPatologiaUseCase:

    def __init__(
        self,
        db: Session,
        especie_patologia_repo: EspeciePatologiaRepository,
        auditoria_repo: AuditoriaPatologiaRepository,
    ) -> None:
        self.db = db
        self.especie_patologia_repo = especie_patologia_repo
        self.auditoria_repo = auditoria_repo

    def execute(
        self, id_especies_patologias: int, dto: EditarPatologiaDTO, usuario_actual: UsuarioActual
    ) -> EspeciePatologia:
        entidad = self.especie_patologia_repo.obtener_por_id(id_especies_patologias)
        if entidad is None:
            raise NotFoundError(
                code="PATOLOGIA_NO_ENCONTRADA",
                message=f"No existe una patología con ID {id_especies_patologias}.",
            )
        if not entidad.es_activo:
            raise BusinessRuleError(
                code="PATOLOGIA_INACTIVA",
                message="No se puede editar una patología inactiva.",
            )

        ts_actual = entidad.fecha_actualizacion
        ts_dto = dto.fecha_actualizacion
        if ts_actual is not None and ts_dto is not None:
            if ts_actual.astimezone(timezone.utc) != ts_dto.astimezone(timezone.utc):
                raise PreconditionFailedError(
                    code="CONFLICTO_CONCURRENCIA",
                    message="La patología fue modificada por otro usuario. Recargue los datos e intente de nuevo.",
                )
        elif ts_actual != ts_dto:
            raise PreconditionFailedError(
                code="CONFLICTO_CONCURRENCIA",
                message="La patología fue modificada por otro usuario. Recargue los datos e intente de nuevo.",
            )

        nombre_nuevo = NombrePatologia(dto.nombre)
        if nombre_nuevo.normalizado() != entidad.nombre.normalizado():
            duplicado = self.especie_patologia_repo.obtener_por_especie_y_nombre(
                entidad.id_especie, nombre_nuevo
            )
            if duplicado is not None and duplicado.id_especies_patologias != entidad.id_especies_patologias:
                raise ConflictError(
                    code="PATOLOGIA_DUPLICADA_EN_ESPECIE",
                    message=f"Ya existe una patología con el nombre '{nombre_nuevo.valor}' para esta especie.",
                    field="nombre",
                )

        snapshot_anterior = entidad._snapshot()
        entidad.actualizar(
            nombre=nombre_nuevo,
            descripcion=dto.descripcion,
            fecha_actualizacion=datetime.now(timezone.utc),
        )

        try:
            actualizada = self.especie_patologia_repo.actualizar(entidad)
            self.auditoria_repo.registrar(
                id_especies_patologias=actualizada.id_especies_patologias,
                id_usuario=usuario_actual.id_usuario,
                tipo_operacion="UPDATE",
                valores_anteriores=snapshot_anterior,
                valores_nuevos=actualizada._snapshot(),
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return actualizada
