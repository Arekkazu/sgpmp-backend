# | Fecha      | Nombre  | Que se hizo                                      |
# |------------|---------|--------------------------------------------------|
# | 2026-10-21 | Leandro | DEV-27 RF-60/18: valida cadena antes de configurar |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Validación común de POST/PATCH RF-18 con el almacén provisional P-1."""
from src.configuration.domain.entities.parametros_heartbeat import TEMPORALES, validar_heartbeat_configurado
from src.shared.errors import ServiceUnavailableError, ValidationError


def validar_cadena_heartbeat(parametros_repo, frecuencia_min, umbral_min):
    """Valida la frecuencia y el umbral contra los parámetros temporales del heartbeat."""
    parametros = parametros_repo.obtener(TEMPORALES)
    try:
        validar_heartbeat_configurado(parametros, frecuencia_min, umbral_min)
    except ServiceUnavailableError as exc:
        raise ValidationError('CADENA_HEARTBEAT_INVALIDA', exc.message) from None
