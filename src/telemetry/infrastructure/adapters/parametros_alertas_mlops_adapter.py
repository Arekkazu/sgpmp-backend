# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-21 | Arekkazu | DEV-32 RF-57: lee los umbrales de tormenta; sin configurar no agrupa (E8) |
# | 2026-10-28 | destroyerban | INC-M03-166-G73 RF-57 CA-2: umbral mínimo de confianza de IA para PREDICCION_PATOLOGIA |
# | 2026-10-28 | destroyerban | INC-M03-167-G75 RF-57 E16: ventana de reevaluación por IA (valor base 60 min) |
import logging

from src.configuration.domain.entities.parametro_mlops import (
    RF57_CONFIANZA,
    RF57_CONFIANZA_MINIMA,
    RF57_CONFIANZA_MINIMA_BASE,
    RF57_VENTANA_REEVALUACION,
    RF57_VENTANA_REEVALUACION_BASE,
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

    def obtener_confianza_minima_ia(self):
        try:
            return numero_configurado(self.parametros_repo.obtener([RF57_CONFIANZA_MINIMA]), RF57_CONFIANZA_MINIMA,
                                      minimo=0, maximo=1)
        except ServiceUnavailableError as exc:
            # El RF publica el valor base (0.75); solo la ausencia lo usa. Un valor inválido falla (DEV-14).
            if exc.code != 'PARAMETRO_CONFIGURACION_AUSENTE':
                raise
            return RF57_CONFIANZA_MINIMA_BASE

    def obtener_ventana_reevaluacion_min(self):
        try:
            return numero_configurado(self.parametros_repo.obtener([RF57_VENTANA_REEVALUACION]),
                                      RF57_VENTANA_REEVALUACION, minimo=1, entero=True)
        except ServiceUnavailableError as exc:
            # Mismo criterio que G73: el RF publica el valor base (60 min); solo la ausencia lo usa.
            if exc.code != 'PARAMETRO_CONFIGURACION_AUSENTE':
                raise
            return RF57_VENTANA_REEVALUACION_BASE

    def obtener_umbrales_tormenta(self):
        # Sin configurar no se inventa un valor (regla de DEV-14): se notifica una por una.
        nombres = [RF57_TORMENTA_SISTEMA, RF57_TORMENTA_UNIDAD]
        try:
            parametros = self.parametros_repo.obtener(nombres)
            return tuple(int(numero_configurado(parametros, n, minimo=1, entero=True)) for n in nombres)
        except ServiceUnavailableError:
            logger.warning('RF-57 E8: umbrales de tormenta sin configurar; las alertas se notifican sin agrupar.')
            return None
