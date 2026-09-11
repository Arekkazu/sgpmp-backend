from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Date, DateTime, ForeignKey, Identity, Integer, Numeric, PrimaryKeyConstraint, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base_model import Base

if TYPE_CHECKING:
    from .detalle_individual_model import DetalleActivoIndividualModel
    from .detalle_poblacional_model import DetalleActivoPoblacionalModel
    from .estado_activo_model import EstadoActivoBiologicoModel
    from .historial_infraestructura_activo_model import HistorialInfraestructuraActivoModel


class ActivoBiologicoModel(Base):
    __tablename__ = 'activos_biologicos'
    __table_args__ = (
        PrimaryKeyConstraint('id_activo_biologico', name='activos_biologicos_pkey'),
        UniqueConstraint('identificador', name='uq_activo_biologico_identificador'),
        {'schema': 'modulo2'},
    )

    id_activo_biologico: Mapped[int] = mapped_column(
        Integer,
        Identity(start=1, increment=1),
        primary_key=True,
    )
    id_especie: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('modulo9.especies.id_especie', name='fk_activo_especie'),
        nullable=False,
    )
    identificador: Mapped[Optional[str]] = mapped_column(String(50))
    id_infraestructura: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('modulo9.infraestructuras.id_infraestructura', name='activos_biologicos_id_infraestructura_fkey'),
        nullable=False,
    )
    # PG enum — usar String para no conflictuar con el tipo existente en PostgreSQL
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    fecha_inicio_ciclo: Mapped[Optional[date]] = mapped_column(Date)
    id_estado: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('modulo2.estados_activos_biologicos.id_estado_activo_biologico', name='activos_biologicos_id_estado_fkey'),
        nullable=False,
    )
    descripcion: Mapped[Optional[str]] = mapped_column(String(255))
    # PG enum — usar String
    origen_financiero: Mapped[str] = mapped_column(String(30), nullable=False)
    costo_adquisicion: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 4))
    atributos_dinamicos: Mapped[Optional[dict]] = mapped_column(JSONB)
    id_usuario: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('modulo1.usuarios.id_usuario', name='activos_biologicos_id_usuario_fkey'),
        nullable=False,
    )
    fecha_creacion: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    id_dispositivo_iot: Mapped[Optional[int]] = mapped_column(Integer)
    soporte_documental: Mapped[Optional[str]] = mapped_column(String(150))
    detalles_procedencia: Mapped[Optional[str]] = mapped_column(String(100))

    # ── Relationships ────────────────────────────────────────────────────────
    estado: Mapped[EstadoActivoBiologicoModel] = relationship(
        'EstadoActivoBiologicoModel',
        lazy='selectin',
    )
    detalle_individual: Mapped[Optional[DetalleActivoIndividualModel]] = relationship(
        'DetalleActivoIndividualModel',
        back_populates='activo',
        cascade='all, delete-orphan',
        lazy='selectin',
        uselist=False,
    )
    detalle_poblacional: Mapped[Optional[DetalleActivoPoblacionalModel]] = relationship(
        'DetalleActivoPoblacionalModel',
        back_populates='activo',
        cascade='all, delete-orphan',
        lazy='selectin',
        uselist=False,
    )
    historial_infraestructura: Mapped[list[HistorialInfraestructuraActivoModel]] = relationship(
        'HistorialInfraestructuraActivoModel',
        back_populates='activo',
        cascade='all, delete-orphan',
        lazy='selectin',
    )
