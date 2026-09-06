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
        id_plantilla: Plantilla (versión concreta) sobre la que se operó.
        id_usuario: Usuario que ejecutó la operación, o ``None`` si no se pudo
            resolver al momento del registro.
        tipo_operacion: Siempre ``"CREATE"`` — las plantillas son inmutables;
            versionar también crea un registro nuevo, nunca actualiza uno existente.
        valores_anteriores: Siempre ``None`` (no aplica a plantillas inmutables).
        valores_nuevos: Snapshot completo de la plantilla creada/versionada.
        fecha_gestion: Marca temporal (UTC) de la operación.
    """

    id_auditoria_plantilla: int
    id_plantilla: int
    id_usuario: Optional[int]
    tipo_operacion: str
    valores_anteriores: Optional[dict[str, Any]]
    valores_nuevos: dict[str, Any]
    fecha_gestion: datetime.datetime
