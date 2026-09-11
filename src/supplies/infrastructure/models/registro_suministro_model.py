"""Modelo ORM para ``modulo5.registro_suministro`` (ledger unificado RF-78/81 / CU-04/05).

Generado con sqlacodegen (reflexión de la BD) y adaptado a las convenciones del
repo: Base compartida, nombre de clase ``<Agregado>Model``, columnas enum de PG
(``origen_precio``, ``naturaleza_costo``, ``tipo_suministro``) mapeadas como
``String`` y sin ``relationship`` cross-module.

Para ALIMENTO/MEDICAMENTO se sigue poblando exclusivamente por los triggers
``fn_trg_poblar_registro_suministro_alimento``/``_medicamento`` (AFTER INSERT en
``registros_consumo_alimentos``/``registros_medicamentos``, ver
``anotaciones/modulo_5/cu04_gaps_bd_rf77_rf81.md`` Gap 1). Desde CU-05 (RF-78),
la app SÍ escribe directamente en esta tabla para SERVICIO_VETERINARIO/
INSEMINACION y para correcciones (``tipo_operacion=CORRECCION``) de cualquier
tipo — ver ``anotaciones/modulo_5/cu05_gaps_bd_rf78_rf79.md``. El trigger
``trg_acumular_costo_ciclo`` (AFTER INSERT, Gap 6) mantiene ``acumulado_ciclo``
atómicamente sin importar el origen de la fila.
"""
from typing import Optional
import datetime
import decimal
import uuid

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    PrimaryKeyConstraint,
    String,
    Uuid,
    UniqueConstraint,
    DateTime,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class RegistroSuministroModel(Base):
    __tablename__ = 'registro_suministro'
    __table_args__ = (
        CheckConstraint('cantidad > 0::numeric', name='registro_suministro_cantidad_check'),
        ForeignKeyConstraint(['id_activo_biologico'], ['modulo2.activos_biologicos.id_activo_biologico'], name='fk_registro_suministro_activos_biologicos'),
        ForeignKeyConstraint(['id_ciclo_productivo'], ['modulo9.ciclos_productivos.id_ciclo_productivo'], name='fk_registro_suministro_ciclos_productivos'),
        ForeignKeyConstraint(['id_gestion_fases'], ['modulo2.gestiones_fases.id_gestion_fases'], name='registro_suministro_id_gestion_fases_fkey'),
        ForeignKeyConstraint(['id_registro_original'], ['modulo5.registro_suministro.id_registro_suministro'], name='registro_suministro_id_registro_original_fkey'),
        PrimaryKeyConstraint('id_registro_suministro', name='registro_suministro_pkey'),
        UniqueConstraint('id_idempotencia', name='registro_suministro_id_idempotencia_key'),
        Index('idx_suministro_activo_ciclo', 'id_activo_biologico', 'id_ciclo_productivo'),
        Index('idx_registro_suministro_gestion_fases', 'id_gestion_fases'),
        {'schema': 'modulo5'}
    )

    id_registro_suministro: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    id_activo_biologico: Mapped[int] = mapped_column(Integer, nullable=False)
    id_ciclo_productivo: Mapped[int] = mapped_column(Integer, nullable=False)
    tipo_suministro: Mapped[str] = mapped_column(String(30), nullable=False)
    cantidad: Mapped[decimal.Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    unidad_medida: Mapped[str] = mapped_column(String(20), nullable=False)
    precio_unitario_resuelto: Mapped[decimal.Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    costo_registro: Mapped[decimal.Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    origen_precio: Mapped[str] = mapped_column(String(20), nullable=False)
    fecha_aplicacion: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    naturaleza_costo: Mapped[str] = mapped_column(String(20), nullable=False)
    justificacion_precio: Mapped[Optional[str]] = mapped_column(String(500))
    observacion: Mapped[Optional[str]] = mapped_column(String(500))
    tipo_operacion: Mapped[Optional[str]] = mapped_column(String(20), server_default=text("'REGISTRO'::character varying"))
    id_registro_original: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    motivo_correccion: Mapped[Optional[str]] = mapped_column(String(500))
    id_idempotencia: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    id_registro_rf75: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    id_registro_rf76: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    fecha_registro: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))
    id_gestion_fases: Mapped[Optional[int]] = mapped_column(Integer)
