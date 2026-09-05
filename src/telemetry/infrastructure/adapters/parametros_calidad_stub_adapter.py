from typing import Optional

from src.telemetry.domain.repositories.parametros_calidad_port import ParametrosCalidad, ParametrosCalidadPort


class ParametrosCalidadStubAdapter(ParametrosCalidadPort):
    """Stub M09 para parámetros de calidad. Devuelve valores por defecto hasta integrar M09."""

    def obtener_parametros(
        self,
        id_sensor: int,
        tipo_variable: Optional[str] = None,
    ) -> ParametrosCalidad:
        return ParametrosCalidad(
            k=3.0,
            M=5,
            N=20,
            umbral_drift=5.0,
            umbral_drift_significativo=10.0,
            P=3,
            frecuencia_muestreo_min=5,
        )
