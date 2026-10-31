# | Fecha      | Nombre | Que se hizo |
# |------------|--------|-------------|
# | 2026-10-31 | Claude | INC-M03-232-G02 RF-53: lectura con checksum que no corresponde no se guarda (HTTP real) |
"""INC-M03-232-G02 (#873, TC-M03-007) por HTTP y PostgreSQL real: la lectura de 25.0 con su
checksum entra; la misma lectura cambiada a 26.0 con el checksum original responde 400, queda
en la bitácora de ingesta como ERROR_ESTRUCTURA y no se guarda. Corregido en 1c9af6f (rc.16).
"""
import pytest
from sqlalchemy import text

from src.telemetry.infrastructure.dto.ingerir_telemetria_dto import checksum_lectura
from tests.integration.test_inc_m03_132_g30_reloj import equipo_g30, payload, rutas_g30  # noqa: F401

pytestmark = pytest.mark.integration


def _con_checksum(lectura):
    return lectura | {'checksum': checksum_lectura(lectura)}


def test_lectura_alterada_con_checksum_original_se_rechaza_y_no_se_guarda(client, db_session, equipo_g30, headers_broker):
    e = equipo_g30
    original = _con_checksum(payload(e, valor=25.0, origen='TIEMPO_REAL'))
    ok = client.post('/iot/telemetria', json=original, headers=headers_broker)
    assert ok.status_code == 201, ok.text

    alterada = original | {'valor': 26.0, 'timestamp_captura': e['captura'].replace(second=0).isoformat()}
    r = client.post('/iot/telemetria', json=alterada, headers=headers_broker)

    assert r.status_code == 400, r.text
    assert 'checksum' in r.text, r.text
    valores = db_session.execute(text('SELECT valor_crudo FROM modulo3.telemetrias WHERE id_sensor=:s'),
                                 {'s': e['sensor']}).scalars().all()
    assert [float(v) for v in valores] == [25.0]
    # La bitácora de ingesta (ERROR_ESTRUCTURA) la escribe RutaIngestaAuditada en su propia
    # sesión, fuera de la transacción de la prueba: aquí no es visible (su FK al sensor de la
    # prueba no existe para esa conexión). La cubre tests/integration/test_dev40_catalogo_rechazos.py.
