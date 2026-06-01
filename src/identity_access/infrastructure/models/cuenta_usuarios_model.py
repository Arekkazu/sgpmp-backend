from typing import Optional
import datetime
import enum

from sqlalchemy import Boolean, CHAR, CheckConstraint, Column, Date, DateTime, Enum, ForeignKeyConstraint, Index, Integer, PrimaryKeyConstraint, Sequence, String, Table, Text, Time, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from base_model import Base


class CuentasUsuarios(Base):
    __tablename__ = 'cuentas_usuarios'
    __table_args__ = (
        CheckConstraint('intentos_fallidos <= 5', name='chk_cuentas_intentos_max_cinco'),
        CheckConstraint('intentos_fallidos >= 0', name='chk_cuentas_intentos_no_negativos'),
        ForeignKeyConstraint(['id_estado_cuenta'], ['modulo1.estados_cuentas.id_estado_cuenta'], name='fk_estado_cuenta'),
        ForeignKeyConstraint(['id_usuario'], ['modulo1.usuarios.id_usuario'], name='fk_usuario'),
        PrimaryKeyConstraint('id_cuenta_usuario', name='uq_usuario_id'),
        UniqueConstraint('id_usuario', name='uq_usuario'),
        {'comment': 'Gestiona el estado operativo y de seguridad de la cuenta de '
                'acceso de cada usuario.\n'
                'Separa la información de identidad (tabla usuarios) de la '
                'información de cuenta\n'
                '(intentos, bloqueos, tokens, verificaciones). Cada usuario tiene '
                'exactamente\n'
                'una cuenta asociada (relación 1:1).',
     'schema': 'modulo1'}
    )

    id_cuenta_usuario: Mapped[int] = mapped_column(Integer, primary_key=True, comment='Identificador único de la cuenta de usuario. Clave primaria (serial).')
    id_usuario: Mapped[int] = mapped_column(Integer, nullable=False, comment='FK hacia modulo1.usuarios. Usuario al que pertenece esta cuenta. Único (1:1).')
    id_estado_cuenta: Mapped[int] = mapped_column(Integer, nullable=False, comment='FK hacia modulo1.estados_cuenta. Estado actual de la cuenta (ej: ACTIVA, BLOQUEADA).')
    tiene_correo_verificado: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('false'), comment='Indica si el usuario ha verificado su correo electrónico mediante el enlace\nde confirmación enviado al registrarse. Por defecto false.')
    intentos_fallidos: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('0'), comment='Contador de intentos de inicio de sesión fallidos consecutivos.\nSe reinicia a 0 tras un login exitoso. Al superar el umbral configurado,\nla cuenta se bloquea automáticamente.')
    fecha_verificacion: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), comment='Marca temporal (con zona horaria) del momento en que el usuario verificó su correo.\nNULL si aún no ha verificado.')
    ultimo_acceso: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), comment='Marca temporal (con zona horaria) del último inicio de sesión exitoso del usuario.\nÚtil para detectar cuentas inactivas.')
    bloqueado_hasta: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), comment='Marca temporal (con zona horaria) hasta la que la cuenta permanece bloqueada\npor exceso de intentos fallidos. NULL si la cuenta no está bloqueada.')
    ultimo_intento_fallido: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), comment='Marca temporal (con zona horaria) del último intento de login fallido registrado.\nUsado para calcular ventanas de tiempo en políticas de bloqueo.')
    token_activacion_actual: Mapped[Optional[str]] = mapped_column(String(255), comment='Token temporal usado para la activación inicial de la cuenta o reactivación.\nSe invalida una vez usado. Máximo 255 caracteres.')
    fecha_cambio_estado: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'), comment='Marca temporal (con zona horaria) del último cambio de estado de la cuenta.')
    motivo_ultimo_cambio: Mapped[Optional[str]] = mapped_column(String(255), comment='Descripción del motivo del último cambio de estado de la cuenta.\nPermite trazabilidad sin consultar gestiones_cuenta. Máximo 255 caracteres.')

    estados_cuentas: Mapped['EstadosCuentas'] = relationship('EstadosCuentas', back_populates='cuentas_usuarios')
    usuarios: Mapped['Usuarios'] = relationship('Usuarios', back_populates='cuentas_usuarios')
    gestiones_cuenta: Mapped[list['GestionesCuenta']] = relationship('GestionesCuenta', back_populates='cuentas_usuarios')
    sesiones: Mapped[list['Sesiones']] = relationship('Sesiones', back_populates='cuentas_usuarios')

