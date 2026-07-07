from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Integer, SmallInteger, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class BitacoraAuditoriaIotModel(Base):
    __tablename__ = 'bitacora_auditoria_iot'
    __table_args__ = ({'schema': 'modulo3'},)

    id_evento: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default='gen_random_uuid()',
    )
    # RF-10 base fields
    id_usuario: Mapped[Optional[int]] = mapped_column(Integer)
    nombre_usuario: Mapped[Optional[str]] = mapped_column(String(255))
    tipo_evento: Mapped[str] = mapped_column(String(80), nullable=False)
    modulo: Mapped[str] = mapped_column(String(10), nullable=False, default='M03')
    descripcion: Mapped[Optional[str]] = mapped_column(String(500))
    resultado: Mapped[str] = mapped_column(String(20), nullable=False)
    direccion_ip: Mapped[Optional[str]] = mapped_column(String(45))
    user_agent: Mapped[Optional[str]] = mapped_column(String(500))
    id_sesion: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True))
    fecha_hora: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # RF-63 IoT extension
    accion_detallada: Mapped[Optional[dict]] = mapped_column(JSONB)
    entidad_afectada_tipo: Mapped[Optional[str]] = mapped_column(String(30))
    entidad_afectada_id: Mapped[Optional[str]] = mapped_column(String(100))
    severidad_log: Mapped[str] = mapped_column(String(10), nullable=False, default='INFO')
    hash_integridad: Mapped[str] = mapped_column(String(64), nullable=False)
    clasificacion_registro: Mapped[str] = mapped_column(String(10), nullable=False, default='TECNICO')
    retencion_aplicable: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    registro_incompleto: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    componente_origen: Mapped[Optional[str]] = mapped_column(String(10))
    timestamp_registro: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default='now()'
    )
