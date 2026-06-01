from typing import Optional
import datetime
import enum

from sqlalchemy import Boolean, CHAR, CheckConstraint, Column, Date, DateTime, Enum, ForeignKeyConstraint, Index, Integer, PrimaryKeyConstraint, Sequence, String, Table, Text, Time, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from base_model import Base


class Sesiones(Base):
    __tablename__ = 'sesiones'
    __table_args__ = (
        CheckConstraint('es_activa IS NOT NULL', name='chk_sesiones_estado_coherente'),
        CheckConstraint('fecha_finalizacion IS NULL OR fecha_inicio <= fecha_finalizacion', name='chk_sesiones_fechas_coherentes'),
        ForeignKeyConstraint(['id_cuenta_usuario'], ['modulo1.cuentas_usuarios.id_cuenta_usuario'], name='fk_cuenta_usuario'),
        ForeignKeyConstraint(['id_token'], ['modulo1.tokens.id_token'], name='fk_token'),
        PrimaryKeyConstraint('id_sesion', name='sesiones_pkey'),
        UniqueConstraint('id_token', name='sesiones_id_token_id_token1_key'),
        Index('uix_sesiones_activa_por_cuenta', 'id_cuenta_usuario', postgresql_where='(es_activa = true)', unique=True),
        {'comment': 'Registra las sesiones de acceso al sistema de cada usuario. '
                'Permite rastrear\n'
                'desde qué dispositivo y dirección IP se conectó, la duración de '
                'la sesión\n'
                'y si sigue activa. Es clave para el control de seguridad y '
                'auditoría de accesos.',
     'schema': 'modulo1'}
    )

    id_sesion: Mapped[int] = mapped_column(Integer, Sequence('sesiones_id_sesiones_seq', schema='modulo1'), primary_key=True, comment='Identificador único de la sesión. Clave primaria (serial).')
    id_token: Mapped[int] = mapped_column(Integer, nullable=False, comment='FK hacia modulo1.tokens. Token de autenticación asociado a esta sesión. Único por sesión.')
    direccion_ip: Mapped[str] = mapped_column(String(45), nullable=False, comment='Dirección IP del cliente desde la que se inició la sesión.\nSoporta IPv4 e IPv6. Máximo 45 caracteres.')
    agente_usuario: Mapped[str] = mapped_column(String(255), nullable=False, comment='Cadena del agente de usuario (navegador o aplicación) del cliente.\nPermite identificar el dispositivo y sistema operativo usado. Máximo 255 caracteres.')
    fecha_inicio: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, comment='Marca temporal (con zona horaria) del momento en que se inició la sesión.')
    fecha_finalizacion: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, comment='Marca temporal (con zona horaria) del momento en que la sesión fue cerrada\no expiró. Si la sesión sigue activa, este valor puede ser la expiración esperada.')
    es_activa: Mapped[bool] = mapped_column(Boolean, nullable=False, comment='Indica si la sesión está actualmente activa. Se actualiza a false al cerrar sesión\no al expirar el token asociado.')
    id_cuenta_usuario: Mapped[int] = mapped_column(Integer, nullable=False, comment='FK hacia modulo1.cuentas_usuarios. Cuenta del usuario que inició esta sesión.')

    cuentas_usuarios: Mapped['CuentasUsuarios'] = relationship('CuentasUsuarios', back_populates='sesiones')
    tokens: Mapped['Tokens'] = relationship('Tokens', back_populates='sesiones')
