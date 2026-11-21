# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-31 | Arekkazu | USAB-M03-M04 M3-09/N-06 RF-59: semáforo y % en rango con el umbral de la especie del área |
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional


class UmbralHistoricoPort(ABC):

    @abstractmethod
    def obtener_umbral_vigente(
        self,
        id_variable_ambiental: int,
        id_especie: Optional[int],
        timestamp: datetime,
    ) -> Optional[dict]:
        """Retorna el umbral RF-17 (M09) activo para la especie y variable dadas.

        `timestamp` se mantiene en la firma para cuando M09 exponga vigencia temporal
        (RF-59 Restricción 16); hoy no hay `fecha_inicio_vigencia`/`fecha_fin_vigencia`
        en `umbrales_ambientales`, así que se resuelve contra el umbral con `es_activo=true`.

        Formato del dict: {"id_umbral_ambiental", "umbral_min", "umbral_max", "niveles",
        "version"}. `niveles` es una lista de {"nivel", "limite_inferior", "limite_superior"}.
        Retorna None si no existe umbral configurado o no se pudo resolver la especie
        (semáforo queda GRIS).
        """

    def obtener_umbral_vigente_area(
        self,
        id_variable_ambiental: int,
        id_infraestructura: Optional[int],
        timestamp: datetime,
        id_sensor: Optional[int] = None,
    ) -> Optional[dict]:
        """M3-09 / M3-12 / N-06: umbral de una especie del área cuando la lectura no tiene
        activo vinculado (sensores ambientales de un área). Misma regla que el trigger del
        dashboard para decidir GRIS: sensor → área → especies del área → umbral. Sin
        ``id_infraestructura`` se usa el área del sensor vigente en ``timestamp``.

        Por defecto no resuelve (adaptadores de prueba); el adaptador de M09 sí.
        """
        return None
