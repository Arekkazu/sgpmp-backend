# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-14/RF-87: notificaciones internas al Contador |
# | 2026-11-08 | Arekkazu | INC-M06-299-G81 RF-89: avisos de vencimiento sin duplicados tras reinicios (marca persistente) |
"""Adaptador de :class:`NotificacionFinancieraPort` sobre M01 (RF-10 + RF-14), mismo patrón que M05:
el aviso cuelga de un evento de ``modulo1.eventos`` y deja una notificación en la bandeja interna.
Hace su propio ``commit`` en una sesión aparte y nunca propaga errores."""
from __future__ import annotations

import json
import logging
from typing import Callable, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.financial_valuation.domain.repositories.notificacion_financiera_port import NotificacionFinancieraPort
from src.identity_access.infrastructure.repositories.evento_repository import SqlAlchemyEventoRepository
from src.identity_access.infrastructure.repositories.notificacion_repository import SqlAlchemyNotificacionRepository

logger = logging.getLogger(__name__)

_ID_CANAL_INTERNO = 2
_SQL_CONTADORES = text("""
    SELECT DISTINCT u.id_usuario FROM modulo1.usuarios u JOIN modulo1.roles r ON r.id_rol = u.id_rol
    LEFT JOIN modulo9.usuarios_fincas uf ON uf.id_usuario = u.id_usuario AND uf.es_activo
    WHERE r.nombre_rol = 'Contador' AND (CAST(:finca AS integer) IS NULL OR uf.id_finca = :finca)
""")

_SQL_YA_NOTIFICADO = text("""
    SELECT EXISTS (SELECT 1 FROM modulo1.eventos e JOIN modulo1.tipos_eventos t ON t.id_tipo_evento = e.tipo_evento
                   WHERE t.nombre = :n AND e.modulo = 'MODULO6' AND e.detalle @> CAST(:d AS jsonb))
""")


class NotificacionFinancieraM01Adapter(NotificacionFinancieraPort):
    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self.session_factory = session_factory

    def a_contadores(self, tipo_evento: str, mensaje: str, detalle: dict, id_finca: Optional[int] = None) -> None:
        db = self.session_factory()
        try:
            destinatarios = sorted({f.id_usuario for f in db.execute(_SQL_CONTADORES, {"finca": id_finca})})
            id_tipo = db.execute(text("SELECT id_tipo_evento FROM modulo1.tipos_eventos WHERE nombre = :n"),
                                 {"n": tipo_evento}).scalar()
            if not destinatarios or id_tipo is None:
                return
            notificaciones = SqlAlchemyNotificacionRepository(db)
            SqlAlchemyEventoRepository(db).registrar(
                tipo_evento=id_tipo, exitoso=True, id_usuario=destinatarios[0], detalle=detalle,
                descripcion=mensaje[:255], modulo="MODULO6",
            )
            id_evento = notificaciones.buscar_ultimo_evento_id(id_usuario=destinatarios[0], tipo_evento=id_tipo)
            for id_usuario in destinatarios:
                notificaciones.registrar(id_evento=id_evento, id_usuario=id_usuario, id_canal=_ID_CANAL_INTERNO,
                                         mensaje=mensaje, estado="en_cola")
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("No se pudo notificar %s a los contadores.", tipo_evento)
        finally:
            db.close()

    def ya_notificado(self, tipo_evento: str, detalle: dict) -> bool:
        db = self.session_factory()
        try:
            return bool(db.execute(_SQL_YA_NOTIFICADO, {"n": tipo_evento, "d": json.dumps(detalle)}).scalar())
        finally:
            db.close()
