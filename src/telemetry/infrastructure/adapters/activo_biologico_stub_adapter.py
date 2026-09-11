from datetime import datetime
from typing import List

from src.telemetry.domain.repositories.activo_biologico_dependency_port import (
    ActivoBiologicoDependencyPort,
    ActivoBiologicoInfo,
)


class ActivoBiologicoStubAdapter(ActivoBiologicoDependencyPort):
    """Stub de M02 hasta que el módulo de activos biológicos esté disponible.
    Retorna lista vacía → las vinculaciones quedan en estado SIN_VINCULAR.
    """

    def obtener_activos_en_momento(
        self, id_infraestructura: int, timestamp: datetime
    ) -> List[ActivoBiologicoInfo]:
        return []
