"""Modelo ORM para `modulo9.preferencias_idiomas` (RF-29)."""
from __future__ import annotations

import datetime

from sqlalchemy import Boolean, DateTime, ForeignKeyConstraint, Integer, PrimaryKeyConstraint, Sequence, String
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class PreferenciaIdiomaModel(Base):
    __tablename__ = 'preferencias_idiomas'
    __table_args__ = (
        ForeignKeyConstraint(
            ['id_usuario'],
            ['modulo1.usuarios.id_usuario'],
            name='preferencias_idiomas_id_usuario_fkey',
        ),
        PrimaryKeyConstraint('id_preferencia_idioma', name='preferencias_idiomas_pkey'),
        {'schema': 'modulo9'},
    )

    id_preferencia_idioma: Mapped[int] = mapped_column(
        Integer,
        Sequence('preferencias_idiomas_id_preferencia_idioma_seq', schema='modulo9'),
        primary_key=True,
    )
    id_usuario: Mapped[int] = mapped_column(Integer, nullable=False)
    locale_code: Mapped[str] = mapped_column(String(5), nullable=False)
    es_por_defecto: Mapped[bool] = mapped_column(Boolean, nullable=False)
    fecha_actualizacion: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
