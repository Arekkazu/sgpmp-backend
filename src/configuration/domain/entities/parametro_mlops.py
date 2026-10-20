"""Parámetros persistidos administrados por M09, almacenados en M04.

Los ejemplos del RF no son valores de respaldo: una lectura incompleta o
inválida falla expresamente. Los límites almacenados pueden restringir, nunca
ampliar, los límites funcionales del consumidor.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from math import isfinite
from typing import Any

from src.shared.errors import ServiceUnavailableError

RF62_K = 'rf62_k'
RF62_M = 'rf62_m'
RF62_N = 'rf62_n'
RF62_DRIFT = 'rf62_umbral_drift'
RF62_P = 'rf62_p'
RF57_CONFIANZA = 'umbral_confianza_edge_ia'
RF72_VENTANA = 'ventana_retroalimentacion_dias'
PARAMETROS_CALIDAD = (RF62_K, RF62_M, RF62_N, RF62_DRIFT, RF62_P)


@dataclass(frozen=True)
class ParametroMLOps:
    nombre: str
    valor: Any
    minimo: Decimal | None = None
    maximo: Decimal | None = None


def numero_configurado(parametros, nombre, *, minimo=None, maximo=None, entero=False, positivo=False):
    parametro = parametros.get(nombre)
    if parametro is None:
        raise ServiceUnavailableError('PARAMETRO_CONFIGURACION_AUSENTE',
                                      f'No se ha configurado el parámetro {nombre}.')
    try:
        if isinstance(parametro.valor, bool) or not isinstance(parametro.valor, (int, float, Decimal)):
            raise ValueError
        valor = Decimal(str(parametro.valor))
        if not valor.is_finite() or (entero and valor != valor.to_integral_value()):
            raise ValueError
        if positivo and valor <= 0:
            raise ValueError
        limites_min = [Decimal(str(v)) for v in (minimo, parametro.minimo) if v is not None]
        limites_max = [Decimal(str(v)) for v in (maximo, parametro.maximo) if v is not None]
        if any(not v.is_finite() for v in limites_min + limites_max):
            raise ValueError
        if limites_min and valor < max(limites_min):
            raise ValueError
        if limites_max and valor > min(limites_max):
            raise ValueError
        return int(valor) if entero else valor
    except (ValueError, TypeError, InvalidOperation, OverflowError):
        raise ServiceUnavailableError('PARAMETRO_CONFIGURACION_INVALIDO',
                                      f'La configuración del parámetro {nombre} es inválida.') from None


def calidad_configurada(parametros):
    valores = {
        'k': numero_configurado(parametros, RF62_K, positivo=True),
        'M': numero_configurado(parametros, RF62_M, minimo=1, entero=True),
        'N': numero_configurado(parametros, RF62_N, minimo=2, entero=True),
        'umbral_drift': numero_configurado(parametros, RF62_DRIFT, minimo=0),
        'P': numero_configurado(parametros, RF62_P, minimo=1, entero=True),
    }
    if valores['M'] > valores['N'] or valores['P'] > valores['N']:
        raise ServiceUnavailableError('PARAMETRO_CONFIGURACION_INVALIDO',
                                      'Las ventanas M y P no pueden superar la serie N de RF-62.')
    # Los cálculos estadísticos existentes trabajan con float.
    for nombre in ('k', 'umbral_drift'):
        convertido = float(valores[nombre])
        if not isfinite(convertido) or (nombre == 'k' and convertido <= 0):
            raise ServiceUnavailableError('PARAMETRO_CONFIGURACION_INVALIDO',
                                          'La configuración estadística excede la precisión admitida.')
        valores[nombre] = convertido
    return valores
