"""Modelo ORM para ``modulo5.fallos_generacion_reportes_gastos`` (RF-77 / motor async).

Generado con sqlacodegen y adaptado (Base compartida, sin relationships). Fallos
técnicos persistentes tras agotar los reintentos configurados, análogo a
``fallos_calculo_ica`` (RF-74).
"""
from typing import Optional
import datetime

from sqlalchemy import Boolean, DateTime, ForeignKeyConstraint, Index, Integer, PrimaryKeyConstraint, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class FalloGeneracionReporteGastoModel(Base):
    __tablename__ = 'fallos_generacion_reportes_gastos'
    __table_args__ = (
        ForeignKeyConstraint(['id_cola'], ['modulo5.cola_generacion_reportes_gastos.id_cola'], name='fallos_generacion_reportes_gastos_id_cola_fkey'),
        PrimaryKeyConstraint('id_fallo', name='fallos_generacion_reportes_gastos_pkey'),
        Index('uq_fallo_reporte_gastos_abierto', 'id_cola', postgresql_where='(NOT resuelto)', unique=True),
        {'schema': 'modulo5'}
    )

    id_fallo: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_cola: Mapped[int] = mapped_column(Integer, nullable=False)
    intentos: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('0'))
    resuelto: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('false'))
    creado_en: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    causa_fallo: Mapped[Optional[str]] = mapped_column(Text)
    timestamp_ultimo_intento: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
