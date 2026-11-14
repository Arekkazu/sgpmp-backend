# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-28 | Arekkazu | BE-0 RF-55: DTOs para crear y editar reglas de alerta |
"""DTOs de entrada del CRUD de reglas de alerta (``/iot/reglas-alertas``, RF-55/RF-57)."""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal, Optional

from pydantic import Field

from src.shared.base_dto import BaseDTO
from src.shared.fechas import FechaHoraUtc

# Valores de modulo3.enum_reglas_alertas_tipo_sensor y enum_telemetria_categoria_variable.
TipoSensorRegla = Literal["HUMEDAD", "TEMPERATURA", "OXIGENO", "PH", "AMONIACO", "SALINIDAD", "LUMINOSIDAD"]
CategoriaVariable = Literal["AMBIENTAL", "ANIMAL", "HIDRICA"]


class _ReglaAlertaDTO(BaseDTO):
    nombre: str = Field(..., min_length=1, max_length=150)
    descripcion: Optional[str] = None
    tipo_sensor: TipoSensorRegla
    categoria_variable: Optional[CategoriaVariable] = None
    # numeric(10,4) en la BD.
    umbral_min: Optional[Decimal] = Field(default=None, max_digits=10, decimal_places=4)
    umbral_max: Optional[Decimal] = Field(default=None, max_digits=10, decimal_places=4)
    # RF-55.2: parámetros de la fórmula compilada en el firmware (p. ej. THI de ESTRES_TERMICO).
    umbrales_severidad: Optional[dict[str, Any]] = None
    ventana_confirmacion_min: Decimal = Field(..., ge=0, max_digits=10, decimal_places=4)
    lectura_confirmacion_max: Decimal = Field(..., ge=1, max_digits=10, decimal_places=4)
    mensaje: Optional[str] = None
    id_finca: Optional[int] = Field(default=None, gt=0)
    id_especie: Optional[int] = Field(default=None, gt=0)


class CrearReglaAlertaDTO(_ReglaAlertaDTO):
    es_regla_compuesta: bool = False
    # Solo para compuestas: se propaga a los Gateway Edge con REGLA_COMPUESTA (DEV-08).
    tiene_ejecutar_edge: bool = False


class EditarReglaAlertaDTO(_ReglaAlertaDTO):
    """Reemplaza la regla completa. ``es_regla_compuesta`` y ``tiene_ejecutar_edge`` no
    cambian después de crearla: para sacarla del Edge se desactiva.

    ``fecha_actualizacion`` debe ser la leída del registro (concurrencia optimista, 412 si cambió).
    """
    fecha_actualizacion: Optional[FechaHoraUtc] = None

    def campos(self) -> dict[str, Any]:
        return self.model_dump(exclude={"fecha_actualizacion"})
