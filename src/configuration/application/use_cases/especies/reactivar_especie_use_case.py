"""Caso de uso: Reactivar especie inactiva del catálogo (Flujo D — RF-15).

Solo el Administrador puede reactivar. La operación se registra como
``UPDATE`` en la auditoría (``REACTIVATE`` no es un valor válido en el
CHECK constraint ``chk_tipo_operacion_especie``).
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.configuration.domain.entities.especie import Especie
from src.configuration.domain.repositories.auditoria_especie_repository import AuditoriaEspecieRepository
from src.configuration.domain.repositories.especie_repository import EspecieRepository
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import BusinessRuleError, NotFoundError


def _snapshot(especie: Especie) -> dict:
    return {
        "id_especie": especie.id_especie,
        "nombre": especie.nombre.valor,
        "descripcion": especie.descripcion,
        "es_activo": especie.es_activo,
        "fecha_creacion": especie.fecha_creacion.isoformat() if especie.fecha_creacion else None,
        "fecha_actualizacion": especie.fecha_actualizacion.isoformat() if especie.fecha_actualizacion else None,
    }


class ReactivarEspecieUseCase:
    """Restaura a activo una especie previamente desactivada."""

    def __init__(
        self,
        db: Session,
        especies_repo: EspecieRepository,
        auditoria_repo: AuditoriaEspecieRepository,
    ) -> None:
        self.db = db
        self.especies_repo = especies_repo
        self.auditoria_repo = auditoria_repo

    def execute(self, id_especie: int, usuario_actual: UsuarioActual) -> Especie:
        especie = self.especies_repo.obtener_por_id(id_especie)
        if especie is None:
            raise NotFoundError(
                code="ESPECIE_NO_ENCONTRADA",
                message=f"No existe una especie con ID {id_especie}.",
            )

        if especie.es_activo:
            raise BusinessRuleError(
                code="ESPECIE_YA_ACTIVA",
                message="La especie ya se encuentra activa.",
            )

        snapshot_anterior = _snapshot(especie)

        especie.activar()
        especie.fecha_actualizacion = datetime.now(timezone.utc)

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
