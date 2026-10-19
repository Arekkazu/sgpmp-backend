from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class SincronizacionReglaEdgeModel(Base):
    """``modulo3.sincronizaciones_reglas_edge`` (DEV-08, migración e3b8c1d9f702)."""

    __tablename__ = 'sincronizaciones_reglas_edge'
    __table_args__ = (
        UniqueConstraint(
            'id_regla_alertas', 'id_dispositivo_iot',
            name='uq_sincronizacion_regla_edge_id_regla_alertas_id_dispositivo_iot',
        ),
        {'schema': 'modulo3'},
    )

    id_sincronizacion_regla_edge: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_regla_alertas: Mapped[int] = mapped_column(
        Integer, ForeignKey('modulo3.reglas_alertas.id_regla_alertas'), nullable=False
    )
    id_dispositivo_iot: Mapped[int] = mapped_column(
        Integer, ForeignKey('modulo9.dispositivos_iot.id_dispositivo_iot'), nullable=False
    )
    version_regla: Mapped[int] = mapped_column(Integer, nullable=False)
    # enum_sincronizacion_regla_edge_estado_sincronizacion: APLICADA | PENDIENTE | NO_CONF
    estado_sincronizacion: Mapped[str] = mapped_column(String(10), nullable=False)
    mensaje: Mapped[Optional[str]] = mapped_column(Text)
    intentos_sincronizacion: Mapped[int] = mapped_column(Integer, nullable=False)
    fecha_ultimo_intento: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fecha_aplicacion: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    id_usuario: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('modulo1.usuarios.id_usuario'))
