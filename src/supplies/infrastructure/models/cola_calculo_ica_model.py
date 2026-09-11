"""Modelo ORM para ``modulo5.cola_calculo_ica`` (RF-74 / cola persistente).

Cola de activos pendientes de cálculo ICA (FA-07 límite superado, FA-06 ventana
excedida, reactivación). Generado con sqlacodegen y adaptado.
"""
from typing import Optional
import datetime

from sqlalchemy import DateTime, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class ColaCalculoIcaModel(Base):
    __tablename__ = 'cola_calculo_ica'
    __table_args__ = {'schema': 'modulo5'}

    id_cola: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_activo_biologico: Mapped[int] = mapped_column(Integer, nullable=False)
    prioridad: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('100'))
    estado: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'EN_COLA'::character varying"))
    fecha_encolado: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    id_ejecucion_batch: Mapped[Optional[int]] = mapped_column(Integer)
    motivo: Mapped[Optional[str]] = mapped_column(String(50))
    fecha_procesado: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
