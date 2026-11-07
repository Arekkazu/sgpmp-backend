"""Puertos hacia afuera del orquestador OTA (DEV-15, D6 de AIOT-DEV-03)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class ResultadoAvisoOta:
    """Respuesta del broker a ``POST /v1/ota/notify`` (BRK-08)."""

    publicado: bool
    mensaje: str
    id_mensaje: Optional[str] = None


class NodoOtaPort(ABC):
    @abstractmethod
    def obtener_seriales(self, ids_dispositivo: list[int]) -> dict[int, str]:
        """Serial de cada dispositivo activo de la lista. Los que no existen o están
        inactivos no aparecen. No depende de quién llama."""
        ...


class AvisoOtaPort(ABC):
    @abstractmethod
    def notificar(self, aviso: dict) -> ResultadoAvisoOta:
        """Pide al broker publicar ``ota/notify`` a un nodo. Nunca lanza.

        El broker publica y responde 202 sin esperar la instalación: el nodo
        reporta después por ``ota/<evento>`` → ``POST /prediccion/ota/reportes``.
        """
        ...


class UrlDescargaPort(ABC):
    @abstractmethod
    def configurada(self) -> bool:
        """Si el ambiente tiene con qué firmar URLs (clave y URL base)."""
        ...

    @abstractmethod
    def generar(self, id_despliegue: int, expira: datetime) -> str:
        """URL temporal y firmada para descargar el artefacto del despliegue (admite Range)."""
        ...

    @abstractmethod
    def es_valida(self, id_despliegue: int, expira_epoch: int, firma: str, ahora: datetime) -> bool:
        """Firma correcta y sin vencer."""
        ...
