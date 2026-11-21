"""Estado de una distribución OTA y de cada nodo (DEV-15; lo consume FE-01b)."""
from __future__ import annotations

from src.prediction.application.use_cases.ota.crear_distribucion_ota_use_case import ResultadoDistribucionOta
from src.prediction.domain.repositories.despliegue_ota_repository import DespliegueOtaRepository
from src.prediction.domain.repositories.distribucion_ota_repository import DistribucionOtaRepository
from src.shared.errors import NotFoundError


class ConsultarDistribucionOtaUseCase:

    def __init__(self, *, distribucion_repo: DistribucionOtaRepository, despliegue_repo: DespliegueOtaRepository) -> None:
        self._distribucion_repo = distribucion_repo
        self._despliegue_repo = despliegue_repo

    def execute(self, id_distribucion: int) -> ResultadoDistribucionOta:
        distribucion = self._distribucion_repo.obtener_por_id(id_distribucion)
        if distribucion is None:
            raise NotFoundError(
                code="DISTRIBUCION_OTA_NO_ENCONTRADA",
                message=f"No existe la distribución OTA {id_distribucion}.",
            )
        return ResultadoDistribucionOta(
            distribucion=distribucion,
            despliegues=self._despliegue_repo.listar_por_distribucion(id_distribucion),
        )
