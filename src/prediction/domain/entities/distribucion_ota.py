"""Distribución OTA de un modelo por componente a varios nodos (DEV-15, RF-70/RF-73, D6).

Una distribución es un ``POST /prediccion/ota/distribuciones``: una versión de un
``(tipo_modelo, componente)`` hacia una lista de nodos, con sus reglas (ventana,
batería mínima, fragmento, reintentos). Cada nodo es una fila de
``despliegues_ota`` (DB-04). El rollout avanza por fases: un nodo canary, luego
el 20–30 % de los nodos y por último el resto. Una fase avanza solo cuando todos
sus nodos activaron la versión; un ``rollback`` o una falla crítica la detienen.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional

FASE_CANARY = "CANARY"
FASE_PARCIAL = "PARCIAL"
FASE_TOTAL = "TOTAL"
FASES = (FASE_CANARY, FASE_PARCIAL, FASE_TOTAL)

ESTADO_EN_CURSO = "EN_CURSO"
ESTADO_COMPLETADA = "COMPLETADA"
ESTADO_DETENIDA = "DETENIDA"

PORCENTAJE_PARCIAL_MIN = 20
PORCENTAJE_PARCIAL_MAX = 30
PORCENTAJE_PARCIAL_DEFAULT = 25


def planificar_fases(cantidad_nodos: int, porcentaje_parcial: int) -> list[str]:
    """Fase de cada nodo, en el orden recibido: 1 canary, ``porcentaje_parcial`` % parcial, el resto total.

    El porcentaje se toma sobre el total de nodos y redondea hacia arriba (al menos
    un nodo) para que la fase parcial nunca quede vacía mientras sobren nodos.
    """
    if cantidad_nodos <= 0:
        return []
    restantes = cantidad_nodos - 1
    parciales = min(restantes, max(1, math.ceil(cantidad_nodos * porcentaje_parcial / 100))) if restantes else 0
    return [FASE_CANARY] + [FASE_PARCIAL] * parciales + [FASE_TOTAL] * (restantes - parciales)


def siguiente_fase(fase: str) -> Optional[str]:
    indice = FASES.index(fase)
    return FASES[indice + 1] if indice + 1 < len(FASES) else None


@dataclass
class DistribucionOta:
    id_version_modelo: int
    tipo_modelo: str
    componente: Optional[str]
    modo_distribucion: str
    tamano_fragmento_bytes: int
    max_reintentos_descarga: int
    porcentaje_parcial: int
    id_usuario: int
    fase_rollout: str = FASE_CANARY
    estado_distribucion: str = ESTADO_EN_CURSO
    ventana_inicio: Optional[datetime] = None
    ventana_fin: Optional[datetime] = None
    nivel_bateria_minimo: Optional[Decimal] = None
    id_distribucion_ota: Optional[int] = None
    fecha_creacion: Optional[datetime] = None
    fecha_actualizacion: Optional[datetime] = None

    @property
    def esta_en_curso(self) -> bool:
        return self.estado_distribucion == ESTADO_EN_CURSO

    def parametros_nodo(self) -> dict:
        """Reglas que el nodo aplica al descargar (``parametros`` de ``ota/notify``)."""
        return {
            "modo_distribucion": self.modo_distribucion,
            "tamano_fragmento_bytes": self.tamano_fragmento_bytes,
            "max_reintentos_descarga": self.max_reintentos_descarga,
            "nivel_bateria_minimo": float(self.nivel_bateria_minimo) if self.nivel_bateria_minimo is not None else None,
            "ventana_inicio": self.ventana_inicio.isoformat() if self.ventana_inicio else None,
            "ventana_fin": self.ventana_fin.isoformat() if self.ventana_fin else None,
        }

    def avanzar_a(self, fase: Optional[str], ahora: datetime) -> None:
        """Pasa a ``fase``; sin fase siguiente la distribución queda COMPLETADA."""
        if fase is None:
            self.estado_distribucion = ESTADO_COMPLETADA
        else:
            self.fase_rollout = fase
        self.fecha_actualizacion = ahora

    def detener(self, ahora: datetime) -> None:
        self.estado_distribucion = ESTADO_DETENIDA
        self.fecha_actualizacion = ahora
