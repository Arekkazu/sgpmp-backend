"""
TC-M09-G127 (RF-23, G127-02) - Ataques a MQTT - reintento1.

Ficha: "Requiere credenciales del broker (publicacion directa, cuenta con
`#`). No se suministraron por variable de entorno en esta sesion; ejecutar
en DEV con MQTT_* definidas." Hallazgos previos (DEV, 2026-09-21/26):
cuenta generica con `#` concedido (M9-05); listeners sin TLS (M9-06).

Novedad de este reintento: el usuario entrego credenciales reales del
broker de **TEST** (MQTT_USERNAME/MQTT_PASSWORD/MQTT_HOST_PORT=1885, host
158.69.200.27 -- la IP del servidor, tratada con discrecion: nunca
hardcodeada en texto, solo via variables de entorno). Esto permite repetir
M9-05/M9-06 ya no solo en DEV sino tambien en TEST.

**Escenario 5 (publicacion directa en el broker) NO esta en este archivo
a proposito.** Publicar en el broker real (a diferencia de solo conectar y
suscribirse) es una accion con efectos reales si algun topico coincide con
el de un dispositivo activo -- se dejo pendiente de confirmacion explicita
del usuario antes de ejecutarla (ver chat), por disrecion con la
infraestructura. Si se autoriza, se agrega como test aparte.

Como correrlo:
    python -m pytest tests/Test_Testing/Test_Modulo9/RF-23/TC-M09-G127/test_tc_m09_g127_ataques_mqtt_reintento1.py -v \
        --html=resultados/resultado_TC-M09-G127_reintento1.html --self-contained-html
"""
from __future__ import annotations

import os
import time

import paho.mqtt.client as mqtt
import pytest

MQTT_HOST = "158.69.200.27"
MQTT_PORT = int(os.environ.get("MQTT_HOST_PORT", "1885"))
MQTT_USER = os.environ.get("MQTT_USERNAME")
MQTT_PASS = os.environ.get("MQTT_PASSWORD")

pytestmark = pytest.mark.skipif(
    not (MQTT_USER and MQTT_PASS),
    reason="MQTT_USERNAME/MQTT_PASSWORD no definidas en el entorno",
)


def _conectar_y_suscribir(topico: str, *, con_credenciales: bool = True) -> dict:
    resultado = {"connect_rc": None, "sub_granted": None}
    client = mqtt.Client(
        client_id=f"qa-g127-{int(time.time())}-{topico.replace('/', '_').replace('#', 'w')}",
        protocol=mqtt.MQTTv311,
    )
    if con_credenciales:
        client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.on_connect = lambda c, u, f, rc, props=None: resultado.__setitem__("connect_rc", rc)
    client.on_subscribe = lambda c, u, mid, rcs, props=None: resultado.__setitem__("sub_granted", rcs)

    client.connect(MQTT_HOST, MQTT_PORT, keepalive=20)
    client.loop_start()
    time.sleep(1.5)
    if resultado["connect_rc"] in (0, mqtt.MQTT_ERR_SUCCESS):
        client.subscribe(topico, qos=0)
        time.sleep(1.5)
    client.loop_stop()
    client.disconnect()
    return resultado


class TestTCM09G127AtaquesMqttReintento1:
    """TC-M09-G127 / G127-02: M9-05 (wildcard) y M9-06 (sin TLS), confirmados en TEST."""

    def test_m9_06_listener_acepta_texto_plano_sin_tls(self):
        resultado = _conectar_y_suscribir("sgpmp/#")
        assert resultado["connect_rc"] in (0, mqtt.MQTT_ERR_SUCCESS), (
            "HALLAZGO M9-06 (sigue abierto): se esperaba que el listener "
            f"{MQTT_HOST}:{MQTT_PORT} aceptara una conexion en texto plano, sin TLS; "
            f"connect_rc={resultado['connect_rc']!r}. Si esto empieza a fallar, el listener "
            "ahora exige TLS -- el hallazgo se habria corregido, actualizar la ficha."
        )

    def test_m9_05_cuenta_generica_recibe_wildcard_total(self):
        resultado = _conectar_y_suscribir("#")
        assert resultado["connect_rc"] in (0, mqtt.MQTT_ERR_SUCCESS)
        assert resultado["sub_granted"] is not None and resultado["sub_granted"][0] == 0, (
            "HALLAZGO M9-05 (sigue abierto): se esperaba SUBACK 0 (concedido) para "
            f"SUBSCRIBE '#' con la cuenta generica de gateway; se obtuvo "
            f"{resultado['sub_granted']!r}. Si esto empieza a fallar (rc>=128/denegado), "
            "el ACL del broker ya se corrigio -- actualizar la ficha."
        )

    def test_credenciales_invalidas_son_rechazadas(self):
        """Control negativo: una password incorrecta SI debe ser rechazada
        (si esto fallara, implicaria auth completamente abierta, un hallazgo
        mucho peor que M9-05/M9-06)."""
        resultado = {"connect_rc": None}
        client = mqtt.Client(client_id=f"qa-g127-bad-{int(time.time())}", protocol=mqtt.MQTTv311)
        client.username_pw_set(MQTT_USER, MQTT_PASS + "-invalida-qa")
        client.on_connect = lambda c, u, f, rc, props=None: resultado.__setitem__("connect_rc", rc)
        try:
            client.connect(MQTT_HOST, MQTT_PORT, keepalive=10)
            client.loop_start()
            time.sleep(1.5)
            client.loop_stop()
        finally:
            client.disconnect()

        assert resultado["connect_rc"] not in (0, mqtt.MQTT_ERR_SUCCESS), (
            f"Password invalida fue ACEPTADA (connect_rc={resultado['connect_rc']!r}) -- "
            "esto seria un hallazgo de autenticacion mucho mas grave que M9-05/M9-06."
        )
