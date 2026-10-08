"""Cálculo de la línea base por visión (RF-24 v2.0, RFC-011): las tres etapas de
auditoría automática, en orden, cada una sobre la salida de la anterior.

1. Filtrado ambiental: descarta observaciones no aptas (RF-62) o con cobertura /
   tracks insuficientes; aborta si quedan menos del mínimo.
2. Recorte p5/p95: por componente, descarta lo que cae fuera de [p5, p95]; un
   componente que queda con pocos datos es no calibrable; si son la mayoría, aborta.
3. Refinamiento iterativo: mediana por componente y recorte de nuevo hasta que
   el cambio relativo sea < ε o se agoten las iteraciones (NO_CONVERGIDA).

Dominio puro: sin BD ni framework.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from src.configuration.domain.entities.observacion_vision import ObservacionVision
from src.configuration.domain.value_objects.calibracion_vision import (
    EstadoCalibracionVision,
    EtapaCalibracionVision,
)


@dataclass(frozen=True)
class ParametrosLineaBase:
    """Umbrales de las tres etapas. La ficha los deja "configurados" sin fijar
    valores; estos son los valores por defecto hasta que Análisis/AIoT los defina."""
    min_observaciones: int = 30
    cobertura_minima: float = 0.5
    tracks_minimos: int = 1
    min_datos_componente: int = 10
    epsilon: float = 0.01          # 1 % de cambio relativo
    max_iteraciones: int = 10


@dataclass
class ResultadoLineaBase:
    estado: EstadoCalibracionVision
    n_observaciones: int
    n_observaciones_validas: int = 0
    etapa_fallo: Optional[EtapaCalibracionVision] = None
    motivo: Optional[str] = None
    valores: dict[str, float] = field(default_factory=dict)
    componentes_no_calibrables: list[str] = field(default_factory=list)
    iteraciones: Optional[int] = None

    @property
    def es_exitosa(self) -> bool:
        return self.estado == EstadoCalibracionVision.EXITOSA


def percentil(valores: list[float], p: float) -> float:
    """Percentil con interpolación lineal entre rangos (el método por defecto de numpy)."""
    ordenados = sorted(valores)
    posicion = (len(ordenados) - 1) * p / 100
    inferior = int(posicion)
    superior = min(inferior + 1, len(ordenados) - 1)
    fraccion = posicion - inferior
    return ordenados[inferior] + (ordenados[superior] - ordenados[inferior]) * fraccion


def mediana(valores: list[float]) -> float:
    return percentil(valores, 50)


def recortar_p5_p95(valores: list[float]) -> list[float]:
    p5, p95 = percentil(valores, 5), percentil(valores, 95)
    return [v for v in valores if p5 <= v <= p95]


def _fallo(estado, etapa, motivo, n_obs, n_validas, **extra) -> ResultadoLineaBase:
    return ResultadoLineaBase(
        estado=estado, etapa_fallo=etapa, motivo=motivo,
        n_observaciones=n_obs, n_observaciones_validas=n_validas, **extra,
    )


def calcular_linea_base(
    observaciones: list[ObservacionVision], parametros: ParametrosLineaBase
) -> ResultadoLineaBase:
    n_obs = len(observaciones)

    # ── Etapa 1 — Filtrado ambiental ─────────────────────────────────────────
    validas = [
        o for o in observaciones
        if o.es_apto_para_ia
        and o.cobertura_ventana >= parametros.cobertura_minima
        and o.n_tracks >= parametros.tracks_minimos
    ]
    if len(validas) < parametros.min_observaciones:
        return _fallo(
            EstadoCalibracionVision.FALLIDA, EtapaCalibracionVision.FILTRADO,
            f"{len(validas)} observaciones válidas de {n_obs} en la ventana; "
            f"el mínimo es {parametros.min_observaciones}.",
            n_obs, len(validas),
        )

    # ── Etapa 2 — Recorte p5/p95 por componente ──────────────────────────────
    por_componente: dict[str, list[float]] = {}
    for o in validas:
        for nombre, valor in o.componentes.items():
            por_componente.setdefault(nombre, []).append(float(valor))

    recortados: dict[str, list[float]] = {}
    no_calibrables: list[str] = []
    for nombre in sorted(por_componente):
        restantes = recortar_p5_p95(por_componente[nombre])
        if len(restantes) < parametros.min_datos_componente:
            no_calibrables.append(nombre)
        else:
            recortados[nombre] = restantes
    if not recortados or len(no_calibrables) > len(por_componente) / 2:
        return _fallo(
            EstadoCalibracionVision.FALLIDA, EtapaCalibracionVision.RECORTE,
            f"{len(no_calibrables)} de {len(por_componente)} componentes quedaron sin datos "
            "suficientes tras el recorte p5/p95.",
            n_obs, len(validas), componentes_no_calibrables=no_calibrables,
        )

    # ── Etapa 3 — Refinamiento iterativo ─────────────────────────────────────
    base = {nombre: mediana(vals) for nombre, vals in recortados.items()}
    for iteracion in range(1, parametros.max_iteraciones + 1):
        cambio_maximo = 0.0
        for nombre, vals in recortados.items():
            siguiente = recortar_p5_p95(vals)
            # Sin datos suficientes para recortar otra vez, el componente queda fijo.
            if len(siguiente) >= parametros.min_datos_componente:
                recortados[nombre] = siguiente
            nueva = mediana(recortados[nombre])
            anterior = base[nombre]
            cambio = abs(nueva - anterior) / abs(anterior) if anterior else abs(nueva - anterior)
            cambio_maximo = max(cambio_maximo, cambio)
            base[nombre] = nueva
        if cambio_maximo < parametros.epsilon:
            return ResultadoLineaBase(
                estado=EstadoCalibracionVision.EXITOSA,
                n_observaciones=n_obs,
                n_observaciones_validas=len(validas),
                valores=base,
                componentes_no_calibrables=no_calibrables,
                iteraciones=iteracion,
            )

    return _fallo(
        EstadoCalibracionVision.NO_CONVERGIDA, EtapaCalibracionVision.REFINAMIENTO,
        f"Sin convergencia tras {parametros.max_iteraciones} iteraciones "
        f"(ε = {parametros.epsilon:.0%}).",
        n_obs, len(validas), componentes_no_calibrables=no_calibrables,
        iteraciones=parametros.max_iteraciones,
    )
