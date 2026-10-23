# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-21 | Arekkazu | DEV-32 RF-57: lee los umbrales de tormenta; sin configurar no agrupa (E8) |
import logging

from src.configuration.domain.entities.parametro_mlops import (
    RF57_CONFIANZA,
    RF57_TORMENTA_SISTEMA,
    RF57_TORMENTA_UNIDAD,
    numero_configurado,
)
from src.shared.errors import ServiceUnavailableError
from src.telemetry.domain.repositories.parametros_alertas_port import ParametrosAlertasPort

logger = logging.getLogger(__name__)


class ParametrosAlertasMLOpsAdapter(ParametrosAlertasPort):
    def __init__(self, parametros_repo):
        self.parametros_repo = parametros_repo

    def obtener_confianza_edge_ia(self):
        return numero_configurado(self.parametros_repo.obtener([RF57_CONFIANZA]), RF57_CONFIANZA,
                                 minimo='0.70', maximo='0.95')

    def obtener_umbrales_tormenta(self):
        # Sin configurar no se inventa un valor (regla de DEV-14): se notifica una por una.
        nombres = [RF57_TORMENTA_SISTEMA, RF57_TORMENTA_UNIDAD]
        try:
            parametros = self.parametros_repo.obtener(nombres)
            return tuple(int(numero_configurado(parametros, n, minimo=1, entero=True)) for n in nombres)
        except ServiceUnavailableError:
            logger.warning('RF-57 E8: umbrales de tormenta sin configurar; las alertas se notifican sin agrupar.')
            return None
