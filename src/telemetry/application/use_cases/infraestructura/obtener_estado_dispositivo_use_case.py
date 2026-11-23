# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-27 | Leandro | INC-M03-127-G27 RF-54/60: comprobar finca autorizada antes de leer el estado y su historial. |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clases y método |
"""Caso de uso de consulta del estado de un dispositivo IoT (RF-54/RF-60).

Verifica que el dispositivo pertenezca a una finca autorizada antes de leer su
estado vigente y el historial de transiciones.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from src.shared.errors import NotFoundError
from src.telemetry.domain.entities.estado_dispositivo_iot import EstadoDispositivoIoT
from src.telemetry.domain.entities.historico_transicion_dispositivo import HistoricoTransicionDispositivo
from src.telemetry.domain.repositories.estado_dispositivo_iot_repository import EstadoDispositivoIoTRepository
from src.telemetry.domain.repositories.historico_transicion_dispositivo_repository import HistoricoTransicionDispositivoRepository


class ResultadoEstadoDispositivo:
    """Estado vigente del dispositivo junto con su historial de transiciones."""

    def __init__(
        self,
        estado: EstadoDispositivoIoT,
        historial: list[HistoricoTransicionDispositivo],
    ) -> None:
        self.estado = estado
        self.historial = historial


class ObtenerEstadoDispositivoUseCase:
    """Orquesta la consulta del estado y del historial de un dispositivo."""

    def __init__(
        self,
        db: Session,
        estado_repo: EstadoDispositivoIoTRepository,
        transicion_repo: HistoricoTransicionDispositivoRepository,
    ) -> None:
        self.db = db
        self.estado_repo = estado_repo
        self.transicion_repo = transicion_repo

    def execute(
        self,
        id_dispositivo_iot: int,
        limite_historial: int = 20,
        *,
        ids_fincas_permitidas: Optional[list[int]] = None,
    ) -> ResultadoEstadoDispositivo:
        """Devuelve el estado vigente y el historial del dispositivo.

        Raises:
            NotFoundError: Si el dispositivo está fuera de las fincas permitidas
                o no tiene estado registrado.
        """
        if ids_fincas_permitidas is not None and not self.estado_repo.pertenece_a_fincas(
            id_dispositivo_iot, ids_fincas_permitidas
        ):
            raise NotFoundError(
                code='ESTADO_DISPOSITIVO_NO_ENCONTRADO',
                message=f'No se encontró estado para el dispositivo {id_dispositivo_iot}.',
            )
        estado = self.estado_repo.obtener_por_dispositivo(id_dispositivo_iot)
        if estado is None:
            raise NotFoundError(
                code='ESTADO_DISPOSITIVO_NO_ENCONTRADO',
                message=f'No se encontró estado para el dispositivo {id_dispositivo_iot}.',
            )
        historial = self.transicion_repo.listar_por_dispositivo(id_dispositivo_iot, limite=limite_historial)
        return ResultadoEstadoDispositivo(estado=estado, historial=historial)
