from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKeyConstraint, Integer, Numeric, PrimaryKeyConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.prediction.infrastructure.models.base_model import Base


class PatologiaVariableModel(Base):
    __tablename__ = "patologias_variables_sensoricas"
    __table_args__ = (
        ForeignKeyConstraint(
            ["id_patologia"],
            ["modulo9.patologias.id_patologia"],
            name="fk_pvs_patologia",
        ),
        PrimaryKeyConstraint("id_patologia_variable", name="patologias_variables_sensoricas_pkey"),
        {"schema": "modulo4"},
    )

    id_patologia_variable: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_patologia: Mapped[int] = mapped_column(Integer, nullable=False)
    id_variable_ambiental: Mapped[int] = mapped_column(Integer, nullable=False)
    peso_evidencia: Mapped[Decimal] = mapped_column(
        Numeric(4, 3), nullable=False, server_default=text("1.000")
    )
    es_variable_critica: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    fecha_asociacion: Mapped[datetime] = mapped_column(DateTime(True), nullable=False, server_default=text("now()"))

    patologia: Mapped["PatologiaM04Model"] = relationship(
        "PatologiaM04Model",
        back_populates="variables",
        foreign_keys=[id_patologia],
    )
