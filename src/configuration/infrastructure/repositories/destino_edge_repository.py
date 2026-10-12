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

from src.configuration.domain.repositories.destino_edge_repository import DestinoEdgeRepository


class SqlAlchemyDestinoEdgeRepository(DestinoEdgeRepository):
    def __init__(self, db: Session) -> None:
        self._db = db

    def listar_seriales_gateway_por_especie(self, id_especie: int) -> list[str]:
        filas = self._db.execute(
            text("SELECT serial FROM modulo9.fn_seriales_gateway_edge_por_especie(:id_especie)"),
            {"id_especie": id_especie},
        )
        return [serial for (serial,) in filas]
