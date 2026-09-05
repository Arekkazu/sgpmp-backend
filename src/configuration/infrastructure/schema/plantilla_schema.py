"""Schemas de respuesta para los endpoints de plantillas de configuración (RF-30, RF-31, RF-32)."""
from __future__ import annotations

import datetime
from typing import Any, Optional

from pydantic import BaseModel


class PlantillaResponse(BaseModel):
    """Datos de una plantilla de configuración."""

    id_plantilla: int
    id_especie: int
    id_usuario: int
    template_name: str
    params_snapshot: dict[str, Any]
    version: int
    fecha_creacion: datetime.datetime

    model_config = {"from_attributes": True}


class PlantillasListResponse(BaseModel):
    """Resultado del listado de plantillas disponibles."""

    total: int
    items: list[PlantillaResponse]


class AplicacionPlantillaResponse(BaseModel):
    """Registro de una aplicación de plantilla (RF-32)."""

    id_aplicacion_plantilla: int
    id_plantilla: int
    id_usuario: int
    target_config: dict[str, Any]
    before_snapshot: Optional[dict[str, Any]]
    after_snapshot: Optional[dict[str, Any]]
    fecha_aplicacion: Optional[datetime.datetime]

    model_config = {"from_attributes": True}


class HistorialAplicacionesResponse(BaseModel):
    """Resultado del historial de aplicaciones de plantillas."""

    total: int
    items: list[AplicacionPlantillaResponse]


class AuditoriaPlantillaResponse(BaseModel):
    """Registro de auditoría de creación/versionado de una plantilla (RF-30)."""

    id_auditoria_plantilla: int
    id_plantilla: int
    id_usuario: Optional[int]
    tipo_operacion: str
    valores_anteriores: Optional[dict[str, Any]]
    valores_nuevos: dict[str, Any]
    fecha_gestion: datetime.datetime

    model_config = {"from_attributes": True}


class HistorialAuditoriaPlantillasResponse(BaseModel):
    """Resultado del historial de auditoría de plantillas (CU-07 Flujo D)."""

    total: int
    items: list[AuditoriaPlantillaResponse]


class VersionEsquemaResponse(BaseModel):
    """Una entrada del changelog del esquema de `params_snapshot` (RF-30)."""

    version: int
    fecha: str
    compatible_con: list[int]
    cambios: list[str]


class EsquemaPlantillaResponse(BaseModel):
    """Esquema vigente del `params_snapshot` y su changelog de versiones (RF-30)."""

    schema_version_actual: int
    categorias: list[str]
    #: {categoría: {campo: descripción del tipo esperado}}
    campos_requeridos: dict[str, dict[str, str]]
    #: Forma de cada `umbrales_ambientales[].niveles[]`.
    campos_nivel_alerta: dict[str, str]
    changelog: list[VersionEsquemaResponse]
