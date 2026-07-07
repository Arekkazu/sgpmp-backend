from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional

from src.telemetry.domain.entities.vinculacion_lectura import VinculacionLectura


class VinculacionLecturaRepository(ABC):

    @abstractmethod
    def guardar(self, vinculacion: VinculacionLectura) -> VinculacionLectura: ...

    @abstractmethod
    def obtener_por_id(self, id_vinculacion_lectura: int) -> Optional[VinculacionLectura]: ...

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
    ) -> tuple[List[VinculacionLectura], int]: ...
