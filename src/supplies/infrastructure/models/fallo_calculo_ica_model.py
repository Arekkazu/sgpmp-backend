"""Modelo ORM para ``modulo5.fallos_calculo_ica`` (RF-74 / E5).

Fallos técnicos persistentes tras agotar los reintentos → estado de negocio
``CA_FALLO_PERSISTENTE``. Generado con sqlacodegen y adaptado (enum→String).
"""
from typing import Optional
import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class FalloCalculoIcaModel(Base):
    __tablename__ = 'fallos_calculo_ica'
    __table_args__ = {'schema': 'modulo5'}

    id_fallo: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_activo_biologico: Mapped[int] = mapped_column(Integer, nullable=False)
    intentos: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('0'))
    resuelto: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('false'))
    creado_en: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    periodo_evaluacion: Mapped[Optional[str]] = mapped_column(String(20))
    causa_fallo: Mapped[Optional[str]] = mapped_column(Text)
    timestamp_ultimo_intento: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    id_ejecucion_batch: Mapped[Optional[int]] = mapped_column(Integer)
    fecha_resolucion: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    tipo_resolucion: Mapped[Optional[str]] = mapped_column(String(20))
