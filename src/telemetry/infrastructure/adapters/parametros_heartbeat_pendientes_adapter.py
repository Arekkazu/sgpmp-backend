"""DEV-14/Análisis debe publicar estos parámetros en M09 (RF-18 no los tiene)."""
from src.shared.errors import ServiceUnavailableError


class ParametrosHeartbeatPendientesAdapter:
    def obtener(self):
        raise ServiceUnavailableError(
            'PARAMETROS_HEARTBEAT_NO_DISPONIBLES',
            'Los umbrales operativos de batería y señal aún no están configurados en M09.',
        )
