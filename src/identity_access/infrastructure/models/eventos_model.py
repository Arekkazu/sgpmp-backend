"""Modelo ORM para la tabla `modulo1.eventos`.

Log de auditoría inmutable. Cada evento almacena un hash SHA-256 de sus campos
clave para detectar modificaciones directas en la tabla.
"""
from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, CHAR, CheckConstraint, Column, Date, DateTime, Enum, ForeignKeyConstraint, Index, Integer, PrimaryKeyConstraint, Sequence, String, Table, Text, Time, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base_model import Base
from .enums_models import EnumEventoResultado

if TYPE_CHECKING:
    from .usuarios_model import Usuarios
    from .tipo_eventos_model import TiposEventos
    from .notificaciones_model import Notificaciones

class Eventos(Base):
    __tablename__ = 'eventos'
    __table_args__ = (
        ForeignKeyConstraint(['id_usuario'], ['modulo1.usuarios.id_usuario'], name='fk_usuario'),
        ForeignKeyConstraint(['tipo_evento'], ['modulo1.tipos_eventos.id_tipo_evento'], name='fk_tipo_evento'),
        PrimaryKeyConstraint('id_evento', name='eventos_pkey'),
        {'comment': 'Registro de todos los eventos significativos que ocurren en el '
                'sistema,\n'
                'generados por usuarios o por procesos automáticos. Sirve como '
                'fuente\n'
                'para notificaciones, auditorías y análisis de comportamiento. '
                'Cubre eventos\n'
                'de todos los módulos del sistema.',
     'schema': 'modulo1'}
    )

    id_evento: Mapped[int] = mapped_column(Integer, primary_key=True, comment='Identificador único del evento. Clave primaria (serial).')
    tipo_evento: Mapped[int] = mapped_column(Integer, nullable=False, comment='FK hacia modulo1.tipos_evento (referencia por ID). Clasifica el tipo de evento ocurrido.')
    fecha_evento: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, comment='Marca temporal (con zona horaria) del momento exacto en que ocurrió el evento.')
    modulo: Mapped[str] = mapped_column(String(50), nullable=False, comment='Nombre del módulo del sistema donde se originó el evento (ej: MODULO1, MODULO6).\nMáximo 50 caracteres.')
    resultado: Mapped[EnumEventoResultado] = mapped_column(Enum(EnumEventoResultado, values_callable=lambda cls: [member.value for member in cls], name='enum_evento_resultado', schema='modulo1'), nullable=False)
    detalle: Mapped[dict] = mapped_column(JSONB, nullable=False, comment='Objeto JSON con el detalle completo del evento: parámetros de entrada,\nentidades afectadas, valores anteriores y nuevos, contexto de ejecución, etc.')
    id_usuario: Mapped[int] = mapped_column(Integer, nullable=False, comment='FK hacia modulo1.usuarios. Usuario que originó o está relacionado con el evento.')
    categoria: Mapped[str] = mapped_column(String(30), nullable=False, comment='Categoría funcional del evento (ej: AUTENTICACION, MODIFICACION, CONSULTA).\nPermite agrupar y filtrar eventos por tipo de operación. Máximo 30 caracteres.')
    estado: Mapped[str] = mapped_column(String(30), nullable=False, comment='Estado actual del evento en su ciclo de vida (ej: PROCESADO, PENDIENTE, ERROR).\nMáximo 30 caracteres.')
    descripcion: Mapped[Optional[str]] = mapped_column(Text, comment='Descripción en lenguaje natural del evento registrado. Opcional.')
    id_sesion: Mapped[Optional[int]] = mapped_column(Integer)
    hash_integridad: Mapped[Optional[str]] = mapped_column(Text)
    # Campos exigidos por la seccion "Entradas" de RF-10. Nullable porque los
    # eventos anteriores a la migracion son inmutables y no se pueden rellenar.
    nombre_usuario: Mapped[Optional[str]] = mapped_column(String(80), comment='Nombre o correo del actor en el momento del evento.')
    direccion_ip: Mapped[Optional[str]] = mapped_column(String(45), comment='IP de origen de la peticion que genero el evento.')
    user_agent: Mapped[Optional[str]] = mapped_column(String(255), comment='Navegador o dispositivo desde el que se origino el evento.')

    usuarios: Mapped['Usuarios'] = relationship('Usuarios', back_populates='eventos')
    tipos_eventos: Mapped['TiposEventos'] = relationship('TiposEventos', back_populates='eventos')
    notificaciones: Mapped[list['Notificaciones']] = relationship('Notificaciones', back_populates='eventos')

