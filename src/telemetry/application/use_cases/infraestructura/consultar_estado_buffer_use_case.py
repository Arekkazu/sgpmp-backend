# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-27 | Leandro | INC-M03-126-G27 RF-54: consultar el reporte del dispositivo conservando el aislamiento por finca. |
# | 2026-10-29 | Arekkazu | TC-DIS-148 RF-54: listado del buffer de todos los dispositivos del alcance |
from src.shared.errors import NotFoundError
from src.telemetry.domain.entities.estado_buffer import EstadoBufferReportado
from src.telemetry.domain.repositories.estado_buffer_repository import EstadoBufferRepository


class ConsultarEstadoBufferUseCase:
    def __init__(self, repositorio: EstadoBufferRepository):
        self.repositorio = repositorio

    def execute(self, id_dispositivo_iot: int, ids_fincas_permitidas: list[int] | None) -> EstadoBufferReportado:
        resultado = self.repositorio.obtener(id_dispositivo_iot, ids_fincas_permitidas)
        if resultado is None:
            raise NotFoundError('DISPOSITIVO_NO_ENCONTRADO', 'No se encontró el dispositivo solicitado.')
        return resultado

    def listar(self, ids_fincas_permitidas: list[int] | None) -> list[EstadoBufferReportado]:
        """TC-DIS-148: el panel del buffer, un reporte por dispositivo del alcance."""
        return self.repositorio.listar(ids_fincas_permitidas)
