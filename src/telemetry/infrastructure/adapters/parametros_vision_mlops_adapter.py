# | Fecha      | Nombre  | Que se hizo |
# |------------|---------|-------------|
# | 2026-10-22 | Leandro | DEV-28 RF-62: lee parametros persistidos en una consulta |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Adaptador de parámetros de calidad de visión contra la configuración MLOps (RF-62).

Lee en una sola consulta los límites de visión, cobertura y ventanas, y
construye los parámetros de calidad y de secuencia que usa el motor de visión.
"""
from decimal import Decimal
from src.configuration.domain.entities.parametros_vision import LIMITES_VISION, vision_configurada
from src.configuration.domain.entities.parametros_heartbeat import COBERTURA, VENTANAS, DURACION
from src.configuration.domain.entities.parametro_mlops import numero_configurado
from src.shared.errors import ServiceUnavailableError
from src.telemetry.domain.entities.calidad_vision import ParametrosCalidadVision
from src.telemetry.domain.entities.secuencia_vision import ParametrosVentanasVision


class ParametrosVisionMLOpsAdapter:
    """Resuelve los parámetros persistidos de calidad de visión."""

    def __init__(self, repositorio):
        self.repositorio = repositorio

    def obtener(self, fps_configurado):
        """Devuelve los umbrales de calidad para la cámara y su FPS configurado.

        Raises:
            ServiceUnavailableError: Si el FPS no es un entero positivo.
        """
        valores = self.repositorio.obtener((*LIMITES_VISION,COBERTURA))
        p = vision_configurada(valores)
        if type(fps_configurado) is not int or fps_configurado <= 0:
            raise ServiceUnavailableError('PARAMETRO_CONFIGURACION_INVALIDO','La camara requiere FPS configurado positivo en RF-23.')
        return ParametrosCalidadVision(p['w1'],p['w2'],p['w3'],Decimal(fps_configurado),
            p['tracks_perdidos_tolerables'],p['factor_en_calibracion'],p['umbral_optima'],p['umbral_degradada'],
            numero_configurado(valores,COBERTURA,minimo='.05',maximo='.90'))

    def obtener_ventanas(self):
        """Devuelve los parámetros de las ventanas de secuencia de visión."""
        valores=self.repositorio.obtener((VENTANAS,COBERTURA,DURACION))
        return ParametrosVentanasVision(
            numero_configurado(valores,VENTANAS,minimo=1,maximo=20,entero=True),
            numero_configurado(valores,COBERTURA,minimo='.05',maximo='.90'),
            numero_configurado(valores,DURACION,minimo=10,maximo=300,entero=True))
