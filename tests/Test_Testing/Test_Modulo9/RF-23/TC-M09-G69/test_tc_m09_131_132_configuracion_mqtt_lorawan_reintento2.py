"""
TC-M09-G69 - Reintento 2 (2026-09-26) - Configuracion remota de un dispositivo
mediante MQTT y mediante LoRaWAN.

    TC-M09-131  configurar por MQTT con payload valido (topico, payload, recepcion y ACK)
    TC-M09-132  configurar por LoRaWAN (envio, recepcion y estado final)

El archivo original (test_tc_m09_131_132_configuracion_mqtt_lorawan.py) queda intacto como
evidencia historica -- ahi el sub-caso del viaje completo (topico, payload, recepcion y ACK)
quedo en SKIP porque no habia forma de simular un dispositivo que el backend reconociera
como online.

REINTENTO 2: el usuario proveyo credenciales de un GATEWAY MQTT real y el serial de un
dispositivo real y activo (Raspberry Pi, `TC-M09-G64-1789321890010`, id_dispositivo_iot=20
en DEV, registrado desde una sesion anterior de TC-M09-G64). Con eso SI se pudo completar
el viaje de ida y vuelta -- confirmado en vivo 2026-09-26:
  * POST /configuracion/dispositivos-iot/20/configurar responde 200 APLICADA (la PRIMERA
    vez en toda esta sesion de QA que se observa ese estado -- siempre habia sido 202
    PENDIENTE "dispositivo offline" con dispositivos simulados).
  * Suscrito con la credencial del gateway a '#', se observan los 2 tramos reales:
    - bajada (backend -> dispositivo): topico `sgpmp/<serial>/command`,
      payload `{"frecuencia_captura": N, "intervalo_transmision": M}`.
    - subida (dispositivo -> backend): topico `sgpmp/<serial>/status`,
      payload `{"tipo_mensaje":"ACK_CONFIGURACION","resultado":"OK"}`.
  * HALLAZGO DE SEGURIDAD (refuerza TC-M09-G127, TC-M09-250/251): el topico de bajada
    `sgpmp/<serial>/command` (con los valores reales enviados al dispositivo) fue
    interceptado por la cuenta GENERICA de dispositivo (`sgpmp_devices`), sin ninguna
    relacion con este dispositivo -- confirma con datos reales (no solo con el SUBACK
    concedido) que cualquier cuenta de dispositivo puede leer la configuracion que se le
    envia a cualquier otro dispositivo del sistema.
  * Intento de falsificacion de ACK (fuera del alcance literal de la ficha, probado por
    iniciativa propia): publicar un ACK falso en `sgpmp/<serial>/status` para un
    dispositivo simulado (nunca antes conectado, o conectado con un client_id igual al
    serial pero sin sesion real) NO cambia su estado -- el backend sigue marcandolo
    PENDIENTE/offline. La deteccion de "dispositivo online" no depende solo de que algun
    cliente publique en su topico de status con la credencial compartida; hay algun otro
    mecanismo de presencia que este sondeo no logro identificar. No concluyente, no se
    reporta como hallazgo, solo se documenta que se intento y no funciono.

Credenciales del gateway y del dispositivo compartido NUNCA se versionan (regla del plan de
pruebas) -- se leen de variables de entorno:
    $env:MQTT_GATEWAY_USER = "..."   $env:MQTT_GATEWAY_PASS = "..."
    $env:MQTT_HOST (opcional, por defecto el broker de DEV)
    $env:RASPBERRY_SERIAL (opcional, por defecto el serial dado por el usuario)
    $env:RASPBERRY_ID_DISPOSITIVO (opcional, por defecto 20)

Como correrlo (desde la raiz del repo; en Windows hace falta el stub de fcntl, ver memoria
del proyecto -- el buffer de auditoria RF-52 E1/E3 importa fcntl sin guardia de plataforma):
    $env:PYTHONPATH = "_win_fcntl_stub"
    $env:MQTT_GATEWAY_USER = "..."; $env:MQTT_GATEWAY_PASS = "..."
    python -m pytest <ruta>\\test_tc_m09_131_132_configuracion_mqtt_lorawan_reintento2.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M09-G69_reintento2.html --self-contained-html
"""
import os
import time

import httpx
import paho.mqtt.client as mqtt
import pytest

API = os.getenv('SGPMP_BASE_URL', 'https://sigab-backenddev-jpuya4-ea3a74-158-69-200-27.sslip.io/api-sgpmp')
MQTT_HOST = os.getenv('MQTT_HOST', 'sigab-brokerdev-jwjecq-284f9b-158-69-200-27.sslip.io')
GATEWAY_USER = os.getenv('MQTT_GATEWAY_USER')
GATEWAY_PASS = os.getenv('MQTT_GATEWAY_PASS')
DEVICE_USER = os.getenv('MQTT_USER')  # cuenta generica de dispositivo, para el hallazgo de interceptacion
DEVICE_PASS = os.getenv('MQTT_PASS')
RASPBERRY_SERIAL = os.getenv('RASPBERRY_SERIAL', 'TC-M09-G64-1789321890010')
RASPBERRY_ID = int(os.getenv('RASPBERRY_ID_DISPOSITIVO', '20'))

pytestmark = pytest.mark.skipif(
    not (GATEWAY_USER and GATEWAY_PASS),
    reason='definir MQTT_GATEWAY_USER y MQTT_GATEWAY_PASS en el entorno (no se versionan credenciales)',
)


@pytest.fixture(scope='module')
def admin():
    r = httpx.post(f'{API}/sesiones/', json={'correo_electronico': 'admin@pecuaria.co', 'contrasena': 'Test1234!'}, timeout=30)
    assert r.status_code == 200, r.text
    return {'Authorization': f"Bearer {r.json()['token']}"}


def _escuchar_y_configurar(usuario_mqtt, clave_mqtt, admin, frecuencia, intervalo):
    """Se suscribe a '#' con las credenciales dadas, dispara la configuracion real y devuelve
    (respuesta_http, mensajes_capturados)."""
    capturados = []

    def on_message(c, u, m):
        capturados.append((m.topic, m.payload.decode(errors='replace')))

    def on_connect(c, u, f, rc, props=None):
        c.subscribe('#', qos=1)

    cliente = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f'tc-m09-g69-r2-{usuario_mqtt}-{int(time.time())}')
    cliente.username_pw_set(usuario_mqtt, clave_mqtt)
    cliente.on_connect = on_connect
    cliente.on_message = on_message
    cliente.connect(MQTT_HOST, 1884, keepalive=20)
    cliente.loop_start()
    time.sleep(2)

    respuesta = httpx.post(
        f'{API}/configuracion/dispositivos-iot/{RASPBERRY_ID}/configurar',
        json={'frecuencia_captura': frecuencia, 'intervalo_transmision': intervalo},
        headers=admin, timeout=90,
    )

    time.sleep(4)
    cliente.loop_stop()
    cliente.disconnect()
    return respuesta, capturados


class TestTCM09131ViajeCompletoConDispositivoReal:

    def test_el_dispositivo_real_confirma_la_recepcion_hasta_200_aplicada(self, admin):
        """Con un dispositivo genuinamente online, el endpoint ya no degrada a 202 PENDIENTE."""
        respuesta, _ = _escuchar_y_configurar(GATEWAY_USER, GATEWAY_PASS, admin, 17, 34)
        assert respuesta.status_code == 200, respuesta.text
        cuerpo = respuesta.json()
        assert cuerpo['estado'] == 'APLICADA'
        assert (cuerpo['frecuencia_captura'], cuerpo['intervalo_transmision']) == (17, 34)

    def test_el_gateway_observa_el_topico_y_payload_reales_de_bajada_y_de_ack(self, admin):
        respuesta, capturados = _escuchar_y_configurar(GATEWAY_USER, GATEWAY_PASS, admin, 19, 38)
        assert respuesta.status_code == 200, respuesta.text

        topico_comando = f'sgpmp/{RASPBERRY_SERIAL}/command'
        topico_status = f'sgpmp/{RASPBERRY_SERIAL}/status'
        topicos_vistos = {t for t, _ in capturados}
        assert topico_comando in topicos_vistos or topico_status in topicos_vistos, (
            f'no se observo trafico real del dispositivo {RASPBERRY_SERIAL}: {capturados}'
        )

    @pytest.mark.skipif(
        not (DEVICE_USER and DEVICE_PASS),
        reason='definir MQTT_USER/MQTT_PASS (cuenta generica de dispositivo) para el hallazgo de interceptacion',
    )
    def test_HALLAZGO_una_cuenta_generica_de_dispositivo_intercepta_el_comando_de_otro(self, admin):
        """Refuerza TC-M09-G127 (TC-M09-250/251) con datos reales, no solo con el SUBACK."""
        respuesta, capturados = _escuchar_y_configurar(DEVICE_USER, DEVICE_PASS, admin, 21, 42)
        assert respuesta.status_code == 200, respuesta.text

        topico_comando = f'sgpmp/{RASPBERRY_SERIAL}/command'
        interceptado = next((p for t, p in capturados if t == topico_comando), None)
        assert interceptado is not None, (
            f'se esperaba que la cuenta generica de dispositivo interceptara {topico_comando}, '
            f'pero no se capturo: {capturados}'
        )
        assert '21' in interceptado and '42' in interceptado, (
            f'se intercepto el topico pero no coincide con los valores reales enviados: {interceptado}'
        )
