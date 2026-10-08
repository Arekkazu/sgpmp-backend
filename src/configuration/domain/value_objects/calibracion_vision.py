"""Value objects de la calibración por visión (RF-24 v2.0, RFC-011)."""
from __future__ import annotations

from enum import Enum


class OrigenDisparo(str, Enum):
    MANUAL = "MANUAL"            # Ingeniero de campo / Administrador
    AUTOMATICO = "AUTOMATICO"    # Módulo 02: nuevo lote / fin de ciclo


class EstadoCalibracionVision(str, Enum):
    EXITOSA = "EXITOSA"
    FALLIDA = "FALLIDA"
    NO_CONVERGIDA = "NO_CONVERGIDA"


class EtapaCalibracionVision(str, Enum):
    """Las tres etapas de auditoría automática, en el orden en que corren."""
    FILTRADO = "FILTRADO"          # Etapa 1 — filtrado ambiental
    RECORTE = "RECORTE"            # Etapa 2 — recorte p5/p95
    REFINAMIENTO = "REFINAMIENTO"  # Etapa 3 — refinamiento iterativo
