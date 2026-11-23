# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-27 | Leandro | INC-M03-133-G170 RF-62: validar correcciones locales de calibracion y estadistica sin alterar M09. |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de las funciones |
"""Correcciones locales de una reevaluación; no modifican la configuración M09."""
from dataclasses import fields,replace
from decimal import Decimal
from math import isfinite
from src.shared.errors import BusinessRuleError
from src.telemetry.domain.repositories.parametros_calidad_port import ParametrosCalidad

ESTADISTICOS=frozenset(f.name for f in fields(ParametrosCalidad))
CALIBRACION=frozenset(('offset','ganancia'))


def _invalido():
    return BusinessRuleError('PARAMETROS_REEVALUACION_INVALIDOS',
        'Los parámetros correctos deben ser numéricos finitos y respetar las ventanas del motor.',
        field='parametros_correctos')


def validar_correcciones(correcciones):
    """Valida y normaliza las correcciones de parámetros de una reevaluación.

    Raises:
        BusinessRuleError: Si algún parámetro no es admitido o no es válido.
    """
    datos=dict(correcciones or {})
    if datos.keys()-(ESTADISTICOS|CALIBRACION):
        raise BusinessRuleError('PARAMETROS_REEVALUACION_INVALIDOS',
            'La solicitud contiene parámetros que el motor de calidad no admite.',field='parametros_correctos')
    for nombre,valor in datos.items():
        if isinstance(valor,bool) or not isinstance(valor,(int,float,Decimal)):
            raise _invalido()
        try:
            numero=Decimal(str(valor))
            if not numero.is_finite() or not isfinite(float(numero)) or (nombre=='ganancia' and numero<=0):
                raise _invalido()
            if nombre in ('M','N','P','frecuencia_muestreo_min'):
                if numero!=numero.to_integral_value() or numero<(2 if nombre=='N' else 1):
                    raise _invalido()
                datos[nombre]=int(numero)
            elif nombre in ESTADISTICOS:
                if numero<0 or (nombre=='k' and numero==0):
                    raise _invalido()
                datos[nombre]=float(numero)
        except (ValueError,OverflowError):
            raise _invalido() from None
    return datos


def corregir_estadisticos(parametros,correcciones):
    """Aplica las correcciones estadísticas y valida la relación entre ventanas."""
    corregidos=replace(parametros,**{k:v for k,v in correcciones.items() if k in ESTADISTICOS})
    if corregidos.M>corregidos.N or corregidos.P>corregidos.N:
        raise _invalido()
    return corregidos


def corregir_calibracion(original,correcciones):
    """Combina las correcciones de calibración con las existentes y las valida."""
    cambios={k:v for k,v in correcciones.items() if k in CALIBRACION}
    if not cambios:
        return original
    corregida={**(original or {}),**cambios}
    if not CALIBRACION<=corregida.keys():
        raise BusinessRuleError('PARAMETROS_REEVALUACION_INVALIDOS',
            'La calibración corregida requiere offset y ganancia conocidos.',field='parametros_correctos')
    validar_correcciones({k:corregida[k] for k in CALIBRACION})
    return corregida
