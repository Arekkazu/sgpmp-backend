from typing import Optional
import datetime
import enum

from sqlalchemy import CHAR, CheckConstraint, Enum, Integer, PrimaryKeyConstraint, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from base_model import Base
from permisos_model import Permisos

class Acciones(Base):
    __tablename__ = 'acciones'
    __table_args__ = (
        CheckConstraint("codigo = ANY (ARRAY['C'::bpchar, 'R'::bpchar, 'U'::bpchar, 'D'::bpchar, 'E'::bpchar])", name='chk_acciones_codigo_dominio'),
        PrimaryKeyConstraint('id_accion', name='acciones_pkey'),
        UniqueConstraint('codigo', name='acciones_codigo_key'),
        {'comment': 'Catálogo de las acciones básicas que pueden realizarse sobre los '
                'recursos del sistema.\n'
                'Generalmente representan las operaciones CRUD y acciones '
                'especiales.\n'
                'Junto con recursos y roles, forma la base del control de acceso.',
     'schema': 'modulo1'}
    )

    id_accion: Mapped[int] = mapped_column(Integer, primary_key=True, comment='Identificador único de la acción. Clave primaria (serial).')
    codigo: Mapped[str] = mapped_column(CHAR(1), nullable=False, comment='Código de un solo carácter que identifica la acción (ej: C=Create, R=Read,\nU=Update, D=Delete, E=Execute). Único en el sistema.')
    descripcion: Mapped[Optional[str]] = mapped_column(String(50), comment='Descripción de la acción que representa el código (ej: "Crear registro",\n"Consultar información"). Máximo 50 caracteres.')

    permisos: Mapped[list['Permisos']] = relationship('Permisos', back_populates='acciones')
