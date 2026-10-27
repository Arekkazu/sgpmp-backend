# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-23 | Arekkazu | PR-667: fechas en UTC y día calendario en la zona del usuario (X-Zona-Horaria) |
# | 2026-10-26 | Arekkazu | INC-M03-161-G66 RF-57: contrato del evento externo y reglas como objeto |
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Optional

from pydantic import Field, field_validator, model_validator

from src.shared.base_dto import BaseDTO
from src.shared.fechas import FechaHoraUtc


class ProcesarEventoAlertaDTO(BaseDTO):
    device_id: int = Field(..., gt=0)
    sensor_id: int = Field(..., gt=0)
    serial: str = Field(..., min_length=1, max_length=100)

    tipo_variable: str = Field(..., min_length=2, max_length=50)
    valor: Decimal = Field(...)
    unidad: str = Field(..., min_length=1, max_length=20)
    timestamp_evento: FechaHoraUtc
    estado_dato: str = Field(..., min_length=2, max_length=30)
    severidad_edge: str = Field(..., min_length=2, max_length=20)
    origen_evento: str = Field(..., min_length=2, max_length=20)

    # Trazabilidad: al menos uno debe estar presente
    id_evento_edge_computing: Optional[int] = None
    id_telemetria: Optional[int] = None
    id_paquete_inferencia: Optional[int] = None

    # Texto (Edge: clasificación RF-55) u objeto {id, nombre, ...} (umbral M09 del backend, G57F).
    reglas_activadas: list[str | dict[str, Any]] = Field(default_factory=list)

    # Datos de IA (para PREDICCION_PATOLOGIA o conflictos Edge vs IA)
    tipo_alerta_ia: Optional[str] = None
    severidad_ia: Optional[str] = None
    probabilidad_ia: Optional[Decimal] = Field(default=None, ge=0, le=1)

    correlacion_variables: Optional[dict[str, Any]] = None
    metadata_evento: Optional[dict[str, Any]] = None

    @field_validator('tipo_variable')
    @classmethod
    def normalizar_tipo_variable(cls, v: str) -> str:
        return v.upper().strip()

    @field_validator('estado_dato')
    @classmethod
    def validar_estado_dato(cls, v: str) -> str:
        validos = {'LECTURA_VALIDA', 'FUERA_DE_RANGO', 'ERROR_CALIBRACION'}
        v = v.upper()
        if v not in validos:
            raise ValueError(f"estado_dato debe ser uno de: {', '.join(validos)}")
        return v

    @field_validator('severidad_edge', 'severidad_ia')
    @classmethod
    def validar_severidad(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        validos = {'LEVE', 'MODERADO', 'CRITICO'}
        v = v.upper()
        if v not in validos:
            raise ValueError(f"severidad debe ser uno de: {', '.join(validos)}")
        return v

    @field_validator('origen_evento')
    @classmethod
    def validar_origen(cls, v: str) -> str:
        validos = {'EDGE', 'BACKEND', 'IA'}
        v = v.upper()
        if v not in validos:
            raise ValueError(f"origen_evento debe ser uno de: {', '.join(validos)}")
        return v


#: RF-57 Entradas: los 11 valores del enum, más los códigos de telemetría de M09 que
#: nombran la misma variable (``TEMP_CORPORAL``, I3P-1).
_UNIDADES_POR_VARIABLE: dict[str, set[str]] = {
    "TEMPERATURA_AMBIENTAL": {"°C", "C"},
    "TEMPERATURA_CORPORAL": {"°C", "C"},
    "TEMP_CORPORAL": {"°C", "C"},
    "HUMEDAD_RELATIVA": {"%"},
    "PH_AGUA": {"pH"},
    "NH3": {"ppm"},
    "CO2": {"ppm"},
    "FRECUENCIA_CARDIACA": {"bpm"},
    "FRECUENCIA_RESPIRATORIA": {"rpm"},
    "ACTIVIDAD": {"m/s²", "m/s2", "g"},
    "OXIGENO_DISUELTO": {"mg/L"},
    "TDS": {"µS/cm", "ppm", "mg/L"},
}

#: Holgura de reloj entre el emisor y el servidor antes de tratar la fecha como futura.
_MAX_DESFASE_FUTURO = timedelta(seconds=60)


def _normalizar_unidad(unidad: str) -> str:
    return unidad.strip().replace("º", "°").replace("μ", "µ").lower()


class EventoAlertaExternoDTO(ProcesarEventoAlertaDTO):
    """Evento que llega por ``POST /iot/alertas`` (RF-57 Fase 2 y Entradas).

    El backend arma ``ProcesarEventoAlertaDTO`` directamente para sus propios flujos
    (RF-17 → RF-57, eventos Edge de RF-56), que ya traen datos del catálogo; este
    contrato solo endurece lo que entra desde fuera. Cualquier fallo es 400
    VAL_ENTRADA y queda en la bitácora como ERROR_ESTRUCTURA_EVENTO (E1).
    """

    @field_validator("tipo_variable")
    @classmethod
    def validar_tipo_variable(cls, v: str) -> str:
        if v not in _UNIDADES_POR_VARIABLE:
            raise ValueError(
                "tipo_variable no pertenece al catálogo de RF-57: "
                "TEMPERATURA_AMBIENTAL, HUMEDAD_RELATIVA, PH_AGUA, NH3, CO2, TEMPERATURA_CORPORAL, "
                "FRECUENCIA_CARDIACA, FRECUENCIA_RESPIRATORIA, ACTIVIDAD, OXIGENO_DISUELTO, TDS."
            )
        return v

    @field_validator("timestamp_evento")
    @classmethod
    def validar_no_futuro(cls, v: datetime) -> datetime:
        if v > datetime.now(timezone.utc) + _MAX_DESFASE_FUTURO:
            raise ValueError("timestamp_evento no puede ser futuro.")
        return v

    @model_validator(mode="after")
    def validar_coherencia(self) -> "EventoAlertaExternoDTO":
        permitidas = {_normalizar_unidad(u) for u in _UNIDADES_POR_VARIABLE[self.tipo_variable]}
        if _normalizar_unidad(self.unidad) not in permitidas:
            raise ValueError(
                f"La unidad '{self.unidad}' no corresponde a {self.tipo_variable} "
                f"(se espera {', '.join(sorted(_UNIDADES_POR_VARIABLE[self.tipo_variable]))})."
            )
        # Restricción 4 / CA-15: la alerta debe poder rastrearse hasta el dato que la originó.
        if self.id_evento_edge_computing is None and self.id_telemetria is None and self.id_paquete_inferencia is None:
            raise ValueError(
                "El evento debe referenciar su origen: id_evento_edge_computing, id_telemetria "
                "o id_paquete_inferencia."
            )
        return self
