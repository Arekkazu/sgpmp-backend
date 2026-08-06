"""Modelo ORM para ``modulo5.configuracion_batch_historial_suministros`` (RF-81 / motor async).

Generado con sqlacodegen y adaptado (Base compartida, sin relationships). Fila
única de configuración: paralelismo, reintentos/backoff, límites de concurrencia
(429), umbrales de nivel de volumen (Nivel 3/4) y umbral de exportación async.
"""
from typing import List
import datetime

from sqlalchemy import ARRAY, Boolean, DateTime, Identity, Integer, PrimaryKeyConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class ConfiguracionBatchHistorialSuministroModel(Base):
    __tablename__ = 'configuracion_batch_historial_suministros'
    __table_args__ = (
        PrimaryKeyConstraint('id_configuracion', name='configuracion_batch_historial_suministros_pkey'),
        {'schema': 'modulo5'}
    )

    id_configuracion: Mapped[int] = mapped_column(Integer, Identity(always=True, start=1, increment=1, minvalue=1, maxvalue=2147483647, cycle=False, cache=1), primary_key=True)
    num_workers_max: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('2'))
    max_reintentos: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('3'))
    backoff_minutos: Mapped[List[int]] = mapped_column(ARRAY(Integer()), nullable=False, server_default=text('ARRAY[1, 3, 5]'))
    limite_concurrencia_exportaciones: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('3'))
    limite_concurrencia_consultas: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('5'))
    umbral_nivel3: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('10000'))
    umbral_nivel4: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('50000'))
    tope_maximo_registros: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('200000'))
    umbral_exportacion_async: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('10000'))
    intervalo_poll_segundos: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('15'))
    es_activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('true'))
    actualizado_en: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
