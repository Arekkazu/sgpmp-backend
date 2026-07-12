from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, Numeric, Sequence, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.prediction.infrastructure.models.base_model import Base


class VersionModeloModel(Base):
    __tablename__ = "versiones_modelos"
    __table_args__ = {"schema": "modulo4"}

    id_version_modelo: Mapped[int] = mapped_column(
        Integer,
        Sequence("versiones_modelos_id_version_modelo_seq", schema="modulo4"),
        primary_key=True,
    )
    nombre_version: Mapped[str] = mapped_column(String(100), nullable=False)
    algoritmo: Mapped[Optional[str]] = mapped_column(String(40))
    tipo_modelo: Mapped[Optional[str]] = mapped_column(String(40))
    descripcion: Mapped[Optional[str]] = mapped_column(Text)
    estado_version: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'EN_VALIDACION'")
    )
    formato_artefacto: Mapped[Optional[str]] = mapped_column(String(30))
    ruta_artefacto: Mapped[Optional[str]] = mapped_column(Text)
    tamanio_artefacto_bytes: Mapped[Optional[int]] = mapped_column(BigInteger)
    hash_artefacto_sha256: Mapped[Optional[str]] = mapped_column(String(64))
    dataset_entrenamiento_hash: Mapped[Optional[str]] = mapped_column(String(64))
    id_proceso_rf71: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    version_referencia: Mapped[Optional[int]] = mapped_column(Integer)
    f1_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 6))
    recall_clase_riesgo_alto: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 6))
    precision_modelo: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 6))
    accuracy: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 6))
    roc_auc_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 6))
    recall_por_clase: Mapped[Optional[dict]] = mapped_column(JSONB)
    matriz_confusion: Mapped[Optional[dict]] = mapped_column(JSONB)
    compatibilidad_variables: Mapped[Optional[list]] = mapped_column(JSONB)
    notas_validacion: Mapped[Optional[str]] = mapped_column(Text)
    detalle_validacion: Mapped[Optional[str]] = mapped_column(Text)
    id_usuario: Mapped[Optional[int]] = mapped_column(Integer)
    esta_produccion: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    fecha_entrenamiento: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    fecha_registro: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    fecha_despliegue: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
