# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-23 | destroyerban | DEV-37 RF-73: reintentos, respaldo local y sincronización de la bitácora M04 |
"""Respaldo local de la bitácora de M04 (RF-73 E2 y E8, DEV-37).

Cuando un evento no se puede persistir tras los reintentos, se guarda aquí con
todos sus campos (incluidos ``id_evento`` y ``fecha_evento`` originales). Al
recuperarse la BD, la sincronización los lleva a la bitácora en el mismo orden
en que se guardaron (FIFO).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import AbstractContextManager
from typing import Optional


class RespaldoAuditoriaM04Port(ABC):
    @abstractmethod
    def guardar(self, evento: dict) -> None:
        """Agrega el evento al respaldo. Lanza si no se pudo escribir."""

    @abstractmethod
    def hay_pendientes(self) -> bool:
        """True si hay eventos esperando sincronización (consulta barata, sin bloqueo)."""

    @abstractmethod
    def pendientes(self) -> AbstractContextManager[Optional[list[dict]]]:
        """Toma los eventos pendientes en orden FIFO.

        Entrega ``None`` si otra sincronización ya los tiene tomados. Si el bloque
        termina sin excepción, se descartan del respaldo; si lanza, se conservan
        para el siguiente intento.
        """
