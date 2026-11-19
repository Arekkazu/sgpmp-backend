# | Fecha      | Nombre   | Que se hizo                                                     |
# |------------|----------|-----------------------------------------------------------------|
# | 2026-11-14 | Arekkazu | M08 RF-105: nivel por tipo de evento, módulo de origen y destino |
"""Nivel, módulo de origen y pantalla de destino de una notificación (RF-105).

El nivel decide los canales: CRÍTICA va por la bandeja, push y correo; ADVERTENCIA por la bandeja y
push; INFORMATIVA solo por la bandeja. Cada tipo de evento tiene un nivel por defecto y quien
registra la notificación puede subirlo (una alerta CRITICO de telemetría), nunca bajarlo.

Los avisos de cuenta de RF-14 (inicio de sesión, cambio de contraseña…) siguen con el envío que ya
tenían; el nivel solo ordena la bandeja y decide qué entrega el proceso en segundo plano.
"""
from __future__ import annotations

from typing import Optional

CRITICA, ADVERTENCIA, INFORMATIVA = "CRITICA", "ADVERTENCIA", "INFORMATIVA"
NIVELES = (CRITICA, ADVERTENCIA, INFORMATIVA)
NUEVA, LEIDA, ATENDIDA, DESCARTADA = "NUEVA", "LEIDA", "ATENDIDA", "DESCARTADA"
ESTADOS = (NUEVA, LEIDA, ATENDIDA, DESCARTADA)

_PRIORIDAD = {CRITICA: 0, ADVERTENCIA: 1, INFORMATIVA: 2}

# Por nombre del tipo (``modulo1.tipos_eventos.nombre``): los ids no son iguales en todas las bases.
_NIVEL_POR_TIPO = {
    "LOGIN_FALLIDO": ADVERTENCIA,
    "CAMBIO_ESTADO_CUENTA": ADVERTENCIA,
    "REUSO_TOKEN_REFRESCO_DETECTADO": ADVERTENCIA,
    "FALLO_ARCHIVADO_AUDITORIA": ADVERTENCIA,
    "INCONSISTENCIA_AUDITORIA_M02": ADVERTENCIA,
    "NOTIFICACION_ALERTA": ADVERTENCIA,
    "REPORTE_GASTOS_FALLIDO": ADVERTENCIA,
    "PROVISION_M06_PENDIENTE": ADVERTENCIA,
    "ALERTA_CONVERSION_ALIMENTICIA": ADVERTENCIA,
    "BATCH_ICA_INTERRUMPIDO": ADVERTENCIA,
    "ALERTA_FINANCIERA_NIC41": ADVERTENCIA,
    "FIN_PERIODO_RETIRO": ADVERTENCIA,
    "ALERTA_INTEGRACION_CONTABLE": CRITICA,
}


def nivel_para(tipo_evento: Optional[str], sugerido: Optional[str] = None) -> str:
    """Nivel definitivo: el del tipo, o el sugerido si es más alto."""
    base = _NIVEL_POR_TIPO.get(tipo_evento or "", INFORMATIVA)
    if sugerido in _PRIORIDAD and _PRIORIDAD[sugerido] < _PRIORIDAD[base]:
        return sugerido
    return base


def prioridad(nivel: str) -> int:
    return _PRIORIDAD.get(nivel, len(_PRIORIDAD))


# Módulo de origen como clave legible para el filtro de la bandeja (el front pone el nombre).
# ``modulo1.eventos.modulo`` trae el número escrito de varias formas ("MODULO3", "Modulo 2"…).
MODULOS = {
    "1": "cuentas", "2": "activos", "3": "telemetria", "4": "prediccion", "5": "suministros",
    "6": "finanzas", "7": "integracion", "8": "reportes", "9": "configuracion",
}
NUMERO_POR_MODULO = {clave: numero for numero, clave in MODULOS.items()}

# Pantalla que abre el clic en una notificación push cuando el origen no indica otra
# (relativa a la base del front).
_DESTINO_POR_MODULO = {
    "activos": "activos-biologicos", "telemetria": "telemetria/alertas", "prediccion": "prediccion",
    "suministros": "suministros", "finanzas": "finanzas", "integracion": "integracion",
}


def modulo_desde(texto: Optional[str]) -> Optional[str]:
    numero = "".join(c for c in (texto or "") if c.isdigit())
    return MODULOS.get(numero)


def destino_por_defecto(modulo: Optional[str]) -> str:
    return _DESTINO_POR_MODULO.get(modulo or "", "dashboard")


_TITULO_POR_MODULO = {
    "cuentas": "Tu cuenta", "activos": "Activos biológicos", "telemetria": "Telemetría",
    "prediccion": "Predicción de salud", "suministros": "Suministros", "finanzas": "Finanzas",
    "integracion": "Integración contable", "reportes": "Reportes", "configuracion": "Configuración",
}


def titulo_push(nivel: str, modulo: Optional[str]) -> str:
    """Título visible del push que envía el entregador: el módulo, y si es crítica, que lo es."""
    seccion = _TITULO_POR_MODULO.get(modulo or "", "SIGAB")
    return f"Alerta crítica · {seccion}" if nivel == CRITICA else seccion
