# | Fecha      | Nombre   | Que se hizo                                      |
# |------------|----------|--------------------------------------------------|
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Base declarativa SQLAlchemy compartida por todos los módulos del sistema.

Centralizar la Base en shared permite que SQLAlchemy resuelva FK cruzadas
entre módulos (ej: modulo9 → modulo1.usuarios) y que Alembic pueda ordenar
las tablas por dependencia correctamente.
"""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base declarativa de SQLAlchemy compartida por todos los modelos ORM."""
    pass
