# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-31 | Arekkazu | USAB-M03-M04 M4-02 RF-64: variables que admite una patología |
from __future__ import annotations

from abc import ABC, abstractmethod

# RF-64 (descripción): las patologías solo se definen sobre estas 11 variables, por su
# código de telemetría en modulo9.variables_ambientales. Turbidez, Salinidad, Nitrito,
# Amoniaco total y Temperatura del agua están en I3P-1 pero no en esta lista (M4-02).
CODIGOS_VARIABLES_PATOLOGIA = frozenset({
    "TEMPERATURA_AMBIENTAL", "HUMEDAD_RELATIVA", "PH_AGUA", "NH3", "CO2",
    "TEMP_CORPORAL", "FRECUENCIA_CARDIACA", "FRECUENCIA_RESPIRATORIA", "ACTIVIDAD",
    "OXIGENO_DISUELTO", "TDS",
})


class VariableI3P1Port(ABC):
    @abstractmethod
    def obtener_ids_activos(self, ids: list[int]) -> list[int]:
        """Devuelve los ids que existen y están activos en el catálogo I3P-1."""
        ...

    def obtener_ids_para_patologia(self, ids: list[int]) -> list[int]:
        """Los ids activos que además están entre las variables del RF-64.

        Por defecto no restringe (adaptadores de prueba); el adaptador de M09 filtra
        por ``CODIGOS_VARIABLES_PATOLOGIA``.
        """
        return self.obtener_ids_activos(ids)
