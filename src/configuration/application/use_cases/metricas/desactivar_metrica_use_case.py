"""Caso de uso: Desactivar métrica de producción (Flujo K — RF-16).

Bloquea la desactivación si existen registros productivos activos que usan
esta métrica (FA-09). Mientras M04 no esté implementado, el puerto es un
stub que siempre retorna False.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.configuration.domain.entities.metrica_produccion import MetricaProduccion
from src.configuration.domain.repositories.auditoria_metrica_repository import AuditoriaMetricaRepository
from src.configuration.domain.repositories.dependencia_metrica_port import DependenciaMetricaPort
from src.configuration.domain.repositories.metrica_produccion_repository import MetricaProduccionRepository
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import BusinessRuleError, NotFoundError


class DesactivarMetricaUseCase:

    def __init__(
        self,
        db: Session,
        metricas_repo: MetricaProduccionRepository,
        auditoria_repo: AuditoriaMetricaRepository,
        dependencia_port: DependenciaMetricaPort,
    ) -> None:
        self.db = db
        self.metricas_repo = metricas_repo
        self.auditoria_repo = auditoria_repo
        self.dependencia_port = dependencia_port

    def execute(self, id_metrica_produccion: int, usuario_actual: UsuarioActual) -> MetricaProduccion:
        metrica = self.metricas_repo.obtener_por_id(id_metrica_produccion)
        if metrica is None:
            raise NotFoundError(
                code="METRICA_NO_ENCONTRADA",
                message=f"No existe una métrica con ID {id_metrica_produccion}.",
            )
        if not metrica.es_activo:
            raise BusinessRuleError(
                code="METRICA_YA_INACTIVA",
                message="La métrica ya se encuentra inactiva.",
            )
        if self.dependencia_port.tiene_dependencias_activas(id_metrica_produccion):
            raise BusinessRuleError(
                code="METRICA_CON_REGISTROS",
                message=(
                    f"No es posible desactivar la métrica '{metrica.nombre.valor}'. "
                    "Existen registros productivos activos que la utilizan."
                ),
            )

        snapshot_anterior = metrica._snapshot()
        metrica.desactivar()
        metrica.fecha_actualizacion = datetime.now(timezone.utc)

        try:
            metrica_actualizada = self.metricas_repo.actualizar(metrica)
            self.auditoria_repo.registrar(
                id_metrica_produccion=metrica_actualizada.id_metrica_produccion,
                id_usuario=usuario_actual.id_usuario,
                tipo_operacion="DEACTIVATE",
                valores_anteriores=snapshot_anterior,
                valores_nuevos=metrica_actualizada._snapshot(),
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return metrica_actualizada
