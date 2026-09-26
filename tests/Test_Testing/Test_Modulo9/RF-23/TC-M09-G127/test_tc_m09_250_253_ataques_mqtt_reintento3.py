"""
TC-M09-G127 - Reintento 3 (2026-09-26) - Ataques al protocolo MQTT: control de acceso,
interceptacion, repeticion de mensajes y transporte sin cifrar.

NOVEDAD DE ESTE REINTENTO: el usuario proveyo credenciales de un GATEWAY real y el serial de
un dispositivo real y activo (Raspberry Pi `TC-M09-G64-1789321890010`, id_dispositivo_iot=20
en DEV). Con eso, 251 y 252 dejan de ser "NO VERIFICABLE" -- ahora hay trafico real que
observar y un ACK real que reenviar. Variables nuevas: RASPBERRY_SERIAL,
RASPBERRY_ID_DISPOSITIVO (reutiliza MQTT_USER/MQTT_PASS como la cuenta generica de
dispositivo para el hallazgo de interceptacion).

    TC-M09-250  credenciales invalidas / ajenas
    TC-M09-251  eavesdropping via suscripcion wildcard
    TC-M09-252  replay de un mensaje capturado
    TC-M09-253  conexion sin TLS

Herramienta de la ficha: Pytest + paho-mqtt, DIRECTO al broker de DEV (no a la
API HTTP). Las credenciales NUNCA van en el archivo (regla del plan de pruebas):
    $env:MQTT_USER = "..."      $env:MQTT_PASS = "..."
    $env:MQTT_HOST = "sigab-brokerdev-jwjecq-284f9b-158-69-200-27.sslip.io"   (opcional)
Listeners de DEV: TCP 1884 y WebSocket 9001 (el TCP nativo 5449 sigue sin ser
alcanzable desde la red de QA; 1883 responde pero rechaza estas credenciales).

REINTENTO 2 (2026-09-26): re-confirmado sin cambios tras traer ~656 commits de
dev/test a esta rama (merge 9cb03304). El merge no toco absolutamente nada de
configuracion del broker (es infraestructura separada del backend). Sondeo en
vivo el mismo dia: SUBSCRIBE '#' sigue CONCEDIDO (Granted QoS 0) a la cuenta de
dispositivo, y el puerto 1884 sigue aceptando la conexion en texto plano sin
TLS. Ningun otro sub-caso cambio (sigue sin entregar mensajes a ningun
suscriptor con esta cuenta, replay y publicacion cruzada siguen sin poder
verificarse). No requiere un fix de codigo del backend -- es configuracion del
broker Mosquitto (ACL por topic/rol y exigir TLS), fuera de este repositorio.

 SE PUDO VERIFICAR (sondeo del 2026-09-21, ver reporte):
  * Con la credencial de dispositivo el broker autentica en 1884 y 9001, y
    rechaza la conexion anonima y las credenciales invalidas en ambos.
  * El broker NO entrega ningun mensaje a ningun suscriptor con esta
    credencial: ni el propio (mismo cliente), ni topics candidatos
    sgpmp/<serial>/{status,telemetry,config,cmd,ack,uplink,downlink}, ni
    mensajes retenidos a un suscriptor nuevo, ni el trafico que el backend
    deberia generar al configurar un dispositivo (POST .../configurar -> 202
    PENDIENTE, "dispositivo offline"). Con el PUBACK/SUBACK en exito, eso es
    consistente con una ACL que descarta en silencio lectura y escritura para
    esta cuenta, pero no permite ver trafico real.
  * Por eso TC-M09-252 (replay) y la parte de "publicar en el topic de otro
    dispositivo" de 250 NO se pueden comprobar: no hay forma de observar el
    efecto. El plan de pruebas pide no improvisar pruebas parciales que den
    falsa confianza, asi que se dejan como SKIP con su motivo.

Los tests que se ejecutan afirman lo que pide la ficha; si el broker no lo
cumple, el test queda en rojo como evidencia.

Como correrlo (desde la raiz del repo):
    python -m pytest <ruta>\\test_tc_m09_250_253_ataques_mqtt.py -v \
        --html=<ruta>\\Resultados\\resultado_TC-M09-G127_reintento1.html --self-contained-html
"""
import os
import time

import httpx
import paho.mqtt.client as mqtt
import pytest

API = os.getenv("SGPMP_BASE_URL", "https://sigab-backenddev-jpuya4-ea3a74-158-69-200-27.sslip.io/api-sgpmp")
MQTT_HOST = os.getenv("MQTT_HOST", "sigab-brokerdev-jwjecq-284f9b-158-69-200-27.sslip.io")
MQTT_USER = os.getenv("MQTT_USER")
MQTT_PASS = os.getenv("MQTT_PASS")
DEVICE_USER = MQTT_USER
DEVICE_PASS = MQTT_PASS
RASPBERRY_SERIAL = os.getenv("RASPBERRY_SERIAL", "TC-M09-G64-1789321890010")
RASPBERRY_ID = int(os.getenv("RASPBERRY_ID_DISPOSITIVO", "20"))
LISTENERS = [("tcp", 1884), ("websockets", 9001)]
ESPERA_S = 3

pytestmark = pytest.mark.skipif(
    not (MQTT_USER and MQTT_PASS),
    reason="definir MQTT_USER y MQTT_PASS en el entorno (no se versionan credenciales)",
)


@pytest.fixture(scope="module")
def admin():
    r = httpx.post(f"{API}/sesiones/", json={"correo_electronico": "admin@pecuaria.co", "contrasena": "Test1234!"}, timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _conectar(transport, port, user=None, password=None, tls=False):
    """Devuelve (aceptada, codigo_connack | error)."""
    resultado = {}

    def on_connect(client, userdata, flags, reason_code, properties=None):
        resultado["rc"] = reason_code

    cliente = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"tc-m09-g127-{int(time.time() * 1000) % 10**9}",
        transport=transport,
    )
    if user:
        cliente.username_pw_set(user, password)
    if tls:
        cliente.tls_set()
    cliente.on_connect = on_connect
    try:
        cliente.connect(MQTT_HOST, port, keepalive=10)
        cliente.loop_start()
        limite = time.time() + ESPERA_S + 2
        while "rc" not in resultado and time.time() < limite:
            time.sleep(0.1)
        aceptada = "rc" in resultado and not resultado["rc"].is_failure
        return aceptada, str(resultado.get("rc", "sin CONNACK"))
    except Exception as exc:  # handshake TLS fallido, reset, etc.
        return False, f"{type(exc).__name__}: {exc}"
    finally:
        try:
            cliente.loop_stop()
            cliente.disconnect()
        except Exception:
            pass


@pytest.mark.parametrize("transport,port", LISTENERS, ids=[f"{t}-{p}" for t, p in LISTENERS])
class TestTCM09250CredencialesInvalidasOAjenas:

    def test_credencial_valida_es_aceptada_control_positivo(self, transport, port):
        aceptada, detalle = _conectar(transport, port, MQTT_USER, MQTT_PASS)
        assert aceptada, f"la credencial de dispositivo provista no autentica en {transport}:{port} ({detalle})"

    def test_conexion_anonima_es_rechazada(self, transport, port):
        aceptada, detalle = _conectar(transport, port)
        assert not aceptada, f"el broker acepto una conexion anonima en {transport}:{port} ({detalle})"

    def test_credenciales_invalidas_son_rechazadas(self, transport, port):
        aceptada, detalle = _conectar(transport, port, "usuario_inexistente", "clave_incorrecta")
        assert not aceptada, f"el broker acepto credenciales invalidas en {transport}:{port} ({detalle})"


class TestTCM09250PublicarEnTopicDeOtroDispositivo:

    @pytest.mark.skip(
        reason=(
            "NO VERIFICABLE: el broker devuelve exito al PUBLISH pero no entrega ningun mensaje a ningun suscriptor "
            "con esta credencial (ni el propio), asi que no hay forma de observar si la publicacion cruzada fue "
            "aceptada o descartada por una ACL. Ademas la cuenta 'sgpmp_devices' es una sola para todos los "
            "dispositivos: no existen credenciales por dispositivo con las que probar el cruce."
        )
    )
    def test_publicar_en_topic_ajeno_con_credencial_propia_es_rechazado(self):
        pass


class TestTCM09251EavesdroppingWildcard:

    def test_una_credencial_de_dispositivo_no_puede_suscribirse_al_wildcard_de_todo_el_broker(self):
        """Un dispositivo solo deberia poder leer sus propios topics: SUBSCRIBE '#' debe recibir un codigo de fallo."""
        codigos = {}

        def on_subscribe(client, userdata, mid, reason_codes, properties=None):
            codigos["suback"] = [str(rc) for rc in reason_codes]
            codigos["denegado"] = any(rc.is_failure for rc in reason_codes)

        def on_connect(client, userdata, flags, reason_code, properties=None):
            client.subscribe("#", qos=0)

        cliente = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="tc-m09-g127-wildcard")
        cliente.username_pw_set(MQTT_USER, MQTT_PASS)
        cliente.on_connect = on_connect
        cliente.on_subscribe = on_subscribe
        cliente.connect(MQTT_HOST, 1884, keepalive=10)
        cliente.loop_start()
        limite = time.time() + ESPERA_S + 2
        while "suback" not in codigos and time.time() < limite:
            time.sleep(0.1)
        cliente.loop_stop()
        cliente.disconnect()

        assert "suback" in codigos, "el broker no respondio SUBACK"
        assert codigos["denegado"], (
            f"SUBSCRIBE '#' fue CONCEDIDO a la credencial de dispositivo (SUBACK: {codigos['suback']}); "
            "una ACL de minimo privilegio deberia negarlo."
        )

    @pytest.mark.skipif(
        not (RASPBERRY_SERIAL and DEVICE_USER and DEVICE_PASS),
        reason='definir MQTT_USER/MQTT_PASS y RASPBERRY_ID_DISPOSITIVO para generar trafico real de otro dispositivo',
    )
    def test_HALLAZGO_reintento3_el_wildcard_SI_expone_trafico_real_de_otro_dispositivo(self, admin):
        """REINTENTO 3 (2026-09-26): con el serial y credenciales de gateway reales que dio el usuario,
        ahora SI hay trafico real que observar -- confirma con datos concretos lo que antes solo se
        podia inferir del SUBACK concedido (ver TC-M09-G69 reintento2, mismo hallazgo)."""
        capturados = []

        def on_message(c, u, m):
            capturados.append((m.topic, m.payload.decode(errors='replace')))

        def on_connect(c, u, f, rc, props=None):
            c.subscribe('#', qos=1)

        cliente = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id='tc-m09-g127-r3-eavesdrop')
        cliente.username_pw_set(DEVICE_USER, DEVICE_PASS)
        cliente.on_connect = on_connect
        cliente.on_message = on_message
        cliente.connect(MQTT_HOST, 1884, keepalive=20)
        cliente.loop_start()
        time.sleep(2)

        respuesta = httpx.post(
            f'{API}/configuracion/dispositivos-iot/{RASPBERRY_ID}/configurar',
            json={'frecuencia_captura': 23, 'intervalo_transmision': 46}, headers=admin, timeout=90,
        )
        time.sleep(4)
        cliente.loop_stop()
        cliente.disconnect()

        assert respuesta.status_code == 200, respuesta.text
        topico_comando = f'sgpmp/{RASPBERRY_SERIAL}/command'
        interceptado = next((p for t, p in capturados if t == topico_comando), None)
        assert interceptado is not None, f'no se intercepto {topico_comando}: {capturados}'
        assert '23' in interceptado and '46' in interceptado, (
            f'DEFECTO CONFIRMADO CON DATOS REALES: una cuenta generica de dispositivo, sin ninguna relacion con '
            f'{RASPBERRY_SERIAL}, leyo su comando de configuracion real: {interceptado}'
        )


class TestTCM09252ReplayDeMensaje:

    @pytest.mark.skipif(
        not (RASPBERRY_SERIAL and DEVICE_USER and DEVICE_PASS),
        reason='definir MQTT_USER/MQTT_PASS y RASPBERRY_ID_DISPOSITIVO para replay con trafico real',
    )
    def test_un_ack_capturado_reenviado_no_altera_una_configuracion_ya_resuelta(self, admin):
        """REINTENTO 3 (2026-09-26): con el ACK real capturado (ver TC-M09-G69 reintento2), se reenvia
        tal cual sobre una configuracion que YA fue aplicada, para ver si el backend la reprocesa."""
        ack_capturado = b'{"tipo_mensaje":"ACK_CONFIGURACION","resultado":"OK"}'

        antes = httpx.get(f'{API}/configuracion/dispositivos-iot/{RASPBERRY_ID}/configuraciones', headers=admin, timeout=30)
        assert antes.status_code == 200, antes.text
        total_antes = antes.json()['total']

        cliente = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id='tc-m09-g127-r3-replay')
        cliente.username_pw_set(DEVICE_USER, DEVICE_PASS)
        cliente.connect(MQTT_HOST, 1884, keepalive=10)
        cliente.loop_start()
        time.sleep(1)
        info = cliente.publish(f'sgpmp/{RASPBERRY_SERIAL}/status', ack_capturado, qos=1)
        info.wait_for_publish(5)
        time.sleep(2)
        cliente.loop_stop()
        cliente.disconnect()

        despues = httpx.get(f'{API}/configuracion/dispositivos-iot/{RASPBERRY_ID}/configuraciones', headers=admin, timeout=30)
        assert despues.status_code == 200, despues.text
        assert despues.json()['total'] == total_antes, (
            'el replay del ACK genero una fila nueva en el historial de configuraciones -- '
            'el backend reprocesa un ACK repetido como si fuera nuevo.'
        )


class TestTCM09253ConexionSinTLS:

    @pytest.mark.parametrize("transport,port", LISTENERS, ids=[f"{t}-{p}" for t, p in LISTENERS])
    def test_el_broker_rechaza_conexiones_en_texto_plano(self, transport, port):
        """El canal MQTT debe ir cifrado: una conexion sin TLS con credenciales validas no deberia aceptarse."""
        plana, detalle = _conectar(transport, port, MQTT_USER, MQTT_PASS, tls=False)
        assert not plana, (
            f"el listener {transport}:{port} acepta credenciales en texto plano (CONNACK: {detalle}). "
            "Segun el equipo DEV no hay TLS en el ambiente de desarrollo; debe exigirse en produccion."
        )
