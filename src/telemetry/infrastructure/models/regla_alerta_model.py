from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Identity, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class ReglaAlertaModel(Base):
    __tablename__ = 'reglas_alertas'
    __table_args__ = {'schema': 'modulo3'}

    id_regla_alertas: Mapped[int] = mapped_column(Integer, Identity(start=1, increment=1), primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    descripcion: Mapped[Optional[str]] = mapped_column(Text)
    # PG enum — String para no conflictuar con tipo existente
    tipo_sensor: Mapped[str] = mapped_column(String(30), nullable=False)
    es_regla_compuesta: Mapped[bool] = mapped_column(Boolean, nullable=False)
    umbral_min: Mapped[Optional[Decimal]] = mapped_column(Numeric)
    umbral_max: Mapped[Optional[Decimal]] = mapped_column(Numeric)
    categoria_variable: Mapped[Optional[str]] = mapped_column(String(40))
    ventana_confirmacion_min: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    lectura_confirmacion_max: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    # Typo en DB: umbrales_severdiad (no umbrales_severidad)
    umbrales_severdiad: Mapped[Optional[Any]] = mapped_column(JSONB)
    id_finca: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey('modulo9.infraestructura.id_infraestructura')
    )
    id_especie: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey('modulo9.especies.id_especie')
    )
    es_activa: Mapped[bool] = mapped_column(Boolean, nullable=False)
    tiene_ejecutar_edge: Mapped[bool] = mapped_column(Boolean, nullable=False)
    id_usuario: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey('modulo1.usuarios.id_usuario')
    )
    fecha_creacion: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fecha_actualizacion: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    version_regla: Mapped[int] = mapped_column(Integer, nullable=False)
    mensaje: Mapped[Optional[str]] = mapped_column(Text)
