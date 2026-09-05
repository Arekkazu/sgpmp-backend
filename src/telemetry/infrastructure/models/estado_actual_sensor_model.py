from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Identity, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class EstadoActualSensorModel(Base):
    __tablename__ = 'estados_actuales_sensores'
    __table_args__ = (
        UniqueConstraint('id_sensor', name='uq_estados_actuales_por_sensor'),
        {'schema': 'modulo3'},
    )

    id_estado_actual_sensor: Mapped[int] = mapped_column(
        Integer, Identity(start=1, increment=1), primary_key=True
    )
    id_sensor: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('modulo9.sensores.id_sensores', ondelete='CASCADE', name='fk_estados_actuales_sensor'),
        nullable=False,
    )
    id_dispositivo_iot: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('modulo9.dispositivos_iot.id_dispositivo_iot', name='fk_estados_actuales_dispositivo'),
        nullable=False,
    )
    ultimo_valor: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4))
    ultima_unidad: Mapped[Optional[str]] = mapped_column(String(20))
    ultimo_timestamp_captura: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    ultimo_timestamp_actualizacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    # PG enums — String para no conflictuar con tipos existentes en PostgreSQL
    estado_semaforo: Mapped[Optional[str]] = mapped_column(String(20))
    estado_calidad: Mapped[Optional[str]] = mapped_column(String(30))
    estado_desviacion: Mapped[Optional[str]] = mapped_column(String(40))
    estado_conectividad: Mapped[Optional[str]] = mapped_column(String(30))
    tiempo_sin_reporte_min: Mapped[Optional[int]] = mapped_column(Integer)
    dato_desactualizado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    id_alerta: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey('modulo3.alertas.id_alerta', ondelete='SET NULL', name='fk_estados_actuales_alerta'),
    )
    tendencia: Mapped[Optional[str]] = mapped_column(String(20))
