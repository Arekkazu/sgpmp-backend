# | Fecha      | Nombre   | Que se hizo                                      |
# |------------|----------|--------------------------------------------------|
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y método |
"""DEV-14/Análisis debe publicar estos parámetros en M09 (RF-18 no los tiene)."""
from src.shared.errors import ServiceUnavailableError


class ParametrosHeartbeatPendientesAdapter:
    """Adaptador pendiente: aún no hay parámetros operativos configurados."""

    def obtener(self):
        """Informa que los umbrales de batería y señal no están disponibles."""

        raise ServiceUnavailableError(
            'PARAMETROS_HEARTBEAT_NO_DISPONIBLES',
            'Los umbrales operativos de batería y señal aún no están configurados en M09.',
        )
