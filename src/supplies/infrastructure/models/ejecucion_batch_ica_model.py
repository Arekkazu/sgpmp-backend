"""Modelo ORM para ``modulo5.ejecuciones_batch_ica`` (RF-74 / motor batch).

Registra el estado y métricas de cada corrida del batch ICA (FA-05/06/12).
Generado con sqlacodegen y adaptado (Base compartida, enum→String, sin relations).
"""
from typing import Optional
import datetime

from sqlalchemy import DateTime, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class EjecucionBatchIcaModel(Base):
    __tablename__ = 'ejecuciones_batch_ica'
    __table_args__ = {'schema': 'modulo5'}

    id_ejecucion: Mapped[int] = mapped_column(Integer, primary_key=True)
    estado: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'EN_EJECUCION'::character varying"))
    tipo_disparo: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'AUTOMATICO'::character varying"))
    hora_inicio: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    cantidad_activos_total: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('0'))
    cantidad_activos_procesados: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('0'))
    cantidad_activos_pendientes: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('0'))
    cantidad_fallidos: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('0'))
    num_workers: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('1'))
    creado_en: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    hora_fin: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    hora_corte: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    causa_interrupcion: Mapped[Optional[str]] = mapped_column(String(50))
    limite_configurado: Mapped[Optional[int]] = mapped_column(Integer)
    id_usuario_disparo: Mapped[Optional[int]] = mapped_column(Integer)
    id_usuario_interrupcion: Mapped[Optional[int]] = mapped_column(Integer)
