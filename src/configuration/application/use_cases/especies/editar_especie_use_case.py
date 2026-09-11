"""Caso de uso: Editar especie existente del catálogo (Flujo B — RF-15).

Administrador e Ingeniero de Campo pueden editar. Concurrencia optimista
mediante ``fecha_actualizacion``: si el valor enviado difiere del almacenado,
la especie fue modificada por otro usuario y se rechaza la operación (412).
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.configuration.domain.entities.especie import Especie
from src.configuration.domain.repositories.auditoria_especie_repository import AuditoriaEspecieRepository
from src.configuration.domain.repositories.especie_repository import EspecieRepository
from src.configuration.domain.value_objects.nombre_especie import NombreEspecie
from src.configuration.infrastructure.dto.editar_especie_dto import EditarEspecieDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import BusinessRuleError, ConflictError, NotFoundError, PreconditionFailedError


def _snapshot(especie: Especie) -> dict:
    return {
        "id_especie": especie.id_especie,
        "nombre": especie.nombre.valor,
        "descripcion": especie.descripcion,
        "es_activo": especie.es_activo,
        "fecha_creacion": especie.fecha_creacion.isoformat() if especie.fecha_creacion else None,
        "fecha_actualizacion": especie.fecha_actualizacion.isoformat() if especie.fecha_actualizacion else None,
    }


class EditarEspecieUseCase:
    """Modifica nombre y/o descripción de una especie activa."""

    def __init__(
        self,
        db: Session,
        especies_repo: EspecieRepository,
        auditoria_repo: AuditoriaEspecieRepository,
    ) -> None:
        self.db = db
        self.especies_repo = especies_repo
        self.auditoria_repo = auditoria_repo

    def execute(self, id_especie: int, dto: EditarEspecieDTO, usuario_actual: UsuarioActual) -> Especie:
        especie = self.especies_repo.obtener_por_id(id_especie)
        if especie is None:
            raise NotFoundError(
                code="ESPECIE_NO_ENCONTRADA",
                message=f"No existe una especie con ID {id_especie}.",
            )

        if not especie.es_activo:
            raise BusinessRuleError(
                code="ESPECIE_INACTIVA",
                message="No se puede editar una especie inactiva. Reactívela primero.",
            )

        # Concurrencia optimista: rechazar si la especie fue modificada desde que el cliente la cargó.
        # Normalizar ambas a UTC para comparar con seguridad aunque varíe el tzinfo.
        ts_actual = especie.fecha_actualizacion
        ts_dto = dto.fecha_actualizacion
        if ts_actual is not None and ts_dto is not None:
            if ts_actual.astimezone(timezone.utc) != ts_dto.astimezone(timezone.utc):
                raise PreconditionFailedError(
                    code="CONFLICTO_CONCURRENCIA",
                    message="La especie fue modificada por otro usuario. Recargue los datos e intente de nuevo.",
                )
        elif ts_actual != ts_dto:
            raise PreconditionFailedError(
                code="CONFLICTO_CONCURRENCIA",
                message="La especie fue modificada por otro usuario. Recargue los datos e intente de nuevo.",
            )

        nombre_nuevo = NombreEspecie(dto.nombre)
        if nombre_nuevo.normalizado() != especie.nombre.normalizado():
            duplicado = self.especies_repo.obtener_por_nombre(nombre_nuevo)
            if duplicado is not None and duplicado.id_especie != especie.id_especie:
                raise ConflictError(
                    code="ESPECIE_DUPLICADA",
                    message=f"El nombre '{nombre_nuevo.valor}' ya pertenece a otra especie del catálogo.",
                    field="nombre",
                )

        snapshot_anterior = _snapshot(especie)

        especie.actualizar(
            nombre=nombre_nuevo,
            descripcion=dto.descripcion,
            fecha_actualizacion=datetime.now(timezone.utc),
        )

        try:
            especie_actualizada = self.especies_repo.actualizar(especie)
            self.auditoria_repo.registrar(
                id_especie=especie_actualizada.id_especie,
                id_usuario=usuario_actual.id_usuario,
                tipo_operacion="UPDATE",
                valores_anteriores=snapshot_anterior,
                valores_nuevos=_snapshot(especie_actualizada),
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return especie_actualizada
