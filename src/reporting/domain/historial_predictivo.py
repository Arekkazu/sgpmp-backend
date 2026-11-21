# | Fecha      | Nombre   | Que se hizo                                                                  |
# |------------|----------|------------------------------------------------------------------------------|
# | 2026-11-18 | Arekkazu | M08 RF-106: TVCO, conflictos, correspondencias, colisiones y pendientes       |
"""Reglas del historial clínico predictivo de un animal (RF-106), sin E/S.

- **TVCO** (tasa de validación clínica observada) = CORRECTO / inferencias con retroalimentación sin conflicto.
  Las que no tienen retroalimentación y las que tienen valoraciones distintas (conflicto) quedan fuera del
  numerador y del denominador (R6, CA-3, CA-8). Dos valoraciones iguales cuentan como una.
- **Correspondencia** (R5b): una predicción y un evento sanitario a ``ventana`` horas o menos se muestran unidos
  por un conector; más lejos, independientes. Es solo visual: no implica causalidad.
- **Colisión** (R5c): marcadores a una hora o menos se agrupan en «N eventos»; al expandir, primero las
  retroalimentaciones, luego los eventos sanitarios, luego las predicciones.
- **Pendientes**: predicciones sin retroalimentación con más de 48 h, por riesgo y luego por fecha, de mayor a menor.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional

COLISION = timedelta(hours=1)
ANTIGUEDAD_PENDIENTE = timedelta(hours=48)
RANGO_MAXIMO_DIAS = 731  # 24 meses
CORRECTO = "CORRECTO"
_PRIORIDAD = {"RETROALIMENTACION": 0, "EVENTO_SANITARIO": 1, "PREDICCION": 2}


@dataclass
class Tvco:
    porcentaje: Optional[float]
    validadas: int
    sin_retroalimentacion: int
    con_conflicto: int
    texto: str

    @property
    def tasa_error(self) -> Optional[float]:
        return None if self.porcentaje is None else round(100 - self.porcentaje, 2)


def valoraciones_por_inferencia(retros: list[dict[str, Any]]) -> dict[Any, set[str]]:
    agrupadas: dict[Any, set[str]] = {}
    for r in retros:
        agrupadas.setdefault(r["id_resultado_inferencia"], set()).add(r["valoracion"])
    return agrupadas


def _plural(n: int, singular: str, plural: str) -> str:
    return f"{n} {singular if n == 1 else plural}"


def calcular_tvco(id_inferencias: list[Any], retros: list[dict[str, Any]]) -> Tvco:
    valoraciones = valoraciones_por_inferencia(retros)
    sin_retro = sum(1 for i in id_inferencias if i not in valoraciones)
    conflicto = [i for i in id_inferencias if len(valoraciones.get(i, ())) > 1]
    validadas = [i for i in id_inferencias if len(valoraciones.get(i, ())) == 1]
    correctas = sum(1 for i in validadas if valoraciones[i] == {CORRECTO})
    if not validadas:
        return Tvco(None, 0, sin_retro, len(conflicto), "Sin datos suficientes para calcular")
    porcentaje = round(correctas / len(validadas) * 100, 2)
    excluidas = sin_retro + len(conflicto)
    texto = f"{porcentaje:g}% ({_plural(len(validadas), 'validada', 'validadas')}"
    if excluidas:
        partes = []
        if conflicto:
            partes.append("conflicto" if not sin_retro else f"{len(conflicto)} conflicto")
        if sin_retro:
            partes.append("sin retro" if not conflicto else f"{sin_retro} sin retro")
        texto += f"; {_plural(excluidas, 'excluida', 'excluidas')}: {' + '.join(partes)}"
    return Tvco(porcentaje, len(validadas), sin_retro, len(conflicto), texto + ")")


@dataclass
class Marcador:
    tipo: str  # PREDICCION, EVENTO_SANITARIO, RETROALIMENTACION
    fecha: datetime
    datos: dict[str, Any] = field(default_factory=dict)


def agrupar_colisiones(marcadores: list[Marcador]) -> list[list[Marcador]]:
    """Grupos de marcadores consecutivos a una hora o menos; dentro de cada grupo, por prioridad visual."""
    grupos: list[list[Marcador]] = []
    for m in sorted(marcadores, key=lambda x: x.fecha):
        if grupos and m.fecha - grupos[-1][-1].fecha <= COLISION:
            grupos[-1].append(m)
        else:
            grupos.append([m])
    return [sorted(g, key=lambda x: (_PRIORIDAD[x.tipo], x.fecha)) for g in grupos]


def correspondencias(predicciones: list[Marcador], eventos: list[Marcador], ventana: timedelta) -> list[dict[str, Any]]:
    """Pares predicción–evento a ``ventana`` o menos (en cualquier sentido), con la diferencia exacta."""
    pares = []
    for p in predicciones:
        for e in eventos:
            delta = abs(e.fecha - p.fecha)
            if delta <= ventana:
                minutos = int(delta.total_seconds() // 60)
                pares.append({"id_resultado_inferencia": p.datos.get("id_resultado_inferencia"),
                              "id_evento": e.datos.get("id_evento"), "diferencia_minutos": minutos,
                              "diferencia": f"Diferencia: {minutos // 60} h" + (f" {minutos % 60} min" if minutos % 60
                                                                                 else ""),
                              "colision": delta <= COLISION})
    return pares


def pendientes(inferencias: list[dict[str, Any]], con_retro: set, ahora: datetime) -> list[dict[str, Any]]:
    viejas = [i for i in inferencias
              if i["id_resultado_inferencia"] not in con_retro and ahora - i["fecha_inferencia"] > ANTIGUEDAD_PENDIENTE]
    return sorted(viejas, key=lambda i: (i["nivel_riesgo"] or 0, i["fecha_inferencia"]), reverse=True)
