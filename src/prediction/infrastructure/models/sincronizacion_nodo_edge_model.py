from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, Sequence, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.prediction.infrastructure.models.base_model import Base


class SincronizacionNodoEdgeModel(Base):
    """``modulo4.sincronizacion_nodos_edge`` (RF-65 E7/E8/E10, DEV-09).

    Una fila por (nodo, tipo_modelo): ``uq_sync_dispositivo_tipo``.
    """

    __tablename__ = "sincronizacion_nodos_edge"
    __table_args__ = {"schema": "modulo4"}

    id_sincronizacion: Mapped[int] = mapped_column(
        Integer,
        Sequence("sincronizacion_nodos_edge_id_sincronizacion_seq", schema="modulo4"),
        primary_key=True,
    )
    id_dispositivo_iot: Mapped[int] = mapped_column(Integer, nullable=False)
    # enum_tipo_modelo — String para no conflictuar con el tipo existente.
    tipo_modelo: Mapped[str] = mapped_column(String(40), nullable=False)
    config_version_servidor: Mapped[int] = mapped_column(Integer, nullable=False)
    config_version_nodo: Mapped[Optional[int]] = mapped_column(Integer)
    # enum_estado_sincronizacion_nodo: PENDIENTE | APLICADA | FALLIDA | DESINCRONIZADO
    estado_sincronizacion: Mapped[str] = mapped_column(String(20), nullable=False)
    intentos_sincronizacion: Mapped[int] = mapped_column(Integer, nullable=False)
    fecha_ultimo_intento: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    fecha_aplicacion: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    motivo_fallo: Mapped[Optional[str]] = mapped_column(Text)
