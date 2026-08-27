"""Expresiones regulares reutilizables para validación de campos de entrada.

Todas las constantes exportadas están precompiladas para mayor rendimiento.
Se usan en los DTOs Pydantic del módulo de identidad y acceso.
"""
import re

PASSWORD = re.compile(
    r"^(?=.*[A-Z])(?=.*\d)(?=.*[@#$%^&+=!]).{8,}$"
)

NOMBRE = re.compile(
    r"^[A-Za-zÁÉÍÓÚáéíóúÑñ ]+$"
)

TELEFONO = re.compile(
    r"^\d{7,15}$"
)

NUMERO_IDENTIFICACION = re.compile(
    r"^[0-9]+$"
)
