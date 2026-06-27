"""Enumeraciones de dominio del módulo configuration.

Reflejan los tipos ENUM definidos en el schema modulo9 de PostgreSQL.
Todas heredan de `str` para ser serializables a JSON y compatibles con
los valores almacenados en las columnas ENUM de la DB.
"""
import enum


class EnumNivelAlerta(str, enum.Enum):
    """Niveles de severidad de alerta ambiental (enum_nivel_alerta en modulo9)."""
    NORMAL = 'normal'
    PRECAUCION = 'precaucion'
    CRITICO = 'critico'


class EnumTipoInfraestructura(str, enum.Enum):
    """Tipos de infraestructura productiva (enum_tipo_infraestructura en modulo9)."""
    CORRAL = 'corral'
    GALPON = 'galpon'
    POTRERO = 'potrero'
    ESTANQUE = 'estanque'
    INVERNADERO = 'invernadero'


class EnumPatologiaCategoria(str, enum.Enum):
    """Categorías de patologías del catálogo (enum_patologia_categoria en modulo9)."""
    METABOLICA = 'metabolica'
    PODAL = 'podal'
    DIARREICA = 'diarreica'
    RESPIRATORIA = 'respiratoria'
