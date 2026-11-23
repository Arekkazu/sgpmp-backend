# | Fecha      | Nombre   | Que se hizo                                      |
# |------------|----------|--------------------------------------------------|
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Base declarativa propia de los modelos ORM del motor."""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base declarativa de los modelos ORM del motor."""
    pass
