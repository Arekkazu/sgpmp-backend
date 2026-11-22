# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-28 | destroyerban | INC-M03-162-G68 RF-57: bandas base de Fase 5, THI y escalada de ESTRES_TERMICO |
# | 2026-10-28 | destroyerban | INC-M03-163-G70 RF-57: condición mínima de ESTRES_TERMICO y RIESGO_HIDRICO, THI NRC |
# | 2026-10-28 | destroyerban | INC-M03-164-G71 RF-57 E14: variable compañera y reglas simples como objeto |
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

#: ESTRES_TERMICO: bandas THI del RF, que son de la escala NRC. La fórmula escrita en el RF es la
#: variante en °C (da valores cercanos a T y nunca alcanza 72); se usa la NRC con T en °C, la misma
#: con la que QA calcula sus casos (24.4 °C y 60 % → 71.98). Si el Edge envía el THI, prevalece.
BANDAS_THI = (_b(CRITICO, desde="84"), _b(MODERADO, desde="79"), _b(LEVE, desde="72"))
_VARIABLES_THI = {"TEMPERATURA_AMBIENTAL", "HUMEDAD_RELATIVA"}
_TEMPERATURA_CORPORAL_ESCALADA = Decimal("40")


def calcular_thi(temperatura: Decimal, humedad: Decimal) -> Decimal:
    f = Decimal("1.8") * temperatura
    thi = (f + 32) - (Decimal("0.55") - Decimal("0.0055") * humedad) * (f - 26)
    return thi.quantize(Decimal("0.01"))


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
        thi = _thi(tipo, valor, corr)
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


def _thi(tipo: str, valor: Decimal, corr: "_Correlacion") -> Optional[Decimal]:
    thi = corr.numero("THI")
    if thi is not None:
        return thi
    otra = corr.numero("HUMEDAD_RELATIVA" if tipo == "TEMPERATURA_AMBIENTAL" else "TEMPERATURA_AMBIENTAL")
    if otra is None or tipo not in _VARIABLES_THI:
        return None
    return calcular_thi(valor, otra) if tipo == "TEMPERATURA_AMBIENTAL" else calcular_thi(otra, valor)


#: Reglas compuestas cuya condición mínima se comprueba (RF-57 Fase 5).
ESTRES_TERMICO, RIESGO_HIDRICO = "ESTRES_TERMICO", "RIESGO_HIDRICO"
COMPUESTAS_VALIDADAS = (ESTRES_TERMICO, RIESGO_HIDRICO)


def condicion_minima(compuesta: str, tipo_variable: str, valor: Decimal,
                     correlacion: Optional[dict[str, Any]] = None) -> Optional[str]:
    """``None`` si la condición mínima de activación se cumple; si no, el motivo.

    - ESTRES_TERMICO: temperatura ambiental + humedad relativa (o el THI) con THI ≥ 72 (LEVE).
    - RIESGO_HIDRICO: pH del agua fuera de rango LEVE o TDS en rango LEVE o superior; el oxígeno
      disuelto es solo complementario.
    """
    tipo = tipo_variable.upper()
    corr = _Correlacion(correlacion)
    if compuesta == ESTRES_TERMICO:
        thi = _thi(tipo, valor, corr)
        if thi is None:
            return "faltan temperatura_ambiental y humedad_relativa (o el THI) en correlacion_variables"
        if severidad_por_bandas(BANDAS_THI, thi) is None:
            return f"THI {thi} < 72: la regla compuesta no se activa"
        return None
    if compuesta == RIESGO_HIDRICO:
        def banda(variable):
            v = valor if tipo == variable else corr.numero(variable)
            return None if v is None else severidad_por_bandas(BANDAS_BASE[variable], v)
        if banda("PH_AGUA") is None and banda("TDS") is None:
            return "ni pH_agua fuera de rango LEVE ni TDS en rango LEVE o superior"
        return None
    return None


def compuestas_declaradas(reglas_activadas) -> list[str]:
    """Reglas compuestas validables que el emisor declara activas (texto u objeto {id, nombre})."""
    textos = []
    for regla in reglas_activadas or []:
        if isinstance(regla, dict):
            textos += [str(regla.get(k, "")) for k in ("nombre", "id", "tipo")]
        else:
            textos.append(str(regla))
    textos = [t.upper() for t in textos]
    return [c for c in COMPUESTAS_VALIDADAS if any(c in t for t in textos)]


#: E14: variable compañera de ESTRES_TERMICO y su ventana de evaluación (RF-57: 10 min).
_COMPANERA_ESTRES_TERMICO = {"TEMPERATURA_AMBIENTAL": "HUMEDAD_RELATIVA", "HUMEDAD_RELATIVA": "TEMPERATURA_AMBIENTAL"}
VENTANA_ESTRES_TERMICO_MIN = 10


def companera_faltante(tipo_variable: str, correlacion: Optional[dict[str, Any]]) -> Optional[str]:
    """Variable requerida de ESTRES_TERMICO que el evento no trae (ni el THI); ``None`` si no falta."""
    companera = _COMPANERA_ESTRES_TERMICO.get(tipo_variable.upper())
    corr = _Correlacion(correlacion)
    if companera is None or corr.numero("THI") is not None or corr.numero(companera) is not None:
        return None
    return companera


def regla_simple(tipo_variable: str, valor: Decimal, id_sensor: Optional[int] = None,
                 id_telemetria: Optional[int] = None) -> dict[str, Any]:
    """Regla simple activada, con la forma {id, nombre} de reglas_activas (E14/E15)."""
    tipo = tipo_variable.upper()
    severidad = severidad_por_bandas(BANDAS_BASE[tipo], valor) if tipo in BANDAS_BASE else None
    return {"id": f"RF57_BASE_{tipo}", "nombre": f"{tipo}_{severidad or 'NORMAL'}", "tipo": "REGLA_SIMPLE_RF57",
            "valor": str(valor), "id_sensor": id_sensor, "id_telemetria": id_telemetria}


def regla_compuesta(compuesta: str, thi: Optional[str] = None) -> dict[str, Any]:
    return {"id": f"RF57_{compuesta}", "nombre": compuesta, "tipo": "REGLA_COMPUESTA_RF57", "thi": thi}


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
