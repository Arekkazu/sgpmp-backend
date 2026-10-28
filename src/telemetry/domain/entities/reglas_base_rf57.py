# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-28 | destroyerban | INC-M03-162-G68 RF-57: bandas base de Fase 5, THI y escalada de ESTRES_TERMICO |
"""RF-57 Fase 5: valores base de las reglas simples y de la regla compuesta ESTRES_TERMICO.

La severidad de un evento externo sale del valor, no de lo que declara el emisor
(CA-1, Restricción 7). Variables cuya banda depende de la especie o de una media
móvil (frecuencia respiratoria, actividad) no se pueden evaluar con un solo valor:
para ellas se conserva la severidad reportada.

``correlacion_variables`` (RF-57 Entradas: "estructura opcional ... ej. THI") no tiene
formato fijado; se acepta un objeto indexado por código de variable, con el valor como
número o como ``{"valor": n}``, y la frecuencia respiratoria como
``{"severidad": "MODERADO"}`` (su rango depende de la especie).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

LEVE, MODERADO, CRITICO = "LEVE", "MODERADO", "CRITICO"
_ORDEN = {None: -1, LEVE: 0, MODERADO: 1, CRITICO: 2}
_SUBIR = {LEVE: MODERADO, MODERADO: CRITICO, CRITICO: CRITICO}


@dataclass(frozen=True)
class Banda:
    severidad: str
    por_debajo_de: Optional[Decimal] = None   # valor < límite
    por_encima_de: Optional[Decimal] = None   # valor > límite
    desde: Optional[Decimal] = None           # valor >= límite

    def aplica(self, valor: Decimal) -> bool:
        return ((self.por_debajo_de is not None and valor < self.por_debajo_de)
                or (self.por_encima_de is not None and valor > self.por_encima_de)
                or (self.desde is not None and valor >= self.desde))


def _b(severidad, debajo=None, encima=None, desde=None) -> Banda:
    conv = lambda x: None if x is None else Decimal(x)
    return Banda(severidad, conv(debajo), conv(encima), conv(desde))


_TEMPERATURA_CORPORAL = (_b(CRITICO, "35.5", "41.0"), _b(MODERADO, "36.0", "40.5"), _b(LEVE, "36.5", "40.0"))

#: Bandas base de RF-57 Fase 5, de la más severa a la menos severa. Fuera de todas = NORMAL.
BANDAS_BASE: dict[str, tuple[Banda, ...]] = {
    "TEMPERATURA_AMBIENTAL": (_b(CRITICO, "14", "36"), _b(MODERADO, "17", "33"), _b(LEVE, "20", "30")),
    "HUMEDAD_RELATIVA": (_b(CRITICO, "30", "90"), _b(MODERADO, "40", "80"), _b(LEVE, "50", "70")),
    "PH_AGUA": (_b(CRITICO, "5.5", "9.5"), _b(MODERADO, "6.0", "9.0"), _b(LEVE, "6.5", "8.5")),
    "NH3": (_b(CRITICO, desde="45"), _b(MODERADO, desde="35"), _b(LEVE, desde="25")),
    "CO2": (_b(CRITICO, desde="4000"), _b(MODERADO, desde="3500"), _b(LEVE, desde="3000")),
    "TEMPERATURA_CORPORAL": _TEMPERATURA_CORPORAL,
    "TEMP_CORPORAL": _TEMPERATURA_CORPORAL,
    "FRECUENCIA_CARDIACA": (_b(CRITICO, "40", "120"), _b(MODERADO, "42", "110"), _b(LEVE, "45", "100")),
    "OXIGENO_DISUELTO": (_b(CRITICO, "2"), _b(MODERADO, "3"), _b(LEVE, "5")),
    "TDS": (_b(CRITICO, desde="2000"), _b(MODERADO, encima="1500"), _b(LEVE, encima="1000")),
}

#: ESTRES_TERMICO: bandas THI del RF (escala NRC). El THI lo deriva el Edge (RF-55) y llega en
#: correlacion_variables: la fórmula del RF está en °C y nunca alcanza 72, así que no se recalcula aquí.
BANDAS_THI = (_b(CRITICO, desde="84"), _b(MODERADO, desde="79"), _b(LEVE, desde="72"))
_VARIABLES_THI = {"TEMPERATURA_AMBIENTAL", "HUMEDAD_RELATIVA"}
_TEMPERATURA_CORPORAL_ESCALADA = Decimal("40")


def severidad_por_bandas(bandas, valor: Decimal) -> Optional[str]:
    return next((b.severidad for b in bandas if b.aplica(valor)), None)


def mayor(a: Optional[str], b: Optional[str]) -> Optional[str]:
    return a if _ORDEN[a] >= _ORDEN[b] else b


@dataclass
class EvaluacionRF57:
    evaluable: bool
    severidad: Optional[str] = None        # None con evaluable=True → banda NORMAL
    detalle: dict[str, Any] = field(default_factory=dict)


def evaluar_evento(tipo_variable: str, valor: Decimal,
                   correlacion: Optional[dict[str, Any]] = None) -> EvaluacionRF57:
    tipo = tipo_variable.upper()
    if tipo not in BANDAS_BASE:
        return EvaluacionRF57(evaluable=False, detalle={"motivo": "banda dependiente de especie o de media móvil"})
    corr = _Correlacion(correlacion)
    severidad = severidad_por_bandas(BANDAS_BASE[tipo], valor)
    detalle: dict[str, Any] = {"regla": f"RF57_BASE_{tipo}", "severidad_por_valor": severidad}

    if tipo in _VARIABLES_THI:
        thi = corr.numero("THI")
        if thi is not None:
            severidad_thi = severidad_por_bandas(BANDAS_THI, thi)
            detalle.update(thi=str(thi), severidad_thi=severidad_thi)
            severidad = mayor(severidad, severidad_thi)
            if severidad_thi is not None:
                motivo = _motivo_escalada(corr)
                if motivo:
                    detalle.update(escalada=motivo, severidad_antes_de_escalar=severidad)
                    severidad = _SUBIR[severidad]
    detalle["severidad_rf57"] = severidad
    return EvaluacionRF57(evaluable=True, severidad=severidad, detalle=detalle)


def _motivo_escalada(corr: "_Correlacion") -> Optional[str]:
    temperatura_corporal = corr.numero("TEMPERATURA_CORPORAL", "TEMP_CORPORAL")
    if temperatura_corporal is not None and temperatura_corporal > _TEMPERATURA_CORPORAL_ESCALADA:
        return f"TEMPERATURA_CORPORAL={temperatura_corporal} > 40"
    nivel_fr = corr.nivel("FRECUENCIA_RESPIRATORIA")
    if _ORDEN.get(nivel_fr, -1) >= _ORDEN[MODERADO]:
        return f"FRECUENCIA_RESPIRATORIA en rango {nivel_fr}"
    return None


def fuera_de_rango_fisico(valor: Decimal, minimo: Optional[Decimal], maximo: Optional[Decimal]) -> bool:
    return (minimo is not None and valor < minimo) or (maximo is not None and valor > maximo)


class _Correlacion:
    def __init__(self, datos: Optional[dict[str, Any]]) -> None:
        self._datos = {str(k).upper().strip(): v for k, v in (datos or {}).items()}

    def _crudo(self, *claves):
        return next((self._datos[c] for c in claves if c in self._datos), None)

    def numero(self, *claves) -> Optional[Decimal]:
        v = self._crudo(*claves)
        if isinstance(v, dict):
            v = v.get("valor", v.get("value"))
        if v is None or isinstance(v, bool):
            return None
        try:
            return Decimal(str(v))
        except (InvalidOperation, ValueError):
            return None

    def nivel(self, *claves) -> Optional[str]:
        v = self._crudo(*claves)
        if isinstance(v, dict):
            v = v.get("severidad", v.get("nivel"))
        return v.upper() if isinstance(v, str) and v.upper() in _SUBIR else None
