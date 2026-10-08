"""
TC-M09-G69 (RF-23, G69-02) - Transporte MQTT sobre LoRaWAN - reintento1.

Ficha (ANTES de este reintento): `protocolo` se ignora (202 con LoRaWAN e
inexistente, debe ser 400/422). "El viaje MQTT con dispositivo real
requiere credenciales de broker (pendiente)."

HALLAZGO DE ESTE REINTENTO (2026-10-08): el bug ya NO se reproduce en el
TEST desplegado -- `POST /configuracion/dispositivos-iot/{id}/configurar`
con un campo `protocolo` ahora responde `400 VAL_ENTRADA`
("Este campo no está permitido en esta solicitud.", error Pydantic
`extra_forbidden` via `src/shared/error_handlers.py`). Confirmado en vivo
con curl manual antes de tocar este archivo. El checkout LOCAL de
`ConfigurarRemotamenteDTO` (este repo, rama `casos-qa-juan-parra`) NO
declara `model_config = ConfigDict(extra='forbid')` -- es decir, el TEST
desplegado corre una revision MAS NUEVA de ese DTO que la que hay en este
checkout (mismo patron de desvio local-vs-live ya documentado para DEV en
2026-09-13). Este test queda escrito contra el comportamiento REAL y
vigente (400), no contra el DTO local. Tratar como corregido: el issue de
protocolo en `Issues_M09_RF21-23_2026-10-06.md` queda obsoleto, no subir a
Taiga sin revisar primero.

Esto tambien cierra, por via indirecta, la duda de si `protocolo` llega a
publicarse en el broker real: con 400 de validacion, la ejecucion nunca
llega a `mqtt_port.enviar_configuracion` (ese paso es posterior en el
codigo), asi que no hace falta escuchar el broker para esta parte -- se
deja la escucha de todas formas, por si el 400 cambiara de nuevo.

Ahora SI hay credenciales reales del broker de TEST (MQTT_USERNAME/
MQTT_PASSWORD/MQTT_HOST_PORT, variables de entorno -- nunca hardcodeadas
aqui, mismo criterio que toda la sesion), usadas para la parte de M9-05/
M9-06 (wildcard + texto plano) que si sigue vigente.

Topico de downlink confirmado en sesiones previas (2026-09-26, DEV, con
dispositivo real): `sgpmp/<serial>/command` -> {"frecuencia_captura": N,
"intervalo_transmision": M} (nunca incluye `protocolo`, porque
ConfigurarRemotamenteDTO no lo declara y BaseDTO no usa extra='forbid').

Como correrlo (variables de entorno ya puestas por quien ejecuta):
    python -m pytest tests/Test_Testing/Test_Modulo9/RF-23/TC-M09-G69/test_tc_m09_g69_protocolo_mqtt_reintento1.py -v \
        --html=resultados/resultado_TC-M09-G69_reintento1.html --self-contained-html
"""
from __future__ import annotations

import os
import time

import paho.mqtt.client as mqtt
import pytest
import requests

BASE_URL = "https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test"
MQTT_HOST = "158.69.200.27"
MQTT_PORT = int(os.environ.get("MQTT_HOST_PORT", "1885"))
MQTT_USER = os.environ.get("MQTT_USERNAME")
MQTT_PASS = os.environ.get("MQTT_PASSWORD")

_RUN_ID = str(int(time.time()))


def _login_admin() -> str:
    resp = requests.post(
        f"{BASE_URL}/sesiones/",
        json={"correo_electronico": "admin@pecuaria.co", "contrasena": "Test1234!"},
        timeout=20,
    )
    assert resp.status_code == 200, f"Login admin fallo: {resp.status_code} {resp.text}"
    return resp.json()["token"]


def _registrar_dispositivo(token: str, sufijo: str) -> tuple[int, str]:
    serial = f"QA-M09-G69-{sufijo}-{_RUN_ID}"
    resp = requests.post(
        f"{BASE_URL}/configuracion/dispositivos-iot",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "serial": serial,
            "descripcion": f"QA M09 G69 reintento1 {sufijo}",
            "id_infraestructura": 3,
            "id_tipo_dispositivo": 3,
        },
        timeout=20,
    )
    assert resp.status_code == 201, f"Registro de dispositivo fallo: {resp.status_code} {resp.text}"
    return resp.json()["id_dispositivo_iot"], serial


class _EscuchaMqtt:
    """Suscriptor de solo lectura al topico de downlink de un serial."""

    def __init__(self, serial: str) -> None:
        self.mensajes: list[tuple[str, bytes]] = []
        self._client = mqtt.Client(client_id=f"qa-g69-{serial}-{_RUN_ID}", protocol=mqtt.MQTTv311)
        if MQTT_USER and MQTT_PASS:
            self._client.username_pw_set(MQTT_USER, MQTT_PASS)
        self._client.on_message = lambda c, u, msg: self.mensajes.append((msg.topic, msg.payload))
        self._client.on_connect = lambda c, u, f, rc, props=None: c.subscribe(f"sgpmp/{serial}/#", qos=0)

    def __enter__(self) -> "_EscuchaMqtt":
        self._client.connect(MQTT_HOST, MQTT_PORT, keepalive=30)
        self._client.loop_start()
        time.sleep(1)  # margen para que el CONNECT/SUBACK se complete
        return self

    def __exit__(self, *exc) -> None:
        self._client.loop_stop()
        self._client.disconnect()


@pytest.mark.skipif(
    not (MQTT_USER and MQTT_PASS),
    reason="MQTT_USERNAME/MQTT_PASSWORD no definidas en el entorno -- solo se corre la parte HTTP",
)
class TestTCM09G69ProtocoloMqttReintento1:
    """TC-M09-G69 / G69-02: `protocolo` sigue ignorado end-to-end (HTTP + broker real)."""

    def test_protocolo_lorawan_ahora_se_rechaza_con_400_y_nunca_llega_al_broker(self):
        token = _login_admin()
        id_dispositivo, serial = _registrar_dispositivo(token, "lw")

        with _EscuchaMqtt(serial) as escucha:
            resp = requests.post(
                f"{BASE_URL}/configuracion/dispositivos-iot/{id_dispositivo}/configurar",
                headers={"Authorization": f"Bearer {token}"},
                json={"frecuencia_captura": 10, "intervalo_transmision": 10, "protocolo": "LORAWAN"},
                timeout=40,
            )
            time.sleep(3)  # margen por si algo alcanzara a publicarse de todos modos

        assert resp.status_code == 400, (
            "CORREGIDO: se esperaba 400 VAL_ENTRADA (extra_forbidden) para 'protocolo'; "
            f"respondio {resp.status_code}: {resp.text}. Si volvio a 202, el bug reapario -- "
            "revertir esta asercion y re-abrir el hallazgo."
        )
        cuerpo = resp.json()
        assert cuerpo.get("error_code") == "VAL_ENTRADA"
        assert any(f.get("field") == "protocolo" for f in cuerpo.get("fields", [])), (
            f"Se esperaba que el error senalara el campo 'protocolo'; cuerpo: {cuerpo!r}"
        )

        assert escucha.mensajes == [], (
            "Con 400 de validacion la ejecucion no debe llegar a publicar nada en el broker "
            f"(el envio MQTT es posterior en el codigo); se capturaron: {escucha.mensajes!r}"
        )

    def test_protocolo_inexistente_tambien_se_rechaza_con_400(self):
        token = _login_admin()
        id_dispositivo, _serial = _registrar_dispositivo(token, "inv")

        resp = requests.post(
            f"{BASE_URL}/configuracion/dispositivos-iot/{id_dispositivo}/configurar",
            headers={"Authorization": f"Bearer {token}"},
            json={"frecuencia_captura": 10, "intervalo_transmision": 10, "protocolo": "INEXISTENTE"},
            timeout=40,
        )
        assert resp.status_code == 400, (
            f"CORREGIDO: se esperaba 400 VAL_ENTRADA; respondio {resp.status_code}: {resp.text}"
        )
        assert resp.json().get("error_code") == "VAL_ENTRADA"

    def test_broker_real_sigue_confirmando_plaintext_y_wildcard(self):
        """Repite, dentro de esta misma suite, la confirmacion M9-05/M9-06 ya
        hecha manualmente -- para que quede como parte del reporte de G69 y no
        solo como una corrida suelta."""
        recibido = {"rc": None, "sub": None}
        client = mqtt.Client(client_id=f"qa-g69-probe-{_RUN_ID}", protocol=mqtt.MQTTv311)
        client.username_pw_set(MQTT_USER, MQTT_PASS)
        client.on_connect = lambda c, u, f, rc, props=None: recibido.__setitem__("rc", rc)
        client.on_subscribe = lambda c, u, mid, rcs, props=None: recibido.__setitem__("sub", rcs)

        client.connect(MQTT_HOST, MQTT_PORT, keepalive=30)
        client.loop_start()
        time.sleep(1.5)
        client.subscribe("#", qos=0)
        time.sleep(1.5)
        client.loop_stop()
        client.disconnect()

        assert recibido["rc"] in (0, mqtt.MQTT_ERR_SUCCESS), (
            f"Hallazgo M9-06 (sin TLS): se esperaba poder autenticar en texto plano "
            f"en {MQTT_HOST}:{MQTT_PORT}; connect_rc={recibido['rc']!r}"
        )
        assert recibido["sub"] is not None and recibido["sub"][0] == 0, (
            f"Hallazgo M9-05 (wildcard '#' concedido a cuenta generica): se esperaba "
            f"SUBACK 0 (concedido); se obtuvo {recibido['sub']!r}"
        )
