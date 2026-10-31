# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-31 | Arekkazu | USAB-M03-M04 M3-09/N-06 RF-59: semáforo y % en rango con el umbral de la especie del área |
# | 2026-10-31 | Claude | INC-M03-246-G88 RF-58/59: mismo semáforo que el dashboard (bandas RF-17 + tolerancia T) |
from datetime import datetime
from typing import Optional

from sqlalchemy import text
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
        self._db = db
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
            "tolerancia_semaforo": umbral.tolerancia_semaforo,
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

    def obtener_umbral_vigente_area(
        self,
        id_variable_ambiental: int,
        id_infraestructura: Optional[int],
        timestamp: datetime,
        id_sensor: Optional[int] = None,
    ) -> Optional[dict]:
        if id_infraestructura is None and id_sensor is None:
            return None
        id_especie = self._db.execute(text(
            "SELECT ie.id_especie FROM modulo9.infraestructuras_especies ie "
            "JOIN modulo9.umbrales_ambientales u ON u.id_especie = ie.id_especie "
            "AND u.id_variable_ambiental = :var AND u.es_activo "
            "WHERE ie.id_infraestructura = COALESCE(CAST(:infra AS integer), ("
            "  SELECT saa.id_infraestructura FROM modulo9.sensores_areas_asociadas saa "
            "  WHERE saa.id_sensor = :sensor AND saa.fecha_asociacion <= :ts "
            "    AND (saa.fecha_finalizacion IS NULL OR saa.fecha_finalizacion > :ts) "
            "  ORDER BY saa.fecha_asociacion DESC LIMIT 1)) "
            "ORDER BY ie.id_especie LIMIT 1"
        ), {"var": id_variable_ambiental, "infra": id_infraestructura,
            "sensor": id_sensor, "ts": timestamp}).scalar()
        return self.obtener_umbral_vigente(id_variable_ambiental, id_especie, timestamp)
