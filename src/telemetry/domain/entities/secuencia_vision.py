# | Fecha      | Nombre  | Que se hizo |
# |------------|---------|-------------|
# | 2026-10-22 | Leandro | DEV-28 RF-60: secuencias temporales de ventanas por camara |
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal


@dataclass(frozen=True)
class VentanaVision:
    identificador: int
    camara: int
    area: int
    inicio: datetime
    fin: datetime
    cobertura: Decimal


@dataclass(frozen=True)
class ParametrosVentanasVision:
    cantidad: int
    cobertura_minima: Decimal
    duracion_seg: int

    def __post_init__(self):
        if (type(self.cantidad) is not int or not 1 <= self.cantidad <= 20
                or type(self.duracion_seg) is not int or not 10 <= self.duracion_seg <= 300
                or not self.cobertura_minima.is_finite()
                or not Decimal('.05') <= self.cobertura_minima <= Decimal('.90')):
            raise ValueError('Los parametros de ventanas no son validos.')


def ventanas_sin_deteccion(ventanas: list[VentanaVision], parametros: ParametrosVentanasVision) -> tuple[VentanaVision, ...]:
    """Cuenta ventanas contiguas reales, no mensajes. Una brecha corta la serie.

    No interpreta individuos observados como tracks ni como ausencia de camara.
    La igualdad con el minimo de cobertura interrumpe la secuencia baja.
    """
    ordenadas = sorted(ventanas,key=lambda v:(v.fin,v.identificador),reverse=True)
    if not ordenadas:
        return ()
    resultado, vistas = [], {}
    ultima = ordenadas[0]
    for v in ordenadas:
        if (v.inicio.utcoffset() is None or v.fin.utcoffset() is None or v.inicio >= v.fin
                or not v.cobertura.is_finite() or not 0 <= v.cobertura <= 1):
            raise ValueError('La ventana debe tener instantes validos y cobertura entre 0 y 1.')
        identidad = (v.camara,v.area,v.inicio,v.fin)
        if identidad in vistas:
            if vistas[identidad] != v.cobertura:
                raise ValueError('Las copias de una ventana no pueden tener coberturas contradictorias.')
            continue
        vistas[identidad] = v.cobertura
        if ((v.camara,v.area)!=(ultima.camara,ultima.area)
                or v.fin-v.inicio!=timedelta(seconds=parametros.duracion_seg)
                or v.cobertura>=parametros.cobertura_minima
                or (resultado and v.fin!=resultado[-1].inicio)):
            break
        resultado.append(v)
        if len(resultado)==parametros.cantidad:
            return tuple(reversed(resultado))
    return ()
