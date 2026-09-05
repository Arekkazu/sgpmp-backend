"""Modelo ORM para ``modulo5.configuracion_batch_reportes_gastos`` (RF-77 / motor async).

Generado con sqlacodegen y adaptado (Base compartida, sin relationships). Fila
única de configuración del motor async de generación de reportes de gastos:
paralelismo, reintentos/backoff, límite de concurrencia (429) e intervalo del poller.
"""
from typing import List

from sqlalchemy import ARRAY, Boolean, DateTime, Identity, Integer, PrimaryKeyConstraint, text
from sqlalchemy.orm import Mapped, mapped_column
import datetime

from .base_model import Base


class ConfiguracionBatchReporteGastoModel(Base):
    __tablename__ = 'configuracion_batch_reportes_gastos'
    __table_args__ = (
        PrimaryKeyConstraint('id_configuracion', name='configuracion_batch_reportes_gastos_pkey'),
        {'schema': 'modulo5'}
    )

    id_configuracion: Mapped[int] = mapped_column(Integer, Identity(always=True, start=1, increment=1, minvalue=1, maxvalue=2147483647, cycle=False, cache=1), primary_key=True)
    num_workers_max: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('2'))
    max_reintentos: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('3'))
    backoff_minutos: Mapped[List[int]] = mapped_column(ARRAY(Integer()), nullable=False, server_default=text('ARRAY[1, 3, 5]'))
    limite_concurrencia: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('5'))
    intervalo_poll_segundos: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('15'))
    es_activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('true'))
    actualizado_en: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
