from src.configuration.domain.entities.parametro_mlops import PARAMETROS_CALIDAD, calidad_configurada
from src.shared.errors import ServiceUnavailableError
from src.telemetry.domain.repositories.parametros_calidad_port import ParametrosCalidad, ParametrosCalidadPort


class ParametrosCalidadMLOpsAdapter(ParametrosCalidadPort):
    """Configuración global del algoritmo existente; sin inferir especies ni scopes.

    Los rangos físicos/biológicos por variable/especie siguen perteneciendo a
    sus adaptadores M09. No se reemplazan por estos parámetros estadísticos.
    """
    def __init__(self, parametros_repo, configuracion_repo):
        self.parametros_repo = parametros_repo
        self.configuracion_repo = configuracion_repo

    def obtener_parametros(self, id_sensor, tipo_variable=None):
        valores = calidad_configurada(self.parametros_repo.obtener(PARAMETROS_CALIDAD))
        configuracion = self.configuracion_repo.obtener_activo()
        if configuracion is None:
            raise ServiceUnavailableError('CONFIGURACION_OPERATIVA_AUSENTE',
                                          'No existe configuración global activa de muestreo en M09.')
        frecuencia = configuracion.frecuencia_muestreo.valor
        if isinstance(frecuencia, bool) or not isinstance(frecuencia, int) or frecuencia <= 0:
            raise ServiceUnavailableError('PARAMETRO_CONFIGURACION_INVALIDO',
                                          'La frecuencia de muestreo de M09 es inválida.')
        return ParametrosCalidad(**valores, frecuencia_muestreo_min=frecuencia)
