"""Entidad de dominio ``MetricaProduccion`` — métrica de producción por especie (RF-16)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from src.configuration.domain.value_objects.aplica_tipo_activo import AplicaTipoActivo
from src.configuration.domain.value_objects.nombre_metrica import NombreMetrica
from src.configuration.domain.value_objects.tipo_medicion import TipoMedicion


@dataclass(eq=False)
class MetricaProduccion:
    """Métrica de producción asociada a una especie.

    Attributes:
        nombre: Nombre validado (único por especie, case-insensitive).
        unidad_medida: Unidad coherente con tipo_medicion (FA-10).
        tipo_medicion: Categoría de medición (PESO/VOLUMEN/LONGITUD/CONTEO/OTRO).
        aplica_a_tipo_activo: Scope (INDIVIDUAL/LOTE/AMBOS).
        id_especie: Especie propietaria.
        es_activo: Estado de disponibilidad (M09). ``tiene_estado`` es campo M04 y no se toca.
        id_metrica_produccion: Identidad. ``None`` hasta que se persiste.
        fecha_actualizacion: Timestamp de última modificación (concurrencia optimista).
    """

    nombre: NombreMetrica
    unidad_medida: str
    tipo_medicion: TipoMedicion
    aplica_a_tipo_activo: AplicaTipoActivo
    id_especie: Optional[int]
    es_activo: bool
    id_metrica_produccion: Optional[int] = None
    fecha_actualizacion: Optional[datetime] = None

    @classmethod
    def crear(
        cls,
        *,
        nombre: NombreMetrica,
        unidad_medida: str,
        tipo_medicion: TipoMedicion,
        aplica_a_tipo_activo: AplicaTipoActivo,
        id_especie: Optional[int],
    ) -> MetricaProduccion:
        return cls(
            nombre=nombre,
            unidad_medida=unidad_medida,
            tipo_medicion=tipo_medicion,
            aplica_a_tipo_activo=aplica_a_tipo_activo,
            id_especie=id_especie,
            es_activo=True,
        )

    def actualizar(
        self,
        *,
        nombre: NombreMetrica,
        unidad_medida: str,
        tipo_medicion: TipoMedicion,
        aplica_a_tipo_activo: AplicaTipoActivo,
        fecha_actualizacion: datetime,
    ) -> None:
        self.nombre = nombre
        self.unidad_medida = unidad_medida
        self.tipo_medicion = tipo_medicion
        self.aplica_a_tipo_activo = aplica_a_tipo_activo
        self.fecha_actualizacion = fecha_actualizacion

    def desactivar(self) -> None:
        self.es_activo = False

    def _snapshot(self) -> dict[str, Any]:
        return {
            "id_metrica_produccion": self.id_metrica_produccion,
            "nombre": self.nombre.valor,
            "unidad_medida": self.unidad_medida,
            "tipo_medicion": self.tipo_medicion.value,
            "aplica_a_tipo_activo": self.aplica_a_tipo_activo.value,
            "id_especie": self.id_especie,
            "es_activo": self.es_activo,
            "fecha_actualizacion": self.fecha_actualizacion.isoformat() if self.fecha_actualizacion else None,
        }

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, MetricaProduccion):
            return NotImplemented
        if self.id_metrica_produccion is None or other.id_metrica_produccion is None:
            return self is other
        return self.id_metrica_produccion == other.id_metrica_produccion

    def __hash__(self) -> int:
        return hash(self.id_metrica_produccion)
