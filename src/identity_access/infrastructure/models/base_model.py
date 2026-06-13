"""Base declarativa de SQLAlchemy compartida por todos los modelos ORM del proyecto."""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Clase base de la que heredan todos los modelos ORM del sistema."""
    pass
