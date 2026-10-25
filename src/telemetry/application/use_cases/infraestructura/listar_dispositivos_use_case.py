# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-24 | Arekkazu | USAB-M03 M3-10 RF-60: listado de dispositivos de las fincas del usuario |
"""Caso de uso: listar los dispositivos IoT con su estado actual (RF-60, M3-10)."""
from __future__ import annotations

from typing import Optional

from src.telemetry.domain.entities.dispositivo_con_estado import DispositivoConEstado
from src.telemetry.domain.repositories.estado_dispositivo_iot_repository import EstadoDispositivoIoTRepository


class ListarDispositivosUseCase:

    def __init__(self, estado_repo: EstadoDispositivoIoTRepository) -> None:
        self.estado_repo = estado_repo

    def execute(
        self,
        ids_fincas_permitidas: Optional[list[int]],
        estado: Optional[str] = None,
    ) -> list[DispositivoConEstado]:
        """``ids_fincas_permitidas`` None = alcance global. Los que fallan primero."""
        return self.estado_repo.listar_con_estado(ids_fincas_permitidas, estado=estado)
