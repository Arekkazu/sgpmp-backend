"""
TC-M09-G127 (RF-23, CU-05) - Ataques al protocolo MQTT: control de acceso,
interceptacion, repeticion de mensajes y transporte sin cifrar.

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

QUE SE PUDO Y QUE NO SE PUDO VERIFICAR (sondeo del 2026-09-21, ver reporte):
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

import paho.mqtt.client as mqtt
import pytest

MQTT_HOST = os.getenv("MQTT_HOST", "sigab-brokerdev-jwjecq-284f9b-158-69-200-27.sslip.io")
MQTT_USER = os.getenv("MQTT_USER")
MQTT_PASS = os.getenv("MQTT_PASS")
LISTENERS = [("tcp", 1884), ("websockets", 9001)]
ESPERA_S = 3

pytestmark = pytest.mark.skipif(
    not (MQTT_USER and MQTT_PASS),
    reason="definir MQTT_USER y MQTT_PASS en el entorno (no se versionan credenciales)",
)


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
            "una ACL de minimo privilegio deberia negarlo. Nota: durante el sondeo la suscripcion no recibio "
            "ningun mensaje, asi que no se pudo demostrar fuga real de trafico."
        )

    @pytest.mark.skip(
        reason=(
            "NO VERIFICABLE: no hay trafico de otros dispositivos que observar. Durante el sondeo (8 s en reposo y 6 s "
            "tras disparar POST /configuracion/dispositivos-iot/{id}/configurar, que respondio 202 PENDIENTE "
            "'dispositivo offline') la suscripcion '#' en TCP 1884 y WS 9001 no recibio ni un mensaje."
        )
    )
    def test_el_wildcard_no_expone_trafico_de_otros_dispositivos(self):
        pass


class TestTCM09252ReplayDeMensaje:

    @pytest.mark.skip(
        reason=(
            "NO VERIFICABLE: requiere capturar un mensaje real (depende de 251) y el broker no entrega mensajes a "
            "ningun suscriptor con esta credencial; el reprocesamiento ocurriria ademas en el dispositivo o en "
            "BROKER-MQTT-SGPMP (repo hermano). Un replay 'a ciegas' seria una prueba parcial con falsa confianza."
        )
    )
    def test_un_mensaje_capturado_reenviado_es_rechazado_o_ignorado(self):
        pass


class TestTCM09253ConexionSinTLS:

    @pytest.mark.parametrize("transport,port", LISTENERS, ids=[f"{t}-{p}" for t, p in LISTENERS])
    def test_el_broker_rechaza_conexiones_en_texto_plano(self, transport, port):
        """El canal MQTT debe ir cifrado: una conexion sin TLS con credenciales validas no deberia aceptarse."""
        plana, detalle = _conectar(transport, port, MQTT_USER, MQTT_PASS, tls=False)
        assert not plana, (
            f"el listener {transport}:{port} acepta credenciales en texto plano (CONNACK: {detalle}). "
            "Segun el equipo DEV no hay TLS en el ambiente de desarrollo; debe exigirse en produccion."
        )
