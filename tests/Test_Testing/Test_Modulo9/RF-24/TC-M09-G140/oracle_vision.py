"""Oráculo matemático externo de TC-M09-G140 (RF-24 v2.0, CU05 Flujo F).

Calcula, **fuera** del producto, las dos lecturas que la matriz admite para la etapa p5/p95 de
la línea base VISION:

    A. DESCARTE       -> se eliminan los valores < p5 y > p95
    B. WINSORIZACIÓN  -> los valores < p5 se sustituyen por p5 y los > p95 por p95

y aplica después la etapa de refinamiento iterativo. No contiene código productivo ni importa
nada de `src/`: es aritmética independiente, para poder contrastar lo que publique el backend.

Dos decisiones de diseño que importan para no falsear el oráculo:

1. **No se elige entre descarte y winsorización.** Se calculan ambas y quien decide es la
   comparación con la salida real del producto.

2. **No se inventa la regla de refinamiento.** `refinar()` exige una especificación explícita
   (`EspecificacionRefinamiento`). Si el requisito no define cómo se actualiza el estimador, en
   qué conjunto, cómo se mide el cambio relativo o qué pasa con el cero, la función levanta
   `EspecificacionIncompleta` en lugar de suponer un algoritmo. Ese bloqueo es documental, no un
   defecto del producto.

De la misma forma, el método de interpolación de percentiles no se elige a ciegas:
`percentil_robusto()` exige que el valor sea **invariante** entre los métodos habituales y, si no
lo es, levanta `PercentilAmbiguo`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, getcontext
from typing import Callable, Iterable, Literal

getcontext().prec = 40

Metodo = Literal["lower", "higher", "nearest", "midpoint", "linear"]
METODOS_HABITUALES: tuple[Metodo, ...] = ("lower", "higher", "nearest", "midpoint", "linear")


class PercentilAmbiguo(ValueError):
    """El percentil depende del método de interpolación, así que el oráculo no es exacto."""


class EspecificacionIncompleta(ValueError):
    """La regla formal de refinamiento no está definida: no se puede construir un oráculo."""


def _ordenar(valores: Iterable) -> list[Decimal]:
    return sorted(Decimal(str(v)) for v in valores)


def percentil(valores: Iterable, q: Decimal, metodo: Metodo) -> Decimal:
    """Percentil `q` (0..100) por el método indicado, con aritmética decimal exacta."""
    xs = _ordenar(valores)
    if not xs:
        raise ValueError("no se puede calcular un percentil sobre un conjunto vacío")
    if len(xs) == 1:
        return xs[0]
    pos = (Decimal(q) / Decimal(100)) * (Decimal(len(xs)) - 1)
    bajo = int(pos)
    alto = min(bajo + 1, len(xs) - 1)
    frac = pos - Decimal(bajo)
    if metodo == "lower" or frac == 0:
        return xs[bajo]
    if metodo == "higher":
        return xs[alto]
    if metodo == "nearest":
        return xs[bajo] if frac < Decimal("0.5") else xs[alto]
    if metodo == "midpoint":
        return (xs[bajo] + xs[alto]) / Decimal(2)
    if metodo == "linear":
        return xs[bajo] + (xs[alto] - xs[bajo]) * frac
    raise ValueError(f"método de percentil desconocido: {metodo}")


def percentil_robusto(valores: Iterable, q: Decimal) -> Decimal:
    """Percentil solo si es invariante entre los métodos habituales.

    Si el requisito no fija el método de interpolación, el único percentil admisible para un
    oráculo exacto es el que coincide en todos ellos. En caso contrario se levanta
    `PercentilAmbiguo`: el bloqueo es del oráculo matemático, no del producto.
    """
    obtenidos = {m: percentil(valores, q, m) for m in METODOS_HABITUALES}
    distintos = set(obtenidos.values())
    if len(distintos) != 1:
        raise PercentilAmbiguo(
            f"p{q} depende del método de interpolación: "
            + ", ".join(f"{m}={v}" for m, v in obtenidos.items())
            + ". Construya una distribución con meseta en los bordes o declare el método en el requisito."
        )
    return distintos.pop()


# --------------------------------------------------------------------------- etapa 2
@dataclass(frozen=True)
class ResultadoEtapa2:
    lectura: Literal["DESCARTE", "WINSORIZACION"]
    p5: Decimal
    p95: Decimal
    cantidad_antes: int
    cantidad_despues: int
    valores: list[Decimal]


def etapa2_descartar(valores: Iterable) -> ResultadoEtapa2:
    xs = _ordenar(valores)
    p5 = percentil_robusto(xs, Decimal(5))
    p95 = percentil_robusto(xs, Decimal(95))
    filtrados = [v for v in xs if p5 <= v <= p95]
    return ResultadoEtapa2("DESCARTE", p5, p95, len(xs), len(filtrados), filtrados)


def etapa2_winsorizar(valores: Iterable) -> ResultadoEtapa2:
    xs = _ordenar(valores)
    p5 = percentil_robusto(xs, Decimal(5))
    p95 = percentil_robusto(xs, Decimal(95))
    ajustados = [p5 if v < p5 else (p95 if v > p95 else v) for v in xs]
    return ResultadoEtapa2("WINSORIZACION", p5, p95, len(xs), len(ajustados), ajustados)


# --------------------------------------------------------------------------- etapa 3
@dataclass(frozen=True)
class EspecificacionRefinamiento:
    """Regla formal de refinamiento. Sin ella no hay oráculo exacto posible.

    Cada campo debe provenir de una fuente formal del requisito, nunca de inferir el algoritmo
    a partir de nombres de funciones o de leer el código como si fuera la especificación.

    Attributes:
        estimador: cómo se calcula el estimador de cada iteración sobre el conjunto vigente.
        actualizar_conjunto: cómo queda el conjunto para la iteración siguiente.
        cambio_relativo: cómo se mide el cambio relativo entre dos estimadores consecutivos.
        criterio_convergencia: comparación exacta que representa haber convergido.
        tratamiento_cero: qué hacer cuando el estimador anterior es cero.
        epsilon: ε configurado, leído de una fuente formal.
        max_iter: máximo de iteraciones configurado, leído de una fuente formal.
    """

    estimador: Callable[[list[Decimal]], Decimal]
    actualizar_conjunto: Callable[[list[Decimal], Decimal], list[Decimal]]
    cambio_relativo: Callable[[Decimal, Decimal], Decimal]
    criterio_convergencia: Callable[[Decimal, Decimal], bool]
    tratamiento_cero: str
    epsilon: Decimal
    max_iter: int
    fuente: str = field(default="")

    def validar(self) -> None:
        faltan = [n for n in ("estimador", "actualizar_conjunto", "cambio_relativo",
                              "criterio_convergencia") if getattr(self, n) is None]
        if faltan:
            raise EspecificacionIncompleta(
                "la regla de refinamiento no está definida en los campos: " + ", ".join(faltan))
        if not self.tratamiento_cero:
            raise EspecificacionIncompleta(
                "el requisito no define qué ocurre cuando el estimador anterior es cero")
        if self.epsilon is None or self.max_iter is None:
            raise EspecificacionIncompleta("ε y el máximo de iteraciones deben venir de una fuente formal")
        if not self.fuente:
            raise EspecificacionIncompleta(
                "se exige declarar la fuente formal de la regla: el código del producto no es el requisito")


@dataclass(frozen=True)
class ResultadoRefinamiento:
    estimador: Decimal | None
    iteraciones: int
    convergio: bool
    historial: list[dict]


def refinar(valores: list[Decimal], spec: EspecificacionRefinamiento) -> ResultadoRefinamiento:
    """Aplica la etapa 3 según la especificación formal. No supone ningún algoritmo."""
    spec.validar()
    conjunto = list(valores)
    if not conjunto:
        return ResultadoRefinamiento(None, 0, False, [])

    anterior = spec.estimador(conjunto)
    historial = [{"iteracion": 0, "estimador": anterior, "n": len(conjunto)}]
    for i in range(1, spec.max_iter + 1):
        conjunto = spec.actualizar_conjunto(conjunto, anterior)
        if not conjunto:
            return ResultadoRefinamiento(anterior, i, False, historial)
        actual = spec.estimador(conjunto)
        cambio = spec.cambio_relativo(anterior, actual)
        historial.append({"iteracion": i, "estimador": actual, "n": len(conjunto), "cambio_relativo": cambio})
        if spec.criterio_convergencia(cambio, spec.epsilon):
            return ResultadoRefinamiento(actual, i, True, historial)
        anterior = actual
    return ResultadoRefinamiento(anterior, spec.max_iter, False, historial)


# --------------------------------------------------------------------------- por componente
def calcular_ambas_lecturas(componentes: dict[str, list], spec: EspecificacionRefinamiento | None) -> dict:
    """Calcula, por componente, las dos lecturas admitidas de la etapa 2 y, si hay
    especificación formal, también la etapa 3.

    Devuelve un diccionario apto para la evidencia. Cuando algo impide el cálculo exacto
    (percentil ambiguo o especificación incompleta) se registra el motivo en lugar de inventar
    un resultado.
    """
    salida: dict = {"componentes": {}, "bloqueos": []}
    for nombre, valores in componentes.items():
        entrada = {"n": len(valores)}
        try:
            desc = etapa2_descartar(valores)
            wins = etapa2_winsorizar(valores)
        except PercentilAmbiguo as e:
            entrada["etapa2"] = None
            entrada["bloqueo"] = f"percentil ambiguo: {e}"
            salida["bloqueos"].append({"componente": nombre, "motivo": str(e), "tipo": "PERCENTIL_AMBIGUO"})
            salida["componentes"][nombre] = entrada
            continue

        entrada["etapa2"] = {
            "DESCARTE": {"p5": str(desc.p5), "p95": str(desc.p95),
                         "cantidad_antes": desc.cantidad_antes, "cantidad_despues": desc.cantidad_despues},
            "WINSORIZACION": {"p5": str(wins.p5), "p95": str(wins.p95),
                              "cantidad_antes": wins.cantidad_antes, "cantidad_despues": wins.cantidad_despues},
        }

        if spec is None:
            entrada["etapa3"] = None
            entrada["bloqueo"] = ("no hay especificación formal de refinamiento: el oráculo exacto "
                                  "de la etapa 3 no es construible")
            salida["bloqueos"].append({"componente": nombre, "tipo": "REFINAMIENTO_SIN_ESPECIFICACION",
                                       "motivo": entrada["bloqueo"]})
        else:
            try:
                r_desc = refinar(desc.valores, spec)
                r_wins = refinar(wins.valores, spec)
                entrada["etapa3"] = {
                    "DESCARTE": {"estimador": str(r_desc.estimador), "iteraciones": r_desc.iteraciones,
                                 "convergio": r_desc.convergio},
                    "WINSORIZACION": {"estimador": str(r_wins.estimador), "iteraciones": r_wins.iteraciones,
                                      "convergio": r_wins.convergio},
                }
            except EspecificacionIncompleta as e:
                entrada["etapa3"] = None
                entrada["bloqueo"] = f"especificación incompleta: {e}"
                salida["bloqueos"].append({"componente": nombre, "tipo": "REFINAMIENTO_SIN_ESPECIFICACION",
                                           "motivo": str(e)})
        salida["componentes"][nombre] = entrada
    return salida
