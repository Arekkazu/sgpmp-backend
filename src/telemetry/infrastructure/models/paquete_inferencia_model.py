from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Identity, Integer, Numeric, PrimaryKeyConstraint, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class PaqueteInferenciaModel(Base):
    __tablename__ = 'paquetes_inferencia'
    __table_args__ = (
        PrimaryKeyConstraint('id_paquetes_inferencia', name='paquetes_inferencia_pkey'),
        {'schema': 'modulo3'},
    )

    id_paquetes_inferencia: Mapped[int] = mapped_column(
        Integer,
        Identity(start=1, increment=1),
        primary_key=True,
    )
    id_sensor: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('modulo9.sensores.id_sensores'),
        nullable=False,
    )
    id_dispositivo_iot: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('modulo9.dispositivos_iot.id_dispositivo_iot'),
        nullable=False,
    )
    id_evento_edge_computing: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('modulo3.eventos_edge_computing.id_evento_edge_computing'),
        nullable=False,
    )
    tipo_variable: Mapped[str] = mapped_column(String, nullable=False)
    valor_numerico: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    unidad: Mapped[Optional[str]] = mapped_column(String)
    # PG enum — String para no conflictuar con tipo existente en PostgreSQL
    estado_calidad: Mapped[str] = mapped_column(String(30), nullable=False)
    estado_desviacion: Mapped[Optional[str]] = mapped_column(String(30))
    severidad: Mapped[Optional[str]] = mapped_column(String(20))
    origen: Mapped[Optional[str]] = mapped_column(String(20))
    contexto_ambiental: Mapped[Optional[dict]] = mapped_column(JSONB)
    # Nota: typo en BD — nombre exacto de columna es contexto_incomplento
    contexto_incomplento: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    metadatos: Mapped[Optional[dict]] = mapped_column(JSONB)
    # FK a modulo4.versiones_modelos — no mapeada, solo Integer
    id_version_modelo: Mapped[Optional[int]] = mapped_column(Integer)
    fecha_envio: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    estado_paquete: Mapped[str] = mapped_column(String(20), nullable=False, default='PENDIENTE')
    intento_envios: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
