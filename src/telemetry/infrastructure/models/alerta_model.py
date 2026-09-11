from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Identity, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class AlertaModel(Base):
    __tablename__ = 'alertas'
    __table_args__ = {'schema': 'modulo3'}

    id_alerta: Mapped[int] = mapped_column(Integer, Identity(start=1, increment=1), primary_key=True)
    tipo_alerta: Mapped[str] = mapped_column(String(40), nullable=False)
    severidad: Mapped[str] = mapped_column(String(20), nullable=False)
    estado_alerta: Mapped[str] = mapped_column(String(30), nullable=False, default='ACTIVA')
    origen_evento: Mapped[str] = mapped_column(String(20), nullable=False)
    tipo_variable: Mapped[str] = mapped_column(String(50), nullable=False)
    valor: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4))
    unidad: Mapped[Optional[str]] = mapped_column(String(20))
    reglas_activas: Mapped[Any] = mapped_column(JSONB, nullable=False, default=list)
    contexto_activo_biologico: Mapped[Optional[Any]] = mapped_column(JSONB)
    metadato_evento: Mapped[Optional[Any]] = mapped_column(JSONB)
    accion_sugerida: Mapped[Optional[str]] = mapped_column(Text)
    motivo_descarte: Mapped[Optional[str]] = mapped_column(Text)
    diagnostico: Mapped[Optional[str]] = mapped_column(Text)

    tiene_inferencia_no_disponible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    tiene_contexto_incompleto: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    tiene_generada_por_reevaluacion: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # PG enums opcionales — String para no conflictuar con tipos existentes
    conflicto_resolucion: Mapped[Optional[str]] = mapped_column(String(30))
    severidad_edge_original: Mapped[Optional[str]] = mapped_column(String(20))
    # Typo en DB: serveridad_ia (no severidad_ia)
    serveridad_ia: Mapped[Optional[str]] = mapped_column(String(20))

    frecuencia_evento: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    ultima_ocurrencia: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    fecha_evento: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fecha_generacion: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fecha_registro: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    fecha_notificacion: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    fecha_atencion: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    fecha_resolucion: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    fecha_vencimiento: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    id_sensor: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey('modulo9.sensores.id_sensores')
    )
    id_dispositivo_ioit: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey('modulo9.dispositivos_iot.id_dispositivo_iot')
    )
    id_activo_biologico: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey('modulo2.activos_biologicos.id_activo_biologico')
    )
    id_infraestructura: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey('modulo9.infraestructura.id_infraestructura')
    )
    id_evento_edge_computing: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey('modulo3.eventos_edge_computing.id_evento_edge_computing')
    )
    id_telemetria: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey('modulo3.telemetria.id_telemetria')
    )
    id_paquete_inferencia: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey('modulo3.paquetes_inferencia.id_paquetes_inferencia')
    )
    id_regla_alerta: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey('modulo3.reglas_alertas.id_regla_alertas')
    )
    id_usuario_atencion: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey('modulo1.usuarios.id_usuario')
    )
    id_usuario_resolucion: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey('modulo1.usuarios.id_usuario')
    )
    referencia_alerta_original: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey('modulo3.alertas.id_alerta')
    )
