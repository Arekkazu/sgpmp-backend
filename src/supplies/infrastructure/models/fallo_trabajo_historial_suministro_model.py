"""Modelo ORM para ``modulo5.fallos_trabajos_historial_suministros`` (RF-81 / motor async).

Generado con sqlacodegen y adaptado (Base compartida, sin relationships). Fallos
técnicos persistentes tras agotar los reintentos configurados.
"""
from typing import Optional
import datetime

from sqlalchemy import Boolean, DateTime, ForeignKeyConstraint, Index, Integer, PrimaryKeyConstraint, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class FalloTrabajoHistorialSuministroModel(Base):
    __tablename__ = 'fallos_trabajos_historial_suministros'
    __table_args__ = (
        ForeignKeyConstraint(['id_cola'], ['modulo5.cola_trabajos_historial_suministros.id_cola'], name='fallos_trabajos_historial_suministros_id_cola_fkey'),
        PrimaryKeyConstraint('id_fallo', name='fallos_trabajos_historial_suministros_pkey'),
        Index('uq_fallo_hist_sum_abierto', 'id_cola', postgresql_where='(NOT resuelto)', unique=True),
        {'schema': 'modulo5'}
    )

    id_fallo: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_cola: Mapped[int] = mapped_column(Integer, nullable=False)
    intentos: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('0'))
    resuelto: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('false'))
    creado_en: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    causa_fallo: Mapped[Optional[str]] = mapped_column(Text)
    timestamp_ultimo_intento: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
