"""Rehidratación tolerante de value objects leídos de la BD.

Las reglas de formato de varios value objects se endurecieron cuando ya había
filas guardadas (vereda obligatoria, serial solo alfanumérico...). Validarlas
también al leer hace que una sola fila antigua convierta todo un listado en un
400 (#166 fincas, #178 dispositivos IoT). Las reglas se siguen aplicando al
escribir: el use case construye el value object directamente.
"""
from dataclasses import fields

from src.shared.errors import ValidationError


def rehidratar(cls, *args, **kwargs):
    """Construye el value object; si la fila ya no cumple la regla vigente, lo
    devuelve con los valores tal cual están guardados en vez de fallar."""
    try:
        return cls(*args, **kwargs)
    except ValidationError:
        vo = object.__new__(cls)
        valores = dict(zip((f.name for f in fields(cls)), args), **kwargs)
        for nombre, valor in valores.items():
            object.__setattr__(vo, nombre, valor)
        return vo
