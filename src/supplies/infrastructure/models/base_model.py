"""Re-exporta la Base declarativa compartida para los modelos de ``modulo5``.

Centralizar la Base en ``src.shared`` permite que SQLAlchemy resuelva las FK
cruzadas entre esquemas (ej: ``modulo5`` → ``modulo1.usuarios`` /
``modulo2.activos_biologicos``).
"""
from src.shared.base_model import Base  # noqa: F401
