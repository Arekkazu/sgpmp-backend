"""Modelo ORM para la tabla `modulo1.tokens`.

Registro de tokens de acceso JWT. `fecha_uso` no-nula indica que el token
fue consumido (revocado o expirado), formando la blacklist de tokens.

Sin `relationship` hacia `Sesiones`: hay tres columnas FK entre ambas tablas
(`sesiones.id_token`, `sesiones.id_token_refresco`, `tokens.id_sesion`), y
ningún repository navega la relación ORM — todo lo hace por `db.get()`/query
explícito. Declarar las tres relaciones solo agregaría ambigüedad sin uso.
"""
from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, ForeignKeyConstraint, Index, Integer, PrimaryKeyConstraint, String, text
from sqlalchemy.orm import Mapped, mapped_column
from .base_model import Base
from .enums_models import EnumTokenTipo


class Tokens(Base):
    __tablename__ = 'tokens'
    __table_args__ = (
        ForeignKeyConstraint(['id_sesion'], ['modulo1.sesiones.id_sesion'], name='fk_tokens_sesion'),
        PrimaryKeyConstraint('id_token', name='tokens_pkey'),
        Index('uix_tokens_hash_valor', 'hash_valor', postgresql_where='(hash_valor IS NOT NULL)', unique=True),
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
    hash_valor: Mapped[Optional[str]] = mapped_column(String(64), comment='Hash SHA-256 del valor del refresh token (nunca se guarda en texto plano). Solo aplica a token_tipo=refresco.')
    id_sesion: Mapped[Optional[int]] = mapped_column(Integer, comment='FK hacia modulo1.sesiones. Backlink de un refresh token hacia la sesión que lo emitió. Solo aplica a token_tipo=refresco.')
