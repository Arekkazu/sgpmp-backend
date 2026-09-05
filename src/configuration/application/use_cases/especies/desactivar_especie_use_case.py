"""Caso de uso: Desactivar especie del catálogo (Flujo C — RF-15).

Solo el Administrador puede desactivar. La operación se bloquea si existe
algún proceso crítico activo asociado a la especie (verificado mediante
:class:`ProcesoCriticoPort`).
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.configuration.domain.entities.especie import Especie
from src.configuration.domain.repositories.auditoria_especie_repository import AuditoriaEspecieRepository
from src.configuration.domain.repositories.especie_repository import EspecieRepository
from src.configuration.domain.repositories.proceso_critico_port import ProcesoCriticoPort
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import BusinessRuleError, LockedError, NotFoundError


def _snapshot(especie: Especie) -> dict:
    return {
        "id_especie": especie.id_especie,
        "nombre": especie.nombre.valor,
        "descripcion": especie.descripcion,
        "es_activo": especie.es_activo,
        "fecha_creacion": especie.fecha_creacion.isoformat() if especie.fecha_creacion else None,
        "fecha_actualizacion": especie.fecha_actualizacion.isoformat() if especie.fecha_actualizacion else None,
    }


class DesactivarEspecieUseCase:
    """Realiza la baja lógica de una especie activa."""

    def __init__(
        self,
        db: Session,
        especies_repo: EspecieRepository,
        auditoria_repo: AuditoriaEspecieRepository,
        proceso_critico_port: ProcesoCriticoPort,
    ) -> None:
        self.db = db
        self.especies_repo = especies_repo
        self.auditoria_repo = auditoria_repo
        self.proceso_critico_port = proceso_critico_port

    def execute(self, id_especie: int, usuario_actual: UsuarioActual) -> Especie:
        especie = self.especies_repo.obtener_por_id(id_especie)
        if especie is None:
            raise NotFoundError(
                code="ESPECIE_NO_ENCONTRADA",
                message=f"No existe una especie con ID {id_especie}.",
            )

        if not especie.es_activo:
            raise BusinessRuleError(
                code="ESPECIE_YA_INACTIVA",
                message="La especie ya se encuentra inactiva.",
            )

        if self.proceso_critico_port.tiene_proceso_activo(id_especie):
            raise LockedError(
                code="ESPECIE_CON_PROCESO_ACTIVO",
                message="No se puede desactivar la especie porque tiene procesos críticos en ejecución.",
            )

        snapshot_anterior = _snapshot(especie)

        especie.desactivar()
        especie.fecha_actualizacion = datetime.now(timezone.utc)

        try:
            especie_actualizada = self.especies_repo.actualizar(especie)
            self.auditoria_repo.registrar(
                id_especie=especie_actualizada.id_especie,
                id_usuario=usuario_actual.id_usuario,
                tipo_operacion="DEACTIVATE",
                valores_anteriores=snapshot_anterior,
                valores_nuevos=_snapshot(especie_actualizada),
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return especie_actualizada
