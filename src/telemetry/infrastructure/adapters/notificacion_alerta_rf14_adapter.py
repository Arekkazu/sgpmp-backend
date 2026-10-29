# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-20 | Arekkazu | DEV-32 RF-57: notificación de alertas por el canal de RF-14, destinatarios por permisos y reintento con backoff |
"""Adaptador de :class:`NotificacionAlertaPort` sobre el servicio de notificaciones de RF-14.

Cada notificación cuelga de un evento en ``modulo1.eventos`` (tipo 32
``NOTIFICACION_ALERTA``): así lo exige ``modulo1.notificaciones.id_evento``.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.identity_access.infrastructure.repositories.evento_repository import SqlAlchemyEventoRepository
from src.identity_access.infrastructure.repositories.notificacion_repository import SqlAlchemyNotificacionRepository
from src.shared.email import send_email
from src.shared.notificacion_service import NotificacionService, _correo_por_defecto
from src.telemetry.domain.repositories.notificacion_alerta_port import NotificacionAlertaPort

logger = logging.getLogger(__name__)

TIPO_EVENTO_NOTIFICACION_ALERTA = 32  # modulo1.tipos_eventos 'NOTIFICACION_ALERTA' (DBA)
_ACCION_LEER, _ACCION_DESCARTAR = 2, 4
# E7: reintentos a los 1, 2, 4, 8 y 16 min del primer intento; la tarea corre cada minuto.
MINUTOS_REINTENTO = frozenset({1, 2, 4, 8, 16})

_SQL_DESTINATARIOS = text(
    "SELECT DISTINCT u.id_usuario "
    "FROM modulo9.infraestructuras i "
    "JOIN modulo9.usuarios_fincas uf ON uf.id_finca = i.id_finca AND uf.es_activo "
    "JOIN modulo1.usuarios u ON u.id_usuario = uf.id_usuario "
    "JOIN modulo1.permisos p ON p.id_rol = u.id_rol AND p.es_activo AND p.id_accion = :accion "
    "JOIN modulo1.recursos r ON r.id_recurso = p.id_recurso AND r.nombre_recurso = 'alertas_operativas' "
    "WHERE i.id_infraestructura = :area"
)
_SQL_ADMINISTRADORES = text(
    "SELECT u.id_usuario FROM modulo1.usuarios u WHERE modulo1.fn_rol_protegido(u.id_rol)"
)
_SQL_FALLIDAS = text(
    "SELECT n.id_notificacion, n.mensaje, n.fecha_envio, u.correo_electronico "
    "FROM modulo1.notificaciones n "
    "JOIN modulo1.eventos e ON e.id_evento = n.id_evento "
    "JOIN modulo1.usuarios u ON u.id_usuario = n.id_usuario "
    "WHERE e.tipo_evento = :tipo AND n.estado_envio = 'fallido' AND n.id_notificacion_canal = 1 "
    "  AND n.fecha_envio > :ahora - interval '20 minutes'"
)


class NotificacionAlertaRf14Adapter(NotificacionAlertaPort):

    def __init__(self, db: Session) -> None:
        self.db = db

    def destinatarios(self, id_infraestructura: Optional[int], *, escalamiento: bool) -> list[int]:
        if id_infraestructura is None:
            return []
        accion = _ACCION_DESCARTAR if escalamiento else _ACCION_LEER
        filas = self.db.execute(_SQL_DESTINATARIOS, {"area": id_infraestructura, "accion": accion}).scalars().all()
        return list(filas)

    def administradores(self) -> list[int]:
        return list(self.db.execute(_SQL_ADMINISTRADORES).scalars().all())

    def enviar(self, id_usuario: int, titulo: str, cuerpo: str, *, agrupable: bool) -> Optional[bool]:
        try:
            SqlAlchemyEventoRepository(self.db).registrar(
                tipo_evento=TIPO_EVENTO_NOTIFICACION_ALERTA,
                exitoso=True,
                id_usuario=id_usuario,
                detalle={"titulo": titulo},
                descripcion=titulo,
                modulo="MODULO3",
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            logger.exception("RF-57: no se pudo registrar el evento de notificación para el usuario %s", id_usuario)
            return None
        return NotificacionService(port=SqlAlchemyNotificacionRepository(self.db), db=self.db).notificar(
            tipo_evento=TIPO_EVENTO_NOTIFICACION_ALERTA,
            id_usuario=id_usuario,
            resolver_correo_destino=True,
            titulo=titulo,
            cuerpo=cuerpo,
            aplicar_anti_spam_email=agrupable,
            aplicar_anti_spam_interno=agrupable,
        )

    def reintentar_fallidas(self, ahora: datetime) -> int:
        enviadas = 0
        for fila in self.db.execute(_SQL_FALLIDAS, {"tipo": TIPO_EVENTO_NOTIFICACION_ALERTA, "ahora": ahora}).all():
            minutos = int((ahora - fila.fecha_envio).total_seconds() // 60)
            if minutos not in MINUTOS_REINTENTO or not fila.correo_electronico:
                continue
            titulo = fila.mensaje.split(".")[0]
            try:
                send_email(to=fila.correo_electronico, subject=titulo,
                           html_body=_correo_por_defecto(TIPO_EVENTO_NOTIFICACION_ALERTA, titulo, fila.mensaje),
                           intentos=1)
            except Exception:
                logger.warning("RF-57 E7: reintento %d min fallido (notificación %s)", minutos, fila.id_notificacion)
                continue
            self.db.execute(text("UPDATE modulo1.notificaciones SET estado_envio = 'enviado' WHERE id_notificacion = :id"),
                            {"id": fila.id_notificacion})
            self.db.commit()
            enviadas += 1
        return enviadas
