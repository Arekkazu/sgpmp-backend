from datetime import datetime
from typing import Optional

from src.telemetry.domain.repositories.umbral_historico_port import UmbralHistoricoPort


class UmbralHistoricoM09Adapter(UmbralHistoricoPort):
    """Stub: M09 aún no expone umbrales versionados con vigencia temporal (RF-59 Restricción 16).

    Cuando M09 implemente `fecha_inicio_vigencia` / `fecha_fin_vigencia` en su catálogo
    de umbrales, reemplazar este stub por la consulta real.
    Mientras tanto todos los semáforos históricos quedan en GRIS.
    """

    def obtener_umbral_vigente(
        self,
        tipo_variable: str,
        id_especie: Optional[int],
        timestamp: datetime,
    ) -> Optional[dict]:
        return None
