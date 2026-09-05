"""Base declarativa de SQLAlchemy para los modelos de identity_access.

Re-exporta desde src.shared.base_model para mantener una única instancia
de Base en todo el sistema.
"""
from src.shared.base_model import Base  # noqa: F401
