"""Modelo ORM para ``modulo5.configuracion_batch_ica`` (RF-74 / parámetros).

Fila única con los parámetros del motor batch (límite de activos, workers, ventana,
hora de ejecución, política de reintentos). Generado con sqlacodegen y adaptado.
"""
from typing import Optional
import datetime

from sqlalchemy import ARRAY, Boolean, DateTime, Integer, Time, text
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class ConfiguracionBatchIcaModel(Base):
    __tablename__ = 'configuracion_batch_ica'
    __table_args__ = {'schema': 'modulo5'}

    id_configuracion: Mapped[int] = mapped_column(Integer, primary_key=True)
    limite_activos: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('5000'))
    num_workers_max: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('4'))
    umbral_paralelizacion: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('500'))
    ventana_horas: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('4'))
    hora_ejecucion: Mapped[datetime.time] = mapped_column(Time, nullable=False, server_default=text("'02:00:00'::time without time zone"))
    max_reintentos: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('3'))
    backoff_minutos: Mapped[list[int]] = mapped_column(ARRAY(Integer()), nullable=False, server_default=text('ARRAY[2, 4, 6]'))
    es_activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('true'))
    actualizado_en: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    id_usuario_actualiza: Mapped[Optional[int]] = mapped_column(Integer)
