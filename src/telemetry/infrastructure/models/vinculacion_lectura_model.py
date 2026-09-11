from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Identity, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class VinculacionLecturaModel(Base):
    __tablename__ = 'vinculaciones_lecturas'
    __table_args__ = {'schema': 'modulo3'}

    id_vinculacion_lectura: Mapped[int] = mapped_column(Integer, Identity(start=1, increment=1), primary_key=True)
    id_telemetria: Mapped[int] = mapped_column(
        Integer, ForeignKey('modulo3.telemetria.id_telemetria'), nullable=False
    )
    # enum_modelo_manejo: INDIVIDUAL|POBLACIONAL
    modelo_manejo: Mapped[str] = mapped_column(String(20), nullable=False)
    id_activo_biologico: Mapped[Optional[int]] = mapped_column(Integer)
    id_infraestructura: Mapped[int] = mapped_column(
        Integer, ForeignKey('modulo9.infraestructura.id_infraestructura'), nullable=False
    )
    fecha_inicio_vinculacion: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fecha_fin_vinculacion: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    # enum_mecanismo_vinculacion: AUTOMATICA|MANUAL|CORRECCION
    mecanismo_vinculacion: Mapped[str] = mapped_column(String(20), nullable=False)
    # enum_estado_vinculacion: VINCULADA|SIN_VINCULAR|AMBIGUA|CORREGIDA
    estado_vinculacion: Mapped[str] = mapped_column(String(20), nullable=False, default='VINCULADA')
    id_usuario: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey('modulo1.usuarios.id_usuario')
    )
    # Typo en DB: motivo_correcion
    motivo_correcion: Mapped[Optional[str]] = mapped_column(Text)
    # Typo en DB: id_vinculacion_remplazada
    id_vinculacion_remplazada: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey('modulo3.vinculaciones_lecturas.id_vinculacion_lectura')
    )
    fecha_creacion: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
