from typing import Optional
import datetime
import enum

from sqlalchemy import Boolean, CHAR, CheckConstraint, Column, Date, DateTime, Enum, ForeignKeyConstraint, Index, Integer, PrimaryKeyConstraint, Sequence, String, Table, Text, Time, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from base_model import Base


class TiposEventos(Base):
    __tablename__ = 'tipos_eventos'
    __table_args__ = (
        PrimaryKeyConstraint('id_tipo_evento', name='tipos_evento_pkey'),
        UniqueConstraint('nombre', name='uq_tipos_evento_nombre'),
        {'comment': 'Catálogo de los tipos de evento que el sistema puede registrar.\n'
                'Cada tipo define una categoría de acción (ej: LOGIN, LOGOUT, '
                'CREACION_USUARIO)\n'
                'y la acción que la desencadenó. Es referenciado por la tabla '
                'eventos.',
     'schema': 'modulo1'}
    )

    id_tipo_evento: Mapped[int] = mapped_column(Integer, Sequence('tipos_evento_id_tipo_evento_seq', schema='modulo1'), primary_key=True, comment='Identificador único del tipo de evento. Clave primaria (serial).')
    nombre: Mapped[str] = mapped_column(String(50), nullable=False, comment='Nombre único del tipo de evento (ej: LOGIN_EXITOSO, CAMBIO_CONTRASENA).\nMáximo 50 caracteres.')
    accion: Mapped[str] = mapped_column(String(50), nullable=False, comment='Acción técnica asociada al tipo de evento (ej: INSERT, UPDATE, AUTH).\nMáximo 50 caracteres.')

    eventos: Mapped[list['Eventos']] = relationship('Eventos', back_populates='tipos_eventos')

