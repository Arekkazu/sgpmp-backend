from typing import Optional
import datetime
import enum

from sqlalchemy import Boolean, CHAR, CheckConstraint, Column, Date, DateTime, Enum, ForeignKeyConstraint, Index, Integer, PrimaryKeyConstraint, Sequence, String, Table, Text, Time, UniqueConstraint, text

from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base_model import Base
from .enums_models import EnumTokenTipo

class Tokens(Base):
    __tablename__ = 'tokens'
    __table_args__ = (
        PrimaryKeyConstraint('id_token', name='tokens_pkey'),
        {'comment': 'Almacena los tokens de uso único generados para operaciones '
                'sensibles del sistema:\n'
                'recuperación de contraseña, verificación de correo, autenticación '
                'temporal, etc.\n'
                'Cada token tiene un tipo, fecha de expiración y registro de si ya '
                'fue utilizado.',
     'schema': 'modulo1'}
    )

    id_token: Mapped[int] = mapped_column(Integer, primary_key=True, comment='Identificador único del token. Clave primaria (serial).')
    fecha_creacion: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'), comment='Marca temporal (con zona horaria) del momento en que se generó el token.')
    token_tipo: Mapped[Optional[EnumTokenTipo]] = mapped_column(Enum(EnumTokenTipo, values_callable=lambda cls: [member.value for member in cls], name='enum_token_tipo', schema='modulo1'), comment='Tipo de token según su propósito. ENUM global (enum_token_tipo).\nEj: RECUPERACION_CONTRASENA, VERIFICACION_CORREO, SESION_TEMPORAL.')
    fecha_expiracion: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), comment='Marca temporal (con zona horaria) en que el token deja de ser válido.\nLos tokens no usados antes de esta fecha son inválidos.')
    fecha_uso: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), comment='Marca temporal (con zona horaria) del momento en que el token fue consumido/usado.\nSi es igual a fecha_creacion o está en el pasado indica que ya fue utilizado.')

    sesiones: Mapped['Sesiones'] = relationship('Sesiones', uselist=False, back_populates='tokens')
