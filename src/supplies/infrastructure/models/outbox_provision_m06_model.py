# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-79: modelo del outbox hacia M06        |
"""Modelo ORM de ``modulo5.outbox_provisiones_m06`` (RF-79, migración bf404c6f1018)."""
import datetime
import decimal
import uuid
from typing import Optional

from sqlalchemy import ARRAY, Boolean, DateTime, Integer, Numeric, String, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class OutboxProvisionM06Model(Base):
    __tablename__ = "outbox_provisiones_m06"
    __table_args__ = {"schema": "modulo5"}

    id_outbox_provision_m06: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    modalidad: Mapped[str] = mapped_column(String(15), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(10), nullable=False)
    id_activo_biologico: Mapped[int] = mapped_column(Integer, nullable=False)
    id_gestion_fases: Mapped[Optional[int]] = mapped_column(Integer)
    id_registro_suministro: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    id_provision: Mapped[Optional[int]] = mapped_column(Integer)
    costo_registro: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(14, 4))
    json_contenido: Mapped[dict] = mapped_column(JSONB, nullable=False)
    estado: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'PENDIENTE'"))
    numero_intentos: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    fecha_intentos: Mapped[list] = mapped_column(ARRAY(DateTime(True)), nullable=False, server_default=text("'{}'"))
    fecha_proximo_intento: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False)
    es_alerta_enviada: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    fecha_creacion: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text("now()"))
    fecha_entrega: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
