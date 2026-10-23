# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-74/77/79/81: notificaciones internas   |
"""Adaptador de :class:`NotificacionSuministrosPort` sobre M01 (RF-10 + RF-14).

Igual que la alerta de fallo de archivado de RF-10: cada aviso cuelga de un
evento en ``modulo1.eventos`` (tipo resuelto por nombre, migración
bf404c6f1018) y se deja una notificación en la bandeja interna por cada
destinatario. Hace su propio ``commit`` y nunca propaga errores.
"""
from __future__ import annotations

import logging
from typing import Iterable

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.identity_access.infrastructure.repositories.evento_repository import SqlAlchemyEventoRepository
from src.identity_access.infrastructure.repositories.notificacion_repository import (
    SqlAlchemyNotificacionRepository,
)
from src.identity_access.infrastructure.repositories.usuario_repository import SqlAlchemyUsuarioRepository
from src.supplies.domain.repositories.notificacion_suministros_port import NotificacionSuministrosPort

logger = logging.getLogger(__name__)

_ID_CANAL_INTERNO = 2
_SQL_TIPO_EVENTO = text("SELECT id_tipo_evento FROM modulo1.tipos_eventos WHERE nombre = :nombre")
_SQL_RESPONSABLES = text(
    """
    SELECT ab.id_usuario
    FROM modulo2.activos_biologicos ab
    WHERE ab.id_activo_biologico = :id_activo AND ab.id_usuario IS NOT NULL
    UNION
    SELECT u.id_usuario
    FROM modulo2.activos_biologicos ab
    JOIN modulo9.infraestructuras i ON i.id_infraestructura = ab.id_infraestructura
    JOIN modulo9.usuarios_fincas uf ON uf.id_finca = i.id_finca
    JOIN modulo1.usuarios u ON u.id_usuario = uf.id_usuario
    JOIN modulo1.roles r ON r.id_rol = u.id_rol
    WHERE ab.id_activo_biologico = :id_activo AND r.nombre_rol = 'Veterinario'
    """
)


class NotificacionSuministrosM01Adapter(NotificacionSuministrosPort):
    def __init__(self, db: Session) -> None:
        self.db = db

    def a_usuarios(self, ids_usuarios: list[int], tipo_evento: str, mensaje: str, detalle: dict) -> None:
        self._notificar(ids_usuarios, tipo_evento, mensaje, detalle)

    def a_permiso(self, id_recurso: int, id_accion: int, tipo_evento: str, mensaje: str, detalle: dict) -> None:
        try:
            ids = SqlAlchemyUsuarioRepository(self.db).listar_ids_con_permiso(id_recurso, id_accion)
        except Exception:
            self.db.rollback()
            logger.exception("No se pudieron resolver los destinatarios de %s.", tipo_evento)
            return
        self._notificar(ids, tipo_evento, mensaje, detalle)

    def a_responsables_activo(self, id_activo: int, tipo_evento: str, mensaje: str, detalle: dict) -> None:
        try:
            ids = [f.id_usuario for f in self.db.execute(_SQL_RESPONSABLES, {"id_activo": id_activo})]
        except Exception:
            self.db.rollback()
            logger.exception("No se pudieron resolver los responsables del activo %s.", id_activo)
            return
        self._notificar(ids, tipo_evento, mensaje, detalle)

    def _notificar(self, ids_usuarios: Iterable[int], tipo_evento: str, mensaje: str, detalle: dict) -> None:
        destinatarios = sorted(set(ids_usuarios))
        if not destinatarios:
            return
        try:
            id_tipo = self.db.execute(_SQL_TIPO_EVENTO, {"nombre": tipo_evento}).scalar()
            if id_tipo is None:
                logger.warning("Tipo de evento %s no existe (falta la migración bf404c6f1018).", tipo_evento)
                return
            notificaciones = SqlAlchemyNotificacionRepository(self.db)
            # El evento necesita un id_usuario (FK): se atribuye al primer destinatario,
            # igual que la alerta de fallo de archivado de RF-10.
            SqlAlchemyEventoRepository(self.db).registrar(
                tipo_evento=id_tipo, exitoso=True, id_usuario=destinatarios[0], detalle=detalle,
                descripcion=mensaje[:255], modulo="MODULO5",
            )
            id_evento = notificaciones.buscar_ultimo_evento_id(id_usuario=destinatarios[0], tipo_evento=id_tipo)
            for id_usuario in destinatarios:
                notificaciones.registrar(
                    id_evento=id_evento, id_usuario=id_usuario, id_canal=_ID_CANAL_INTERNO,
                    mensaje=mensaje, estado="en_cola",
                )
            self.db.commit()
        except Exception:
            self.db.rollback()
            logger.exception("No se pudo notificar %s a %s.", tipo_evento, destinatarios)
