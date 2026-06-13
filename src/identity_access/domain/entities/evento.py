"""Entidad de dominio ``Evento`` del contexto de identidad y acceso.

Representa un registro del log de auditoría como concepto de negocio, para la
vista de consulta. Python puro, independiente del ORM. El flag de integridad
(hash) no forma parte de la entidad: lo calcula el repositorio y lo devuelve
aparte, porque depende de un campo técnico (``hash_integridad``).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(eq=False)
class Evento:
    """Evento del log de auditoría (modelo de lectura).

    Attributes:
        id_evento: Identidad del evento.
        tipo_evento: Tipo de evento (FK a tipos_eventos).
        fecha_evento: Marca temporal en que ocurrió.
        modulo: Módulo del sistema donde se originó.
        resultado: Resultado de la operación (``EXITOSO``/``FALLIDO`` como texto).
        detalle: Diccionario con el contexto del evento (JSONB en DB).
        id_usuario: Usuario relacionado con el evento.
        categoria: Categoría funcional (AUTENTICACION, MODIFICACION, ...).
        estado: Estado del evento en su ciclo de vida.
        id_sesion: Sesión asociada, si aplica.
    """

    id_evento: int
    tipo_evento: int
    fecha_evento: datetime
    modulo: str
    resultado: str
    detalle: dict
    id_usuario: int
    categoria: str
    estado: str
    id_sesion: Optional[int] = None

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Evento):
            return NotImplemented
        return self.id_evento == other.id_evento

    def __hash__(self) -> int:
        return hash(self.id_evento)
