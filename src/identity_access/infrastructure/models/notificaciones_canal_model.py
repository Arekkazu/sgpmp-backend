"""Modelo ORM para la tabla `modulo1.notificaciones_canal`.

Catálogo de canales de notificación disponibles (ej: EMAIL=1, INTERNO=2, PUSH=3).
"""
from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Optional
from sqlalchemy import Date, Enum, Integer, PrimaryKeyConstraint, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base_model import Base
from .enums_models import EnumEstadoEnvio

if TYPE_CHECKING:
    from .notificaciones_model import Notificaciones


class NotificacionesCanal(Base):
    __tablename__ = 'notificaciones_canal'
    __table_args__ = (
        PrimaryKeyConstraint('id_notificacion_canal', name='notificaciones_canal_pkey'),
        {'comment': 'Catálogo de los canales disponibles para el envío de '
                'notificaciones a usuarios.\n'
                'Define cada canal de comunicación habilitado en el sistema (ej: '
                'EMAIL, SMS, PUSH)\n'
                'y la fecha en que fue registrado.',
     'schema': 'modulo1'}
    )

    id_notificacion_canal: Mapped[int] = mapped_column(Integer, primary_key=True, comment='Identificador único del canal de notificación. Clave primaria (serial).')
    canal: Mapped[EnumEstadoEnvio] = mapped_column(Enum(EnumEstadoEnvio, values_callable=lambda cls: [member.value for member in cls], name='enum_estado_envio', schema='modulo1'), nullable=False, comment='Tipo de canal de envío. Reutiliza el ENUM modulo1.enum_estado_envio como tipo,\nrepresenta el medio de comunicación (ej: EMAIL, SMS, PUSH_NOTIFICATION).')
    fecha_envio: Mapped[datetime.date] = mapped_column(Date, nullable=False, comment='Fecha de registro o última activación del canal en el sistema.')
    nombre: Mapped[str] = mapped_column(String(30), nullable=False, comment='Nombre descriptivo del canal de notificación (ej: "Correo Corporativo", "SMS Colombia").\nMáximo 30 caracteres.')

    notificaciones: Mapped[list['Notificaciones']] = relationship('Notificaciones', back_populates='notificaciones_canal')
