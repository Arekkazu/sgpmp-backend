# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-03 | Arekkazu | QA-M03 RF-57: correos de alertas con nombres y rótulos legibles en vez de ids y códigos |
"""Textos de las notificaciones de alertas (bandeja, push y correo).

Antes salían ids y códigos: «Alerta CRITICO: fiebre en TEMP_CORPORAL. Valor 40.5700 °C.
Área 2. Alerta #496.» Los rótulos son los mismos del catálogo ``telemetry:codigos`` del
frontend, para que el correo y la pantalla digan lo mismo.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from src.shared.plantilla_correo import formatear_fecha
from src.telemetry.domain.entities.alerta import Alerta
from src.telemetry.domain.repositories.notificacion_alerta_port import ContextoAlerta

_SEVERIDAD = {"CRITICO": "crítica", "MODERADO": "moderada", "LEVE": "leve"}

_ETIQUETAS = {
    # Tipos de alerta
    "ESTRES_TERMICO": "Estrés térmico",
    "SINDROME_RESPIRATORIO": "Síndrome respiratorio",
    "RIESGO_HIDRICO": "Riesgo hídrico",
    "FIEBRE": "Fiebre",
    "INACTIVIDAD_ANORMAL": "Inactividad anormal",
    "FALLO_AMBIENTAL": "Falla ambiental",
    "PREDICCION_PATOLOGIA": "Predicción de patología",
    "TORMENTA_DE_ALERTAS": "Tormenta de alertas",
    "RIESGO_CONTAGIO": "Riesgo de contagio",
    "REGLA_SIMPLE": "Variable fuera de rango",
    "TECNICA": "Falla técnica",
    "HEARTBEAT": "Dispositivo sin señal",
    "EVALUACION_PERIODICA": "Evaluación periódica",
    # Variables
    "TEMPERATURA_AMBIENTAL": "Temperatura ambiental",
    "HUMEDAD_RELATIVA": "Humedad relativa",
    "NH3": "Amoniaco (NH3)",
    "CO2": "Dióxido de carbono (CO2)",
    "PH_AGUA": "pH del agua",
    "OXIGENO_DISUELTO": "Oxígeno disuelto",
    "TDS": "Conductividad eléctrica",
    "TEMP_CORPORAL": "Temperatura corporal",
    "FRECUENCIA_CARDIACA": "Frecuencia cardiaca",
    "FRECUENCIA_RESPIRATORIA": "Frecuencia respiratoria",
    "ACTIVIDAD": "Actividad",
}


def etiqueta(codigo: Optional[str]) -> str:
    """``TEMP_CORPORAL`` → «Temperatura corporal»; lo que no está en el catálogo se humaniza."""
    if not codigo:
        return ""
    if codigo in _ETIQUETAS:
        return _ETIQUETAS[codigo]
    if "_" not in codigo and any(c.islower() for c in codigo):
        return codigo  # ya viene escrito para personas («pH del agua»)
    texto = " ".join(codigo.replace("_", " ").split()).lower()
    return texto[:1].upper() + texto[1:]


def _minuscula(texto: str) -> str:
    """Primera letra en minúscula, salvo siglas («pH», «CO2»)."""
    return texto[:1].lower() + texto[1:] if texto[1:2].islower() else texto


def severidad(codigo: str) -> str:
    return _SEVERIDAD.get(codigo, codigo.lower())


def valor(numero: Decimal | float | int) -> str:
    """``Decimal('40.5700')`` → «40,57»; ``Decimal('90.0000')`` → «90»."""
    texto = format(Decimal(str(numero)).normalize(), "f")
    return texto.replace(".", ",")


def lugar(ctx: ContextoAlerta) -> str:
    """«BOV-001 · Potrero 1 (finca El Rosal)», con lo que haya."""
    partes = [p for p in (ctx.activo, ctx.area) if p]
    texto = " · ".join(partes) if partes else "un área sin identificar"
    return f"{texto} (finca {ctx.finca})" if ctx.finca else texto


def cuando(momento: Optional[datetime]) -> str:
    return f" Detectada el {formatear_fecha(momento)}." if momento else ""


def titulo(alerta: Alerta, ctx: ContextoAlerta) -> str:
    donde = ctx.activo or ctx.area
    base = f"Alerta {severidad(alerta.severidad)}: {_minuscula(etiqueta(alerta.tipo_alerta))}"
    return f"{base} en {donde}" if donde else base


def cuerpo(alerta: Alerta, ctx: ContextoAlerta) -> str:
    texto = f"{etiqueta(alerta.tipo_alerta)} ({severidad(alerta.severidad)}) en {lugar(ctx)}."
    variable = etiqueta(alerta.tipo_variable)
    if alerta.valor is not None:
        texto += f" {variable}: {valor(alerta.valor)} {alerta.unidad or ''}".rstrip() + "."
    elif variable:
        texto += f" Variable: {_minuscula(variable)}."
    texto += cuando(alerta.fecha_evento)
    if ctx.sensor:
        texto += f" Sensor: {ctx.sensor}."
    return texto + " Revísela en el panel de alertas."


def resumen(alertas: list[tuple[Alerta, ContextoAlerta]]) -> str:
    """Tormenta (E8): las LEVE y MODERADO de una ventana en un solo aviso."""
    n = len(alertas)
    lineas = "; ".join(
        f"{etiqueta(a.tipo_alerta)} en {c.activo or c.area or 'un área sin identificar'} ({severidad(a.severidad)})"
        for a, c in alertas[:20]
    )
    extra = f" y {n - 20} más" if n > 20 else ""
    return (f"Llegaron muchas alertas en poco tiempo, así que {'esta' if n == 1 else f'estas {n}'} "
            f"de severidad leve o moderada se agrupan en un solo aviso: {lineas}{extra}. "
            "Revíselas en el panel de alertas.")


def titulo_resumen(n: int) -> str:
    return f"Resumen de {n} {'alerta' if n == 1 else 'alertas'}"
