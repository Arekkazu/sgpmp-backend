"""Modelo ORM para ``modulo5.provision_nic41`` (RF-79 / CU-05).

Generado con sqlacodegen y adaptado (Base compartida, enum PG ``modalidad``
mapeado como ``String``, sin ``relationship`` cross-module). Artefacto
CONSOLIDADO (ver ``anotaciones/modulo_5/cu05_gaps_bd_rf78_rf79.md`` Gap 11 —
``modalidad='INCREMENTAL'`` no se usa en este CU), inmutable una vez generado;
correcciones crean una nueva fila con ``version_reporte`` incrementado e
``id_reporte_anterior`` apuntando a la versión previa. ``hash_integridad`` lo
calcula automáticamente el trigger ``trg_provision_hash`` (BEFORE INSERT/UPDATE),
la app nunca lo asigna.
"""
from typing import Optional
import datetime
import decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    PrimaryKeyConstraint,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class ProvisionNic41Model(Base):
    __tablename__ = 'provision_nic41'
    __table_args__ = (
        ForeignKeyConstraint(['id_activo_biologico'], ['modulo2.activos_biologicos.id_activo_biologico'], name='fk_provision_nic41_activos_biologicos'),
        ForeignKeyConstraint(['id_ciclo_productivo'], ['modulo9.ciclos_productivos.id_ciclo_productivo'], name='fk_provision_nic41_ciclos_productivos'),
        ForeignKeyConstraint(['id_gestion_fases'], ['modulo2.gestiones_fases.id_gestion_fases'], name='idx_provision_gestion_fases_fkey'),
        ForeignKeyConstraint(['id_reporte_anterior'], ['modulo5.provision_nic41.id_provision'], name='provision_nic41_id_reporte_anterior_fkey'),
        PrimaryKeyConstraint('id_provision', name='provision_nic41_pkey'),
        Index('idx_provision_activo_estado', 'id_activo_biologico', 'estado'),
        Index('idx_provision_gestion_fases', 'id_gestion_fases'),
        {'schema': 'modulo5'}
    )

    id_provision: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_activo_biologico: Mapped[int] = mapped_column(Integer, nullable=False)
    modalidad: Mapped[str] = mapped_column(String(20), nullable=False)
    monto_provision: Mapped[decimal.Decimal] = mapped_column(Numeric, nullable=False)
    id_ciclo_productivo: Mapped[Optional[int]] = mapped_column(Integer)
    id_gestion_fases: Mapped[Optional[int]] = mapped_column(Integer)
    desglose_categoria: Mapped[Optional[dict]] = mapped_column(JSONB)
    lista_registros: Mapped[Optional[list]] = mapped_column(JSONB)
    version_reporte: Mapped[Optional[int]] = mapped_column(Integer, server_default=text('1'))
    id_reporte_anterior: Mapped[Optional[int]] = mapped_column(Integer)
    motivo_correccion: Mapped[Optional[str]] = mapped_column(String(500))
    es_reporte_potencialmente_incompleto: Mapped[Optional[bool]] = mapped_column(Boolean, server_default=text('false'))
    hash_integridad: Mapped[Optional[str]] = mapped_column(String(64))
    estado: Mapped[Optional[str]] = mapped_column(String(30), server_default=text("'GENERADO'::character varying"))
    fecha_generacion: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))
    fecha_entrega_m06: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
