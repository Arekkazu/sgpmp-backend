"""Modelo ORM para ``modulo5.auditorias_suministros`` (RF-80, RF-78/79 / CU-05).

Generado con sqlacodegen y adaptado (Base compartida, columnas enum de PG
``tipo_operacion``/``resultado``/``origen_precio`` mapeadas como ``String``,
sin ``relationship`` cross-module). Tabla de auditoría compartida por todo
``modulo5`` (usada también por triggers de CU-01/02/04). Este CU es el primero
que la escribe desde Python — vía ``AuditoriaSuministroPort`` — para los 8
eventos de negocio de RF-78/79 (``SUMINISTRO_REGISTRADO``,
``CONFLICTO_CONCURRENCIA``, ``PROVISION_INCREMENTAL_ENTREGADA``, etc., ver
``anotaciones/modulo_5/cu05_gaps_bd_rf78_rf79.md`` Gap 4). ``hash_integridad``
lo calcula automáticamente el trigger ``trg_audit_hash`` (BEFORE INSERT/UPDATE),
la app nunca lo asigna.
"""
from typing import Optional
import datetime
import decimal

from sqlalchemy import (
    ARRAY,
    Boolean,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    JSON,
    Numeric,
    PrimaryKeyConstraint,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class AuditoriaSuministroModel(Base):
    __tablename__ = 'auditorias_suministros'
    __table_args__ = (
        ForeignKeyConstraint(['id_activo_biologico'], ['modulo2.activos_biologicos.id_activo_biologico'], name='fk_auditorias_suministros_activo_biologico'),
        ForeignKeyConstraint(['id_ciclo_productivo'], ['modulo9.ciclos_productivos.id_ciclo_productivo'], name='fk_auditorias_suministros_ciclo_productivo'),
        ForeignKeyConstraint(['id_gestion_fases'], ['modulo2.gestiones_fases.id_gestion_fases'], name='idx_auditorias_suministros_gestion_fases_fkey'),
        ForeignKeyConstraint(['id_sesion'], ['modulo1.sesiones.id_sesion'], name='fk_auditoria_suministro_sesion'),
        ForeignKeyConstraint(['id_usuario'], ['modulo1.usuarios.id_usuario'], name='fk_auditoria_suministro_usuario'),
        PrimaryKeyConstraint('id_auditoria_suministro', name='auditorias_suministros_pkey'),
        {'schema': 'modulo5'}
    )

    id_auditoria_suministro: Mapped[int] = mapped_column(Integer, primary_key=True)
    entidad_afectada: Mapped[str] = mapped_column(String(80), nullable=False)
    tipo_operacion: Mapped[str] = mapped_column(String(40), nullable=False)
    id_usuario: Mapped[int] = mapped_column(Integer, nullable=False)
    resultado: Mapped[str] = mapped_column(String(20), nullable=False)
    fecha_evento: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    datos_anteriores: Mapped[Optional[dict]] = mapped_column(JSON)
    datos_nuevos: Mapped[Optional[dict]] = mapped_column(JSON)
    ip_origen: Mapped[Optional[str]] = mapped_column(String(45))
    id_sesion: Mapped[Optional[int]] = mapped_column(Integer)
    fecha_emision: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    id_activo_biologico: Mapped[Optional[int]] = mapped_column(Integer)
    id_ciclo_productivo: Mapped[Optional[int]] = mapped_column(Integer)
    costo_afectado: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric)
    origen_precio: Mapped[Optional[str]] = mapped_column(String(20))
    clasificacion_registro: Mapped[Optional[str]] = mapped_column(String(20), server_default=text("'NIC41'::character varying"))
    retencion_aplicable: Mapped[Optional[str]] = mapped_column(String(10), server_default=text("'5 años'::character varying"))
    hash_integridad: Mapped[Optional[str]] = mapped_column(String(64))
    registro_incompleto: Mapped[Optional[bool]] = mapped_column(Boolean, server_default=text('false'))
    detalle_causa: Mapped[Optional[str]] = mapped_column(Text)
    numero_reintentos: Mapped[Optional[int]] = mapped_column(Integer)
    fecha_intentos: Mapped[Optional[list]] = mapped_column(ARRAY(DateTime(True)))
    id_gestion_fases: Mapped[Optional[int]] = mapped_column(Integer)
