"""
TC-M09-G69 (RF-23, CU-05) - Configuracion remota de un dispositivo mediante MQTT y
mediante LoRaWAN.

    TC-M09-131  configurar por MQTT con payload valido (topico, payload, recepcion y ACK)
    TC-M09-132  configurar por LoRaWAN (envio, recepcion y estado final)

Un solo archivo y un solo reporte para todo el TC. Contra DEV (ambiente vigente):
    SGPMP_BASE_URL   (opcional, por defecto DEV)
    MQTT_USER / MQTT_PASS / MQTT_HOST   (solo para el control positivo de acceso al broker;
                                         NUNCA se versionan credenciales)

Arquitectura real (anotaciones/modulo_9/estado_M09.md): el backend NO habla MQTT; llama por HTTP
a BROKER-MQTT-SGPMP (POST /v1/commands), que publica en Mosquitto y espera hasta 30 s el ACK del
dispositivo. Responde 200 APLICADA (ACK), 202 PENDIENTE (dispositivo offline o broker
inalcanzable) o 504 NO_CONF (sin ACK). El backend no tiene ningun soporte LoRaWAN (solo el header
X-Gateway-Id de trazabilidad en la ingesta de telemetria).

Que se pudo y que no (sondeo 2026-09-21):
  * 131: la peticion se acepta y la configuracion queda persistida con los parametros enviados.
    NO se pudo completar el viaje de ida y vuelta: con un dispositivo simulado conectado al broker de
    DEV (mismo client_id que el serial, estado online retenido, suscripcion a sgpmp/<serial>/# y
    sgpmp/+/config) el backend sigue respondiendo 202 "Dispositivo offline" en ~1.5 s y el
    dispositivo simulado no recibe ningun mensaje. El contrato de topics/presencia no esta
    cerrado (lo dice el propio documento del equipo) y la cuenta de dispositivo no recibe
    entregas del broker. Se deja SKIP en vez de improvisar una prueba con falsa confianza.
  * 132: el campo `protocolo` no existe en el contrato de configuracion; se ignora por completo.

Como correrlo (desde la raiz del repo):
    $env:MQTT_USER = "..."; $env:MQTT_PASS = "..."
    python -m pytest <ruta>\\test_tc_m09_131_132_configuracion_mqtt_lorawan.py -v \
        --html=<ruta>\\Resultados\\resultado_TC-M09-G69.html --self-contained-html
"""
import os
import time

import httpx
import paho.mqtt.client as mqtt
import pytest

API = os.getenv('SGPMP_BASE_URL', 'https://sigab-backenddev-jpuya4-ea3a74-158-69-200-27.sslip.io/api-sgpmp')
MQTT_HOST = os.getenv('MQTT_HOST', 'sigab-brokerdev-jwjecq-284f9b-158-69-200-27.sslip.io')
MQTT_USER = os.getenv('MQTT_USER')
MQTT_PASS = os.getenv('MQTT_PASS')
ID_INFRAESTRUCTURA = 6
ID_TIPO_GENERICO = 1
PARAMETROS_VALIDOS = {'frecuencia_captura': 10, 'intervalo_transmision': 20}


@pytest.fixture(scope='module')
def admin():
    r = httpx.post(f'{API}/sesiones/', json={'correo_electronico': 'admin@pecuaria.co', 'contrasena': 'Test1234!'}, timeout=30)
    assert r.status_code == 200, r.text
    return {'Authorization': f"Bearer {r.json()['token']}"}


def _nuevo_dispositivo(admin, etiqueta: str) -> int:
    serial = f'QA-G69-{etiqueta}-{int(time.time()) % 100000}'
    r = httpx.post(
        f'{API}/configuracion/dispositivos-iot',
        json={'serial': serial, 'descripcion': f'QA TC-M09-G69 {etiqueta}', 'id_tipo_dispositivo': ID_TIPO_GENERICO,
              'id_infraestructura': ID_INFRAESTRUCTURA},
        headers=admin, timeout=30,
    )
    assert r.status_code == 201, r.text
    return r.json()['id_dispositivo_iot']


def _configurar(admin, id_dispositivo: int, **extra) -> httpx.Response:
    return httpx.post(
        f'{API}/configuracion/dispositivos-iot/{id_dispositivo}/configurar',
        json={**PARAMETROS_VALIDOS, **extra}, headers=admin, timeout=90,
    )


class TestTCM09131ConfiguracionPorMQTT:

    @pytest.mark.skipif(not (MQTT_USER and MQTT_PASS), reason='definir MQTT_USER y MQTT_PASS (no se versionan credenciales)')
    def test_el_broker_mqtt_de_dev_es_alcanzable_y_autentica_al_dispositivo(self):
        """Control positivo: primer tramo de la comunicacion extremo a extremo (dispositivo -> broker)."""
        resultado = {}
        cliente = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id='tc-m09-g69-control')
        cliente.username_pw_set(MQTT_USER, MQTT_PASS)
        cliente.on_connect = lambda c, u, f, rc, p=None: resultado.setdefault('rc', rc)
        cliente.connect(MQTT_HOST, 1884, keepalive=10)
        cliente.loop_start()
        limite = time.time() + 6
        while 'rc' not in resultado and time.time() < limite:
            time.sleep(0.1)
        cliente.loop_stop()
        cliente.disconnect()
        assert 'rc' in resultado and not resultado['rc'].is_failure, f"CONNACK: {resultado.get('rc')}"

    def test_configuracion_con_payload_valido_es_aceptada_y_queda_persistida(self, admin):
        id_dispositivo = _nuevo_dispositivo(admin, '131')
        r = _configurar(admin, id_dispositivo)

        assert r.status_code in (200, 202, 504), r.text
        cuerpo = r.json()
        assert cuerpo['estado'] in ('APLICADA', 'PENDIENTE', 'NO_CONF')
        assert (cuerpo['frecuencia_captura'], cuerpo['intervalo_transmision']) == (10, 20)

        historial = httpx.get(f'{API}/configuracion/dispositivos-iot/{id_dispositivo}/configuraciones', headers=admin, timeout=30)
        assert historial.status_code == 200, historial.text
        ids = [c['id_configuracion_remota'] for c in historial.json().get('items', historial.json() if isinstance(historial.json(), list) else [])]
        assert cuerpo['id_configuracion_remota'] in ids

    @pytest.mark.skip(
        reason=(
            'NO VERIFICABLE: el viaje completo (topico, payload enviado, recepcion y ACK -> 200 APLICADA) exige un '
            'dispositivo simulado que el broker reconozca como online. Con un dispositivo simulado conectado en DEV el '
            'backend sigue respondiendo 202 "Dispositivo offline" y el dispositivo no recibe mensajes; el contrato de '
            'topics/presencia con el equipo IoT no esta cerrado y la cuenta de dispositivo no recibe entregas del broker.'
        )
    )
    def test_configuracion_por_mqtt_llega_al_dispositivo_y_recibe_ack(self):
        pass


class TestTCM09132ConfiguracionPorLoRaWAN:

    def test_el_backend_permite_elegir_lorawan_como_protocolo_de_configuracion(self, admin):
        id_dispositivo = _nuevo_dispositivo(admin, '132')
        r = _configurar(admin, id_dispositivo, protocolo='LoRaWAN')

        assert r.status_code in (200, 202, 504), r.text
        cuerpo = r.json()
        assert cuerpo.get('protocolo') == 'LoRaWAN', (
            f'la respuesta no refleja el protocolo pedido (campos: {sorted(cuerpo)}): el campo `protocolo` no existe en el '
            'contrato de configuracion remota y se ignora; el backend no tiene ninguna ruta LoRaWAN (solo MQTT via BROKER-MQTT-SGPMP).'
        )

    def test_un_protocolo_inexistente_es_rechazado(self, admin):
        id_dispositivo = _nuevo_dispositivo(admin, '132b')
        r = _configurar(admin, id_dispositivo, protocolo='PROTOCOLO_INEXISTENTE')
        assert r.status_code in (400, 422), (
            f'protocolo inexistente aceptado con HTTP {r.status_code}: el campo se descarta en silencio, '
            'por lo que tampoco puede distinguirse MQTT de LoRaWAN.'
        )
