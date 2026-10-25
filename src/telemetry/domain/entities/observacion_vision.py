# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-23 | Arekkazu | INTEG RFC-012..016 RF-53: catálogo de calibración de DB-09 con alias del sobre D4 |
"""Entidad ``ObservacionVision`` — vector de comportamiento de un área (RF-53/RF-56/RF-62 v2.0, RFC-011).

La cámara (Edge de visión) envía por ventana un vector estructurado del área y
las dimensiones de calidad de la ventana. M03 calcula su índice de calidad
propio y ``apto_para_ia`` con la misma regla de tres tramos (80/40) de RF-62.

Compatibilidad INC-M09-77-G137 (#513): este cálculo heredado usa pesos iguales
y el catálogo de calibración (hoy CALIBRADO/EN_CALIBRACION/SIN_LINEA_BASE, DB-09). Los RF actualizados ya
definen AIOT-SPEC-01 (fórmula ponderada y otros estados); su adopción requiere
alinear catálogo, metadata y configuración M09. DEV-07 preserva este cálculo
sin presentarlo como implementación de esa fórmula posterior.
"""
from __future__ import annotations

import datetime
import math
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Optional

from src.telemetry.domain.entities.telemetria_calidad import (
    ClasificacionCalidad,
    clasificar_desde_indice,
    derivar_aptitud,
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


_PUNTAJE_ESTADO = {
    EstadoCalibracionCamara.CALIBRADA: 100,
    EstadoCalibracionCamara.DEGRADADA: 50,
    EstadoCalibracionCamara.SIN_DETECCION: 0,
}


def calcular_indice_calidad_vision(
    *,
    cobertura_ventana: Decimal,
    cantidad_tracks: int,
    cantidad_tracks_perdidos: int,
    fps_efectivo: Decimal,
    fps_nominal: Optional[int],
    estado_calibracion: EstadoCalibracionCamara,
) -> int:
    """Índice 0-100: promedio de las cuatro dimensiones de RF-62 v2.0, cada una en 0-100.

    Compatibilidad heredada; no es la fórmula ponderada de AIOT-SPEC-01.
    """
    total_tracks = cantidad_tracks + cantidad_tracks_perdidos
    # Sin fps nominal registrado en RF-21 no hay contra qué medir la caída.
    fps = 1.0 if not fps_nominal else min(float(fps_efectivo) / fps_nominal, 1.0)
    dimensiones = (
        float(cobertura_ventana) * 100,
        (cantidad_tracks / total_tracks * 100) if total_tracks else 0.0,
        fps * 100,
        _PUNTAJE_ESTADO[estado_calibracion],
    )
    # Mitad hacia arriba: round() de Python lleva 96.5 a 96 (al par).
    return math.floor(sum(dimensiones) / len(dimensiones) + 0.5)


@dataclass
class ObservacionVision:
    id_observacion_vision: Optional[int]
    id_dispositivo_iot: int
    id_infraestructura: int
    fecha_observacion: datetime.datetime
    cobertura_ventana: Decimal
    cantidad_tracks: int
    cantidad_tracks_perdidos: int
    fps_efectivo: Decimal
    estado_calibracion: EstadoCalibracionCamara
    vector: dict[str, float]
    indice_calidad: int
    clasificacion_calidad: ClasificacionCalidad
    es_apto_para_ia: bool
    fecha_inicio_ventana: Optional[datetime.datetime] = None
    version_cascada: Optional[dict[str, str]] = None

    # RF-62 v2.0: un vector de comportamiento no es evidencia contable; M06
    # (NIC 41) nunca debe recibirlo como apto.
    es_apto_para_nic41 = False

    @classmethod
    def crear(
        cls,
        *,
        id_dispositivo_iot: int,
        id_infraestructura: int,
        fecha_observacion: datetime.datetime,
        cobertura_ventana: Decimal,
        cantidad_tracks: int,
        cantidad_tracks_perdidos: int,
        fps_efectivo: Decimal,
        fps_nominal: Optional[int],
        estado_calibracion: EstadoCalibracionCamara,
        vector: dict[str, float],
        fecha_inicio_ventana: Optional[datetime.datetime] = None,
        version_cascada: Optional[dict[str, str]] = None,
    ) -> "ObservacionVision":
        indice = calcular_indice_calidad_vision(
            cobertura_ventana=cobertura_ventana,
            cantidad_tracks=cantidad_tracks,
            cantidad_tracks_perdidos=cantidad_tracks_perdidos,
            fps_efectivo=fps_efectivo,
            fps_nominal=fps_nominal,
            estado_calibracion=estado_calibracion,
        )
        clasificacion = clasificar_desde_indice(indice)
        return cls(
            id_observacion_vision=None,
            id_dispositivo_iot=id_dispositivo_iot,
            id_infraestructura=id_infraestructura,
            fecha_observacion=fecha_observacion,
            cobertura_ventana=cobertura_ventana,
            cantidad_tracks=cantidad_tracks,
            cantidad_tracks_perdidos=cantidad_tracks_perdidos,
            fps_efectivo=fps_efectivo,
            estado_calibracion=estado_calibracion,
            vector=vector,
            indice_calidad=indice,
            clasificacion_calidad=clasificacion,
            es_apto_para_ia=derivar_aptitud(clasificacion)[0],
            fecha_inicio_ventana=fecha_inicio_ventana,
            version_cascada=version_cascada,
        )
