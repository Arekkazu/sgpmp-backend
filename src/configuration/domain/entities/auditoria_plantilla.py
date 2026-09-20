"""Entidad de lectura ``AuditoriaPlantilla`` (RF-30 — CU-07 Flujo D).

Fila de solo lectura de ``modulo9.auditorias_plantillas``: registro
append-only de creación y versionado de plantillas de configuración.
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class AuditoriaPlantilla:
    """Snapshot de una operación de auditoría sobre una plantilla.

    Attributes:
        id_auditoria_plantilla: Identidad del registro de auditoría.
        id_plantilla: Plantilla (versión concreta) sobre la que se operó, o
            ``None`` si el intento falló antes de que existiera un id (ej. una
            creación rechazada por nombre duplicado).
        id_usuario: Usuario que ejecutó la operación, o ``None`` si no se pudo
            resolver al momento del registro.
        tipo_operacion: ``"CREATE"`` (crear/versionar), ``"READ"`` (consultar)
            o ``"APPLY"`` (aplicar).
        resultado: ``"EXITOSO"`` o ``"FALLIDO"``.
        valores_anteriores: Estado previo, cuando aplica (ej. versionado).
        valores_nuevos: Snapshot del estado tras la operación, o detalle del
            error cuando ``resultado == "FALLIDO"``.
        fecha_gestion: Marca temporal (UTC) de la operación.
    """

    id_auditoria_plantilla: int
    id_plantilla: Optional[int]
    id_usuario: Optional[int]
    tipo_operacion: str
    resultado: str
    valores_anteriores: Optional[dict[str, Any]]
    valores_nuevos: dict[str, Any]
    fecha_gestion: datetime.datetime
