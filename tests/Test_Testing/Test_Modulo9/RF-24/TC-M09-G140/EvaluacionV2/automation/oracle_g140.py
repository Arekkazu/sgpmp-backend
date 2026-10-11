"""Oráculo INDEPENDIENTE de la línea base por visión — TC-M09-G140 (RF-24 v2.0, CU05 Flujo F).

Implementa desde cero las tres etapas descritas en la matriz QA, sin importar **nada** del
producto: ni `calcular_linea_base`, ni `recortar_p5_p95`, ni `mediana`, ni `percentil`, ni
ningún módulo `src.configuration...` o `src.telemetry...`. Si este archivo importara el
algoritmo del backend dejaría de ser un oráculo y pasaría a ser un espejo.

Etapas (§15 del paquete):

  1. FILTRADO       — conserva solo observaciones con apto_para_ia, cobertura >= cobertura_minima
                      y n_tracks >= tracks_minimos; aborta si quedan menos de min_observaciones.
  2. RECORTE        — por componente, p5 y p95. La matriz admite DOS lecturas y aquí se calculan
                      las dos: DESCARTE (se eliminan los valores fuera de [p5, p95]) y
                      WINSORIZACION (se recortan al borde más cercano, sin perder datos).
  3. REFINAMIENTO   — mediana por componente, se repite el recorte, se recalcula la mediana y se
                      mide el cambio relativo; converge cuando el cambio máximo < epsilon y
                      declara NO_CONVERGIDA si agota max_iteraciones.

El percentil usa la definición estándar de interpolación lineal entre rangos (el método
"linear" de numpy / tipo 7 de Hyndman-Fan), escrita aquí a mano.

Uso como script (imprime los dos oráculos de los datasets del grupo):
    python oracle_g140.py
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Optional

# ── Parámetros (se pasan explícitamente; estos son solo los de referencia del paquete) ──
@dataclass(frozen=True)
class Parametros:
    min_observaciones: int = 30
    cobertura_minima: float = 0.5
    tracks_minimos: int = 1
    min_datos_componente: int = 10
    epsilon: float = 0.01
    max_iteraciones: int = 10


DESCARTE = "DESCARTE"
WINSORIZACION = "WINSORIZACION"


# ── Primitivas estadísticas propias ──────────────────────────────────────────
def percentil(valores: list[float], p: float) -> float:
    """Percentil p (0-100) con interpolación lineal entre rangos.

    Implementación propia: se ordena, se sitúa la posición fraccionaria
    (n-1)·p/100 y se interpola entre los dos vecinos.
    """
    if not valores:
        raise ValueError("percentil de una lista vacía")
    datos = sorted(float(v) for v in valores)
    if len(datos) == 1:
        return datos[0]
    posicion = (len(datos) - 1) * (p / 100.0)
    bajo = int(posicion // 1)
    alto = min(bajo + 1, len(datos) - 1)
    peso = posicion - bajo
    return datos[bajo] + (datos[alto] - datos[bajo]) * peso


def mediana(valores: list[float]) -> float:
    return percentil(valores, 50.0)


def limites_p5_p95(valores: list[float]) -> tuple[float, float]:
    return percentil(valores, 5.0), percentil(valores, 95.0)


def aplicar_descarte(valores: list[float]) -> list[float]:
    """Elimina los valores fuera de [p5, p95]; los iguales a los bordes se conservan."""
    p5, p95 = limites_p5_p95(valores)
    return [v for v in valores if p5 <= v <= p95]


def aplicar_winsorizacion(valores: list[float]) -> list[float]:
    """Lleva cada valor fuera de [p5, p95] al borde más cercano; no se pierde ningún dato."""
    p5, p95 = limites_p5_p95(valores)
    return [p5 if v < p5 else (p95 if v > p95 else v) for v in valores]


def _recorte(valores: list[float], modo: str) -> list[float]:
    if modo == DESCARTE:
        return aplicar_descarte(valores)
    if modo == WINSORIZACION:
        return aplicar_winsorizacion(valores)
    raise ValueError(f"modo de recorte desconocido: {modo}")


def cambio_relativo(nuevo: float, anterior: float) -> float:
    """|nuevo − anterior| / |anterior|, o la diferencia absoluta si el anterior es 0."""
    return abs(nuevo - anterior) / abs(anterior) if anterior else abs(nuevo - anterior)


# ── Observación de entrada del oráculo ───────────────────────────────────────
@dataclass(frozen=True)
class Obs:
    apto_para_ia: bool
    cobertura_ventana: float
    n_tracks: int
    componentes: dict[str, float]


# ── Resultado del oráculo ────────────────────────────────────────────────────
@dataclass
class Resultado:
    modo_recorte: str
    estado: str                                  # EXITOSA | FALLIDA | NO_CONVERGIDA
    etapa_fallo: Optional[str] = None            # FILTRADO | RECORTE | REFINAMIENTO
    motivo: Optional[str] = None
    n_observaciones: int = 0
    n_observaciones_validas: int = 0
    valores: dict[str, float] = field(default_factory=dict)
    componentes_no_calibrables: list[str] = field(default_factory=list)
    iteraciones: Optional[int] = None
    traza: dict = field(default_factory=dict)

    def a_dict(self) -> dict:
        return {
            "modo_recorte": self.modo_recorte,
            "estado": self.estado,
            "etapa_fallo": self.etapa_fallo,
            "motivo": self.motivo,
            "n_observaciones": self.n_observaciones,
            "n_observaciones_validas": self.n_observaciones_validas,
            "valores": self.valores,
            "componentes_no_calibrables": self.componentes_no_calibrables,
            "iteraciones": self.iteraciones,
            "traza": self.traza,
        }


def calcular(observaciones: list[Obs], par: Parametros, modo: str) -> Resultado:
    """Las tres etapas, en orden, cada una sobre la salida de la anterior."""
    n_obs = len(observaciones)
    traza: dict = {"modo_recorte": modo, "parametros": par.__dict__.copy()}

    # ── Etapa 1 — Filtrado ambiental ─────────────────────────────────────────
    validas = [o for o in observaciones
               if o.apto_para_ia
               and o.cobertura_ventana >= par.cobertura_minima
               and o.n_tracks >= par.tracks_minimos]
    traza["etapa_1"] = {
        "entradas": n_obs,
        "validas": len(validas),
        "descartadas_por_aptitud": sum(1 for o in observaciones if not o.apto_para_ia),
        "descartadas_por_cobertura": sum(
            1 for o in observaciones if o.apto_para_ia and o.cobertura_ventana < par.cobertura_minima),
        "descartadas_por_tracks": sum(
            1 for o in observaciones if o.apto_para_ia
            and o.cobertura_ventana >= par.cobertura_minima and o.n_tracks < par.tracks_minimos),
        "minimo_exigido": par.min_observaciones,
    }
    if len(validas) < par.min_observaciones:
        return Resultado(
            modo_recorte=modo, estado="FALLIDA", etapa_fallo="FILTRADO",
            motivo=(f"{len(validas)} observaciones válidas de {n_obs} en la ventana; "
                    f"el mínimo es {par.min_observaciones}."),
            n_observaciones=n_obs, n_observaciones_validas=len(validas), traza=traza)

    # ── Etapa 2 — Recorte p5/p95 por componente ──────────────────────────────
    por_componente: dict[str, list[float]] = {}
    for o in validas:
        for nombre, valor in o.componentes.items():
            por_componente.setdefault(nombre, []).append(float(valor))

    recortados: dict[str, list[float]] = {}
    no_calibrables: list[str] = []
    traza["etapa_2"] = {}
    for nombre in sorted(por_componente):
        originales = por_componente[nombre]
        p5, p95 = limites_p5_p95(originales)
        restantes = _recorte(originales, modo)
        traza["etapa_2"][nombre] = {
            "n_entrada": len(originales), "p5": p5, "p95": p95,
            "n_tras_recorte": len(restantes),
            "min_datos_componente": par.min_datos_componente,
            "mediana_de_entrada": mediana(originales),
            "mediana_tras_recorte": mediana(restantes) if restantes else None,
        }
        if len(restantes) < par.min_datos_componente:
            no_calibrables.append(nombre)
        else:
            recortados[nombre] = restantes
    if not recortados or len(no_calibrables) > len(por_componente) / 2:
        return Resultado(
            modo_recorte=modo, estado="FALLIDA", etapa_fallo="RECORTE",
            motivo=(f"{len(no_calibrables)} de {len(por_componente)} componentes quedaron sin "
                    "datos suficientes tras el recorte p5/p95."),
            n_observaciones=n_obs, n_observaciones_validas=len(validas),
            componentes_no_calibrables=no_calibrables, traza=traza)

    # ── Etapa 3 — Refinamiento iterativo ─────────────────────────────────────
    base = {nombre: mediana(vals) for nombre, vals in recortados.items()}
    traza["etapa_3"] = {"mediana_inicial": dict(base), "iteraciones": []}
    trabajo = {nombre: list(vals) for nombre, vals in recortados.items()}

    for iteracion in range(1, par.max_iteraciones + 1):
        detalle: dict = {"iteracion": iteracion, "componentes": {}}
        cambio_maximo = 0.0
        for nombre, vals in trabajo.items():
            siguiente = _recorte(vals, modo)
            # Sin datos suficientes para recortar otra vez, el componente queda fijo.
            if len(siguiente) >= par.min_datos_componente:
                trabajo[nombre] = siguiente
            nueva = mediana(trabajo[nombre])
            anterior = base[nombre]
            cambio = cambio_relativo(nueva, anterior)
            cambio_maximo = max(cambio_maximo, cambio)
            detalle["componentes"][nombre] = {
                "n_antes": len(vals), "n_despues": len(trabajo[nombre]),
                "mediana_anterior": anterior, "mediana_nueva": nueva,
                "cambio_relativo": cambio,
            }
            base[nombre] = nueva
        detalle["cambio_maximo"] = cambio_maximo
        detalle["epsilon"] = par.epsilon
        detalle["convergio"] = cambio_maximo < par.epsilon
        traza["etapa_3"]["iteraciones"].append(detalle)
        if cambio_maximo < par.epsilon:
            return Resultado(
                modo_recorte=modo, estado="EXITOSA",
                n_observaciones=n_obs, n_observaciones_validas=len(validas),
                valores=dict(base), componentes_no_calibrables=no_calibrables,
                iteraciones=iteracion, traza=traza)

    return Resultado(
        modo_recorte=modo, estado="NO_CONVERGIDA", etapa_fallo="REFINAMIENTO",
        motivo=(f"Sin convergencia tras {par.max_iteraciones} iteraciones "
                f"(ε = {par.epsilon:.0%})."),
        n_observaciones=n_obs, n_observaciones_validas=len(validas),
        componentes_no_calibrables=no_calibrables,
        iteraciones=par.max_iteraciones, traza=traza)


def ambas_lecturas(observaciones: list[Obs], par: Parametros) -> dict:
    """§17: el oráculo entrega las dos interpretaciones admitidas, sin elegir ninguna."""
    return {
        "ORACLE_DESCARTE": calcular(observaciones, par, DESCARTE).a_dict(),
        "ORACLE_WINSORIZACION": calcular(observaciones, par, WINSORIZACION).a_dict(),
    }


def coincide(producto: dict[str, float], oraculo: dict[str, float], tol: float = 1e-9) -> bool:
    """Comparación componente por componente con tolerancia solo por serialización de float."""
    if set(producto) != set(oraculo):
        return False
    return all(abs(float(producto[k]) - float(oraculo[k])) <= tol for k in producto)


# ══════════════════════════════════════════════════════════════════════════════
# Datasets del grupo (deterministas, sin aleatoriedad)
# ══════════════════════════════════════════════════════════════════════════════

def apta(densidad: float, tasa: float) -> Obs:
    return Obs(apto_para_ia=True, cobertura_ventana=1.0, n_tracks=20,
               componentes={"densidad_actividad": densidad, "tasa_movimiento": tasa})


def no_apta(densidad: float, tasa: float) -> Obs:
    return Obs(apto_para_ia=False, cobertura_ventana=0.1, n_tracks=0,
               componentes={"densidad_actividad": densidad, "tasa_movimiento": tasa})


def vector_k(i: int) -> tuple[float, float]:
    """§24: 40 vectores deterministas del conjunto K de TC-M09-284."""
    return (round(10.0 + ((i % 5) - 2) * 0.01, 6),
            round(5.0 + ((i % 7) - 3) * 0.005, 6))


def dataset_k() -> list[Obs]:
    return [apta(*vector_k(i)) for i in range(40)]


def dataset_m() -> list[Obs]:
    """§25: 10 observaciones NO aptas con valores ~100× la mediana de K."""
    return [no_apta(1000.0, 500.0) for _ in range(10)]


#: §35 — componente `densidad_actividad` de TC-M09-285: veinte 1 y luego 2..21.
DENSIDAD_285: list[float] = [1.0] * 20 + [float(v) for v in range(2, 22)]

#: §52 — componente `densidad_actividad` de TC-M09-286 (dataset no convergente).
DENSIDAD_286: list[float] = (
    [1.0] * 8 + [2.0] * 3 + [4.0] * 3 + [5.0] * 3 + [6.0] * 2
    + [8.0] * 3 + [10.0] + [20.0] * 3 + [50.0] * 2 + [100.0] * 2
)


def dataset_285() -> list[Obs]:
    return [apta(d, d * 10) for d in DENSIDAD_285]


def dataset_286_fail() -> list[Obs]:
    return [apta(d, d * 10) for d in DENSIDAD_286]


def dataset_286_base(n: int) -> list[Obs]:
    """§50: N observaciones aptas idénticas y estables para la línea base previa."""
    return [apta(10.0, 5.0) for _ in range(n)]


def _resumen() -> dict:
    par = Parametros()
    k, m = dataset_k(), dataset_m()
    assert len(DENSIDAD_285) == 40, len(DENSIDAD_285)
    assert len(DENSIDAD_286) == 30, len(DENSIDAD_286)
    return {
        "parametros_de_referencia": par.__dict__.copy(),
        "TC-M09-284": {
            "K": ambas_lecturas(k, par),
            "K+M": ambas_lecturas(k + m, par),
            "vectores_K": [{"i": i, "densidad_actividad": d, "tasa_movimiento": t}
                           for i, (d, t) in enumerate(vector_k(i) for i in range(40))],
        },
        "TC-M09-285": {
            "densidad_actividad": DENSIDAD_285,
            "tasa_movimiento": [d * 10 for d in DENSIDAD_285],
            **ambas_lecturas(dataset_285(), par),
        },
        "TC-M09-286": {
            "densidad_actividad": DENSIDAD_286,
            "tasa_movimiento": [d * 10 for d in DENSIDAD_286],
            "con_max_iteraciones_1": ambas_lecturas(
                dataset_286_fail(), Parametros(max_iteraciones=1)),
            "con_max_iteraciones_de_referencia": ambas_lecturas(dataset_286_fail(), par),
        },
    }


if __name__ == "__main__":
    print(json.dumps(_resumen(), indent=2, ensure_ascii=False))
