"""Modelo ORM para ``modulo5.reporte_gastos_acumulados`` (RF-77 / CU-04).

Generado con sqlacodegen (reflexión de la BD) y adaptado a las convenciones del
repo: Base compartida, nombre de clase ``<Agregado>Model`` y sin ``relationship``
cross-module (se usan queries explícitas). Es el snapshot persistido de cada
reporte generado (RNF "historial de reportes" de RF-77); el desglose temporal y
la tendencia se guardan aparte, en ``ejecuciones_generacion_reportes_gastos.resultado_json``.

Triggers de BD: ``fn_trg_reporte_gastos_fechas_coherentes`` (BEFORE INSERT/UPDATE)
y ``fn_trg_reporte_gastos_no_delete`` (BEFORE DELETE) — la app no los duplica.
"""
from typing import Optional
import datetime
import decimal

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    PrimaryKeyConstraint,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class ReporteGastoAcumuladoModel(Base):
    __tablename__ = 'reporte_gastos_acumulados'
    __table_args__ = (
        ForeignKeyConstraint(['id_activo_biologico'], ['modulo2.activos_biologicos.id_activo_biologico'], name='fk_registro_gasto_acumulado_activo_biologico'),
        ForeignKeyConstraint(['id_infraestructura'], ['modulo9.infraestructuras.id_infraestructura'], name='fk_registro_gasto_acumulado_infraestructura'),
        ForeignKeyConstraint(['id_usuario'], ['modulo1.usuarios.id_usuario'], name='fk_registro_gasto_acumulado_usuario'),
        PrimaryKeyConstraint('id_reporte_gasto_acumulado', name='reporte_gastos_acumulados_pkey'),
        {'schema': 'modulo5'}
    )

    id_reporte_gasto_acumulado: Mapped[int] = mapped_column(Integer, primary_key=True)
    fecha_incio_reporte: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    fecha_fin_report: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    total_costo_alimento: Mapped[decimal.Decimal] = mapped_column(Numeric(16, 4), nullable=False, server_default=text('0'))
    total_costo_medicamento: Mapped[decimal.Decimal] = mapped_column(Numeric(16, 4), nullable=False, server_default=text('0'))
    total_costo_directo: Mapped[decimal.Decimal] = mapped_column(Numeric(16, 4), nullable=False)
    id_usuario: Mapped[int] = mapped_column(Integer, nullable=False)
    fecha_generacion: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    id_activo_biologico: Mapped[Optional[int]] = mapped_column(Integer)
    id_infraestructura: Mapped[Optional[int]] = mapped_column(Integer)
    categoria: Mapped[Optional[str]] = mapped_column(String(60))
