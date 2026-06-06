from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKeyConstraint, Integer, PrimaryKeyConstraint, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base_model import Base

if TYPE_CHECKING:
    from .usuarios_model import Usuarios


class DispositivosFcm(Base):
    __tablename__ = 'dispositivos_fcm'
    __table_args__ = (
        ForeignKeyConstraint(['id_usuario'], ['modulo1.usuarios.id_usuario'], ondelete='CASCADE', name='dispositivos_fcm_id_usuario_fkey'),
        PrimaryKeyConstraint('id_dispositivo', name='dispositivos_fcm_pkey'),
        UniqueConstraint('fcm_token', name='uq_dispositivos_fcm_token'),
        {'schema': 'modulo1'}
    )

    id_dispositivo: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_usuario: Mapped[int] = mapped_column(Integer, nullable=False)
    fcm_token: Mapped[str] = mapped_column(Text, nullable=False)
    fecha_registro: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    ultimo_uso: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    user_agent: Mapped[Optional[str]] = mapped_column(Text)

    usuarios: Mapped['Usuarios'] = relationship('Usuarios', back_populates='dispositivos_fcm')
