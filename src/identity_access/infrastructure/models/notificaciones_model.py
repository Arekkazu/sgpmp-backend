# | Fecha      | Nombre   | Que se hizo                                                   |
# |------------|----------|---------------------------------------------------------------|
# | 2026-11-14 | Arekkazu | M08 RF-105: nivel, ciclo de vida, agrupación y reintentos push |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Modelo ORM para la tabla `modulo1.notificaciones`.

Registro de notificaciones enviadas o en cola por canal. Incluye el estado
de envío y si el usuario la ha leído (para notificaciones internas).

RF-105: ``nivel`` y ``estado`` mapean ENUMs de PostgreSQL como ``String`` (convención del
proyecto). En la fila interna, ``estado_envio`` es el estado del push: ``en_cola`` pendiente,
``enviado`` entregado o sin dispositivos, ``fallido`` a reintentar en ``fecha_proximo_intento``.
"""
from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, SmallInteger, CHAR, CheckConstraint, Column, Date, DateTime, Enum, ForeignKeyConstraint, Index, Integer, PrimaryKeyConstraint, Sequence, String, Table, Text, Time, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base_model import Base
from .enums_models import EnumEstadoEnvio

if TYPE_CHECKING:
    from .eventos_model import Eventos
    from .notificaciones_canal_model import NotificacionesCanal
    from .usuarios_model import Usuarios

class Notificaciones(Base):
    """Modelo ORM de las notificaciones (tabla ``modulo1.notificaciones``)."""
    __tablename__ = 'notificaciones'
    __table_args__ = (
        ForeignKeyConstraint(['id_evento'], ['modulo1.eventos.id_evento'], name='fk_evento'),
        ForeignKeyConstraint(['id_notificacion_canal'], ['modulo1.notificaciones_canal.id_notificacion_canal'], name='fk_notificacion_canal'),
        ForeignKeyConstraint(['id_usuario'], ['modulo1.usuarios.id_usuario'], name='fk_usuario'),
        PrimaryKeyConstraint('id_notificacion', name='notificaciones_pkey'),
        {'comment': 'Registra las notificaciones generadas y enviadas a los usuarios '
                'del sistema.\n'
                'Cada notificación está asociada a un evento y se envía por un '
                'canal específico\n'
                '(correo, SMS, push, etc.). Permite rastrear si fue leída y su '
                'estado de envío.',
     'schema': 'modulo1'}
    )

    id_notificacion: Mapped[int] = mapped_column(Integer, Sequence('notificaciones_id_notificaciones_seq', schema='modulo1'), primary_key=True, comment='Identificador único de la notificación. Clave primaria (serial).')
    id_evento: Mapped[int] = mapped_column(Integer, nullable=False, comment='FK hacia modulo1.eventos. Evento que originó el envío de esta notificación.')
    mensaje: Mapped[str] = mapped_column(Text, nullable=False, comment='Contenido textual de la notificación enviada al usuario.')
    fecha_envio: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, comment='Marca temporal (con zona horaria) del momento en que se envió o programó la notificación.')
    es_leido: Mapped[bool] = mapped_column(Boolean, nullable=False, comment='Indica si el usuario ya leyó o visualizó la notificación en la interfaz.')
    id_notificacion_canal: Mapped[int] = mapped_column(Integer, nullable=False, comment='FK hacia modulo1.notificaciones_canal. Canal por el que se envió la notificación\n(ej: EMAIL, SMS, PUSH).')
    id_usuario: Mapped[int] = mapped_column(Integer, nullable=False, comment='FK hacia modulo1.usuarios. Usuario destinatario de la notificación.')
    estado_envio: Mapped[EnumEstadoEnvio] = mapped_column(Enum(EnumEstadoEnvio, values_callable=lambda cls: [member.value for member in cls], name='enum_estado_envio', schema='modulo1'), nullable=False, server_default='en_cola', comment='Estado del envío de la notificación (en_cola, enviado, fallido).')
    nivel: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'INFORMATIVA'"))
    estado: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'NUEVA'"))
    accion_documentada: Mapped[Optional[str]] = mapped_column(Text)
    fecha_lectura: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    fecha_atencion: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    fecha_descarte: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    id_activo_biologico: Mapped[Optional[int]] = mapped_column(Integer)
    json_contexto: Mapped[Optional[dict]] = mapped_column(JSONB(none_as_null=True))
    ocurrencias: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('1'))
    fecha_ultima_ocurrencia: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    intentos_push: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=text('0'))
    fecha_proximo_intento: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))

    eventos: Mapped['Eventos'] = relationship('Eventos', back_populates='notificaciones')
    notificaciones_canal: Mapped['NotificacionesCanal'] = relationship('NotificacionesCanal', back_populates='notificaciones')
    usuarios: Mapped['Usuarios'] = relationship('Usuarios', back_populates='notificaciones')

