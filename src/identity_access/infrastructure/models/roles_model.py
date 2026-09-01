"""Modelo ORM para la tabla `modulo1.roles`.

Catálogo de roles del sistema para el control de acceso basado en roles (RBAC).
Los roles marcados con `es_protegido=True` no pueden ser eliminados ni modificados.
"""
from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Optional
from sqlalchemy import Boolean, Integer, PrimaryKeyConstraint, String, Time, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base_model import Base

if TYPE_CHECKING:
    from .permisos_model import Permisos
    from .usuarios_model import Usuarios


class Roles(Base):
    __tablename__ = 'roles'
    __table_args__ = (
        PrimaryKeyConstraint('id_rol', name='roles_pkey'),
        UniqueConstraint('nombre_rol', name='uq_nombre'),
        {'comment': 'Catálogo de roles del sistema. Un rol agrupa un conjunto de '
                'permisos y define\n'
                'el nivel de acceso de los usuarios asignados. Permite gestionar '
                'la seguridad\n'
                'mediante control de acceso basado en roles (RBAC).',
     'schema': 'modulo1'}
    )

    id_rol: Mapped[int] = mapped_column(Integer, primary_key=True, comment='Identificador único del rol. Clave primaria (serial).')
    nombre_rol: Mapped[str] = mapped_column(String(100), nullable=False, comment='Nombre único del rol (ej: ADMINISTRADOR, VETERINARIO, LIDER_AREA, AUDITOR).\nMáximo 100 caracteres. No puede repetirse.')
    es_protegido: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('false'), comment='Indica si el rol es de sistema y no puede ser modificado ni eliminado por usuarios.\nLos roles protegidos son creados durante la inicialización del sistema (ej: SUPERADMIN).')
    descripcion: Mapped[Optional[str]] = mapped_column(String(255), comment='Descripción del alcance y propósito del rol dentro del sistema.\nMáximo 255 caracteres.')
    fecha_creacion: Mapped[Optional[datetime.time]] = mapped_column(Time(True), server_default=text('now()'), comment='Marca temporal (con zona horaria) del momento en que se creó el rol.')
    fecha_actualizacion: Mapped[Optional[datetime.time]] = mapped_column(Time(True), comment='Marca temporal (con zona horaria) de la última modificación del rol.\nDebe actualizarse mediante trigger.')

    # La base de datos elimina los permisos al borrar el rol. ``"all"`` evita
    # que SQLAlchemy intente poner ``id_rol=NULL`` o borrar los hijos antes que
    # el padre, lo cual chocaria con el NOT NULL y con la guarda de permiso minimo.
    permisos: Mapped[list['Permisos']] = relationship(
        'Permisos',
        back_populates='roles',
        passive_deletes='all',
    )
    usuarios: Mapped[list['Usuarios']] = relationship('Usuarios', back_populates='roles')

