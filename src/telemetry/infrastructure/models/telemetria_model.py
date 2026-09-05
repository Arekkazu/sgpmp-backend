from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Identity, Integer, Numeric, PrimaryKeyConstraint, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class TelemetriaModel(Base):
    __tablename__ = 'telemetrias'
    __table_args__ = (
        PrimaryKeyConstraint('id_telemetria', name='telemetrias_pkey'),
        UniqueConstraint(
            'id_sensor', 'id_variable', 'timestamp_captura', 'origen',
            name='uq_telemetria_sensor_variable_captura_origen',
        ),
        {'schema': 'modulo3'},
    )

    id_telemetria: Mapped[int] = mapped_column(
        Integer,
        Identity(start=1, increment=1),
        primary_key=True,
    )
    id_sensor: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('modulo9.sensores.id_sensores', name='fk_sensor_id'),
        nullable=False,
    )
    id_variable: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('modulo9.variables_ambientales.id_variable_ambiental', name='fk_variable_id'),
        nullable=False,
    )
    id_dispositivo_iot: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('modulo9.dispositivos_iot.id_dispositivo_iot', name='fk_dispositivo_iot_id'),
        nullable=False,
    )
    valor_crudo: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    valor_ajustado: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))
    timestamp_captura: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    timestamp_envio: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    timestamp_procesamiento: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # PG enum — usar String para no conflictuar con el tipo existente en PostgreSQL
    origen: Mapped[str] = mapped_column(String(20), nullable=False)
    estado_calidad: Mapped[str] = mapped_column(String(30), nullable=False)
    calibrado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    latitud: Mapped[Optional[Decimal]] = mapped_column(Numeric(9, 6))
    longitud: Mapped[Optional[Decimal]] = mapped_column(Numeric(9, 6))
    metadatos: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    categoria_variable: Mapped[str] = mapped_column(String(20), nullable=False)
    unidad_medida: Mapped[str] = mapped_column(String(20), nullable=False)
    version_calibracion: Mapped[Optional[str]] = mapped_column(String(50))
    parametros_calibracion: Mapped[Optional[dict]] = mapped_column(JSONB)
    valor_agregado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ventana_agregacion_min: Mapped[Optional[int]] = mapped_column(Integer)
    tipo_dato: Mapped[str] = mapped_column(String(20), nullable=False, default='CRUDO')
    latencia_alta: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    frecuencia_anomala: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    posible_drift: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    dato_buferizado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Nota: typo en la DB — nombre exacto de la columna es dato_agredado_edge
    dato_agredado_edge: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reloj_desincronizado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    latencia_procesamiento_ms: Mapped[Optional[int]] = mapped_column(Integer)
    nivel_bateria_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    calidad_senal_rssi: Mapped[Optional[Decimal]] = mapped_column(Numeric(7, 2))
    calidad_senal_snr: Mapped[Optional[Decimal]] = mapped_column(Numeric(7, 2))
    frecuencia_muestreo_min: Mapped[Optional[int]] = mapped_column(Integer)
    estado_conectividad: Mapped[Optional[bool]] = mapped_column(Boolean)
    # RF-62: flags de aptitud
    apto_para_ia: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    apto_para_nic41: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
