from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, CHAR, CheckConstraint, Column, Date, DateTime, Enum, ForeignKeyConstraint, Index, Integer, PrimaryKeyConstraint, Sequence, String, Table, Text, Time, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base_model import Base
from .enums_models import EnumAccionCuenta

if TYPE_CHECKING:
    from .cuenta_usuarios_model import CuentasUsuarios
    from .usuarios_model import Usuarios

class GestionesCuenta(Base):
    __tablename__ = 'gestiones_cuenta'
    __table_args__ = (
        ForeignKeyConstraint(['id_cuenta_usuario'], ['modulo1.cuentas_usuarios.id_cuenta_usuario'], name='fk_cuenta'),
        ForeignKeyConstraint(['id_usuario_responsable'], ['modulo1.usuarios.id_usuario'], name='fk_usuario_responsable'),
        PrimaryKeyConstraint('id_gestion_cuenta', name='gestiones_cuenta_pkey'),
        {'comment': 'Bitácora de las gestiones administrativas realizadas sobre las '
                'cuentas de usuario.\n'
                'Registra acciones como activaciones, suspensiones, bloqueos y '
                'desbloqueos,\n'
                'indicando quién las realizó, por qué y cuándo. Garantiza '
                'trazabilidad completa\n'
                'de las decisiones administrativas sobre cuentas.',
     'schema': 'modulo1'}
    )

    id_gestion_cuenta: Mapped[int] = mapped_column(Integer, primary_key=True, comment='Identificador único de la gestión de cuenta. Clave primaria (serial).')
    accion_cuenta: Mapped[EnumAccionCuenta] = mapped_column('accion_cuenta ', Enum(EnumAccionCuenta, values_callable=lambda cls: [member.value for member in cls], name='enum_accion_cuenta', schema='modulo1'), nullable=False, comment='Tipo de acción administrativa aplicada sobre la cuenta. ENUM global\n(enum_accion_cuenta). Ej: ACTIVACION, SUSPENSION, BLOQUEO, DESBLOQUEO.')
    motivo_accion: Mapped[str] = mapped_column(String(255), nullable=False, comment='Justificación o motivo por el cual se realizó la acción sobre la cuenta.\nRequerido para garantizar trazabilidad. Máximo 255 caracteres.')
    fecha_accion: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, comment='Marca temporal (con zona horaria) del momento en que se ejecutó la gestión.')
    id_usuario_responsable: Mapped[int] = mapped_column(Integer, nullable=False, comment='FK hacia modulo1.usuarios. Usuario administrador que ejecutó la gestión sobre la cuenta.')
    id_cuenta_usuario: Mapped[int] = mapped_column(Integer, nullable=False, comment='FK hacia modulo1.cuentas_usuarios. Cuenta sobre la que se aplicó la gestión administrativa.')

    cuentas_usuarios: Mapped['CuentasUsuarios'] = relationship('CuentasUsuarios', back_populates='gestiones_cuenta')
    usuarios: Mapped['Usuarios'] = relationship('Usuarios', back_populates='gestiones_cuenta')

