"""Entidad de dominio: umbral ambiental por especie (agregado raíz CU03 RF-17)."""
from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from src.configuration.domain.entities.nivel_alerta_ambiental import NivelAlertaAmbiental

# modulo9.umbrales_ambientales/niveles_alerta_ambientales son NUMERIC(_, 2) — se fija
# la misma escala al serializar para que valores_anteriores/valores_nuevos no varíen
# de representación textual según si el Decimal viene recién parseado del DTO o
# releído de BD (INC-M09-105-G30, observación 2: "42.0" vs "42.00").
_ESCALA_SNAPSHOT = Decimal('0.01')


def _decimal_snapshot(valor: Decimal) -> str:
    return str(valor.quantize(_ESCALA_SNAPSHOT))


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
    # INC-M09-104-G29 (RF-17): estado de la propagación hacia el Nodo Edge.
    # PENDIENTE (recién guardado o broker inalcanzable) / APLICADA (ACK del
    # Edge) / NO_CONF (se publicó pero no hubo ACK a tiempo) — mismo
    # vocabulario que ConfiguracionRemota (RF-23).
    estado_sincronizacion: str = 'PENDIENTE'
    fecha_ultima_sincronizacion: Optional[datetime.datetime] = None
    motivo_fallo_sincronizacion: Optional[str] = None

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

    def marcar_pendiente_sincronizacion(self, motivo: str) -> None:
        self.estado_sincronizacion = 'PENDIENTE'
        self.motivo_fallo_sincronizacion = motivo

    def marcar_sincronizado(self, ts_ahora: datetime.datetime) -> None:
        self.estado_sincronizacion = 'APLICADA'
        self.fecha_ultima_sincronizacion = ts_ahora
        self.motivo_fallo_sincronizacion = None

    def marcar_fallo_sincronizacion(self, motivo: str) -> None:
        self.estado_sincronizacion = 'NO_CONF'
        self.motivo_fallo_sincronizacion = motivo

    def _snapshot(self) -> dict:
        return {
            'id_umbral_ambiental': self.id_umbral_ambiental,
            'id_especie': self.id_especie,
            'id_variable_ambiental': self.id_variable_ambiental,
            'unidad_medida': self.unidad_medida,
            'valor_min': _decimal_snapshot(self.valor_min),
            'valor_max': _decimal_snapshot(self.valor_max),
            'es_activo': self.es_activo,
            'fecha_actualizacion': self.fecha_actualizacion.isoformat() if self.fecha_actualizacion else None,
            'niveles': [
                {
                    'nivel': n.nivel.value,
                    'limite_inferior': _decimal_snapshot(n.limite_inferior),
                    'limite_superior': _decimal_snapshot(n.limite_superior),
                }
                for n in self.niveles
            ],
        }
