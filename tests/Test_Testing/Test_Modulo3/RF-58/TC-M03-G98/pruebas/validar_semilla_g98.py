"""Valida en local valores candidatos RF-57; no acredita recursos de TEST.

Los IDs y el serial son sintéticos. El POST real requiere relaciones públicas
comprobadas, token de servicio y control del efecto de notificación.
"""
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import sys

sys.dont_write_bytecode = True
RAIZ = Path(__file__).resolve().parents[6]
sys.path.insert(0, str(RAIZ))

from src.telemetry.infrastructure.dto.procesar_evento_alerta_dto import EventoAlertaExternoDTO  # noqa: E402
from src.telemetry.domain.entities.reglas_base_rf57 import evaluar_evento, regla_simple  # noqa: E402


def cuerpo(variable: str, valor: str, unidad: str, severidad: str, sensor: int) -> dict:
    return {
        "device_id": sensor,
        "sensor_id": sensor,
        "serial": "SERIAL_SINTETICO_SOLO_LOCAL",
        "tipo_variable": variable,
        "valor": valor,
        "unidad": unidad,
        "timestamp_evento": datetime.now(timezone.utc).isoformat(),
        "estado_dato": "LECTURA_VALIDA",
        "severidad_edge": severidad,
        "origen_evento": "BACKEND",
        "id_telemetria": sensor,
        "reglas_activadas": [regla_simple(variable, Decimal(valor), sensor, sensor)],
    }


# Cada terna corresponde a CRITICO, MODERADO y LEVE, respectivamente.
# La selección real exige sensores distintos y M09 configurado en la misma área.
CANDIDATOS = {
    "TEMPERATURA_AMBIENTAL": ("C", ("10", "16", "19")),
    "HUMEDAD_RELATIVA": ("%", ("20", "35", "45")),
    "PH_AGUA": ("pH", ("5.0", "5.7", "6.2")),
    "NH3": ("ppm", ("50", "38", "28")),
    "CO2": ("ppm", ("4500", "3700", "3200")),
    "TEMPERATURA_CORPORAL": ("C", ("35", "35.7", "36.2")),
    "FRECUENCIA_CARDIACA": ("bpm", ("30", "41", "44")),
    "OXIGENO_DISUELTO": ("mg/L", ("1.5", "2.5", "4")),
    "TDS": ("ppm", ("2200", "1700", "1200")),
}
SEVERIDADES = ("CRITICO", "MODERADO", "LEVE")
for variable, (unidad, valores) in CANDIDATOS.items():
    for indice, (severidad, valor) in enumerate(zip(SEVERIDADES, valores)):
        dto = EventoAlertaExternoDTO.model_validate(
            cuerpo(variable, valor, unidad, severidad, 101 + indice)
        )
        evaluacion = evaluar_evento(dto.tipo_variable, dto.valor, dto.correlacion_variables)
        assert evaluacion.evaluable and evaluacion.severidad == severidad, (variable, severidad)
        assert len(dto.reglas_activadas) == 1
print(f"G98: {len(CANDIDATOS) * 3} modelos DTO/RF-57 válidos; sin red ni recursos TEST")
