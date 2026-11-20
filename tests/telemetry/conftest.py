# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-19 | Arekkazu | SEG-M03-01 RF-63: cada prueba empieza sin eventos de auditoría pendientes de reintento |
"""La cola de reintentos de la auditoría IoT es del proceso: sin limpiarla, un evento fallido de una
prueba se guardaría en la bitácora falsa de la siguiente."""
import pytest

from src.telemetry.application.use_cases.auditoria import registrar_evento_auditoria_iot_use_case as auditoria


@pytest.fixture(autouse=True)
def _sin_pendientes_de_auditoria():
    auditoria._PENDIENTES.clear()
    yield
    auditoria._PENDIENTES.clear()
