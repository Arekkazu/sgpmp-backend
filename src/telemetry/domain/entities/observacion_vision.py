# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-23 | Arekkazu | INTEG RFC-012..016 RF-53: catálogo de calibración de DB-09 con alias del sobre D4 |
# | 2026-10-25 | Arekkazu | INC-M03-134-G192 RF-62: calidad ponderada evaluada después de la ingesta |
"""Entidad ``ObservacionVision`` — vector de comportamiento de un área (RF-53/RF-56/RF-62 v2.0, RFC-011).

La cámara (Edge de visión) envía por ventana un vector estructurado del área y
los indicadores de calidad de la ventana. La ingesta guarda la observación sin
evaluar; RF-62 la evalúa después, de forma asíncrona (worker post-commit o
``POST /iot/calidad/vision/{id}/evaluar``), con el índice ponderado de
AIOT-SPEC-01 (``calidad_vision.evaluar_calidad_vision``). Mientras no se evalúa,
``es_apto_para_ia`` es None y RF-24 no la consume (INC-M03-134-G192).
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Optional

from src.telemetry.domain.entities.calidad_vision import (
    ClaseCalidadVision,
    EstadoCalibracionVision,
    ParametrosCalidadVision,
    ResultadoCalidadVision,
    evaluar_calidad_vision,
)


class EstadoCalibracionCamara(str, Enum):
    # RF-60 v2.0: "cámara con señal pero sin detección válida" (turbidez,
    # oclusión, baja luz) no es fallo del dispositivo sino calidad.
    # DB-09 (be29f17bb7fc) cambió el catálogo SQL a CALIBRADO/EN_CALIBRACION/
    # SIN_LINEA_BASE: los valores se persisten así y los nombres viejos del sobre
    # D4 se siguen aceptando como alias, para no romper al broker ni al Edge.
    CALIBRADA = 'CALIBRADO'
    DEGRADADA = 'EN_CALIBRACION'
    SIN_DETECCION = 'SIN_LINEA_BASE'

    @classmethod
    def _missing_(cls, valor):
        return {'CALIBRADA': cls.CALIBRADA, 'DEGRADADA': cls.DEGRADADA,
                'SIN_DETECCION': cls.SIN_DETECCION}.get(valor)


@dataclass
class ObservacionVision:
    id_observacion_vision: Optional[int]
    id_dispositivo_iot: int
    id_infraestructura: int
    fecha_observacion: datetime.datetime
    cobertura_ventana: Decimal
    cantidad_tracks: Optional[int]
    cantidad_tracks_perdidos: int
    fps_efectivo: Decimal
    estado_calibracion: EstadoCalibracionCamara
    vector: dict[str, float]
    fecha_inicio_ventana: Optional[datetime.datetime] = None
    version_cascada: Optional[dict[str, str]] = None
    n_individuos_observados: Optional[int] = None
    origen: Optional[str] = None
    # RF-62: None hasta que se evalúa.
    indice_calidad_vision: Optional[Decimal] = None
    clasificacion_calidad: Optional[ClaseCalidadVision] = None
    es_apto_para_ia: Optional[bool] = None
    es_confianza_baja: Optional[bool] = None
    flags_detectados: Optional[dict] = None
    fecha_evaluacion_calidad: Optional[datetime.datetime] = None

    # RF-62 v2.0: un vector de comportamiento no es evidencia contable; M06
    # (NIC 41) nunca debe recibirlo como apto.
    es_apto_para_nic41 = False

    @property
    def esta_evaluada(self) -> bool:
        return self.fecha_evaluacion_calidad is not None

    @classmethod
    def crear(
        cls,
        *,
        id_dispositivo_iot: int,
        id_infraestructura: int,
        fecha_observacion: datetime.datetime,
        cobertura_ventana: Decimal,
        cantidad_tracks: Optional[int],
        cantidad_tracks_perdidos: int,
        fps_efectivo: Decimal,
        estado_calibracion: EstadoCalibracionCamara,
        vector: dict[str, float],
        fecha_inicio_ventana: Optional[datetime.datetime] = None,
        version_cascada: Optional[dict[str, str]] = None,
        n_individuos_observados: Optional[int] = None,
        origen: Optional[str] = None,
    ) -> "ObservacionVision":
        return cls(
            id_observacion_vision=None,
            id_dispositivo_iot=id_dispositivo_iot,
            id_infraestructura=id_infraestructura,
            fecha_observacion=fecha_observacion,
            cobertura_ventana=cobertura_ventana,
            cantidad_tracks=cantidad_tracks,
            cantidad_tracks_perdidos=cantidad_tracks_perdidos,
            fps_efectivo=fps_efectivo,
            estado_calibracion=EstadoCalibracionCamara(estado_calibracion),
            vector=vector,
            fecha_inicio_ventana=fecha_inicio_ventana,
            version_cascada=version_cascada,
            n_individuos_observados=n_individuos_observados,
            origen=origen,
        )

    def evaluar(
        self,
        parametros: ParametrosCalidadVision,
        *,
        duracion_seg: Decimal,
        ahora: datetime.datetime,
    ) -> ResultadoCalidadVision:
        """Aplica RF-62 (AIOT-SPEC-01) y guarda el resultado en la observación."""
        resultado = evaluar_calidad_vision(
            cobertura=self.cobertura_ventana,
            fps=self.fps_efectivo,
            perdidos=self.cantidad_tracks_perdidos,
            calibracion=EstadoCalibracionVision(self.estado_calibracion.value),
            parametros=parametros,
            duracion_seg=duracion_seg,
        )
        self.indice_calidad_vision = resultado.indice
        self.clasificacion_calidad = resultado.clase
        self.es_apto_para_ia = resultado.apto_para_ia
        self.es_confianza_baja = resultado.confianza_baja
        self.flags_detectados = resultado.flags_detectados
        self.fecha_evaluacion_calidad = ahora
        return resultado
