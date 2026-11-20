# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-06 | Arekkazu | M07 RF-102 4.1/FA-1, RF-98 FA-5: alertas internas al Administrador (RF-14) |
# | 2026-11-19 | Leandro | INC-M07-371-G58 RF-102: permitir avisos críticos de archivado visibles por destinatario. |
# | 2026-11-20 | Arekkazu | QA-M07 CU04 H-03 RF-98: el anti-spam compara el mensaje, no solo el tipo de aviso |
"""Alertas de M07 en la bandeja interna (RF-14), mismo patrón que M06: el aviso cuelga de un evento de
``modulo1.eventos``. Los destinatarios son quienes pueden leer la auditoría de integración (por permiso,
no por rol fijo). Hace su propio ``commit``, no repite el mismo mensaje en 10 minutos y nunca propaga errores.

El anti-spam es por mensaje: dos avisos distintos seguidos (la 4.0 y la 5.0 bloqueadas en el mismo ciclo, o
un registro alterado justo después de otro aviso) llegan los dos (CU04 H-03)."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Callable

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from src.identity_access.infrastructure.models.notificaciones_model import Notificaciones
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
        db = None
        try:
            db = session_factory()
            id_tipo = db.execute(text("SELECT id_tipo_evento FROM modulo1.tipos_eventos WHERE nombre = 'ALERTA_INTEGRACION_CONTABLE'")).scalar()
            if id_tipo is None:
                return
            notificaciones = SqlAlchemyNotificacionRepository(db)
            desde = datetime.now(timezone.utc) - timedelta(minutes=_VENTANA_MINUTOS)
            ya_avisados = set(db.scalars(select(Notificaciones.id_usuario).where(
                Notificaciones.mensaje == mensaje, Notificaciones.id_notificacion_canal == _ID_CANAL_INTERNO,
                Notificaciones.fecha_envio >= desde)))
            destinatarios = [f.id_usuario for f in db.execute(_SQL_DESTINATARIOS) if f.id_usuario not in ya_avisados]
            if not destinatarios:
                return
            eventos = SqlAlchemyEventoRepository(db)
            for id_usuario in destinatarios:
                # La bandeja aplica RLS también sobre el evento del aviso.
                id_evento = eventos.registrar(tipo_evento=id_tipo, exitoso=False, id_usuario=id_usuario,
                                              detalle=detalle, descripcion=mensaje[:255], modulo="MODULO7")
                notificaciones.registrar(id_evento=id_evento, id_usuario=id_usuario, id_canal=_ID_CANAL_INTERNO,
                                         mensaje=mensaje, estado="en_cola")
            db.commit()
        except Exception:
            if db is not None:
                db.rollback()
            logger.exception("No se pudo alertar al Administrador: %s", mensaje)
        finally:
            if db is not None:
                db.close()

    return alertar
