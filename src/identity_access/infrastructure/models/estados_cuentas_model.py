from typing import Optional
import datetime
import enum

from sqlalchemy import Integer, PrimaryKeyConstraint, Sequence, String,  UniqueConstraint

from sqlalchemy.orm import Mapped, mapped_column, relationship
from base_model import Base
from cuenta_usuarios_model import CuentasUsuarios


class EstadosCuentas(Base):
    __tablename__ = 'estados_cuentas'
    __table_args__ = (
        PrimaryKeyConstraint('id_estado_cuenta', name='estados_cuenta_pkey'),
        UniqueConstraint('nombre', name='uq_estados_cuenta_nombre'),
        {'comment': 'Catálogo de los posibles estados en que puede encontrarse una '
                'cuenta de usuario.\n'
                'Define el ciclo de vida de la cuenta (ej: ACTIVA, INACTIVA, '
                'SUSPENDIDA, BLOQUEADA).\n'
                'Es referenciado por la tabla cuentas_usuarios.',
     'schema': 'modulo1'}
    )

    id_estado_cuenta: Mapped[int] = mapped_column(Integer, Sequence('estados_cuenta_id_estado_cuentas_seq', schema='modulo1'), primary_key=True, comment='Identificador único del estado de cuenta. Clave primaria (serial).')
    nombre: Mapped[str] = mapped_column(String(55), nullable=False, comment='Nombre único del estado (ej: ACTIVA, BLOQUEADA, SUSPENDIDA). Máximo 55 caracteres.')
    descripcion: Mapped[Optional[str]] = mapped_column(String(255), comment='Descripción del significado del estado y las condiciones bajo las cuales\nuna cuenta puede estar en él. Máximo 255 caracteres.')

    cuentas_usuarios: Mapped[list['CuentasUsuarios']] = relationship('CuentasUsuarios', back_populates='estados_cuentas')

