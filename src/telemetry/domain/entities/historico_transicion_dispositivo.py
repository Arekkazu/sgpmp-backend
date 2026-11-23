# | Fecha      | Nombre   | Que se hizo                                      |
# |------------|----------|--------------------------------------------------|
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo y clase pública |
"""Entidad de dominio del histórico de transiciones de estado de un dispositivo IoT.

Registra cada cambio de estado del dispositivo con su causa, el usuario
responsable y las notas de la transición. Es un dataclass puro, sin ORM.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional


@dataclass
class HistoricoTransicionDispositivo:
    """Una transición de estado registrada para un dispositivo IoT."""

    id_transaccion: Optional[int]
    id_dispositivo_iot: int
    estado_anterior: str
    estado_nuevo: str
    causa_primaria: Optional[str]
    causa_secundaria: Optional[Any]
    id_usuario_responsable: Optional[int]
    notas: Optional[str]
    fecha_transicion: datetime
