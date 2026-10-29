"""Adaptador real de ``NodoEdgePort`` contra ``modulo9`` (DEV-09, RF-65 FA-08).

Reemplaza a ``NodoEdgeStubAdapter``, que respondía siempre que había nodos: ahora
``MODO_EDGE_SIN_NODOS`` se decide con datos. Los nodos de un ``tipo_modelo`` son
los Gateway Edge activos instalados en un área activa con ese
``tipo_modelo_asignado`` (M09·RF-20, D-06) o que atienden un dispositivo activo
de esa área (``id_dispositivo_gateway``), el mismo criterio de Gateway que la
propagación de umbrales de RF-17. El meta-modelo ``MODELO_RIESGO_CONTAGIO`` no
se asigna a un área, así que no tiene nodos.

``modulo9`` tiene RLS forzada y un Veterinario (que configura el motor) no ve
``dispositivos_iot``: la búsqueda corre ``como_sistema`` para que el resultado
no dependa de quién configura.
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.prediction.domain.entities.sincronizacion_nodo_edge import NodoEdge
from src.prediction.domain.repositories.nodo_edge_port import NodoEdgePort
from src.shared.database import como_sistema

_SQL_NODOS_POR_TIPO_MODELO = text(
    """
    SELECT DISTINCT g.id_dispositivo_iot, g.serial
    FROM modulo9.infraestructuras i
    JOIN modulo9.dispositivos_iot d
      ON d.id_infraestructura = i.id_infraestructura
     AND d.es_activo
    JOIN modulo9.dispositivos_iot g
      ON g.id_dispositivo_iot = COALESCE(d.id_dispositivo_gateway, d.id_dispositivo_iot)
     AND g.es_activo
    JOIN modulo9.tipos_dispositivo_iot t
      ON t.id_tipo_dispositivo = g.id_tipo_dispositivo
     AND t.nombre = 'GATEWAY_EDGE'
    WHERE i.es_activo
      AND i.tipo_modelo_asignado = :tipo_modelo
    ORDER BY g.serial
    """
)


class NodoEdgeM09Adapter(NodoEdgePort):

    def __init__(self, db: Session) -> None:
        self.db = db

    def listar_nodos_activos(self, tipo_modelo: str) -> list[NodoEdge]:
        with como_sistema(self.db):
            filas = self.db.execute(_SQL_NODOS_POR_TIPO_MODELO, {"tipo_modelo": tipo_modelo}).all()
        return [NodoEdge(id_dispositivo_iot=f.id_dispositivo_iot, serial=f.serial) for f in filas]
