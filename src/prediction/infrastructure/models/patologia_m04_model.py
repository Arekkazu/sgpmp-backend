from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, Sequence, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.prediction.infrastructure.models.base_model import Base


class PatologiaM04Model(Base):
    __tablename__ = "patologias"
    __table_args__ = {"schema": "modulo9"}

    id_patologia: Mapped[int] = mapped_column(
        Integer,
        Sequence("patologias_id_patologias_seq", schema="modulo9"),
        primary_key=True,
    )
    nombre: Mapped[str] = mapped_column(String(60), nullable=False)
    es_activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    es_base: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    version_catalogo: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    especie_aplicable: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default=text("'TODAS'::character varying")
    )
    descripcion_clinica: Mapped[Optional[str]] = mapped_column(Text)
    fecha_creacion_m04: Mapped[datetime] = mapped_column(DateTime(True), nullable=False, server_default=text("now()"))
    id_usuario_creador: Mapped[Optional[int]] = mapped_column(Integer)
    fecha_actualizacion: Mapped[Optional[datetime]] = mapped_column(DateTime(True))

    variables: Mapped[list["PatologiaVariableModel"]] = relationship(
        "PatologiaVariableModel",
        back_populates="patologia",
        cascade="all, delete-orphan",
        lazy="selectin",
        foreign_keys="PatologiaVariableModel.id_patologia",
    )
