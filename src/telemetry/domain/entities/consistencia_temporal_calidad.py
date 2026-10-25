# | Fecha      | Nombre  | Que se hizo                                      |
# |------------|---------|--------------------------------------------------|
# | 2026-10-21 | Leandro | DEV-43 RF-62: gaps e inactividad reconocida RF-60 |
"""Reglas temporales definidas por RF-62; las ambigüedades no se resuelven aquí."""
from datetime import datetime, timezone
from math import isfinite

from src.shared.errors import ServiceUnavailableError
from src.telemetry.domain.repositories.contexto_calidad_port import IntervaloInactividad


def utc(fecha: datetime) -> datetime:
    if fecha.tzinfo is None or fecha.utcoffset() is None:
        raise ServiceUnavailableError('CONTEXTO_TEMPORAL_INVALIDO',
                                      'La serie de calidad requiere fechas con zona horaria.')
    return fecha.astimezone(timezone.utc)


def unir_periodos(periodos: tuple[IntervaloInactividad, ...], hasta: datetime):
    intervalos = []
    for periodo in periodos:
        inicio, fin = utc(periodo.inicio), utc(periodo.fin) if periodo.fin else utc(hasta)
        if fin < inicio:
            raise ServiceUnavailableError('CONTEXTO_TEMPORAL_INVALIDO',
                                          'RF-60 contiene un periodo de inactividad invertido.')
        if inicio <= hasta:
            intervalos.append((inicio, min(fin, hasta)))
    unidos = []
    for inicio, fin in sorted(intervalos):
        if unidos and inicio <= unidos[-1][1]:
            unidos[-1] = (unidos[-1][0], max(fin, unidos[-1][1]))
        else:
            unidos.append((inicio, fin))
    return unidos


def cubierto(inicio, fin, periodos):
    return any(a <= inicio and b >= fin for a, b in periodos)


def detectar_gaps(lecturas, captura, frecuencia, periodos):
    fechas = sorted({utc(l.timestamp_captura) for l in lecturas} | {utc(captura)})
    gaps, excluidos = [], []
    for anterior, actual in zip(fechas, fechas[1:]):
        # El snapshot de frecuencia de la lectura que abre el intervalo gobierna
        # ese segmento; sin snapshot se usa la configuración vigente documentada.
        muestras = [l.frecuencia_muestreo_min for l in lecturas
                    if utc(l.timestamp_captura) == anterior and l.frecuencia_muestreo_min is not None]
        if len(set(muestras)) > 1:
            raise ServiceUnavailableError('FRECUENCIA_HISTORICA_AMBIGUA',
                                          'Las lecturas simultáneas declaran frecuencias diferentes.')
        intervalo = muestras[0] if muestras else frecuencia
        if (isinstance(intervalo, bool) or not isinstance(intervalo, (int, float)) or
                not isfinite(intervalo) or intervalo <= 0):
            raise ServiceUnavailableError('PARAMETRO_CONFIGURACION_INVALIDO',
                                          'El intervalo de muestreo debe ser positivo.')
        real = (actual - anterior).total_seconds() / 60
        if real <= 2 * intervalo:
            continue
        detalle = {'timestamp_lectura_anterior': anterior.isoformat(),
                   'timestamp_lectura_actual': actual.isoformat(),
                   'gap_real_minutos': real, 'gap_esperado_minutos': intervalo,
                   'umbral_gap_minutos': 2 * intervalo}
        if cubierto(anterior, actual, periodos):
            excluidos.append(detalle)
        elif any(a < actual and b > anterior for a, b in periodos):
            raise ServiceUnavailableError('SOLAPAMIENTO_INACTIVIDAD_PENDIENTE',
                'Falta definir el tratamiento RF-62 del gap parcialmente cubierto por inactividad.')
        else:
            gaps.append(detalle)
    return gaps, excluidos
