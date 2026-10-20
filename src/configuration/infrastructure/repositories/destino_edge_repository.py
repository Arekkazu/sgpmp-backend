"""Implementación SQLAlchemy del puerto DestinoEdgeRepository (RF-17).

Llama a ``modulo9.fn_seriales_gateway_edge_por_especie`` (migración
``a3c9e5d17b42``), ``SECURITY DEFINER``: la política RLS de
``dispositivos_iot`` solo deja leer a Administrador e Ingeniero de Campo, pero
un Veterinario también crea y edita umbrales, y la propagación no puede
depender de eso.
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.configuration.domain.repositories.destino_edge_repository import (
    DestinoEdgeRepository,
    GatewayEdgeDestino,
)
from src.shared.database import como_sistema

# DEV-10: mismo criterio de Gateway que fn_seriales_gateway_edge_por_especie.
_SQL_GATEWAYS_DEL_AREA = text(
    """
    SELECT DISTINCT g.id_dispositivo_iot, g.serial
    FROM modulo9.dispositivos_iot d
    JOIN modulo9.dispositivos_iot g
      ON g.id_dispositivo_iot = COALESCE(d.id_dispositivo_gateway, d.id_dispositivo_iot)
     AND g.es_activo
    JOIN modulo9.tipos_dispositivo_iot t
      ON t.id_tipo_dispositivo = g.id_tipo_dispositivo
     AND t.nombre = 'GATEWAY_EDGE'
    WHERE d.id_infraestructura = :id_infraestructura
      AND d.es_activo
    ORDER BY g.serial
    """
)


class SqlAlchemyDestinoEdgeRepository(DestinoEdgeRepository):
    def __init__(self, db: Session) -> None:
        self._db = db

    def listar_seriales_gateway_por_especie(self, id_especie: int) -> list[str]:
        filas = self._db.execute(
            text("SELECT serial FROM modulo9.fn_seriales_gateway_edge_por_especie(:id_especie)"),
            {"id_especie": id_especie},
        )
        return [serial for (serial,) in filas]

    def listar_gateways_por_infraestructura(self, id_infraestructura: int) -> list[GatewayEdgeDestino]:
        # modulo9 tiene RLS forzada (FORCE ROW LEVEL SECURITY) y quien edita un
        # área no siempre ve dispositivos_iot: se busca como el usuario de servicio.
        with como_sistema(self._db):
            filas = self._db.execute(_SQL_GATEWAYS_DEL_AREA, {"id_infraestructura": id_infraestructura}).all()
        return [GatewayEdgeDestino(id_dispositivo_iot=f.id_dispositivo_iot, serial=f.serial) for f in filas]
