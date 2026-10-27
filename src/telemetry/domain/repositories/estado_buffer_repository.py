# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-27 | Leandro | INC-M03-126-G27 RF-54: definir consulta del último reporte dentro del alcance por finca. |
from abc import ABC, abstractmethod
from src.telemetry.domain.entities.estado_buffer import EstadoBufferReportado


class EstadoBufferRepository(ABC):
    @abstractmethod
    def obtener(self, id_dispositivo_iot: int, ids_fincas_permitidas: list[int] | None) -> EstadoBufferReportado | None:
        """None indica dispositivo inexistente o fuera del alcance; no implica buffer vacío."""
        ...
