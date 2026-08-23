"""Implementación SQLAlchemy del puerto de dominio :class:`EventoRepository`.

Mapea filas de la tabla ``eventos`` a la entidad :class:`Evento` y recalcula el
hash SHA-256 de cada registro para devolver el flag de integridad: si el hash
almacenado no coincide con el recalculado, el evento pudo ser alterado
directamente en la tabla.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.identity_access.domain.entities.evento import Evento
from src.identity_access.domain.repositories.evento_repository import EventoRepository
from src.identity_access.domain.value_objects.evento_categoria import (
    EventoCategoria,
    categoria_para_tipo_evento,
    tipos_evento_para_categoria,
)
from src.identity_access.infrastructure.models.enums_models import EnumEventoResultado
from src.identity_access.infrastructure.models.eventos_model import Eventos
from src.shared.errors import InfrastructureError


class SqlAlchemyEventoRepository(EventoRepository):
    """Adaptador SQLAlchemy de lectura para la tabla ``eventos``."""

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _a_entidad(orm: Eventos) -> Evento:
        """Convierte una fila ORM ``Eventos`` en la entidad :class:`Evento`."""
        try:
            categoria = categoria_para_tipo_evento(orm.tipo_evento).value
        except ValueError:
            # Conserva accesibles los eventos históricos de tipos externos o
            # aún no catalogados. Los eventos nuevos desconocidos se rechazan.
            categoria = orm.categoria

        return Evento(
            id_evento=orm.id_evento,
            tipo_evento=orm.tipo_evento,
            fecha_evento=orm.fecha_evento,
            modulo=orm.modulo,
            resultado=getattr(orm.resultado, "value", orm.resultado),
            detalle=orm.detalle,
            id_usuario=orm.id_usuario,
            categoria=categoria,
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
        categoria: Optional[EventoCategoria] = None,
    ) -> list[tuple[Evento, bool]]:
        eventos = (
            self._query_con_filtros(
                id_usuario,
                tipo_evento,
                categoria,
                fecha_desde,
                fecha_hasta,
            )
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
        categoria: Optional[EventoCategoria] = None,
    ) -> int:
        return self._query_con_filtros(
            id_usuario,
            tipo_evento,
            categoria,
            fecha_desde,
            fecha_hasta,
        ).count()

    def _query_con_filtros(
        self,
        id_usuario,
        tipo_evento,
        categoria,
        fecha_desde,
        fecha_hasta,
    ):
        query = self.db.query(Eventos)
        if id_usuario is not None:
            query = query.filter(Eventos.id_usuario == id_usuario)
        if tipo_evento is not None:
            query = query.filter(Eventos.tipo_evento == tipo_evento)
        if categoria is not None:
            # La columna de los eventos históricos contiene el valor erróneo
            # AUTENTICACION. Filtrar por tipos canónicos permite consultarlos
            # correctamente sin violar la inmutabilidad de la auditoría.
            query = query.filter(
                Eventos.tipo_evento.in_(tipos_evento_para_categoria(categoria))
            )
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

    # ── Escritura de eventos (comando) ──────────────────────────────────────
    def registrar(
        self,
        tipo_evento: int,
        exitoso: bool,
        id_usuario: int,
        detalle: dict,
        id_sesion: Optional[int] = None,
    ) -> None:
        # El hash SHA-256 cubre los campos clave del evento para detectar
        # modificaciones posteriores en la tabla de auditoría.
        try:
            categoria = categoria_para_tipo_evento(tipo_evento)
        except ValueError as exc:
            raise InfrastructureError(
                code="CATEGORIA_EVENTO_NO_DEFINIDA",
                message=(
                    "No se pudo registrar la auditoría porque el tipo de evento "
                    "no tiene una categoría configurada."
                ),
                original_error=exc,
                field="tipo_evento",
            ) from exc

        resultado = EnumEventoResultado.EXITOSO if exitoso else EnumEventoResultado.FALLIDO
        fecha = datetime.now(timezone.utc)
        contenido_hash = json.dumps({
            "tipo_evento": tipo_evento,
            "fecha_evento": fecha.isoformat(),
            "id_usuario": id_usuario,
            "resultado": resultado.value,
            "modulo": "MODULO1",
            "detalle": detalle,
        }, sort_keys=True, default=str)
        hash_integridad = hashlib.sha256(contenido_hash.encode("utf-8")).hexdigest()

        evento = Eventos(
            tipo_evento=tipo_evento,
            fecha_evento=fecha,
            modulo="MODULO1",
            resultado=resultado,
            detalle=detalle,
            id_usuario=id_usuario,
            categoria=categoria.value,
            estado="PROCESADO",
            id_sesion=id_sesion,
            hash_integridad=hash_integridad,
        )
        self.db.add(evento)
        self.db.flush()

    def contar_solicitudes_recuperacion_por_ip(self, ip: str, desde: datetime) -> int:
        # .astext extrae el valor de texto de la columna JSONB sin comillas adicionales.
        return (
            self.db.query(func.count(Eventos.id_evento))
            .filter(
                Eventos.tipo_evento == 7,
                Eventos.fecha_evento >= desde,
                Eventos.detalle["ip"].astext == ip,
            )
            .scalar()
        )
