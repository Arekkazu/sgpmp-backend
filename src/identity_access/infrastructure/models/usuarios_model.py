"""Modelo ORM para la tabla `modulo1.usuarios`.

Entidad central del sistema: almacena la información personal, de autenticación
y de rol de cada usuario registrado.
"""
from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, CHAR, CheckConstraint, Column, Date, DateTime, Enum, ForeignKeyConstraint, Index, Integer, PrimaryKeyConstraint, Sequence, String, Table, Text, Time, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base_model import Base
from .enums_models import EnumUsuarioGenero

if TYPE_CHECKING:
    from .roles_model import Roles
    from .cuenta_usuarios_model import CuentasUsuarios
    from .dispositivos_fcm_model import DispositivosFcm
    from .eventos_model import Eventos
    from .gestiones_cuenta_model import GestionesCuenta
    from .notificaciones_model import Notificaciones

class Usuarios(Base):
    __tablename__ = 'usuarios'
    __table_args__ = (
        CheckConstraint("apellidos::text ~ '^[A-Za-zÁÉÍÓÚáéíóúÑñ ]+$'::text", name='chk_usuario_apellidos_validos'),
        CheckConstraint("correo_electronico::text ~* '^[A-Za-z0-9._%%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$'::text", name='chk_usuario_formato_correo'),
        CheckConstraint("nombre::text ~ '^[A-Za-zÁÉÍÓÚáéíóúÑñ ]+$'::text", name='chk_usuario_nombre_validos'),
        CheckConstraint("tipo_identificacion::text = ANY (ARRAY['CC'::character varying::text, 'CE'::character varying::text, 'Pasaporte'::character varying::text])", name='chk_usuario_tipo_identificacion'),
        ForeignKeyConstraint(['id_rol'], ['modulo1.roles.id_rol'], name='fk_rol'),
        PrimaryKeyConstraint('id_usuario', name='usuarios_pkey'),
        UniqueConstraint('correo_electronico', name='uq_usuario_correo_electronico'),
        UniqueConstraint('numero_identificacion', name='uq_usuario_numero_identificacion'),
        {'comment': 'Tabla maestra de usuarios del sistema. Almacena la información '
                'personal,\n'
                'de autenticación y de rol de cada persona registrada. Es la '
                'entidad central\n'
                'del módulo 1 y es referenciada por prácticamente todos los demás '
                'módulos\n'
                'del sistema para asociar acciones a un usuario específico.',
     'schema': 'modulo1'}
    )

    id_usuario: Mapped[int] = mapped_column(Integer, Sequence('usuarios_id_usuarios_seq', schema='modulo1'), primary_key=True, comment='Identificador único del usuario. Clave primaria generada automáticamente (serial).\nEs la FK más referenciada en todo el sistema.')
    correo_electronico: Mapped[str] = mapped_column(String(100), nullable=False, comment='Dirección de correo electrónico del usuario. Única en el sistema.\nEs el canal principal de comunicación y recuperación de cuenta. Máximo 100 caracteres.')
    contrasena_cifrada: Mapped[str] = mapped_column(String(255), nullable=False, comment='Hash de la contraseña del usuario. Nunca se almacena la contraseña en texto plano.\nSe recomienda bcrypt o argon2. Máximo 255 caracteres.')
    id_rol: Mapped[int] = mapped_column(Integer, nullable=False, comment='FK hacia modulo1.roles. Define el rol asignado al usuario, que determina\nsus permisos y accesos dentro del sistema.')
    fecha_registro: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=text('now()'), comment='Marca temporal (con zona horaria) del momento en que el usuario fue creado en el sistema.\nSe asigna automáticamente con now().')
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('1'), comment='Contador de versión del registro. Se incrementa con cada actualización.\nPermite control de concurrencia optimista (optimistic locking).')
    # Nullable desde el gap de SSO AgroFusion (2026-08-08): el payload RS256 del
    # handoff SSO solo trae sub+email; una cuenta PENDIENTE_DATOS queda con estos
    # 6 campos en NULL hasta que el usuario complete su perfil. Ver
    # anotaciones/modulo_1/gaps_bd_sso_agrofusion.md.
    tipo_identificacion: Mapped[Optional[str]] = mapped_column(String(10), comment='Tipo de documento de identidad del usuario (ej: CC, CE, NIT, PA).\nMáximo 10 caracteres. Usado junto con numero_identificacion para identificación civil.')
    numero_identificacion: Mapped[Optional[str]] = mapped_column(String(20), comment='Número del documento de identidad del usuario. Único en el sistema.\nMáximo 20 caracteres. No puede repetirse sin importar el tipo de identificación.')
    nombre: Mapped[Optional[str]] = mapped_column(String(80), comment='Nombre(s) del usuario. Máximo 80 caracteres.')
    apellidos: Mapped[Optional[str]] = mapped_column(String(80), comment='Apellido(s) del usuario. Máximo 80 caracteres.')
    fecha_nacimiento: Mapped[Optional[datetime.date]] = mapped_column(Date, comment='Fecha de nacimiento del usuario. Usada para validaciones de edad mínima\ny para perfiles demográficos.')
    genero: Mapped[Optional[EnumUsuarioGenero]] = mapped_column(Enum(EnumUsuarioGenero, values_callable=lambda cls: [member.value for member in cls], name='enum_usuario_genero', schema='modulo1'), comment='Género del usuario. ENUM global del sistema (enum_usuario_genero).')
    telefono: Mapped[Optional[str]] = mapped_column(String(20), comment='Número de teléfono de contacto del usuario. Opcional. Máximo 20 caracteres.')
    direccion: Mapped[Optional[str]] = mapped_column(String(150), comment='Dirección física de residencia o contacto del usuario. Opcional. Máximo 150 caracteres.')
    fecha_actualizacion: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'), comment='Marca temporal (con zona horaria) de la última modificación del registro del usuario.\nDebe actualizarse mediante trigger cada vez que el registro cambie.')

    roles: Mapped['Roles'] = relationship('Roles', back_populates='usuarios')
    cuentas_usuarios: Mapped['CuentasUsuarios'] = relationship('CuentasUsuarios', uselist=False, back_populates='usuarios')
    dispositivos_fcm: Mapped[list['DispositivosFcm']] = relationship('DispositivosFcm', back_populates='usuarios')
    eventos: Mapped[list['Eventos']] = relationship('Eventos', back_populates='usuarios')
    gestiones_cuenta: Mapped[list['GestionesCuenta']] = relationship('GestionesCuenta', back_populates='usuarios')
    notificaciones: Mapped[list['Notificaciones']] = relationship('Notificaciones', back_populates='usuarios')

