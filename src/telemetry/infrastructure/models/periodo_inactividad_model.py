# | Fecha      | Nombre   | Que se hizo                                      |
# |------------|----------|--------------------------------------------------|
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo y modelo ORM |
"""Modelo ORM de los periodos de inactividad (tabla ``modulo3.periodos_inactividad``).

Delimita el intervalo sin reporte de un dispositivo, los sensores afectados y
su diagnóstico.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import ARRAY, Boolean, DateTime, ForeignKey, Identity, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class PeriodoInactividadModel(Base):
    """Fila de la tabla ``modulo3.periodos_inactividad``."""

    __tablename__ = 'periodos_inactividad'
    __table_args__ = {'schema': 'modulo3'}

    id_periodo_inactividad: Mapped[int] = mapped_column(Integer, Identity(start=1, increment=1), primary_key=True)
    id_dispositivo_iot: Mapped[int] = mapped_column(
        Integer, ForeignKey('modulo9.dispositivos_iot.id_dispositivo_iot'), nullable=False
    )
    sensores_afectados: Mapped[Any] = mapped_column(ARRAY(Integer), nullable=False)
    fecha_inicio: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    fecha_fin: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    duracion_min: Mapped[Optional[int]] = mapped_column(Integer)
    # enum_estado_dispositivo
    estado_durante_periodo: Mapped[str] = mapped_column(String(30), nullable=False)
    # enum_causa_primaria
    causa_primaria: Mapped[str] = mapped_column(String(50), nullable=False)
    caso_diagnosticado: Mapped[Any] = mapped_column(JSONB, nullable=False, default=dict)
    buffer_activo_durante: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    id_alerta: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey('modulo3.alertas.id_alerta')
    )
