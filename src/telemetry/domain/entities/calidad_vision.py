# | Fecha      | Nombre  | Que se hizo |
# |------------|---------|-------------|
# | 2026-10-22 | Leandro | DEV-28 RF-62: indice ponderado y oraculo determinista de vision |
# | 2026-10-25 | Arekkazu | INC-M03-134-G192 RF-62: indice a 2 decimales (NUMERIC(5,2)) antes de clasificar |
"""AIOT-SPEC-01 integrada en RF-62.

La aritmetica fija su contexto decimal. El indice se redondea a 2 decimales
(``indice_calidad_vision NUMERIC(5,2)``) antes de clasificar, para que el valor
guardado y su clase coincidan en los bordes (79.996 se guarda 80.00 y es OPTIMA).
"""
from dataclasses import dataclass
from decimal import Decimal, localcontext, ROUND_HALF_EVEN
from fractions import Fraction
from enum import Enum


class EstadoCalibracionVision(str, Enum):
    CALIBRADO = 'CALIBRADO'
    EN_CALIBRACION = 'EN_CALIBRACION'
    SIN_LINEA_BASE = 'SIN_LINEA_BASE'


class ClaseCalidadVision(str, Enum):
    OPTIMA = 'OPTIMA'
    DEGRADADA = 'DEGRADADA'
    NO_APTA = 'NO_APTA'


@dataclass(frozen=True)
class ParametrosCalidadVision:
    w1: Decimal
    w2: Decimal
    w3: Decimal
    fps_configurado: Decimal
    tracks_perdidos_tolerables: int
    factor_en_calibracion: Decimal
    umbral_optima: Decimal
    umbral_degradada: Decimal
    cobertura_minima: Decimal

    def __post_init__(self):
        valores = (self.w1,self.w2,self.w3,self.fps_configurado,self.factor_en_calibracion,
                   self.umbral_optima,self.umbral_degradada,self.cobertura_minima)
        if any(not isinstance(v, Decimal) or not v.is_finite() for v in valores):
            raise ValueError('La politica requiere numeros decimales finitos.')
        if any(not 0 <= w <= 1 for w in (self.w1,self.w2,self.w3)) or sum(Fraction(w) for w in (self.w1,self.w2,self.w3)) != 1:
            raise ValueError('Los pesos deben estar entre 0 y 1 y sumar 1.')
        if self.fps_configurado <= 0 or type(self.tracks_perdidos_tolerables) is not int or not 1 <= self.tracks_perdidos_tolerables <= 50:
            raise ValueError('FPS y tolerancia deben ser divisores validos.')
        if not (0 <= self.factor_en_calibracion <= 1 and 0 <= self.umbral_degradada < self.umbral_optima <= 100
                and Decimal('.05') <= self.cobertura_minima <= Decimal('.90')):
            raise ValueError('Los limites de la politica de vision son inconsistentes.')


@dataclass(frozen=True)
class ResultadoCalidadVision:
    indice: Decimal
    clase: ClaseCalidadVision
    apto_para_ia: bool
    confianza_baja: bool
    flags_detectados: dict
    parametros_aplicados: dict

    @property
    def apto_para_nic41(self):
        return False


def evaluar_calidad_vision(*, cobertura: Decimal, fps: Decimal, perdidos: int,
                          calibracion: EstadoCalibracionVision, parametros: ParametrosCalidadVision,
                          duracion_seg: Decimal) -> ResultadoCalidadVision:
    calibracion = EstadoCalibracionVision(calibracion)
    if (not all(isinstance(v,Decimal) and v.is_finite() for v in (cobertura,fps,duracion_seg))
            or not 0 <= cobertura <= 1 or fps < 0 or duracion_seg <= 0
            or type(perdidos) is not int or perdidos < 0):
        raise ValueError('Los indicadores de vision no pertenecen al dominio.')
    p = parametros
    with localcontext() as contexto:
        contexto.prec = 28
        contexto.rounding = ROUND_HALF_EVEN
        factor_fps = min(Decimal(1),fps/p.fps_configurado)
        factor_perdidas = 1-min(Decimal(1),Decimal(perdidos)/p.tracks_perdidos_tolerables)
        modificador = {EstadoCalibracionVision.CALIBRADO: Decimal(1),
            EstadoCalibracionVision.EN_CALIBRACION:p.factor_en_calibracion,
            EstadoCalibracionVision.SIN_LINEA_BASE:Decimal(0)}[calibracion]
        indice = (100*(p.w1*cobertura+p.w2*factor_fps+p.w3*factor_perdidas)*modificador).quantize(Decimal('0.01'))
        esperados = p.fps_configurado*duracion_seg
    if calibracion == EstadoCalibracionVision.SIN_LINEA_BASE or indice < p.umbral_degradada:
        clase = ClaseCalidadVision.NO_APTA
    else:
        clase = ClaseCalidadVision.OPTIMA if indice >= p.umbral_optima else ClaseCalidadVision.DEGRADADA
    flags = {
        'cobertura_baja': {'activo':cobertura<p.cobertura_minima,'cobertura_ventana':str(cobertura),
            'frames_procesados':None,'frames_esperados':str(esperados)},
        'tracking_inestable': {'activo':perdidos>=p.tracks_perdidos_tolerables,
            'n_tracks_perdidos':perdidos,'tracks_perdidos_tolerables':p.tracks_perdidos_tolerables},
        'fps_insuficiente': {'activo':fps<p.fps_configurado,'fps_efectivo':str(fps),'fps_configurado':str(p.fps_configurado)},
        'sin_linea_base': {'activo':calibracion==EstadoCalibracionVision.SIN_LINEA_BASE},
    }
    snapshot = {k:str(v) for k,v in vars(p).items()}
    snapshot.update(estado_calibracion=calibracion.value,factor_calibracion=str(modificador),duracion_seg=str(duracion_seg))
    return ResultadoCalidadVision(indice,clase,clase!=ClaseCalidadVision.NO_APTA,
                                 clase==ClaseCalidadVision.DEGRADADA,flags,snapshot)
