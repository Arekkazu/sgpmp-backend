# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-02 | Arekkazu | AJF-04 RF-60: parámetros de heartbeat por categoría para la pantalla de dispositivos |
"""AJF-04: lo que explica al Ingeniero por qué un dispositivo pasó a SIN_SEÑAL o INACTIVO.

Mismas fórmulas que ``ParametrosComunicacionHeartbeat`` (RF-60): umbral_activo =
max(intervalo, frecuencia), umbral_sin_senal = umbral_activo + margen y umbral_inactivo
= umbral_sin_senal + inactividad extendida. Aquí no se inventa nada: un parámetro que
falta queda en ``faltantes`` y sus umbrales en None ("Sin configurar").
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class ConfiguracionHeartbeatLeida:
    """Valores tal como están guardados; None = no configurado."""
    intervalos_por_tipo: dict[str, int]
    intervalo_camara_seg: Optional[int]
    frecuencia_muestreo_seg: Optional[int]
    margen_tolerancia_seg: Optional[int]
    inactividad_extendida_seg: Optional[int]
    #: Categorías de dispositivo registradas en M09 (aunque no tengan intervalo).
    categorias: tuple[str, ...] = ()


@dataclass(frozen=True)
class ParametrosHeartbeatCategoria:
    categoria: str
    intervalo_heartbeat_seg: Optional[int]
    frecuencia_muestreo_seg: Optional[int]
    margen_tolerancia_seg: Optional[int]
    umbral_sin_senal_seg: Optional[int]
    umbral_inactivo_seg: Optional[int]
    #: intervalo ≤ frecuencia / 2 ≤ frecuencia ≤ umbral_sin_senal; None si falta algún valor.
    cadena_valida: Optional[bool]
    faltantes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def configurado(self) -> bool:
        return not self.faltantes


def parametros_por_categoria(c: ConfiguracionHeartbeatLeida) -> list[ParametrosHeartbeatCategoria]:
    categorias = sorted({*c.categorias, *c.intervalos_por_tipo, 'CAMARA'})
    resultado = []
    for categoria in categorias:
        intervalo = c.intervalo_camara_seg if categoria == 'CAMARA' else c.intervalos_por_tipo.get(categoria)
        faltantes = [nombre for nombre, valor in (
            ('intervalo_heartbeat_camara' if categoria == 'CAMARA' else 'intervalos_heartbeat_por_tipo', intervalo),
            ('frecuencia_muestreo', c.frecuencia_muestreo_seg),
            ('margen_tolerancia', c.margen_tolerancia_seg),
            ('tiempo_inactividad_extendida', c.inactividad_extendida_seg),
        ) if valor is None]
        sin_senal = inactivo = cadena = None
        if intervalo is not None and c.frecuencia_muestreo_seg is not None and c.margen_tolerancia_seg is not None:
            sin_senal = max(intervalo, c.frecuencia_muestreo_seg) + c.margen_tolerancia_seg
            cadena = 2 * intervalo <= c.frecuencia_muestreo_seg <= sin_senal
            if c.inactividad_extendida_seg is not None:
                inactivo = sin_senal + c.inactividad_extendida_seg
        resultado.append(ParametrosHeartbeatCategoria(
            categoria=categoria, intervalo_heartbeat_seg=intervalo,
            frecuencia_muestreo_seg=c.frecuencia_muestreo_seg, margen_tolerancia_seg=c.margen_tolerancia_seg,
            umbral_sin_senal_seg=sin_senal, umbral_inactivo_seg=inactivo, cadena_valida=cadena,
            faltantes=tuple(faltantes),
        ))
    return resultado


@dataclass(frozen=True)
class VentanaObservada:
    """Una ventana de visión de una cámara (``modulo3.observaciones_vision``)."""
    id_observacion_vision: int
    inicio: Optional[object]
    fin: object
    cobertura: object
    n_individuos: Optional[int]


@dataclass(frozen=True)
class ResumenVentanasVision:
    es_camara: bool
    ventanas: list[VentanaObservada]
    ventanas_consecutivas: Optional[int]
    cobertura_minima: Optional[object]
    duracion_seg: Optional[int]
    consecutivas_bajo_minimo: int
    #: DETECCION_VALIDA | SIN_DETECCION_VALIDA | SIN_VENTANAS | SIN_CONFIGURAR | NO_ES_CAMARA
    resultado: str


def resumir_ventanas(es_camara: bool, ventanas: list[VentanaObservada], ventanas_consecutivas: Optional[int],
                     cobertura_minima, duracion_seg: Optional[int]) -> ResumenVentanasVision:
    """Ventanas de la más reciente a la más antigua. Igual que ``ventanas_sin_deteccion``: la
    igualdad con la cobertura mínima corta la secuencia baja."""
    def resumen(consecutivas: int, resultado: str) -> ResumenVentanasVision:
        return ResumenVentanasVision(es_camara, ventanas, ventanas_consecutivas, cobertura_minima, duracion_seg,
                                     consecutivas, resultado)
    if not es_camara:
        return resumen(0, 'NO_ES_CAMARA')
    if not ventanas:
        return resumen(0, 'SIN_VENTANAS')
    if ventanas_consecutivas is None or cobertura_minima is None:
        return resumen(0, 'SIN_CONFIGURAR')
    consecutivas = 0
    for v in ventanas:
        if v.cobertura >= cobertura_minima:
            break
        consecutivas += 1
    return resumen(consecutivas, 'SIN_DETECCION_VALIDA' if consecutivas >= ventanas_consecutivas else 'DETECCION_VALIDA')
