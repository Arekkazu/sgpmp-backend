"""Modelo ORM para la tabla ``modulo5.registros_consumo_alimentos`` (RF-75).

Generado con sqlacodegen (reflexión de la BD) y adaptado a las convenciones del
repo: Base compartida, nombre de clase ``<Agregado>Model`` y sin ``relationship``
cross-module (se usan queries explícitas). Varios campos los gestiona la BD por
trigger y NO deben calcularse en la aplicación:

- ``costo_total``: lo calcula ``fn_trg_calcular_costo_total_consumo`` (BEFORE
  INSERT) con el precio del catálogo activo.
- La auditoría la escribe ``fn_trg_auditoria_consumo_alimento`` en
  ``modulo5.auditorias_suministros``.
- Inmutabilidad y no-borrado se refuerzan por triggers BEFORE UPDATE/DELETE.
"""
from typing import Optional
import datetime
import decimal
import uuid

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    PrimaryKeyConstraint,
    String,
    Time,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class RegistroConsumoAlimentoModel(Base):
    __tablename__ = 'registros_consumo_alimentos'
    __table_args__ = (
        CheckConstraint("estado_registro::text = 'VALIDADO'::text OR estado_registro::text = 'ANULADO'::text AND justificacion_anulacion IS NOT NULL AND char_length(justificacion_anulacion::text) >= 20", name='chk_consumo_anulacion'),
        ForeignKeyConstraint(['id_activo_biologico'], ['modulo2.activos_biologicos.id_activo_biologico'], name='fk_registro_consumo_alimento_activo_biologico'),
        ForeignKeyConstraint(['id_tipo_alimento'], ['modulo5.tipos_alimentos.id_tipo_elemento'], name='fk_registro_consumo_alimento_tipo_alimento'),
        ForeignKeyConstraint(['id_usuario'], ['modulo1.usuarios.id_usuario'], name='fk_registro_consumo_alimento_usuario'),
        PrimaryKeyConstraint('id_consumo_alimeto', name='registros_consumo_alimentos_pkey'),
        Index('idx_consumo_activo_fecha_estado', 'id_activo_biologico', 'fecha_consumo', 'estado_registro'),
        Index('uq_consumo_validado_dup', 'id_activo_biologico', 'fecha_consumo', postgresql_where="((estado_registro)::text = 'VALIDADO'::text)", unique=True),
        {'schema': 'modulo5'}
    )

    id_consumo_alimeto: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_activo_biologico: Mapped[int] = mapped_column(Integer, nullable=False)
    id_tipo_alimento: Mapped[int] = mapped_column(Integer, nullable=False)
    tipo_alimento: Mapped[str] = mapped_column(String(100), nullable=False)
    tipo_unidad: Mapped[str] = mapped_column(String(20), nullable=False)
    cantidad_suministrada: Mapped[decimal.Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    estado_registro: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'VALIDADO'::character varying"))
    costo_total: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(14, 4))
    observacion: Mapped[Optional[str]] = mapped_column(String(60))
    fecha_inicio_periodo: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    fecha_fin_periodo: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    fecha_registro: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))
    id_usuario: Mapped[Optional[int]] = mapped_column(Integer)
    fecha_consumo: Mapped[Optional[datetime.date]] = mapped_column(Date)
    hora_suministro: Mapped[Optional[datetime.time]] = mapped_column(Time)
    costo_unitario: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(14, 4))
    consumo_por_individuo_kg: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(10, 4))
    justificacion_anulacion: Mapped[Optional[str]] = mapped_column(String(255))
    fecha_hora_anulacion: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    id_registro_rf75: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, server_default=text('gen_random_uuid()'))
