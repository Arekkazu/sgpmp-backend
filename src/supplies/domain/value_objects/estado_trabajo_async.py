"""Estado compartido de un trabajo asíncrono (RF-77 y RF-81 / CU-04).

Ambos motores async (generación de reportes y trabajos de historial) usan el
mismo ciclo de vida de trabajo: ``PENDIENTE`` → ``EN_PROCESO`` → ``COMPLETADO`` |
``FALLIDO``. Se mantiene como ``str``-``Enum``; en la BD las columnas
correspondientes son ``varchar`` (ver ``cu04_gaps_bd_rf77_rf81.md``).
"""
from __future__ import annotations

from enum import Enum


class EstadoTrabajoAsync(str, Enum):
    PENDIENTE = "PENDIENTE"
    EN_PROCESO = "EN_PROCESO"
    COMPLETADO = "COMPLETADO"
    FALLIDO = "FALLIDO"
