"""Modelo ORM para la tabla ``modulo5.registros_medicamentos`` (RF-76).

Generado con sqlacodegen (reflexión de la BD) y adaptado a las convenciones del
repo: Base compartida, nombre de clase ``<Agregado>Model``, el enum PG
``enum_registro_medicamenti_via_aplicacion`` mapeado como ``String`` (CLAUDE.md)
y sin ``relationship`` cross-module. Campos gestionados por triggers de la BD:

- ``costo_total_medicamento``: lo calcula ``fn_trg_calcular_costo_total_medicamento``.
- La auditoría la escribe ``fn_trg_auditoria_medicamento`` en ``modulo5.auditorias_suministros``.
- Inmutabilidad, re-anulación y no-borrado se refuerzan por triggers.
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
    Text,
    Time,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class RegistroMedicamentoModel(Base):
    __tablename__ = 'registros_medicamentos'
    __table_args__ = (
        CheckConstraint("estado_registro::text = 'VALIDADO'::text OR estado_registro::text = 'ANULADO'::text AND justificacion_anulacion IS NOT NULL AND char_length(justificacion_anulacion::text) >= 20", name='chk_medicamento_anulacion'),
        ForeignKeyConstraint(['id_activo_biologico'], ['modulo2.activos_biologicos.id_activo_biologico'], name='fk_registro_medicamento_activo_biologico'),
        ForeignKeyConstraint(['id_evento_sanitario'], ['modulo2.eventos_sanitarios.id_evento'], ondelete='SET NULL', onupdate='CASCADE', name='fk_registro_medicamento_evento_sanitario'),
        ForeignKeyConstraint(['id_usuario'], ['modulo1.usuarios.id_usuario'], name='fk_registro_medicamento_usuario'),
        ForeignKeyConstraint(['id_usuario_veterinario'], ['modulo1.usuarios.id_usuario'], name='fk_registro_medicamento_usuario_vet'),
        PrimaryKeyConstraint('id_registro_medicamento', name='registros_medicamentos_pkey'),
        Index('idx_medicamento_activo_fecha_estado', 'id_activo_biologico', 'fecha_aplicacion', 'estado_registro'),
        Index('uq_medicamento_validado_dup', 'id_activo_biologico', 'fecha_aplicacion', postgresql_where="((estado_registro)::text = 'VALIDADO'::text)", unique=True),
        {'schema': 'modulo5'}
    )

    id_registro_medicamento: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_activo_biologico: Mapped[int] = mapped_column(Integer, nullable=False)
    nombre_medicamento: Mapped[str] = mapped_column(String(100), nullable=False)
    descripcion_clinica: Mapped[str] = mapped_column(Text, nullable=False)
    unidad_dosis: Mapped[str] = mapped_column(String(20), nullable=False)
    cantidad: Mapped[decimal.Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    fecha_aplicacion: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    costo_unitario_medicamento: Mapped[decimal.Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    costo_total_medicamento: Mapped[decimal.Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    fecha_registro: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    id_usuario: Mapped[int] = mapped_column(Integer, nullable=False)
    estado_registro: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'VALIDADO'::character varying"))
    via_aplicacion: Mapped[Optional[str]] = mapped_column(String(20))
    lote_medicameto: Mapped[Optional[str]] = mapped_column(String(60))
    fehca_vencimietno_lote: Mapped[Optional[datetime.date]] = mapped_column(Date)
    id_usuario_veterinario: Mapped[Optional[int]] = mapped_column(Integer)
    hora_aplicacion: Mapped[Optional[datetime.time]] = mapped_column(Time)
    periodo_retiro_dias: Mapped[Optional[int]] = mapped_column(Integer, server_default=text('0'))
    fecha_fin_retiro: Mapped[Optional[datetime.date]] = mapped_column(Date)
    dosis_por_individuo: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(10, 4))
    motivo_aplicacion: Mapped[Optional[str]] = mapped_column(String(500))
    id_evento_sanitario: Mapped[Optional[int]] = mapped_column(Integer)
    justificacion_anulacion: Mapped[Optional[str]] = mapped_column(String(255))
    fecha_hora_anulacion: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    id_registro_rf76: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, server_default=text('gen_random_uuid()'))
    nombre_veterinario: Mapped[Optional[str]] = mapped_column(String(150))
