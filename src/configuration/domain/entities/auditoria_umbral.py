"""Entidad de lectura ``AuditoriaUmbral`` (RF-17 — CU-03).

Fila de solo lectura de ``modulo9.auditorias_umbrales_ambientales``: registro
append-only de creación, edición y desactivación de umbrales ambientales.
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class AuditoriaUmbral:
    """Snapshot de una operación de auditoría sobre un umbral ambiental.

    Attributes:
        id_auditoria_umbral: Identidad del registro de auditoría.
        id_umbral_ambiental: Umbral sobre el que se operó.
        id_usuario: Usuario que ejecutó la operación, o ``None`` si no se pudo
            resolver al momento del registro.
        tipo_operacion: ``"CREATE"``, ``"UPDATE"`` o ``"DEACTIVATE"``.
        valores_anteriores: Estado previo (``None`` en creación).
        valores_nuevos: Snapshot del estado tras la operación.
        fecha_gestion: Marca temporal (UTC) de la operación.
    """

    id_auditoria_umbral: int
    id_umbral_ambiental: int
    id_usuario: Optional[int]
    tipo_operacion: str
    valores_anteriores: Optional[dict[str, Any]]
    valores_nuevos: dict[str, Any]
    fecha_gestion: datetime.datetime
