# | Fecha      | Nombre | Que se hizo |
# |------------|--------|-------------|
# | 2026-10-31 | Claude | INC-M03-246-G88 RF-58: tolerancia T del semáforo configurable en el umbral |
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


# RF-58 Fase 3: T por defecto cuando el umbral no la configura (10 % del rango).
TOLERANCIA_SEMAFORO_DEFECTO_PCT = Decimal('0.10')

MOTIVO_CAMBIOS_SIN_PROPAGAR = "Cambios guardados, pendientes de propagar al Nodo Edge."


@dataclass(eq=False)
class UmbralAmbiental:
    """Umbral de una variable ambiental para una especie, con sus niveles normal / precaución / crítico (RF-17).

    Lleva además el estado de sincronización hacia los dispositivos Edge.
    """
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
    # INC-M03-246-G88 (RF-58 Fase 3): tolerancia T del semáforo en la unidad del umbral.
    # None = valor por defecto (10 % del rango), lo que se aplicaba antes de que fuera configurable.
    tolerancia_semaforo: Optional[Decimal] = None

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
        tolerancia_semaforo: Optional[Decimal] = None,
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
            tolerancia_semaforo=tolerancia_semaforo,
        )

    def actualizar(
        self,
        valor_min: Decimal,
        valor_max: Decimal,
        niveles: list[NivelAlertaAmbiental],
        id_usuario: int,
        ts_ahora: datetime.datetime,
        tolerancia_semaforo: Optional[Decimal] = None,
    ) -> None:
        self.valor_min = valor_min
        self.valor_max = valor_max
        self.niveles = niveles
        self.tolerancia_semaforo = tolerancia_semaforo
        self.id_usuario = id_usuario
        self.fecha_actualizacion = ts_ahora
        # INC-M09-104-G29: los valores nuevos todavía no llegaron al Edge. Si la
        # propagación posterior no alcanza a persistir su resultado, el umbral
        # no debe quedar mostrando el APLICADA de la versión anterior.
        self.marcar_pendiente_sincronizacion(MOTIVO_CAMBIOS_SIN_PROPAGAR)

    @property
    def tolerancia_semaforo_efectiva(self) -> Decimal:
        """T que aplica el semáforo RF-58: la configurada o el 10 % del rango."""
        if self.tolerancia_semaforo is not None:
            return self.tolerancia_semaforo
        return ((self.valor_max - self.valor_min) * TOLERANCIA_SEMAFORO_DEFECTO_PCT).quantize(_ESCALA_SNAPSHOT)

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
            'tolerancia_semaforo': (
                _decimal_snapshot(self.tolerancia_semaforo) if self.tolerancia_semaforo is not None else None
            ),
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
