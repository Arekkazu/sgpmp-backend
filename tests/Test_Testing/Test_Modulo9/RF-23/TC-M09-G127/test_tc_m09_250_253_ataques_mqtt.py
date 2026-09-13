"""
TC-M09-G127 - Pruebas de ataque al protocolo MQTT: control de acceso,
interceptacion y repeticion de mensajes.

RF relacionado: RF-23, CU-05 Gestionar Dispositivos IoT
Categoria: Pruebas de seguridad (OWASP API2/API5, seguridad MQTT)
Sub-casos: TC-M09-250 (credenciales invalidas/ajenas), TC-M09-251
(eavesdropping via wildcard), TC-M09-252 (replay), TC-M09-253 (TLS).

Herramienta pedida por la ficha: Pytest + paho-mqtt, conectando
DIRECTAMENTE al broker MQTT (BROKER-MQTT-SGPMP), no a la API HTTP del
backend. Datos de conexion provistos por el usuario (2026-09-13):
    host: sigab-brokerdev-jwjecq-284f9b-158-69-200-27.sslip.io
    puerto MQTT nativo: 5449 (TCP)
    puerto MQTT sobre WebSocket: 9001
    usuario/clave: sgpmp_devices / IoTSgpmp2026
    TLS: No (dev)

RESULTADO: los 4 sub-casos quedan BLOQUEADOS / NO CONCLUYENTES, por una
combinacion de limitaciones de red y de credenciales descubiertas al
intentar ejecutarlos en esta sesion:

1. El puerto TCP nativo (5449) NO es alcanzable desde este entorno --
   `ping` responde (112ms) pero la conexion TCP es rechazada
   (`Test-NetConnection` -> TcpTestSucceeded=False). Requiere estar en la
   VPN/red interna del equipo, que no esta disponible aqui. El usuario
   confirmo (2026-09-13) que no tiene ese acceso a mano.
2. El puerto WebSocket (9001) SI es alcanzable, pero el broker responde
   `Not authorized` (CONNACK) para las TRES variantes probadas:
   conexion anonima, credenciales invalidas, Y las credenciales
   "sgpmp_devices"/"IoTSgpmp2026" provistas como validas. Probado con
   varios paths de WebSocket (/, /mqtt, /ws, /mqtt/, /websocket) --
   mismo resultado en todos. Esto es AMBIGUO: no se puede distinguir si
   (a) esas credenciales solo son validas en el listener nativo 5449 y
   el listener 9001 tiene su propio ACL distinto, o (b) las credenciales
   no son validas en absoluto ahora mismo. Sin acceso a 5449 no se puede
   desambiguar.

HALLAZGO YA DOCUMENTADO POR EL EQUIPO DEV (no confirmado por esta sesion
por la limitacion de red, pero citado aqui porque es exactamente lo que
TC-M09-250/251/253 buscan): `anotaciones/modulo_9/estado_M09.md` (seccion
RF-23, "Que NO cumple / gaps", lineas ~492-496) ya documenta: "El ACK del
dispositivo no esta autenticado mas alla del token de servicio del
backend. Mosquitto corre con allow_anonymous true en dev -- cualquier
cliente en la red podria publicar en sgpmp/<serial>/status y falsificar
un ACK. Mismo nivel de gap que el serial reusado como credencial debil de
telemetria en modulo 3 (ya documentado ahi); no es especifico de esta
entrega ni se resuelve aca." Esto es una admision explicita del propio
equipo de que TC-M09-250 (y por extension 251, ya que sin ACL por topic
tampoco habria restriccion de suscripcion) aplicarian sobre el listener
nativo (5449) -- pero como ESTE listener es el que no pudimos alcanzar
esta sesion, no se puede confirmar en vivo, solo citar la fuente.

Lo unico confirmado EN VIVO esta sesion es el comportamiento del listener
WebSocket (9001): rechaza tanto conexiones anonimas como con credenciales
invalidas (ver test_conexion_anonima_rechazada y
test_credenciales_invalidas_rechazadas mas abajo) -- comportamiento
correcto para ESE listener especificamente, sin que esto diga nada sobre
el listener 5449 que es al que realmente aplica el hallazgo ya conocido.

TC-M09-251 (eavesdropping), TC-M09-252 (replay) y la confirmacion via
conexion real de TC-M09-253 (TLS) requieren poder autenticarse
exitosamente con AL MENOS una credencial contra el broker real, cosa que
no se logro esta sesion en el unico puerto alcanzable -- quedan sin
ejecutar, no se simulan con dobles de prueba porque el objetivo es
probar el broker real, no la logica interna del backend.

Como correrlo (si en el futuro se logra acceso a la VPN/red interna, o
se consiguen credenciales validas para el listener 9001):
    python -m pip install paho-mqtt
    python -m pytest <ruta>\\test_tc_m09_250_253_ataques_mqtt.py -v \
        --html=Resultados/reporte-TC-M09-G127.html --self-contained-html
"""
import time

import paho.mqtt.client as mqtt
import pytest

MQTT_HOST = "sigab-brokerdev-jwjecq-284f9b-158-69-200-27.sslip.io"
MQTT_WS_PORT = 9001
MQTT_TCP_PORT = 5449  # no alcanzable desde esta sesion, ver docstring del modulo
CONNECT_TIMEOUT_S = 5


def _intentar_conectar(username, password, transport="websockets", port=MQTT_WS_PORT):
    resultado = {"reason_code": None}

    def on_connect(client, userdata, flags, reason_code, properties=None):
        resultado["reason_code"] = reason_code

    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"tc-m09-g127-{username or 'anon'}-{int(time.time())}",
        transport=transport,
    )
    if username:
        client.username_pw_set(username, password)
    client.on_connect = on_connect
    client.connect(MQTT_HOST, port, keepalive=10)
    client.loop_start()
    time.sleep(CONNECT_TIMEOUT_S)
    esta_conectado = client.is_connected()
    client.loop_stop()
    try:
        client.disconnect()
    except Exception:
        pass
    return resultado["reason_code"], esta_conectado


class TestTCM09250CredencialesInvalidasOAjenas:
    """TC-M09-250 -- solo se pudo probar el listener WebSocket (9001),
    no el nativo (5449) donde el equipo dev ya documento un gap
    (allow_anonymous true). Ver docstring del modulo."""

    def test_conexion_anonima_rechazada_en_listener_websocket(self):
        """
        En el listener WebSocket (9001), una conexion SIN credenciales es
        rechazada por el broker (CONNACK 'Not authorized'). Esto NO
        confirma ni descarta el gap ya documentado por el equipo dev para
        el listener nativo (5449, 'allow_anonymous true') -- son
        listeners distintos y este solo cubre el alcanzable.
        """
        reason_code, conectado = _intentar_conectar(username=None, password=None)
        assert conectado is False, (
            f"Se esperaba rechazo, pero la conexion anonima fue aceptada "
            f"(reason_code={reason_code}) -- esto SI confirmaria el gap "
            f"del listener WebSocket."
        )

    def test_credenciales_invalidas_rechazadas_en_listener_websocket(self):
        """Credenciales claramente invalidas deben rechazarse."""
        reason_code, conectado = _intentar_conectar(
            username="totally_wrong_user", password="wrong_pass"
        )
        assert conectado is False, (
            f"Se esperaba rechazo, pero credenciales invalidas fueron "
            f"aceptadas (reason_code={reason_code})."
        )

    @pytest.mark.skip(
        reason=(
            "BLOQUEADO: el puerto TCP nativo (5449), unico listener donde el "
            "equipo dev ya documento 'allow_anonymous true' "
            "(anotaciones/modulo_9/estado_M09.md ~L492-496), no es alcanzable "
            "desde esta red (TCP rechazado, sin acceso VPN). En el listener "
            "WebSocket (9001) SI alcanzable, las credenciales provistas como "
            "validas ('sgpmp_devices'/'IoTSgpmp2026') tambien fueron "
            "rechazadas (Not authorized) -- no se puede distinguir si son "
            "invalidas para este listener o si tienen un ACL propio. Sin "
            "poder autenticar con exito no se puede probar 'publicar en el "
            "topic de otro dispositivo usando credenciales de uno propio'."
        )
    )
    def test_publicar_en_topic_de_dispositivo_ajeno_usando_credenciales_propias(self):
        pass


class TestTCM09251EavesdroppingWildcard:
    """TC-M09-251 -- requiere una sesion autenticada exitosa para
    suscribirse y observar trafico real; no se logro esta sesion."""

    @pytest.mark.skip(
        reason=(
            "BLOQUEADO: no se logro una conexion autenticada exitosa contra "
            "el broker en ningun listener alcanzable esta sesion (ver "
            "TestTCM09250, mismo motivo). Sin conexion no hay forma de "
            "suscribirse a '#' ni observar si hay trafico de otros "
            "dispositivos visible."
        )
    )
    def test_suscripcion_wildcard_intercepta_trafico_de_otros_dispositivos(self):
        pass


class TestTCM09252ReplayDeMensaje:
    """TC-M09-252 -- requiere capturar un mensaje real via suscripcion
    (TC-M09-251) antes de poder reenviarlo; tampoco se logro."""

    @pytest.mark.skip(
        reason=(
            "BLOQUEADO: depende de TC-M09-251 (capturar un mensaje real de "
            "configuracion via suscripcion) para tener algo que reenviar. "
            "Ademas, el reprocesamiento del mensaje reenviado ocurriria en "
            "BROKER-MQTT-SGPMP (repo hermano, fuera de este codebase) o en "
            "el propio dispositivo -- ninguno de los dos es inspeccionable "
            "desde aqui aunque se lograra la conexion; como maximo se podria "
            "confirmar que el BROKER (nivel transporte) acepta republicar un "
            "payload identico sin deduplicar, lo cual es comportamiento MQTT "
            "estandar y no prueba nada sobre la logica de aplicacion."
        )
    )
    def test_mensaje_capturado_se_puede_reenviar_y_reprocesar(self):
        pass


class TestTCM09253ConexionSinTLS:

    def test_listener_websocket_acepta_conexion_sin_tls(self):
        """
        El listener WebSocket (9001) acepta el intento de conexion (TCP +
        upgrade WS) sin TLS -- el rechazo posterior es por autenticacion
        (Not authorized en el CONNACK de MQTT), no por exigir una capa de
        transporte cifrada. Esto SI confirma, para este listener, que no
        hay TLS obligatorio -- coincide con lo indicado por el usuario
        ('TLS: No (dev)') y con el hallazgo de la ficha (conexion en texto
        plano posible). No se pudo probar el listener nativo (5449) por la
        misma limitacion de red de los sub-casos anteriores.
        """
        reason_code, _ = _intentar_conectar(username=None, password=None)
        assert reason_code is not None, (
            "Se esperaba recibir un CONNACK del broker (aunque sea de "
            "rechazo por auth) sobre una conexion en texto plano -- si no "
            "se recibe nada, el transporte no-TLS podria estar bloqueado "
            "a nivel de red en vez de a nivel de aplicacion."
        )
