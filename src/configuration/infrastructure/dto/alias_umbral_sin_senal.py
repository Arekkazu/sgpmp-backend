# | Fecha      | Nombre   | Que se hizo                                      |
# |------------|----------|--------------------------------------------------|
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""RFC-015 C1: alias de entrada sin renombrar ni duplicar la columna existente."""
from pydantic import TypeAdapter

_ENTERO = TypeAdapter(int)


def validar_alias_umbral(datos):
    """Rechaza el payload si trae heartbeat y umbral sin señal con valores distintos."""
    if isinstance(datos, dict) and 'heartbeat' in datos and 'umbral_sin_senal' in datos:
        anterior = _ENTERO.validate_python(datos['heartbeat'])
        canonico = _ENTERO.validate_python(datos['umbral_sin_senal'])
        if anterior != canonico:
            raise ValueError('heartbeat y umbral_sin_senal identifican el mismo parámetro y deben coincidir.')
        datos = {k: v for k, v in datos.items() if k != 'heartbeat'}
    return datos
