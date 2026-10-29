# | Fecha      | Nombre  | Que se hizo |
# |------------|---------|-------------|
# | 2026-10-22 | Leandro | DEV-44 RF-61: lectura vigente y configuracion temporal |
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional

from src.telemetry.domain.entities.vinculacion_lectura import VinculacionLectura


class VinculacionLecturaRepository(ABC):

    def bloquear_lectura(self, identificador): raise NotImplementedError

    def vigente(self, identificador): raise NotImplementedError

    def ultima(self, identificador): raise NotImplementedError

    def contexto_lectura(self, identificador, captura): raise NotImplementedError

    @abstractmethod
    def guardar(self, vinculacion: VinculacionLectura) -> VinculacionLectura: ...

    @abstractmethod
    def obtener_por_id(
        self,
        id_vinculacion_lectura: int,
        *,
        ids_fincas_permitidas: Optional[list[int]] = None,
    ) -> Optional[VinculacionLectura]: ...

    @abstractmethod
    def actualizar(self, vinculacion: VinculacionLectura) -> VinculacionLectura: ...

    @abstractmethod
    def listar(
        self,
        id_telemetria: Optional[int] = None,
        estado_vinculacion: Optional[str] = None,
        mecanismo_vinculacion: Optional[str] = None,
        id_infraestructura: Optional[int] = None,
        fecha_desde: Optional[datetime] = None,
        fecha_hasta: Optional[datetime] = None,
        pagina: int = 1,
        por_pagina: int = 50,
        *,
        ids_fincas_permitidas: Optional[list[int]] = None,
    ) -> tuple[List[VinculacionLectura], int]: ...
