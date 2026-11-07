# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-06 | Arekkazu | M07 RF-102 4.1/FA-1, RF-98 FA-5: alertas internas al Administrador (RF-14) |
"""Alertas de M07 en la bandeja interna (RF-14), mismo patrón que M06: el aviso cuelga de un evento de
``modulo1.eventos``. Los destinatarios son quienes pueden leer la auditoría de integración (por permiso,
no por rol fijo). Hace su propio ``commit``, no repite la misma alerta en 10 minutos y nunca propaga errores."""
from __future__ import annotations

import logging
from typing import Callable

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.identity_access.infrastructure.repositories.evento_repository import SqlAlchemyEventoRepository
from src.identity_access.infrastructure.repositories.notificacion_repository import SqlAlchemyNotificacionRepository

logger = logging.getLogger(__name__)

_ID_CANAL_INTERNO = 2
_VENTANA_MINUTOS = 10
_SQL_DESTINATARIOS = text("""
    SELECT DISTINCT u.id_usuario FROM modulo1.usuarios u
    JOIN modulo1.permisos p ON p.id_rol = u.id_rol AND p.es_activo AND p.id_accion = 2
    JOIN modulo1.recursos r ON r.id_recurso = p.id_recurso AND r.nombre_recurso = 'auditoria_integracion'
    JOIN modulo1.cuentas_usuarios c ON c.id_usuario = u.id_usuario AND c.id_estado_cuenta = 2
""")


def alertador_administrador(session_factory: Callable[[], Session]) -> Callable[[str, dict], None]:
    def alertar(mensaje: str, detalle: dict) -> None:
        db = session_factory()
        try:
            id_tipo = db.execute(text("SELECT id_tipo_evento FROM modulo1.tipos_eventos WHERE nombre = 'ALERTA_INTEGRACION_CONTABLE'")).scalar()
            notificaciones = SqlAlchemyNotificacionRepository(db)
            destinatarios = [f.id_usuario for f in db.execute(_SQL_DESTINATARIOS)
                             if not notificaciones.verificar_anti_spam(f.id_usuario, id_tipo, _ID_CANAL_INTERNO, _VENTANA_MINUTOS)]
            if id_tipo is None or not destinatarios:
                return
            SqlAlchemyEventoRepository(db).registrar(tipo_evento=id_tipo, exitoso=False, id_usuario=destinatarios[0],
                                                     detalle=detalle, descripcion=mensaje[:255], modulo="MODULO7")
            id_evento = notificaciones.buscar_ultimo_evento_id(id_usuario=destinatarios[0], tipo_evento=id_tipo)
            for id_usuario in destinatarios:
                notificaciones.registrar(id_evento=id_evento, id_usuario=id_usuario, id_canal=_ID_CANAL_INTERNO,
                                         mensaje=mensaje, estado="en_cola")
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("No se pudo alertar al Administrador: %s", mensaje)
        finally:
            db.close()

    return alertar
