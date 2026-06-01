from typing import Optional
import datetime
import enum

from sqlalchemy import Boolean, CHAR, CheckConstraint, Column, Date, DateTime, Enum, ForeignKeyConstraint, Index, Integer, PrimaryKeyConstraint, Sequence, String, Table, Text, Time, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from base_model import Base

class Notificaciones(Base):
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

    eventos: Mapped['Eventos'] = relationship('Eventos', back_populates='notificaciones')
    notificaciones_canal: Mapped['NotificacionesCanal'] = relationship('NotificacionesCanal', back_populates='notificaciones')
    usuarios: Mapped['Usuarios'] = relationship('Usuarios', back_populates='notificaciones')

