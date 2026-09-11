from __future__ import annotations

import uuid
from typing import Optional
import datetime

from sqlalchemy import Boolean, DateTime, Index, Integer, PrimaryKeyConstraint, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class BitacoraAuditoriaM02Model(Base):
    __tablename__ = 'bitacora_auditoria_m02'
    __table_args__ = (
        PrimaryKeyConstraint('id_bitacora', name='bitacora_auditoria_m02_pkey'),
        Index('idx_bitacora_m02_activo', 'id_activo_biologico'),
        Index('idx_bitacora_m02_clasificacion', 'clasificacion_biologica'),
        Index('idx_bitacora_m02_resultado', 'resultado'),
        Index('idx_bitacora_m02_rf_origen', 'rf_origen'),
        Index('idx_bitacora_m02_timestamp_evento', 'timestamp_evento'),
        Index('idx_bitacora_m02_usuario', 'id_usuario_responsable'),
        {'schema': 'modulo2'},
    )

    id_bitacora: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_evento: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, server_default=text('gen_random_uuid()')
    )
    rf_origen: Mapped[str] = mapped_column(String(10), nullable=False)
    tipo_evento: Mapped[str] = mapped_column(String(80), nullable=False)
    clasificacion_biologica: Mapped[str] = mapped_column(String(30), nullable=False)
    timestamp_evento: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    timestamp_registro: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text('now()')
    )
    resultado: Mapped[str] = mapped_column(
        String(15), nullable=False, server_default=text("'EXITOSO'::character varying")
    )
    severidad_log: Mapped[str] = mapped_column(
        String(10), nullable=False, server_default=text("'INFO'::character varying")
    )
    hash_integridad: Mapped[str] = mapped_column(String(64), nullable=False)
    registro_incompleto: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('false'))
    id_activo_biologico: Mapped[Optional[int]] = mapped_column(Integer)
    tipo_activo: Mapped[Optional[str]] = mapped_column(String(15))
    descripcion: Mapped[Optional[str]] = mapped_column(String(500))
    detalle_tecnico: Mapped[Optional[dict]] = mapped_column(JSONB)
    id_usuario_responsable: Mapped[Optional[int]] = mapped_column(Integer)
    modulo_consumidor: Mapped[Optional[str]] = mapped_column(String(30))
    id_evento_correlacionado: Mapped[Optional[uuid.UUID]] = mapped_column(PG_UUID(as_uuid=True))
