"""Implementación SQLAlchemy del port de notificaciones.

Gestiona el registro de notificaciones enviadas, la verificación de anti-spam
por ventana temporal y la consulta de tokens FCM de los dispositivos registrados.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from src.identity_access.application.ports.notificaciones_ports import NotificacionesPort
from src.identity_access.infrastructure.models.cuenta_usuarios_model import CuentasUsuarios
from src.identity_access.infrastructure.models.dispositivos_fcm_model import DispositivosFcm
from src.identity_access.infrastructure.models.enums_models import EnumEstadoEnvio
from src.identity_access.infrastructure.models.eventos_model import Eventos
from src.identity_access.infrastructure.models.notificaciones_model import Notificaciones


class NotificacionesSQLRepository(NotificacionesPort):
    """Repositorio SQLAlchemy para `Notificaciones` y `DispositivosFcm`."""

    def __init__(self, db: Session):
        self.db = db

    def registrar(
        self,
        id_evento: int,
        id_usuario: int,
        id_canal: int,
        mensaje: str,
        estado_envio: EnumEstadoEnvio,
    ) -> Notificaciones:
        notificacion = Notificaciones(
            id_evento=id_evento,
            id_usuario=id_usuario,
            id_notificacion_canal=id_canal,
            mensaje=mensaje,
            fecha_envio=datetime.now(timezone.utc),
            es_leido=False,
            estado_envio=estado_envio,
        )
        self.db.add(notificacion)
        self.db.flush()
        self.db.refresh(notificacion)
        return notificacion

    def actualizar_estado(self, notificacion: Notificaciones, estado: EnumEstadoEnvio) -> None:
        notificacion.estado_envio = estado
        self.db.flush()

    def verificar_anti_spam(
        self, id_usuario: int, tipo_evento: int, id_canal: int, ventana_minutos: int
    ) -> bool:
        desde = datetime.now(timezone.utc) - timedelta(minutes=ventana_minutos)
        existe = (
            self.db.query(Notificaciones)
            .join(Eventos, Notificaciones.id_evento == Eventos.id_evento)
            .filter(
                Notificaciones.id_usuario == id_usuario,
                Eventos.tipo_evento == tipo_evento,
                Notificaciones.id_notificacion_canal == id_canal,
                Notificaciones.fecha_envio >= desde,
            )
            .first()
        )
        return existe is not None

    def buscar_ultimo_evento_id(self, id_usuario: int, tipo_evento: int) -> Optional[int]:
        evento = (
            self.db.query(Eventos)
            .filter(
                Eventos.id_usuario == id_usuario,
                Eventos.tipo_evento == tipo_evento,
            )
            .order_by(Eventos.id_evento.desc())
            .first()
        )
        return evento.id_evento if evento else None

    def buscar_estado_cuenta(self, id_usuario: int) -> Optional[int]:
        cuenta = (
            self.db.query(CuentasUsuarios)
            .filter(CuentasUsuarios.id_usuario == id_usuario)
            .first()
        )
        return cuenta.id_estado_cuenta if cuenta else None

    def buscar_fcm_tokens(self, id_usuario: int) -> list[str]:
        rows = (
            self.db.query(DispositivosFcm.fcm_token)
            .filter(DispositivosFcm.id_usuario == id_usuario)
            .all()
        )
        return [row.fcm_token for row in rows]

    def guardar_fcm_token(self, id_usuario: int, token: str, user_agent: Optional[str] = None) -> None:
        dispositivo = DispositivosFcm(
            id_usuario=id_usuario,
            fcm_token=token,
            user_agent=user_agent,
        )
        self.db.add(dispositivo)
        self.db.flush()
