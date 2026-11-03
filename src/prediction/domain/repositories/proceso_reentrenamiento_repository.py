# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-02 | Arekkazu | AJF-14 RF-71: puerto de procesos de reentrenamiento |
# | 2026-11-02 | Arekkazu | AJF-14 RF-71: días de lecturas contados con sesión de sistema (RLS de telemetrias) |
# | 2026-11-03 | Arekkazu | AJF-14 RF-71 BE-6: reentrenamiento programado por antigüedad de la versión (0 = apagado) |
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from src.prediction.domain.entities.proceso_reentrenamiento import DatosAnimalReentrenamiento, ProcesoReentrenamiento


class ProcesoReentrenamientoRepository(ABC):

    @abstractmethod
    def crear(self, proceso: ProcesoReentrenamiento) -> ProcesoReentrenamiento: ...

    @abstractmethod
    def obtener(self, id_proceso: uuid.UUID) -> Optional[ProcesoReentrenamiento]: ...

    @abstractmethod
    def abierto_de(self, id_activo_biologico: int) -> Optional[ProcesoReentrenamiento]:
        """El proceso PENDIENTE o EN_CURSO del animal, si hay."""

    @abstractmethod
    def tomar_siguiente(self) -> Optional[ProcesoReentrenamiento]:
        """El PENDIENTE más antiguo, bloqueado para esta transacción (``FOR UPDATE SKIP LOCKED``)."""

    @abstractmethod
    def guardar(self, proceso: ProcesoReentrenamiento) -> ProcesoReentrenamiento: ...

    @abstractmethod
    def listar(self, *, tipo_modelo: Optional[str], id_activo_biologico: Optional[int], estado: Optional[str],
               desde: Optional[datetime], hasta: Optional[datetime], pagina: int, por_pagina: int,
               ) -> tuple[list[ProcesoReentrenamiento], int]: ...

    @abstractmethod
    def en_curso(self) -> list[ProcesoReentrenamiento]:
        """Procesos EN_CURSO (para el vigilante de latidos)."""

    @abstractmethod
    def datos_animal(self, id_activo_biologico: int) -> Optional[DatosAnimalReentrenamiento]:
        """None si el animal no existe o no está en el alcance."""

    @abstractmethod
    def horas_de_lecturas(self, id_activo_biologico: int) -> float:
        """Horas entre la primera y la última lectura válida de los sensores directos del animal
        (14 días). Se pide con la sesión de sistema: es una regla del motor, no lo que ve el usuario."""

    @abstractmethod
    def candidatos_programados(self, dias: int) -> list[tuple[int, str]]:
        """BE-6: (animal, tipo de modelo) individuales atendidos cuya versión vigente tiene más de
        ``dias`` días y que no tienen un proceso abierto."""

    @abstractmethod
    def version_de_proceso(self, id_proceso: uuid.UUID) -> Optional[int]:
        """La versión registrada por RF-69 con ``id_proceso_rf71`` = este proceso (BE-3)."""

    @abstractmethod
    def retroalimentaciones_verificadas(self, id_activo_biologico: int) -> list[dict]:
        """Diagnósticos clínicos vigentes del animal con la ventana de su inferencia (RF-72)."""
