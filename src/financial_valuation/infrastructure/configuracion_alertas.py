# | Fecha       | Nombre | Que se hizo |
# |-------------|--------|-------------|
# | 2026-11-10  | —      | TC-M06-G109: interruptor QA de los avisos de vencimiento, apagado por defecto |
# | 2026-11-10  | —      | TC-M06-G109: la vía general de alertas solo existe con SGPMP_ENTORNO=PROD |
"""Configuración del aviso de vencimiento de precios (RF-89).

Lee ``SGPMP_ENTORNO``, la misma variable de M07, pero no usa su valor por defecto.
M07 y ``docker-compose.yml`` tratan la ausencia como ``DEV``. Para estas alertas la
ausencia, el vacío y cualquier valor distinto de ``PROD``, ``TEST`` o ``DEV`` detienen
el envío. La vía de todos los Contadores solo se abre con ``PROD`` explícito y el
interruptor QA apagado. ``TEST`` y ``DEV`` no tienen esa vía. El modo QA, cuando el
entorno es uno de los tres conocidos, exige las dos listas válidas.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

_VERDADEROS = {"1", "true", "si", "sí"}
_FALSOS = {"0", "false", "no"}
_ENTORNOS_CONOCIDOS = {"PROD", "TEST", "DEV"}


@dataclass(frozen=True)
class DecisionAlertas:
    modo: str
    destinatarios: tuple[int, ...] = ()
    precios: tuple[int, ...] = ()
    motivo: str = ""

    @property
    def permite_envio(self) -> bool:
        if self.modo == "qa":
            return lista_cerrada_valida(self.destinatarios) and lista_cerrada_valida(self.precios)
        return self.modo == "produccion"


def resolver_envio_alertas() -> DecisionAlertas:
    """Decide producción, QA o detención. Cualquier fallo de lectura detiene el envío."""
    try:
        entorno = entorno_para_alertas()
        if entorno is None:
            return DecisionAlertas("bloqueado", motivo="el entorno no autoriza el envío de alertas")
        interruptor = _leer("M06_ALERTAS_QA_HABILITADAS")
        if interruptor is not None and interruptor.lower() not in (_FALSOS | _VERDADEROS):
            return DecisionAlertas("bloqueado", motivo="el interruptor QA no tiene un valor reconocido")
        qa_activo = interruptor is not None and interruptor.lower() in _VERDADEROS
        if qa_activo:
            destinatarios = _identificadores(_leer("M06_ALERTAS_QA_DESTINATARIOS"))
            precios = _identificadores(_leer("M06_ALERTAS_QA_PRECIOS_PERMITIDOS"))
            if not destinatarios or not precios:
                return DecisionAlertas("bloqueado", motivo="la lista QA de destinatarios o de precios no es válida")
            return DecisionAlertas("qa", destinatarios, precios)
        if entorno == "PROD":
            return DecisionAlertas("produccion")
        return DecisionAlertas("bloqueado", motivo="la vía general solo está disponible con SGPMP_ENTORNO=PROD")
    except Exception:
        return DecisionAlertas("bloqueado", motivo="no se pudo leer la configuración de alertas QA")


def entorno_para_alertas() -> str | None:
    """``PROD``, ``TEST`` o ``DEV`` tras recortar y pasar a mayúsculas. Cualquier otro caso, ``None``."""
    valor = _leer("SGPMP_ENTORNO")
    if valor is None:
        return None
    normalizado = valor.upper()
    if normalizado in _ENTORNOS_CONOCIDOS:
        return normalizado
    return None


def lista_cerrada_valida(ids) -> bool:
    """True solo si hay identificadores enteros positivos. No acepta booleanos ni texto."""
    if isinstance(ids, (str, bytes)) or not isinstance(ids, (tuple, list)):
        return False
    if not ids:
        return False
    return all(type(identificador) is int and identificador > 0 for identificador in ids)


def _leer(nombre: str) -> str | None:
    valor = os.getenv(nombre)
    if valor is None:
        return None
    valor = valor.strip()
    return valor or None


def _identificadores(valor: str | None) -> tuple[int, ...] | None:
    if valor is None:
        return None
    partes = [parte.strip() for parte in valor.split(",")]
    if not partes or any(not parte for parte in partes):
        return None
    identificadores: list[int] = []
    for parte in partes:
        if not parte.isdecimal():
            return None
        identificador = int(parte)
        if identificador <= 0:
            return None
        identificadores.append(identificador)
    if len(identificadores) != len(set(identificadores)):
        return None
    return tuple(identificadores)
