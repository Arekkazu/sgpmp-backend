"""Regla de formato del número de identificación.

El RF-01 admite tres tipos de documento (`CC`, `CE`, `Pasaporte`) y exige
rechazar caracteres alfabéticos en el número. La exigencia solo puede aplicarse
a los documentos colombianos: un pasaporte es alfanumérico por naturaleza, así
que la regla depende del tipo declarado.

La restricción `chk_usuario_tipo_identificacion` de `modulo1.usuarios` limita la
columna exactamente a esos tres valores, por lo que basta comparar literales.
"""
from typing import Optional

from src.shared.regex import IDENTIFICACION_NUMERICA, IDENTIFICACION_PASAPORTE

TIPO_PASAPORTE = "Pasaporte"

MENSAJE_NUMERICO = (
    "El número de identificación debe contener únicamente dígitos del 0 al 9."
)
MENSAJE_PASAPORTE = (
    "El número de pasaporte debe contener únicamente letras y dígitos, "
    "sin espacios ni signos de puntuación."
)


def identificacion_valida(tipo: Optional[str], numero: Optional[str]) -> bool:
    """Indica si ``numero`` cumple el formato exigido para ``tipo``.

    Devuelve un booleano en vez de lanzar para que cada capa levante su propio
    error: ``ValueError`` en los DTO de Pydantic, ``ValidationError`` de dominio
    en la entidad y en los casos de uso.

    Args:
        tipo: Tipo de documento declarado. Cualquier valor distinto de
            ``Pasaporte`` (incluido ``None``) se valida con la regla numérica,
            que es la más estricta.
        numero: Número a validar. ``None`` se considera inválido; los flujos que
            admiten identificación ausente (provisión mínima por SSO) no llaman
            a esta función.
    """
    if numero is None:
        return False

    patron = (
        IDENTIFICACION_PASAPORTE
        if tipo == TIPO_PASAPORTE
        else IDENTIFICACION_NUMERICA
    )
    return bool(patron.fullmatch(numero))


def mensaje_identificacion_invalida(tipo: Optional[str]) -> str:
    """Mensaje de error acorde al tipo de documento rechazado."""
    return MENSAJE_PASAPORTE if tipo == TIPO_PASAPORTE else MENSAJE_NUMERICO
