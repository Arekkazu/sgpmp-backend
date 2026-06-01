import datetime
from typing import Optional
from sqlalchemy import Boolean, CHAR, CheckConstraint, Column, Date, DateTime, Enum, ForeignKeyConstraint, Index, Integer, PrimaryKeyConstraint, Sequence, String, Table, Text, Time, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from base_model import Base




class Permisos(Base):
    __tablename__ = 'permisos'
    __table_args__ = (
        ForeignKeyConstraint(['id_accion'], ['modulo1.acciones.id_accion'], name='fk_accion_permiso'),
        ForeignKeyConstraint(['id_recurso'], ['modulo1.recursos.id_recurso'], name='fk_recurso_permiso'),
        ForeignKeyConstraint(['id_rol'], ['modulo1.roles.id_rol'], name='fk_recurso_rol'),
        PrimaryKeyConstraint('id_permiso', name='permisos_pkey'),
        UniqueConstraint('id_rol', 'id_recurso', 'id_accion', name='uq_permiso_unico'),
        {'comment': 'Define los permisos del sistema, asociando un rol a una acción '
                'permitida\n'
                'sobre un recurso específico. Es la tabla que implementa la matriz '
                'de control\n'
                'de acceso (ACL) del sistema: qué rol puede hacer qué acción sobre '
                'qué recurso.',
     'schema': 'modulo1'}
    )

    id_permiso: Mapped[int] = mapped_column(Integer, primary_key=True, comment='Identificador único del permiso. Clave primaria (serial).')
    nombre: Mapped[str] = mapped_column(String(50), nullable=False, comment='Nombre descriptivo y único del permiso (ej: VER_REPORTES, EDITAR_ACTIVOS).\nMáximo 20 caracteres.')
    fecha_creacion: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'), comment='Marca temporal (con zona horaria) del momento en que se creó el permiso.')
    es_activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('true'), comment='Indica si el permiso está vigente y aplicable. Un permiso inactivo no se evalúa\nen las validaciones de acceso, permitiendo deshabilitarlo sin eliminarlo.')
    id_recurso: Mapped[int] = mapped_column(Integer, nullable=False, comment='FK hacia modulo1.recursos. Recurso del sistema sobre el que aplica este permiso.')
    id_accion: Mapped[int] = mapped_column(Integer, nullable=False, comment='FK hacia modulo1.acciones. Acción específica que este permiso autoriza sobre el recurso.')
    id_rol: Mapped[int] = mapped_column(Integer, nullable=False, comment='FK hacia modulo1.roles. Rol al que se le concede este permiso.')
    descripcion: Mapped[Optional[str]] = mapped_column(String(255), comment='Descripción del alcance del permiso: qué acción autoriza y sobre qué contexto.\n255 caracteres fijos (tipo char).')
    fecha_actualizacion: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), comment='Marca temporal (con zona horaria) de la última modificación del permiso.')

    acciones: Mapped['Acciones'] = relationship('Acciones', back_populates='permisos')
    recursos: Mapped['Recursos'] = relationship('Recursos', back_populates='permisos')
    roles: Mapped['Roles'] = relationship('Roles', back_populates='permisos')

