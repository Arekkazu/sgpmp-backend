import hashlib
import json
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from src.identity_access.application.ports.auditoria_ports import AuditoriaPort
from src.identity_access.infrastructure.models.eventos_model import Eventos


class AuditoriaSQLRepository(AuditoriaPort):

    def __init__(self, db: Session):
        self.db = db

    def listar_eventos(
        self,
        id_usuario: Optional[int],
        tipo_evento: Optional[int],
        fecha_desde: Optional[datetime],
        fecha_hasta: Optional[datetime],
        offset: int,
        limit: int,
    ) -> list[tuple[Eventos, bool]]:
        eventos = self._query_con_filtros(id_usuario, tipo_evento, fecha_desde, fecha_hasta) \
            .order_by(Eventos.fecha_evento.desc()) \
            .offset(offset).limit(limit).all()
        return [(e, self._verificar_hash(e)) for e in eventos]

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
