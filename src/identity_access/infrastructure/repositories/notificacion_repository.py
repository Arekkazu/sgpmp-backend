"""Implementación SQLAlchemy del puerto de dominio :class:`NotificacionRepository`.

Traduce el estado de envío de texto al enum ``EnumEstadoEnvio`` de la columna y
gestiona el registro de notificaciones, el control anti-spam por ventana
temporal y la consulta/registro de dispositivos FCM.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from src.identity_access.domain.entities.notificacion import Notificacion
from src.identity_access.domain.repositories.notificacion_repository import NotificacionRepository
from src.identity_access.infrastructure.models.cuenta_usuarios_model import CuentasUsuarios
from src.identity_access.infrastructure.models.dispositivos_fcm_model import DispositivosFcm
from src.identity_access.infrastructure.models.enums_models import EnumEstadoEnvio
from src.identity_access.infrastructure.models.eventos_model import Eventos
from src.identity_access.infrastructure.models.notificaciones_model import Notificaciones
from src.identity_access.infrastructure.models.usuarios_model import Usuarios
from src.shared.db_error_translator import raise_from_db_error


ID_CANAL_INTERNO = 2


class SqlAlchemyNotificacionRepository(NotificacionRepository):
    """Adaptador SQLAlchemy para ``Notificaciones`` y ``DispositivosFcm``."""

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _a_entidad(orm: Notificaciones, tipo_evento: int) -> Notificacion:
        return Notificacion(
            id_notificacion=orm.id_notificacion,
            id_evento=orm.id_evento,
            tipo_evento=tipo_evento,
            id_usuario=orm.id_usuario,
            mensaje=orm.mensaje,
            fecha_envio=orm.fecha_envio,
            es_leido=orm.es_leido,
            estado_envio=getattr(orm.estado_envio, "value", orm.estado_envio),
        )

    def registrar(
        self,
        id_evento: int,
        id_usuario: int,
        id_canal: int,
        mensaje: str,
        estado: str,
    ) -> int:
        notificacion = Notificaciones(
            id_evento=id_evento,
            id_usuario=id_usuario,
            id_notificacion_canal=id_canal,
            mensaje=mensaje,
            fecha_envio=datetime.now(timezone.utc),
            es_leido=False,
            estado_envio=EnumEstadoEnvio(estado),
        )
        self.db.add(notificacion)
        self.db.flush()
        self.db.refresh(notificacion)
        return notificacion.id_notificacion

    def actualizar_estado(self, id_notificacion: int, estado: str) -> None:
        notificacion = self.db.get(Notificaciones, id_notificacion)
        notificacion.estado_envio = EnumEstadoEnvio(estado)
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

    def buscar_correo_usuario(self, id_usuario: int) -> Optional[str]:
        fila = (
            self.db.query(Usuarios.correo_electronico)
            .filter(Usuarios.id_usuario == id_usuario)
            .first()
        )
        return fila.correo_electronico if fila else None

    def buscar_fcm_tokens(self, id_usuario: int) -> list[str]:
        rows = (
            self.db.query(DispositivosFcm.fcm_token)
            .filter(DispositivosFcm.id_usuario == id_usuario)
            .all()
        )
        return [row.fcm_token for row in rows]

    def guardar_fcm_token(self, id_usuario: int, token: str, user_agent: Optional[str] = None) -> None:
        """Registra el token del dispositivo del usuario.

        No lleva UPSERT a proposito: `uq_dispositivos_fcm_token` la resuelve el
        trigger `trg_fcm_2_revocar_token_previo`, que borra la fila previa con
        ese token antes del INSERT. Un token FCM es por navegador, no por
        usuario, asi que al entrar un segundo usuario en el mismo equipo el
        dispositivo se reasigna en vez de chocar. Ver
        `anotaciones/modulo_1/fcm_tokens.md`.
        """
        dispositivo = DispositivosFcm(
            id_usuario=id_usuario,
            fcm_token=token,
            user_agent=user_agent,
        )
        self.db.add(dispositivo)
        self.db.flush()

    def _query_internas(self, id_usuario: int, solo_no_leidas: bool):
        query = (
            self.db.query(Notificaciones, Eventos.tipo_evento)
            .join(Eventos, Notificaciones.id_evento == Eventos.id_evento)
            .filter(
                Notificaciones.id_usuario == id_usuario,
                Notificaciones.id_notificacion_canal == ID_CANAL_INTERNO,
            )
        )
        if solo_no_leidas:
            query = query.filter(Notificaciones.es_leido.is_(False))
        return query

    def listar_internas(
        self,
        id_usuario: int,
        solo_no_leidas: bool,
        offset: int,
        limit: int,
    ) -> list[Notificacion]:
        filas = (
            self._query_internas(id_usuario, solo_no_leidas)
            .order_by(
                Notificaciones.fecha_envio.desc(),
                Notificaciones.id_notificacion.desc(),
            )
            .offset(offset)
            .limit(limit)
            .all()
        )
        return [self._a_entidad(orm, tipo_evento) for orm, tipo_evento in filas]

    def contar_internas(self, id_usuario: int, solo_no_leidas: bool) -> int:
        return self._query_internas(id_usuario, solo_no_leidas).count()

    def obtener_interna(
        self,
        id_notificacion: int,
        id_usuario: int,
    ) -> Optional[Notificacion]:
        fila = (
            self._query_internas(id_usuario, solo_no_leidas=False)
            .filter(Notificaciones.id_notificacion == id_notificacion)
            .first()
        )
        if fila is None:
            return None
        orm, tipo_evento = fila
        return self._a_entidad(orm, tipo_evento)

    def guardar(self, notificacion: Notificacion) -> None:
        orm = (
            self.db.query(Notificaciones)
            .filter(
                Notificaciones.id_notificacion == notificacion.id_notificacion,
                Notificaciones.id_usuario == notificacion.id_usuario,
                Notificaciones.id_notificacion_canal == ID_CANAL_INTERNO,
            )
            .first()
        )
        if orm is None:
            return
        orm.es_leido = notificacion.es_leido
        try:
            self.db.flush()
        except Exception as exc:
            raise_from_db_error(exc)
