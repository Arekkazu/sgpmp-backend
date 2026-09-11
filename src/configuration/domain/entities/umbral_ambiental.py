"""Entidad de dominio: umbral ambiental por especie (agregado raíz CU03 RF-17)."""
from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from src.configuration.domain.entities.nivel_alerta_ambiental import NivelAlertaAmbiental


@dataclass(eq=False)
class UmbralAmbiental:
    id_especie: int
    id_variable_ambiental: int
    unidad_medida: str
    valor_min: Decimal
    valor_max: Decimal
    es_activo: bool
    niveles: list[NivelAlertaAmbiental] = field(default_factory=list)
    id_umbral_ambiental: Optional[int] = None
    fecha_actualizacion: Optional[datetime.datetime] = None
    id_usuario: Optional[int] = None

    @classmethod
    def crear(
        cls,
        id_especie: int,
        id_variable_ambiental: int,
        unidad_medida: str,
        valor_min: Decimal,
        valor_max: Decimal,
        niveles: list[NivelAlertaAmbiental],
        id_usuario: int,
    ) -> 'UmbralAmbiental':
        return cls(
            id_especie=id_especie,
            id_variable_ambiental=id_variable_ambiental,
            unidad_medida=unidad_medida,
            valor_min=valor_min,
            valor_max=valor_max,
            es_activo=True,
            niveles=niveles,
            id_usuario=id_usuario,
        )

    def actualizar(
        self,
        valor_min: Decimal,
        valor_max: Decimal,
        niveles: list[NivelAlertaAmbiental],
        id_usuario: int,
        ts_ahora: datetime.datetime,
    ) -> None:
        self.valor_min = valor_min
        self.valor_max = valor_max
        self.niveles = niveles
        self.id_usuario = id_usuario
        self.fecha_actualizacion = ts_ahora

    def desactivar(self) -> None:
        self.es_activo = False

    def _snapshot(self) -> dict:
        return {
            'id_umbral_ambiental': self.id_umbral_ambiental,
            'id_especie': self.id_especie,
            'id_variable_ambiental': self.id_variable_ambiental,
            'unidad_medida': self.unidad_medida,
            'valor_min': str(self.valor_min),
            'valor_max': str(self.valor_max),
            'es_activo': self.es_activo,
            'fecha_actualizacion': self.fecha_actualizacion.isoformat() if self.fecha_actualizacion else None,
            'niveles': [
                {
                    'nivel': n.nivel.value,
                    'limite_inferior': str(n.limite_inferior),
                    'limite_superior': str(n.limite_superior),
                }
                for n in self.niveles
            ],
        }
