# | Fecha      | Nombre  | Que se hizo |
# |------------|---------|-------------|
# | 2026-10-22 | Leandro | DEV-28 RF-53/62: parametros de calidad de vision en DEV-14 |
"""Claves del indice RF-62; defaults D solo para siembra explicita."""
from fractions import Fraction

from src.configuration.domain.entities.parametro_mlops import numero_configurado
from src.shared.errors import ServiceUnavailableError

W1, W2, W3 = 'w1', 'w2', 'w3'
TOLERABLES = 'tracks_perdidos_tolerables'
OPTIMA, DEGRADADA = 'umbral_optima', 'umbral_degradada'
FACTOR = 'factor_en_calibracion'
LIMITES_VISION = {
    W1: (0, 1), W2: (0, 1), W3: (0, 1), TOLERABLES: (1, 50),
    OPTIMA: (0, 100), DEGRADADA: (0, 100), FACTOR: (0, 1),
}
PREDETERMINADOS_VISION = {
    W1: .40, W2: .35, W3: .25, TOLERABLES: 5,
    OPTIMA: 80, DEGRADADA: 40, FACTOR: .70,
}


def vision_configurada(parametros):
    valores = {nombre: numero_configurado(parametros, nombre,
        minimo=limites[0], maximo=limites[1], entero=nombre == TOLERABLES)
        for nombre, limites in LIMITES_VISION.items()}
    if sum(Fraction(valores[n]) for n in (W1, W2, W3)) != 1:
        raise ServiceUnavailableError('PARAMETRO_CONFIGURACION_INVALIDO', 'Los pesos de vision deben sumar exactamente 1.')
    if valores[OPTIMA] <= valores[DEGRADADA]:
        raise ServiceUnavailableError('PARAMETRO_CONFIGURACION_INVALIDO', 'El umbral optimo debe superar al degradado.')
    return valores
