# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-83/84/86/88/90: núcleo de cálculo NIC 41 (Python puro) |
# | 2026-11-09 | destroyerban | INC-M06-318-G20 RF-84: log de auditoría del ajuste manual de costos de venta |
"""Núcleo de cálculo NIC 41 de M06. Python puro: lo usan todos los casos de uso.

- RF-84 (¶12, ¶5): ``valor_neto = magnitud × precio − costos de venta``. Los costos de M05 son
  gasto del período y nunca se restan aquí (RF-84 R1).
- RF-83 (¶26, ¶51): la variación entre dos mediciones se separa en efecto precio y efecto de
  transformación biológica con la descomposición del ejemplo ilustrativo de la NIC 41:
  ``VN(m_ant, p_act) = VN_act × m_ant / m_act`` (el valor neto es lineal en la magnitud), así
  ``precio = VN(m_ant, p_act) − VN_ant`` y ``transformación = VN_act − VN(m_ant, p_act)``, y la
  suma es exactamente ``VN_act − VN_ant``.
- RF-86 (v2.0): toda línea de asiento lleva valor positivo; una pérdida invierte el par de cuentas.
- RF-88 (¶30, ¶54): depreciación en línea recta por meses sobre el costo de adquisición.
- RF-90 5.8: reparto de un costo compartido con residuo al de mayor participación.
"""
from __future__ import annotations

import calendar
import hashlib
import json
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal
from typing import Optional

from src.financial_valuation.domain.value_objects.nic41 import Sentido, TipoCierre

Q4 = Decimal("0.0001")
Q2 = Decimal("0.01")
CERO = Decimal("0")


def q4(valor: Decimal) -> Decimal:
    return Decimal(valor).quantize(Q4, rounding=ROUND_HALF_UP)


def truncar2(valor: Decimal) -> Decimal:
    """RF-86 v2.0: el valor de la línea se trunca a 2 decimales."""
    return Decimal(valor).quantize(Q2, rounding=ROUND_DOWN)


# --- RF-84: valor razonable menos costos de venta ---------------------------------------------

COMPONENTES_COSTO = ("transporte", "comisiones", "impuestos", "otros")


@dataclass(frozen=True)
class CostosVenta:
    transporte: Decimal = CERO
    comisiones: Decimal = CERO
    impuestos: Decimal = CERO
    otros: Decimal = CERO
    # Método por componente: PARAMETRIZADO o MANUAL (RF-84 entradas metodo_costo_*).
    metodos: dict = field(default_factory=dict)
    # Valor parametrizado que reemplazó cada componente MANUAL (None si M09 no lo parametriza): RF-84 salida 3.
    originales: dict = field(default_factory=dict)

    @property
    def total(self) -> Decimal:
        return self.transporte + self.comisiones + self.impuestos + self.otros

    @property
    def metodo_global(self) -> str:
        """PARAMETRIZADO, MANUAL o MIXTO (``enum_calculos_valor_razonable_metodo_costo``)."""
        valores = set(self.metodos.values()) or {"PARAMETRIZADO"}
        return valores.pop() if len(valores) == 1 else "MIXTO"

    @property
    def tiene_manuales(self) -> bool:
        return "MANUAL" in self.metodos.values()


def costos_venta(
    bruto: Decimal,
    pct_transporte: Optional[Decimal],
    pct_comisiones: Optional[Decimal],
    pct_impuestos: Optional[Decimal],
    manuales: Optional[dict] = None,
) -> CostosVenta:
    """Costos de venta de un cálculo: los parametrizados (fracción del bruto, M09) y los que el
    Contador sobrescribe a mano (RF-84 paso 4). ``otros`` siempre es manual.

    Un componente sin parámetro ni valor manual queda en 0 sin método (no hay costo que deducir);
    sin ningún parámetro, el caso de uso exige el ingreso manual (RF-84 FA-1)."""
    manuales = manuales or {}
    pcts = {"transporte": pct_transporte, "comisiones": pct_comisiones, "impuestos": pct_impuestos}
    valores: dict[str, Decimal] = {}
    metodos: dict[str, str] = {}
    originales: dict[str, Optional[Decimal]] = {}
    for componente in COMPONENTES_COSTO:
        parametrizado = (q4(bruto * Decimal(pcts[componente]))
                         if componente != "otros" and pcts[componente] is not None else None)
        if componente in manuales and manuales[componente] is not None:
            valor = Decimal(manuales[componente])
            if valor < 0:
                raise ValueError(f"El costo de {componente} no puede ser negativo.")
            valores[componente], metodos[componente] = q4(valor), "MANUAL"
            originales[componente] = parametrizado
        elif parametrizado is not None:
            valores[componente], metodos[componente] = parametrizado, "PARAMETRIZADO"
        else:
            valores[componente] = CERO
    return CostosVenta(**valores, metodos=metodos, originales=originales)


@dataclass(frozen=True)
class ValorNeto:
    magnitud: Decimal
    precio_unitario: Decimal
    bruto: Decimal
    costos: CostosVenta
    neto: Decimal

    @property
    def requiere_revision(self) -> bool:
        """RF-84 R3 / FA-2: un valor neto ≤ 0 queda en REVISION_REQUERIDA."""
        return self.neto <= 0


def valor_neto(magnitud: Decimal, precio_unitario: Decimal, costos: CostosVenta) -> ValorNeto:
    bruto = q4(Decimal(magnitud) * Decimal(precio_unitario))
    return ValorNeto(Decimal(magnitud), Decimal(precio_unitario), bruto, costos, q4(bruto - costos.total))


# --- RF-83: separación precio / transformación ------------------------------------------------

@dataclass(frozen=True)
class Variacion:
    total: Decimal
    precio: Decimal
    transformacion: Decimal


def descomponer_variacion(
    vn_anterior: Decimal,
    vn_actual: Decimal,
    magnitud_anterior: Optional[Decimal],
    magnitud_actual: Decimal,
    *,
    hubo_evento_biologico: bool,
) -> Variacion:
    """Separa la variación del valor neto (RF-83 pasos 4-6).

    Sin evento biológico (cierre, cambio de precio) toda la variación es efecto precio
    (RF-83 paso 4). Si no hay magnitud anterior comparable, toda es transformación."""
    total = q4(vn_actual - vn_anterior)
    if not hubo_evento_biologico:
        return Variacion(total, total, CERO)
    if magnitud_anterior is None or magnitud_actual <= 0:
        return Variacion(total, CERO, total)
    pre_ajustado = q4(vn_actual * Decimal(magnitud_anterior) / Decimal(magnitud_actual))
    precio = q4(pre_ajustado - vn_anterior)
    return Variacion(total, precio, total - precio)


# --- RF-86: sentido y valor de una línea ------------------------------------------------------

def sentido_por_signo(monto: Decimal) -> Optional[tuple[Sentido, Decimal]]:
    """Ganancia o pérdida con valor positivo truncado; ``None`` si no hay nada que asentar."""
    valor = truncar2(abs(monto))
    if valor <= 0:
        return None
    return (Sentido.GANANCIA if monto > 0 else Sentido.PERDIDA), valor


# --- RF-88: modelo de costo --------------------------------------------------------------------

def meses_transcurridos(desde: date, hasta: date) -> int:
    """Meses calendario completos entre dos fechas (0 si ``hasta`` es anterior)."""
    meses = (hasta.year - desde.year) * 12 + (hasta.month - desde.month)
    if hasta.day < desde.day and hasta.day != calendar.monthrange(hasta.year, hasta.month)[1]:
        meses -= 1
    return max(meses, 0)


@dataclass(frozen=True)
class ValorPorCosto:
    costo_adquisicion: Decimal
    depreciacion_acumulada: Decimal
    deterioro_acumulado: Decimal
    valor_contable: Decimal

    @property
    def totalmente_depreciado(self) -> bool:
        return self.valor_contable <= 0


def valor_por_costo(
    costo_adquisicion: Decimal, vida_util_meses: int, meses: int, deterioro_acumulado: Decimal = CERO
) -> ValorPorCosto:
    """RF-88 paso 4-6: costo − depreciación acumulada − deterioro, nunca negativo."""
    depreciacion = q4(min(Decimal(costo_adquisicion), Decimal(costo_adquisicion) * meses / vida_util_meses))
    contable = max(CERO, q4(Decimal(costo_adquisicion) - depreciacion - Decimal(deterioro_acumulado)))
    return ValorPorCosto(Decimal(costo_adquisicion), depreciacion, Decimal(deterioro_acumulado), contable)


# --- RF-90 5.8: reparto -----------------------------------------------------------------------

def repartir(monto: Decimal, participaciones: dict[int, Decimal]) -> dict[int, Decimal]:
    """Reparte ``monto`` truncando a 2 decimales; el residuo va al de mayor participación
    (empate: menor id). La suma es exactamente el monto (RF-90 CA-7)."""
    total = sum(participaciones.values(), CERO)
    if not participaciones or total <= 0:
        raise ValueError("El reparto necesita al menos un activo con participación positiva.")
    partes = {k: truncar2(Decimal(monto) * v / total) for k, v in participaciones.items()}
    mayor = min(participaciones, key=lambda k: (-participaciones[k], k))
    partes[mayor] += Decimal(monto) - sum(partes.values(), CERO)
    return partes


# --- RF-87: períodos ---------------------------------------------------------------------------

_MESES_POR_TIPO = {TipoCierre.MENSUAL: 1, TipoCierre.TRIMESTRAL: 3, TipoCierre.ANUAL: 12}


def rango_periodo(dia: date, tipo: TipoCierre) -> tuple[date, date]:
    """Período calendario que contiene ``dia``."""
    meses = _MESES_POR_TIPO[TipoCierre(tipo)]
    mes_inicio = ((dia.month - 1) // meses) * meses + 1
    inicio = date(dia.year, mes_inicio, 1)
    mes_fin = mes_inicio + meses - 1
    return inicio, date(dia.year, mes_fin, calendar.monthrange(dia.year, mes_fin)[1])


def periodo_siguiente(fin: date, tipo: TipoCierre) -> tuple[date, date]:
    dia = date(fin.year + (fin.month == 12), fin.month % 12 + 1, 1)
    return rango_periodo(dia, tipo)


def hash_sha256(contenido: object) -> str:
    """Hash de integridad sobre JSON canónico (claves ordenadas, decimales como texto)."""
    texto = json.dumps(contenido, sort_keys=True, ensure_ascii=False, default=str, separators=(",", ":"))
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()
