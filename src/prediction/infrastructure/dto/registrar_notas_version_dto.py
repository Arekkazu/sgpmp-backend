# | Fecha      | Nombre   | Que se hizo                                      |
# |------------|----------|--------------------------------------------------|
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""DTO de notas de validación de una versión."""
from src.shared.base_dto import BaseDTO


class RegistrarNotasVersionDTO(BaseDTO):
    """Notas de validación de una versión de modelo."""
    notas_validacion: str
