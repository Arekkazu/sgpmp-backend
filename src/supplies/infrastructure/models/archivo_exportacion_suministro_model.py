# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-77/RF-81: archivos exportados          |
"""Modelo ORM de ``modulo5.archivos_exportacion_suministros`` (RF-77 24 h / RF-81 72 h)."""
import datetime
import uuid
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Integer, LargeBinary, String, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import Base


class ArchivoExportacionSuministroModel(Base):
    __tablename__ = "archivos_exportacion_suministros"
    __table_args__ = {"schema": "modulo5"}

    id_archivo_exportacion_suministro: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    origen: Mapped[str] = mapped_column(String(10), nullable=False)
    id_referencia: Mapped[Optional[int]] = mapped_column(Integer)
    formato: Mapped[str] = mapped_column(String(10), nullable=False)
    nombre_archivo: Mapped[str] = mapped_column(String(255), nullable=False)
    tipo_contenido: Mapped[str] = mapped_column(String(100), nullable=False)
    contenido: Mapped[Optional[bytes]] = mapped_column(LargeBinary)
    tamano_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    total_registros: Mapped[int] = mapped_column(Integer, nullable=False)
    id_usuario: Mapped[int] = mapped_column(Integer, nullable=False)
    fecha_generacion: Mapped[datetime.datetime] = mapped_column(
        DateTime(True), nullable=False, server_default=text("now()")
    )
    fecha_expiracion: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False)
    fecha_eliminacion: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
