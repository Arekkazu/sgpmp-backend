"""Caso de uso: Editar patología del catálogo (Flujo F — RF-16).

Edita el registro global en ``modulo9.patologias``.
Concurrencia optimista mediante ``fecha_actualizacion`` (FA-07).
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.configuration.domain.entities.patologia import Patologia
from src.configuration.domain.repositories.auditoria_patologia_repository import AuditoriaPatologiaRepository
from src.configuration.domain.repositories.patologia_repository import PatologiaRepository
from src.configuration.domain.value_objects.nombre_patologia import NombrePatologia
from src.configuration.infrastructure.dto.editar_patologia_dto import EditarPatologiaDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import BusinessRuleError, ConflictError, NotFoundError, PreconditionFailedError


def _snapshot(patologia: Patologia) -> dict:
    return {
        "id_patologia": patologia.id_patologia,
        "nombre": patologia.nombre.valor,
        "descripcion": patologia.descripcion,
        "es_activo": patologia.es_activo,
        "fecha_actualizacion": patologia.fecha_actualizacion.isoformat() if patologia.fecha_actualizacion else None,
    }


class EditarPatologiaUseCase:

    def __init__(
        self,
        db: Session,
        patologias_repo: PatologiaRepository,
        auditoria_repo: AuditoriaPatologiaRepository,
    ) -> None:
        self.db = db
        self.patologias_repo = patologias_repo
        self.auditoria_repo = auditoria_repo

    def execute(self, id_patologia: int, dto: EditarPatologiaDTO, usuario_actual: UsuarioActual) -> Patologia:
        patologia = self.patologias_repo.obtener_por_id(id_patologia)
        if patologia is None:
            raise NotFoundError(
                code="PATOLOGIA_NO_ENCONTRADA",
                message=f"No existe una patología con ID {id_patologia}.",
            )
        if not patologia.es_activo:
            raise BusinessRuleError(
                code="PATOLOGIA_INACTIVA",
                message="No se puede editar una patología inactiva.",
            )

        ts_actual = patologia.fecha_actualizacion
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
        if nombre_nuevo.normalizado() != patologia.nombre.normalizado():
            duplicado = self.patologias_repo.obtener_por_nombre(nombre_nuevo)
            if duplicado is not None and duplicado.id_patologia != patologia.id_patologia:
                raise ConflictError(
                    code="PATOLOGIA_DUPLICADA",
                    message=f"El nombre '{nombre_nuevo.valor}' ya existe en el catálogo de patologías.",
                    field="nombre",
                )

        snapshot_anterior = _snapshot(patologia)
        patologia.actualizar(
            nombre=nombre_nuevo,
            descripcion=dto.descripcion,
            fecha_actualizacion=datetime.now(timezone.utc),
        )

        try:
            patologia_actualizada = self.patologias_repo.actualizar(patologia)
            self.auditoria_repo.registrar(
                id_patologia=patologia_actualizada.id_patologia,
                id_usuario=usuario_actual.id_usuario,
                tipo_operacion="UPDATE",
                valores_anteriores=snapshot_anterior,
                valores_nuevos=_snapshot(patologia_actualizada),
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return patologia_actualizada
