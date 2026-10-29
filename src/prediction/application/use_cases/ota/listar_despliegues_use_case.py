# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-27 | Leandro | INC-M04-158-G086 RF-73: identificar consultas globales sin inventar entidades de negocio. |
# | 2026-10-29 | Arekkazu | QA-M04-27-10 CU09 H-04 RF-73: consultar la OTA no emite HISTORIAL_CONSULTADO |
from __future__ import annotations

from typing import Optional

from src.prediction.domain.entities.despliegue_ota import DespliegueOta
from src.prediction.domain.repositories.despliegue_ota_repository import DespliegueOtaRepository
from src.prediction.domain.repositories.version_modelo_port import VersionModeloPort
from src.shared.errors import NotFoundError, ValidationError

_ESTADOS_VALIDOS = {"EXITOSO", "FALLIDO", "PENDIENTE", "SIN_CAMBIOS", "EN_PROCESO"}
_LIMIT_MAX = 100


class ListarDesplieguesUseCase:
    def __init__(
        self,
        *,
        repo: DespliegueOtaRepository,
        version_port: VersionModeloPort,
    ) -> None:
        self._repo = repo
        self._version_port = version_port

    def execute(
        self,
        *,
        id_version: Optional[int],
        id_dispositivo: Optional[int],
        estado: Optional[str],
        limit: int,
        offset: int,
    ) -> tuple[list[DespliegueOta], int]:
        if id_version is not None and self._version_port.obtener_estado(id_version) is None:
            raise NotFoundError(
                code="VERSION_NO_ENCONTRADA",
                message="La versión de modelo especificada no existe.",
            )

        if estado is not None and estado not in _ESTADOS_VALIDOS:
            raise ValidationError(
                code="ESTADO_INVALIDO",
                message=f"El estado '{estado}' no es válido. Valores permitidos: {', '.join(sorted(_ESTADOS_VALIDOS))}.",
                field="estado",
            )

        limit = min(limit, _LIMIT_MAX)
        offset = max(offset, 0)

        return self._repo.listar(
            id_version=id_version,
            id_dispositivo=id_dispositivo,
            estado=estado,
            limit=limit,
            offset=offset,
        )
