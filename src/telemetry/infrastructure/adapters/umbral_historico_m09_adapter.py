from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from src.configuration.infrastructure.repositories.umbral_ambiental_repository import (
    SqlAlchemyUmbralAmbientalRepository,
)
from src.telemetry.domain.repositories.umbral_historico_port import UmbralHistoricoPort


class UmbralHistoricoM09Adapter(UmbralHistoricoPort):
    """Resuelve el umbral RF-17 (M09) vigente para el semáforo histórico de Monitoreo (M03).

    INC-M09-107-G32 (#298): antes era un stub que siempre devolvía `None`. La correlación
    especie/variable ya es resoluble dentro de esta misma base de datos —
    `modulo3.telemetrias.id_variable` es el mismo `id_variable_ambiental` de M09, y
    `modulo3.vinculaciones_lecturas.id_activo_biologico` → `modulo2.activos_biologicos.id_especie`
    entrega la especie— así que se reutiliza el repositorio real de M09 en vez de duplicar
    su consulta. Lo que sigue bloqueado (mismo root cause que INC-M09-104-G29) es la
    propagación hacia el Nodo Edge, no esta lectura.
    """

    def __init__(self, db: Session) -> None:
        self._umbral_repo = SqlAlchemyUmbralAmbientalRepository(db)

    def obtener_umbral_vigente(
        self,
        id_variable_ambiental: int,
        id_especie: Optional[int],
        timestamp: datetime,
    ) -> Optional[dict]:
        if id_especie is None:
            return None

        umbral = self._umbral_repo.obtener_por_especie_y_variable(id_especie, id_variable_ambiental)
        if umbral is None or not umbral.es_activo:
            return None

        return {
            "id_umbral_ambiental": umbral.id_umbral_ambiental,
            "umbral_min": umbral.valor_min,
            "umbral_max": umbral.valor_max,
            "niveles": [
                {
                    "nivel": n.nivel.value,
                    "limite_inferior": n.limite_inferior,
                    "limite_superior": n.limite_superior,
                }
                for n in umbral.niveles
            ],
            "version": umbral.fecha_actualizacion,
        }
