# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-74/77/79/81: notificaciones internas   |
# | 2026-11-12 | Leandro | INC-M05-350/351-G05 RF-74: resolver destinatarios activos por rol para el aviso manual. |
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
from src.shared.database import sesion_sistema
from src.supplies.domain.repositories.notificacion_suministros_port import NotificacionSuministrosPort

logger = logging.getLogger(__name__)

_ID_CANAL_INTERNO = 2
_SQL_TIPO_EVENTO = text("SELECT id_tipo_evento FROM modulo1.tipos_eventos WHERE nombre = :nombre")
_SQL_USUARIOS_POR_ROL = text("""
    SELECT u.id_usuario
    FROM modulo1.usuarios u
    JOIN modulo1.roles r USING (id_rol)
    JOIN modulo1.cuentas_usuarios c USING (id_usuario)
    JOIN modulo1.estados_cuentas e USING (id_estado_cuenta)
    WHERE r.nombre_rol = ANY(:roles) AND lower(e.nombre) = 'activo'
""")
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

    def a_roles(self, roles: tuple[str, ...], tipo_evento: str, mensaje: str, detalle: dict) -> None:
        try:
            # M01 protege la lectura de cada bandeja, también en INSERT RETURNING.
            with sesion_sistema() as db:
                ids = db.execute(_SQL_USUARIOS_POR_ROL, {"roles": list(roles)}).scalars().all()
                NotificacionSuministrosM01Adapter(db)._notificar(
                    ids, tipo_evento, mensaje, detalle, evento_por_destinatario=True,
                )
        except Exception:
            logger.exception("No se pudo preparar el aviso %s para los roles %s.", tipo_evento, roles)

    def _notificar(
        self, ids_usuarios: Iterable[int], tipo_evento: str, mensaje: str, detalle: dict,
        *, evento_por_destinatario: bool = False,
    ) -> None:
        destinatarios = sorted(set(ids_usuarios))
        if not destinatarios:
            return
        try:
            id_tipo = self.db.execute(_SQL_TIPO_EVENTO, {"nombre": tipo_evento}).scalar()
            if id_tipo is None:
                logger.warning("Tipo de evento %s no existe (falta la migración bf404c6f1018).", tipo_evento)
                return
            notificaciones = SqlAlchemyNotificacionRepository(self.db)
            eventos = SqlAlchemyEventoRepository(self.db)
            # La bandeja une la notificación con el evento bajo RLS. En los avisos
            # por rol cada destinatario debe poder leer su propio evento.
            grupos = ([id_usuario] for id_usuario in destinatarios) if evento_por_destinatario else (destinatarios,)
            for grupo in grupos:
                id_evento = eventos.registrar(
                    tipo_evento=id_tipo, exitoso=True, id_usuario=grupo[0], detalle=detalle,
                    descripcion=mensaje[:255], modulo="MODULO5",
                )
                for id_usuario in grupo:
                    notificaciones.registrar(
                        id_evento=id_evento, id_usuario=id_usuario, id_canal=_ID_CANAL_INTERNO,
                        mensaje=mensaje, estado="en_cola",
                    )
            self.db.commit()
        except Exception:
            self.db.rollback()
            logger.exception("No se pudo notificar %s a %s.", tipo_evento, destinatarios)
