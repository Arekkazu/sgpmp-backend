# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-27 | destroyerban | INC-M03-116-G59 RF-56: consulta del paquete por id con alcance por finca |
from abc import ABC, abstractmethod
from typing import Optional

from src.telemetry.domain.entities.telemetria import PaqueteInferencia


class PaqueteInferenciaRepository(ABC):
    @abstractmethod
    def obtener_por_evento(
        self, id_evento: int, *, bloquear_evento: bool = False,
    ) -> Optional[PaqueteInferencia]:
        """Recupera el paquete existente.

        bloquear_evento serializa la consolidación del mismo evento hasta el
        commit/rollback del caso de uso, incluso si todavía no tiene paquete.
        """
        ...

    @abstractmethod
    def obtener(
        self, id_paquete: int, *, ids_fincas_permitidas: Optional[list[int]] = None,
    ) -> Optional[PaqueteInferencia]:
        """El paquete, o None si no existe o su equipo no es de esas fincas.

        ``ids_fincas_permitidas`` None = alcance global (auditor), como en la bitácora RF-63.
        """
        ...

    @abstractmethod
    def guardar(self, paquete: PaqueteInferencia) -> PaqueteInferencia: ...

    @abstractmethod
    def actualizar_estado(self, id_paquete: int, estado: str, intento: int) -> None: ...
