"""Caso de uso: Editar etapa del ciclo productivo (Flujo B — RF-16).

Concurrencia optimista mediante ``fecha_actualizacion`` (FA-07).
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.configuration.domain.entities.ciclo_biologico import CicloBiologico
from src.configuration.domain.repositories.auditoria_ciclo_repository import AuditoriaCicloRepository
from src.configuration.domain.repositories.ciclo_biologico_repository import CicloBiologicoRepository
from src.configuration.domain.value_objects.duracion_dias import DuracionDias
from src.configuration.domain.value_objects.nombre_etapa import NombreEtapa
from src.configuration.infrastructure.dto.editar_ciclo_dto import EditarCicloDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import BusinessRuleError, ConflictError, NotFoundError, PreconditionFailedError


def _snapshot(ciclo: CicloBiologico) -> dict:
    return {
        "id_ciclo_biologico": ciclo.id_ciclo_biologico,
        "nombre": ciclo.nombre.valor,
        "descripcion": ciclo.descripcion,
        "duracion_dias": ciclo.duracion_dias.valor,
        "id_especie": ciclo.id_especie,
        "es_activo": ciclo.es_activo,
        "fecha_actualizacion": ciclo.fecha_actualizacion.isoformat() if ciclo.fecha_actualizacion else None,
    }


class EditarCicloUseCase:

    def __init__(
        self,
        db: Session,
        ciclos_repo: CicloBiologicoRepository,
        auditoria_repo: AuditoriaCicloRepository,
    ) -> None:
        self.db = db
        self.ciclos_repo = ciclos_repo
        self.auditoria_repo = auditoria_repo

    def execute(self, id_ciclo_biologico: int, dto: EditarCicloDTO, usuario_actual: UsuarioActual) -> CicloBiologico:
        ciclo = self.ciclos_repo.obtener_por_id(id_ciclo_biologico)
        if ciclo is None:
            raise NotFoundError(
                code="ETAPA_NO_ENCONTRADA",
                message=f"No existe una etapa con ID {id_ciclo_biologico}.",
            )
        if not ciclo.es_activo:
            raise BusinessRuleError(
                code="ETAPA_INACTIVA",
                message="No se puede editar una etapa inactiva. Reactívela primero.",
            )

        ts_actual = ciclo.fecha_actualizacion
        ts_dto = dto.fecha_actualizacion
        if ts_actual is not None and ts_dto is not None:
            if ts_actual.astimezone(timezone.utc) != ts_dto.astimezone(timezone.utc):
                raise PreconditionFailedError(
                    code="CONFLICTO_CONCURRENCIA",
                    message="La etapa fue modificada por otro usuario. Recargue los datos e intente de nuevo.",
                )
        elif ts_actual != ts_dto:
            raise PreconditionFailedError(
                code="CONFLICTO_CONCURRENCIA",
                message="La etapa fue modificada por otro usuario. Recargue los datos e intente de nuevo.",
            )

        nombre_nuevo = NombreEtapa(dto.nombre)
        if nombre_nuevo.normalizado() != ciclo.nombre.normalizado():
            duplicado = self.ciclos_repo.obtener_por_nombre_y_especie(nombre_nuevo, ciclo.id_especie)
            if duplicado is not None and duplicado.id_ciclo_biologico != ciclo.id_ciclo_biologico:
                raise ConflictError(
                    code="ETAPA_DUPLICADA",
                    message=f"Ya existe una etapa con el nombre '{nombre_nuevo.valor}' para esta especie.",
                    field="nombre",
                )

        snapshot_anterior = _snapshot(ciclo)
        ciclo.actualizar(
            nombre=nombre_nuevo,
            duracion_dias=DuracionDias(dto.duracion_dias),
            descripcion=dto.descripcion,
            fecha_actualizacion=datetime.now(timezone.utc),
        )

        try:
            ciclo_actualizado = self.ciclos_repo.actualizar(ciclo)
            self.auditoria_repo.registrar(
                id_ciclo_biologico=ciclo_actualizado.id_ciclo_biologico,
                id_usuario=usuario_actual.id_usuario,
                tipo_operacion="UPDATE",
                valores_anteriores=snapshot_anterior,
                valores_nuevos=_snapshot(ciclo_actualizado),
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return ciclo_actualizado
