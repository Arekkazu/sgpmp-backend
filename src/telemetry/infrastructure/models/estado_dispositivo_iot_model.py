# | Fecha      | Nombre   | Que se hizo                                      |
# |------------|----------|--------------------------------------------------|
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo y modelo ORM |
"""Modelo ORM del estado actual de un dispositivo IoT (tabla ``modulo3.estados_dispositivos_iot``).

Guarda el estado vigente (activo, sin señal, buffer activo, inactivo, en
mantenimiento o desconocido), el último contacto y las causas asociadas.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, ForeignKey, Identity, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class EstadoDispositivoIoTModel(Base):
    """Fila de la tabla ``modulo3.estados_dispositivos_iot``."""

    __tablename__ = 'estados_dispositivos_iot'
    __table_args__ = {'schema': 'modulo3'}

    id_estado_dispositivo_iot: Mapped[int] = mapped_column(Integer, Identity(start=1, increment=1), primary_key=True)
    id_dispositivo_iot: Mapped[int] = mapped_column(
        Integer, ForeignKey('modulo9.dispositivos_iot.id_dispositivo_iot'), nullable=False
    )
    # enum_estado_dispositivo: ACTIVO|SIN_SEÑAL|BUFFER_ACTIVO|INACTIVO|EN_MANTENIMIENTO|DESCONOCIDO
    estado_actual: Mapped[str] = mapped_column(String(30), nullable=False, default='ACTIVO')
    fecha_ultimo_contacto: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    # Typo en DB: id_ultimo_heardbeat
    id_ultimo_heardbeat: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey('modulo3.heartbeats.id_heartbeat')
    )
    tiempo_sin_contacto: Mapped[Optional[int]] = mapped_column(Integer)
    # enum_causa_primaria
    causa_primaria: Mapped[Optional[str]] = mapped_column(String(50))
    causas_secundarias: Mapped[Optional[Any]] = mapped_column(JSONB)
    fecha_ultima_actualizacion: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    id_usuario: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey('modulo1.usuarios.id_usuario')
    )
