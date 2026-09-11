"""Modelo ORM para ``modulo5.resultado_ica`` (RF-74 / CU-02).

Generado con sqlacodegen (reflexión de la BD) y adaptado a las convenciones del
repo: Base compartida, nombre de clase ``<Agregado>Model``, columnas enum de PG
mapeadas como ``String`` (evita conflictos con los tipos enum ya existentes) y
sin ``relationship`` cross-module (se usan queries explícitas).

Auditoría: la escribe ``fn_trg_auditoria_resultado_ica`` (AFTER INSERT/UPDATE) en
``modulo5.auditorias_suministros`` — la app NO la duplica.
"""
from typing import Optional
import datetime
import decimal

from sqlalchemy import Boolean, Date, DateTime, Integer, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class ResultadoIcaModel(Base):
    __tablename__ = 'resultado_ica'
    __table_args__ = {'schema': 'modulo5'}

    id_resultado_ica: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_activo_biologico: Mapped[int] = mapped_column(Integer, nullable=False)
    periodo_evaluacion: Mapped[str] = mapped_column(String(20), nullable=False)
    fecha_inicio_periodo: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    fecha_fin_periodo: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    estado_resultado: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'CALCULADO'::character varying"))
    es_vigente: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('true'))
    intento: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('1'))
    alimento_consumido_total_kg: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(14, 4))
    ganancia_peso_kg: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(10, 4))
    ca_calculado: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(10, 4))
    clasificacion_ca: Mapped[Optional[str]] = mapped_column(String(20))
    data_quality_score: Mapped[Optional[int]] = mapped_column(Integer)
    causa_no_calculo: Mapped[Optional[str]] = mapped_column(String(50))
    tipo_calculo: Mapped[Optional[str]] = mapped_column(String(30), server_default=text("'AUTOMATICO'::character varying"))
    fecha_calculo: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))
    id_usuario: Mapped[Optional[int]] = mapped_column(Integer)
    id_version: Mapped[Optional[int]] = mapped_column(Integer, server_default=text('1'))
    creado_en: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))
