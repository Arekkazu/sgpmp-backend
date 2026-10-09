"""Entidades de la calibración por visión (RF-24 v2.0, RFC-011).

- ``CalibracionVision``: un intento de cálculo de línea base, exitoso o no
  (`modulo9.calibraciones_vision`). Es historial inmutable.
- ``LineaBaseVision``: la línea base vigente de un par (área, especie)
  (`modulo9.lineas_base_vision`). Solo la publica una calibración exitosa.
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import Optional

from src.configuration.domain.entities.linea_base_vision import ResultadoLineaBase
from src.configuration.domain.value_objects.calibracion_vision import (
    EstadoCalibracionVision,
    EtapaCalibracionVision,
    OrigenDisparo,
)


@dataclass(eq=False)
class CalibracionVision:
    """Un intento de cálculo de línea base por visión para un par (área, especie),
    exitoso o fallido.
    """
    id_infraestructura: int
    id_especie: int
    origen_disparo: OrigenDisparo
    id_usuario: Optional[int]
    ventana_observacion: dict
    fecha_calibracion: datetime.datetime
    estado: EstadoCalibracionVision
    n_observaciones: int
    n_observaciones_validas: int
    etapa_fallo: Optional[EtapaCalibracionVision] = None
    motivo: Optional[str] = None
    # {"valores": {componente: mediana}, "componentes_no_calibrables": [...]}; solo si EXITOSA.
    linea_base: Optional[dict] = None
    iteraciones: Optional[int] = None
    observaciones: Optional[str] = None
    id_calibracion_vision: Optional[int] = None
    fecha_creacion: Optional[datetime.datetime] = None

    @classmethod
    def desde_resultado(
        cls,
        resultado: ResultadoLineaBase,
        *,
        id_infraestructura: int,
        id_especie: int,
        origen_disparo: OrigenDisparo,
        id_usuario: Optional[int],
        ventana_observacion: dict,
        fecha_calibracion: datetime.datetime,
        observaciones: Optional[str] = None,
    ) -> "CalibracionVision":
        linea_base = None
        if resultado.es_exitosa:
            linea_base = {
                "valores": resultado.valores,
                "componentes_no_calibrables": resultado.componentes_no_calibrables,
            }
        return cls(
            id_infraestructura=id_infraestructura,
            id_especie=id_especie,
            origen_disparo=origen_disparo,
            id_usuario=id_usuario,
            ventana_observacion=ventana_observacion,
            fecha_calibracion=fecha_calibracion,
            estado=resultado.estado,
            n_observaciones=resultado.n_observaciones,
            n_observaciones_validas=resultado.n_observaciones_validas,
            etapa_fallo=resultado.etapa_fallo,
            motivo=resultado.motivo,
            linea_base=linea_base,
            iteraciones=resultado.iteraciones,
            observaciones=observaciones,
        )

    @property
    def es_exitosa(self) -> bool:
        return self.estado == EstadoCalibracionVision.EXITOSA

    def _snapshot(self) -> dict:
        return {
            "id_calibracion_vision": self.id_calibracion_vision,
            "id_infraestructura": self.id_infraestructura,
            "id_especie": self.id_especie,
            "origen_disparo": self.origen_disparo.value,
            "ventana_observacion": self.ventana_observacion,
            "estado": self.estado.value,
            "etapa_fallo": self.etapa_fallo.value if self.etapa_fallo else None,
            "motivo": self.motivo,
            "linea_base": self.linea_base,
            "n_observaciones": self.n_observaciones,
            "n_observaciones_validas": self.n_observaciones_validas,
            "iteraciones": self.iteraciones,
        }


@dataclass(eq=False)
class LineaBaseVision:
    """Línea base vigente de un par (área, especie): la última calibración por visión
    exitosa.
    """
    id_infraestructura: int
    id_especie: int
    id_calibracion_vision: int
    valor: dict = field(default_factory=dict)
    fecha_publicacion: Optional[datetime.datetime] = None
