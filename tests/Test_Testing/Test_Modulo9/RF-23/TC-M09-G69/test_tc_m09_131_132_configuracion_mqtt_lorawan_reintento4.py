"""
TC-M09-G69 (RF-23, TC-M09-131/132) - Reintento 4 (2026-10-05) - ejecutado contra DEV con cuenta de admin de DEV (credenciales por variable de entorno ADMIN_DEV_EMAIL / ADMIN_DEV_PASSWORD, no se guardan en el archivo).

Contexto: la foto del PR compara dynsec y mTLS para el broker. Con dynsec cada dispositivo tiene su propia credencial y ACL, sin TLS, y se revoca desde el frontend. La parte MQTT de este TC depende de esas credenciales de broker, que aun no estan en el entorno; por eso el viaje MQTT queda omitido.

Numeracion: G69 ya tenia reintento1 (contrato, 2026-09-19) y reintento2 (dispositivo real
en DEV, 2026-09-26), por eso este es reintento3.

Que se puede verificar en TEST y que no:
  * Contrato `protocolo` (TC-M09-132): SI, por HTTP. Se compara la respuesta con y sin el campo.
  * Viaje MQTT con dispositivo real (TC-M09-131): NO en TEST. La Raspberry activa
    (serial TC-M09-G64-1789321890010, id 20 en DEV) NO existe en TEST, y el broker MQTT
    conocido solo corresponde a DEV. Esos casos quedan SKIPPED de forma explicita.

Credenciales: ninguna se escribe en el archivo; el admin de TEST se toma de las variables
publicas del repo (misma cuenta que el resto de colecciones de TEST).

Como correrlo (desde la raiz del repo):
    $env:SGPMP_BASE_URL = "https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test"
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    python -m pytest <ruta>\\test_tc_m09_131_132_configuracion_mqtt_lorawan_reintento3.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M09-G69_reintento3.html --self-contained-html
"""
import os

import httpx
import pytest

API = os.getenv('SGPMP_BASE_URL', 'https://sigab-backenddev-jpuya4-ea3a74-158-69-200-27.sslip.io/api-sgpmp')
ADMIN = {'correo_electronico': os.environ['ADMIN_DEV_EMAIL'], 'contrasena': os.environ['ADMIN_DEV_PASSWORD']}
SERIAL_REAL = 'TC-M09-G64-1789321890010'


@pytest.fixture(scope='module')
def admin():
    r = httpx.post(f'{API}/sesiones/', json=ADMIN, timeout=30)
    assert r.status_code == 200, r.text
    return {'Authorization': f"Bearer {r.json()['token']}"}


def _dispositivo_fresco(admin):
    """Cada caso usa un dispositivo NUEVO: el endpoint responde 409 CONFIG_PENDIENTE_EXISTENTE
    si el dispositivo ya tiene una configuracion pendiente (hallazgo de la corrida previa)."""
    serial = f'QA-G69-R4-{os.urandom(4).hex()}'
    r = httpx.post(f'{API}/configuracion/dispositivos-iot', headers=admin, timeout=30, json={
        'serial': serial, 'descripcion': 'QA TC-M09-G69 reintento3', 'id_infraestructura': 3,
        'id_tipo_dispositivo': 1, 'es_activo': True})
    assert r.status_code == 201, r.text
    return r.json()['id_dispositivo_iot']


def _configurar(admin, id_dispositivo, extra=None):
    body = {'frecuencia_captura': 17, 'intervalo_transmision': 34}
    body.update(extra or {})
    return httpx.post(f'{API}/configuracion/dispositivos-iot/{id_dispositivo}/configurar',
                      json=body, headers=admin, timeout=90)


class TestTCM09132ContratoProtocolo:

    def test_protocolo_lorawan_deberia_reflejarse_o_rechazarse_no_ignorarse(self, admin):
        base = _configurar(admin, _dispositivo_fresco(admin))
        lora = _configurar(admin, _dispositivo_fresco(admin), {'protocolo': 'LoRaWAN'})
        # La ficha espera que LoRaWAN se rechace (400) o se refleje en la respuesta.
        refleja = 'protocolo' in lora.text and 'LoRaWAN' in lora.text
        assert lora.status_code == 400 or refleja, (
            f'protocolo=LoRaWAN se ignoro: sin campo {base.status_code}, con campo {lora.status_code}, '
            f'y la respuesta no lo refleja. El contrato no tiene el campo protocolo (TC-M09-G69 / G128).'
        )

    def test_protocolo_inexistente_deberia_responder_400(self, admin):
        r = _configurar(admin, _dispositivo_fresco(admin), {'protocolo': 'PROTOCOLO_INEXISTENTE'})
        assert r.status_code == 400, f'protocolo inexistente respondio {r.status_code}, se esperaba 400'


class TestTCM09131ViajeMqttDispositivoReal:

    @pytest.mark.skip(reason='La Raspberry activa no existe en TEST (serial TC-M09-G64-1789321890010 solo en DEV) y el broker MQTT no tiene equivalente en TEST.')
    def test_el_dispositivo_real_confirma_hasta_200_aplicada(self):
        pass
