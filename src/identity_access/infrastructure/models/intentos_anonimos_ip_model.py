"""Modelo ORM para la tabla `modulo1.intentos_anonimos_ip`.

Registro de solo inserción para rate limiting por IP en flujos sin actor
identificado (correo inexistente, token inválido). Ver
``IntentoAnonimoRepository`` para el porqué de esta tabla separada de
``eventos``.
"""
from __future__ import annotations

import datetime

from sqlalchemy import DateTime, Index, Integer, PrimaryKeyConstraint, String, text
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class IntentosAnonimosIp(Base):
    __tablename__ = 'intentos_anonimos_ip'
    __table_args__ = (
        PrimaryKeyConstraint('id_intento_anonimo_ip', name='intentos_anonimos_ip_pkey'),
        Index('idx_intentos_anonimos_ip_tipo_ip_fecha', 'tipo', 'ip', 'fecha_intento'),
        {'schema': 'modulo1'},
    )

    id_intento_anonimo_ip: Mapped[int] = mapped_column(Integer, primary_key=True)
    tipo: Mapped[str] = mapped_column(
        String(40), nullable=False,
        comment='Discrimina el flujo que origina el intento, ej. RESTABLECER_TOKEN_INVALIDO.',
    )
    ip: Mapped[str] = mapped_column(String(45), nullable=False)
    fecha_intento: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text('now()'),
    )
