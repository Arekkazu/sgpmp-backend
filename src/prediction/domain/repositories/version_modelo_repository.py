from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from typing import Optional

from src.prediction.domain.entities.version_modelo import VersionModelo


class VersionModeloRepository(ABC):

    @abstractmethod
    def guardar(self, entidad: VersionModelo) -> VersionModelo: ...

    @abstractmethod
    def actualizar(self, entidad: VersionModelo) -> VersionModelo: ...

    @abstractmethod
    def obtener_por_id(self, id_version: int) -> Optional[VersionModelo]: ...

    @abstractmethod
    def obtener_activo_por_tipo(self, tipo_modelo: str) -> Optional[VersionModelo]: ...

    @abstractmethod
    def listar(
        self,
        *,
        tipo_modelo: Optional[str] = None,
        estado: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[VersionModelo], int]: ...

    @abstractmethod
    def registrar_historial(
        self,
        *,
        id_version_modelo: int,
        estado_anterior: Optional[str],
        estado_nuevo: str,
        tipo_actor: str,
        id_usuario: Optional[int] = None,
        id_sistema: Optional[str] = None,
        id_proceso_rf71: Optional[uuid.UUID] = None,
        correlacion_id: Optional[uuid.UUID] = None,
        motivo: Optional[str] = None,
    ) -> None: ...
