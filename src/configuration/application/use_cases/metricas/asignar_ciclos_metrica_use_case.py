"""Caso de uso: habilitar una métrica como producto en ciclos productivos (RF-43 E-04).

RF-43 rechaza un evento productivo cuyo producto no está habilitado para el
ciclo de la fase activa, pero no había dónde configurarlo. Solo se aceptan
ciclos de la especie de la métrica.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.configuration.domain.entities.ciclo_metrica import CicloMetrica
from src.configuration.domain.repositories.ciclo_metrica_repository import CicloMetricaRepository
from src.configuration.domain.repositories.metrica_produccion_repository import MetricaProduccionRepository
from src.shared.errors import BusinessRuleError, NotFoundError


class AsignarCiclosMetricaUseCase:
    """Deja la métrica habilitada exactamente en los ciclos indicados."""

    def __init__(
        self,
        db: Session,
        metricas_repo: MetricaProduccionRepository,
        ciclos_repo: CicloMetricaRepository,
    ) -> None:
        self.db = db
        self.metricas_repo = metricas_repo
        self.ciclos_repo = ciclos_repo

    def execute(self, id_metrica_produccion: int, ids_ciclos_productivos: list[int]) -> list[CicloMetrica]:
        metrica = self.metricas_repo.obtener_por_id(id_metrica_produccion)
        if metrica is None:
            raise NotFoundError(
                code="METRICA_NO_ENCONTRADA",
                message=f"No existe una métrica con ID {id_metrica_produccion}.",
            )
        if not metrica.es_activo:
            raise BusinessRuleError(
                code="METRICA_INACTIVA",
                message="No se puede habilitar una métrica inactiva en ciclos productivos.",
            )

        pedidos = set(ids_ciclos_productivos)
        de_la_especie = {c.id_ciclo_productivo for c in self.ciclos_repo.listar_por_metrica(
            id_metrica_produccion, metrica.id_especie,
        )}
        ajenos = sorted(pedidos - de_la_especie)
        if ajenos:
            raise BusinessRuleError(
                code="CICLO_DE_OTRA_ESPECIE",
                message=(
                    "Solo se pueden habilitar ciclos productivos de la especie de la métrica. "
                    f"No pertenecen a ella: {', '.join(map(str, ajenos))}."
                ),
                field="ids_ciclos_productivos",
            )

        try:
            self.ciclos_repo.reemplazar(id_metrica_produccion, pedidos)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return self.ciclos_repo.listar_por_metrica(id_metrica_produccion, metrica.id_especie)
