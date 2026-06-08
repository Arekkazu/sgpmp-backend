"""Implementación SQLAlchemy del puerto de dominio :class:`EventoRepository`.

Mapea filas de la tabla ``eventos`` a la entidad :class:`Evento` y recalcula el
hash SHA-256 de cada registro para devolver el flag de integridad: si el hash
almacenado no coincide con el recalculado, el evento pudo ser alterado
directamente en la tabla.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from src.identity_access.domain.entities.evento import Evento
from src.identity_access.domain.repositories.evento_repository import EventoRepository
from src.identity_access.infrastructure.models.eventos_model import Eventos


class SqlAlchemyEventoRepository(EventoRepository):
    """Adaptador SQLAlchemy de lectura para la tabla ``eventos``."""

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _a_entidad(orm: Eventos) -> Evento:
        """Convierte una fila ORM ``Eventos`` en la entidad :class:`Evento`."""
        return Evento(
            id_evento=orm.id_evento,
            tipo_evento=orm.tipo_evento,
            fecha_evento=orm.fecha_evento,
            modulo=orm.modulo,
            resultado=getattr(orm.resultado, "value", orm.resultado),
            detalle=orm.detalle,
            id_usuario=orm.id_usuario,
            categoria=orm.categoria,
            estado=orm.estado,
            id_sesion=orm.id_sesion,
        )

    def listar_eventos(
        self,
        id_usuario: Optional[int],
        tipo_evento: Optional[int],
        fecha_desde: Optional[datetime],
        fecha_hasta: Optional[datetime],
        offset: int,
        limit: int,
    ) -> list[tuple[Evento, bool]]:
        eventos = (
            self._query_con_filtros(id_usuario, tipo_evento, fecha_desde, fecha_hasta)
            .order_by(Eventos.fecha_evento.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return [(self._a_entidad(e), self._verificar_hash(e)) for e in eventos]

    def contar_eventos(
        self,
        id_usuario: Optional[int],
        tipo_evento: Optional[int],
        fecha_desde: Optional[datetime],
        fecha_hasta: Optional[datetime],
    ) -> int:
        return self._query_con_filtros(id_usuario, tipo_evento, fecha_desde, fecha_hasta).count()

    def _query_con_filtros(self, id_usuario, tipo_evento, fecha_desde, fecha_hasta):
        query = self.db.query(Eventos)
        if id_usuario is not None:
            query = query.filter(Eventos.id_usuario == id_usuario)
        if tipo_evento is not None:
            query = query.filter(Eventos.tipo_evento == tipo_evento)
        if fecha_desde is not None:
            query = query.filter(Eventos.fecha_evento >= fecha_desde)
        if fecha_hasta is not None:
            query = query.filter(Eventos.fecha_evento <= fecha_hasta)
        return query

    def _verificar_hash(self, evento: Eventos) -> bool:
        if evento.hash_integridad is None:
            return True
        contenido = json.dumps({
            "tipo_evento": evento.tipo_evento,
            "fecha_evento": evento.fecha_evento.isoformat() if evento.fecha_evento else None,
            "id_usuario": evento.id_usuario,
            "resultado": evento.resultado.value if hasattr(evento.resultado, "value") else evento.resultado,
            "modulo": evento.modulo,
            "detalle": evento.detalle,
        }, sort_keys=True, default=str)
        hash_calculado = hashlib.sha256(contenido.encode("utf-8")).hexdigest()
        return hash_calculado == evento.hash_integridad
