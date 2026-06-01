from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Optional
from sqlalchemy import Boolean, DateTime, Integer, PrimaryKeyConstraint, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base_model import Base

if TYPE_CHECKING:
    from .permisos_model import Permisos



class Recursos(Base):
    __tablename__ = 'recursos'
    __table_args__ = (
        PrimaryKeyConstraint('id_recurso', name='recursos_pkey'),
        UniqueConstraint('nombre_recurso', name='uq_nombre_recurso'),
        {'comment': 'Catálogo de los recursos del sistema sobre los que se controlan '
                'los permisos de acceso.\n'
                'Un recurso puede ser una tabla, vista, módulo, endpoint o proceso '
                'especial.\n'
                'Es uno de los pilares de la matriz de control de acceso (ACL) '
                'junto con acciones y roles.',
     'schema': 'modulo1'}
    )

    id_recurso: Mapped[int] = mapped_column(Integer, primary_key=True, comment='Identificador único del recurso. Clave primaria (entero, no serial — se asigna manualmente).')
    nombre_recurso: Mapped[str] = mapped_column(String(60), nullable=False, comment='Nombre único del recurso en el sistema (ej: GESTION_USUARIOS, REPORTES_FINANCIEROS).\nMáximo 60 caracteres.')
    es_proceso_especial: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('false'), comment='Indica si el recurso corresponde a un proceso especial o crítico del sistema\nque requiere validaciones adicionales de acceso. Por defecto false.')
    fecha_creacion: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'), comment='Marca temporal (con zona horaria) del momento en que se registró el recurso.\nNótese que el tipo es TIME WITH TIME ZONE, no TIMESTAMP — heredado del diseño original.')
    descripcion: Mapped[Optional[str]] = mapped_column(String(255), comment='Descripción del recurso: qué representa, a qué entidad o funcionalidad del sistema\ncorresponde. Máximo 255 caracteres.')

    permisos: Mapped[list['Permisos']] = relationship('Permisos', back_populates='recursos')
