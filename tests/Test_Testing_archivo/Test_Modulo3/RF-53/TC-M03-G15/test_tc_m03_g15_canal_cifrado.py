"""
TC-M03-G15 - Rechazar comunicacion no cifrada (ASVS V9).

RF relacionado: RF-53 (CU01). Caso: TC-M03-031.

Criterio de la ficha: una peticion por HTTP plano o con una version de TLS
obsoleta no se acepta; ningun dato se procesa por un canal no cifrado (se
rechaza o se redirige a HTTPS).

Que verifica este archivo contra el backend TEST (endpoint real POST /iot/telemetria):
1. HTTP plano (puerto 80), sin seguir redirecciones: se acepta que la conexion se
   rechace o que responda con una redireccion a https://. Falla si el backend
   procesa el datagrama (cualquier respuesta propia de la API, 2xx/4xx con
   error_code, significa que el payload se leyo en claro).
2. TLS 1.0 y TLS 1.1: el handshake debe fallar.
3. Control: TLS 1.2 o superior negocia correctamente (si no, los puntos 2 no
   significan nada).
4. La respuesta HTTPS incluye Strict-Transport-Security (HSTS), que impide al
   cliente volver a usar HTTP plano.

El datagrama usa un dispositivo inexistente (999999): aunque el canal plano lo
procesara, no se crea ningun registro en TEST.

Si el OpenSSL local no permite ofrecer TLS 1.0/1.1 (politicas de seguridad del
sistema), esa prueba se marca SKIP en vez de dar un falso PASS; en ese caso usar
testssl.sh, como sugiere la ficha:

    testssl.sh --protocols https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io

La coleccion TC-M03-G15.postman_collection.json cubre el punto 1 desde Postman.

Como correrlo (desde la raiz del repo):

    python -m pytest tests/Test_Testing/Test_Modulo3/RF-53/TC-M03-G15 -v \
        --html=reporte-TC-M03-G15.html --self-contained-html
"""
from __future__ import annotations

import os
import socket
import ssl
from datetime import datetime, timezone

import pytest
import requests

HOST = os.getenv("TEST_HOST", "sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io")
PREFIJO = os.getenv("TEST_PREFIJO", "/api-sgpmp-test")
TIMEOUT = 10

_DATAGRAMA = {
    "device_id": 999999,
    "sensor_id": 999999,
    "tipo_variable": "TEMPERATURA_AMBIENTAL",
    "valor": 25.0,
    "unidad": "°C",
    "timestamp_captura": datetime.now(timezone.utc).isoformat(),
    "origen": "TIEMPO_REAL",
    "access_key": "TC-M03-031-CANAL-PLANO",
}


def _handshake(version: ssl.TLSVersion) -> str:
    """Intenta un handshake fijando exactamente la version; devuelve la version negociada."""
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    ctx.minimum_version = version
    ctx.maximum_version = version
    if version < ssl.TLSVersion.TLSv1_2:
        ctx.set_ciphers("DEFAULT:@SECLEVEL=0")
    with socket.create_connection((HOST, 443), timeout=TIMEOUT) as sock:
        with ctx.wrap_socket(sock, server_hostname=HOST) as tls:
            return tls.version()


def _cliente_puede_ofrecer(version: ssl.TLSVersion) -> bool:
    """El OpenSSL local puede tener deshabilitadas las versiones viejas: entonces la prueba no es concluyente."""
    try:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.minimum_version = version
        ctx.maximum_version = version
        ctx.set_ciphers("DEFAULT:@SECLEVEL=0")
        return True
    except (ValueError, ssl.SSLError):
        return False


def test_tc_m03_031a_http_plano_no_procesa_el_datagrama():
    url = f"http://{HOST}{PREFIJO}/iot/telemetria"
    try:
        r = requests.post(url, json=_DATAGRAMA, timeout=TIMEOUT, allow_redirects=False)
    except requests.exceptions.ConnectionError:
        return  # el puerto 80 no acepta la conexion: rechazado

    if r.status_code in (301, 302, 307, 308):
        destino = r.headers.get("Location", "")
        assert destino.startswith("https://"), f"Redirige pero no a HTTPS: Location={destino!r}"
        return

    cuerpo = r.text[:300]
    assert "error_code" not in cuerpo and "id_telemetria" not in cuerpo, (
        f"El backend proceso el datagrama por HTTP plano: HTTP {r.status_code} {cuerpo}"
    )
    assert r.status_code >= 400, f"HTTP plano respondio {r.status_code} sin redirigir a HTTPS: {cuerpo}"


@pytest.mark.parametrize("version", [ssl.TLSVersion.TLSv1, ssl.TLSVersion.TLSv1_1], ids=["TLS1.0", "TLS1.1"])
def test_tc_m03_031b_tls_obsoleto_se_rechaza(version):
    if not _cliente_puede_ofrecer(version):
        pytest.skip(f"El OpenSSL local no permite ofrecer {version.name}; verificar con testssl.sh")
    try:
        negociada = _handshake(version)
    except ssl.SSLError as exc:
        # "no protocols available" es del lado del cliente (no llego a ofrecer la version);
        # cualquier otro error (alerta protocol_version, unsupported protocol) es el servidor rechazandola.
        if "no protocols available" in str(exc).lower():
            pytest.skip(f"El cliente local no pudo ofrecer {version.name}: {exc}; verificar con testssl.sh")
        return  # el servidor rechazo el handshake
    except (ConnectionResetError, socket.timeout):
        return  # el servidor corto la conexion: rechazado
    pytest.fail(f"El servidor acepto un handshake con {negociada}")


def test_tc_m03_031c_control_tls_moderno_negocia():
    try:
        negociada = _handshake(ssl.TLSVersion.TLSv1_2)
    except ssl.SSLError:
        negociada = _handshake(ssl.TLSVersion.TLSv1_3)
    assert negociada in ("TLSv1.2", "TLSv1.3")


def test_tc_m03_031d_https_publica_hsts():
    r = requests.get(f"https://{HOST}{PREFIJO}/health", timeout=TIMEOUT)
    assert r.status_code == 200
    hsts = r.headers.get("Strict-Transport-Security")
    assert hsts and "max-age=" in hsts, f"Sin cabecera HSTS valida: {hsts!r}"
