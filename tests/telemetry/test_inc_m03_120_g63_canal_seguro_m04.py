# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-27 | destroyerban | INC-M03-120-G63 RF-56: canal seguro hacia M04 contra servidores TLS locales |
"""INC-M03-120-G63 (RF-56 Fase 6, TC-M03-125): canal seguro M03 → M04.

Pruebas aisladas: cada servidor escucha solo en 127.0.0.1, con certificados generados en la
prueba. No hay tráfico hacia DEV/TEST ni hacia otros sistemas. Se verifica con el cliente real
(``MotorInferenciaHttpAdapter``, httpx + ssl) que:

- HTTP plano se rechaza (URL ``http://`` y servidor sin TLS detrás de una URL ``https://``).
- TLS obsoleto (1.0, 1.1 y 1.2, por debajo del mínimo 1.3) no completa el handshake.
- Certificado no confiable o con otro nombre se rechaza.
- La configuración aprobada (TLS 1.3 y certificado de la CA configurada) se acepta.
"""
from __future__ import annotations

import ipaddress
import logging
import socket
import ssl
import threading
import warnings
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from src.telemetry.domain.entities.telemetria import PaqueteInferencia
from src.telemetry.infrastructure.adapters.motor_inferencia_http_adapter import (
    CanalInferenciaInseguroError,
    CanalInferenciaNoDisponibleError,
    MotorInferenciaHttpAdapter,
    contexto_tls,
    motor_inferencia_http_desde_entorno,
)

# ---------------------------------------------------------------- certificados de prueba

def _clave():
    return ec.generate_private_key(ec.SECP256R1())


def _nombre(cn):
    return x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])


def _ca(cn):
    clave = _clave()
    ahora = datetime.now(timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(_nombre(cn)).issuer_name(_nombre(cn))
            .public_key(clave.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(ahora - timedelta(minutes=5)).not_valid_after(ahora + timedelta(days=1))
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
            .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=False, key_encipherment=False,
                                         data_encipherment=False, key_agreement=False, key_cert_sign=True,
                                         crl_sign=True, encipher_only=False, decipher_only=False), critical=True)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(clave.public_key()), critical=False)
            .sign(clave, hashes.SHA256()))
    return cert, clave


def _servidor_firmado(ca_cert, ca_clave, nombres):
    clave = _clave()
    ahora = datetime.now(timezone.utc)
    san = [x509.IPAddress(ipaddress.ip_address(n)) if n[0].isdigit() else x509.DNSName(n) for n in nombres]
    cert = (x509.CertificateBuilder().subject_name(_nombre(nombres[0])).issuer_name(ca_cert.subject)
            .public_key(clave.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(ahora - timedelta(minutes=5)).not_valid_after(ahora + timedelta(days=1))
            .add_extension(x509.SubjectAlternativeName(san), critical=False)
            .add_extension(x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
            .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_clave.public_key()), critical=False)
            .sign(ca_clave, hashes.SHA256()))
    return cert, clave


def _pem(directorio, nombre, cert, clave=None):
    ruta_cert = directorio / f"{nombre}.crt"
    ruta_cert.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    if clave is None:
        return str(ruta_cert), None
    ruta_clave = directorio / f"{nombre}.key"
    ruta_clave.write_bytes(clave.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                               serialization.NoEncryption()))
    return str(ruta_cert), str(ruta_clave)


@pytest.fixture(scope="module")
def pki(tmp_path_factory):
    d = tmp_path_factory.mktemp("pki_g63")
    ca, ca_clave = _ca("CA pruebas M04")
    otra_ca, otra_clave = _ca("CA no confiable")
    return {
        "ca": _pem(d, "ca", ca)[0],
        "valido": _pem(d, "m04", *_servidor_firmado(ca, ca_clave, ["127.0.0.1", "localhost"])),
        "otro_nombre": _pem(d, "otro", *_servidor_firmado(ca, ca_clave, ["m04.otro.example"])),
        "no_confiable": _pem(d, "ajeno", *_servidor_firmado(otra_ca, otra_clave, ["127.0.0.1"])),
    }

# ---------------------------------------------------------------- servidor M04 de prueba (127.0.0.1)

class _Servidor:
    def __init__(self, tls=None, estado=200, location=None):
        self.recibidas = []
        servidor = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                largo = int(self.headers.get("Content-Length", 0))
                version = self.connection.version() if isinstance(self.connection, ssl.SSLSocket) else None
                servidor.recibidas.append({"cuerpo": self.rfile.read(largo), "version_tls": version,
                                           "authorization": self.headers.get("Authorization")})
                self.send_response(estado)
                if location:
                    self.send_header("Location", location)
                self.send_header("Content-Length", "0")
                self.end_headers()

            def log_message(self, *args):
                pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.httpd.handle_error = lambda *a: None
        if tls is not None:
            self.httpd.socket = tls.wrap_socket(self.httpd.socket, server_side=True)
        self.puerto = self.httpd.server_address[1]
        self.hilo = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.hilo.start()

    def url(self, esquema="https", host="127.0.0.1"):
        return f"{esquema}://{host}:{self.puerto}/inferencia/paquetes"

    def cerrar(self):
        self.httpd.shutdown()
        self.httpd.server_close()


def _tls_servidor(cert_y_clave, minimo=None, maximo=None):
    contexto = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    contexto.load_cert_chain(*cert_y_clave)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        if minimo is not None and minimo < ssl.TLSVersion.TLSv1_2:
            # OpenSSL 3 solo ofrece TLS 1.0/1.1 con el nivel de seguridad 0.
            contexto.set_ciphers("DEFAULT:@SECLEVEL=0")
        if minimo is not None:
            contexto.minimum_version = minimo
        if maximo is not None:
            contexto.maximum_version = maximo
    return contexto


@pytest.fixture(scope="module")
def canal_directo(pki):
    """Omite si algo intercepta el TLS local (p. ej. Avast Web Shield re-firma hasta 127.0.0.1).

    Con interceptación el cliente no habla con el servidor de prueba y ningún resultado es evidencia.
    """
    servidor = _Servidor(tls=_tls_servidor(pki["valido"]))
    sondeo = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    sondeo.check_hostname = False
    sondeo.verify_mode = ssl.CERT_NONE
    try:
        with socket.create_connection(("127.0.0.1", servidor.puerto), timeout=5) as crudo,                 sondeo.wrap_socket(crudo) as tls:
            servido = x509.load_der_x509_certificate(tls.getpeercert(binary_form=True))
    finally:
        servidor.cerrar()
    with open(pki["valido"][0], "rb") as f:
        esperado = x509.load_pem_x509_certificate(f.read())
    if servido != esperado:
        pytest.skip(f"TLS local interceptado (emisor servido: {servido.issuer.rfc4514_string()}); "
                    "ejecutar en un entorno sin inspección TLS, p. ej. el contenedor del backend")


@pytest.fixture
def servidores(canal_directo):
    creados = []

    def crear(**kw):
        s = _Servidor(**kw)
        creados.append(s)
        return s

    yield crear
    for s in creados:
        s.cerrar()


def _paquete():
    return PaqueteInferencia(id_sensor=7, id_dispositivo_iot=3, id_evento_edge_computing=11,
                             tipo_variable="TEMPERATURA_AMBIENTAL", valor_numerico=Decimal("38.5"),
                             estado_calidad="VALIDO", fecha_envio=datetime.now(timezone.utc),
                             estado_paquete="PENDIENTE", intento_envios=0, contexto_incompleto=False,
                             id_paquetes_inferencia=99)


def _cliente(url, pki, minimo="1.3", token="token-servicio-m04"):
    return MotorInferenciaHttpAdapter(url, contexto_tls(minimo, pki["ca"]), token=token, timeout=5)

# ---------------------------------------------------------------- configuración segura aprobada

def test_tls13_con_certificado_de_la_ca_configurada_es_aceptado(servidores, pki):
    m04 = servidores(tls=_tls_servidor(pki["valido"]))
    assert _cliente(m04.url(), pki).enviar_paquete(_paquete()) is True
    assert len(m04.recibidas) == 1
    recibida = m04.recibidas[0]
    assert recibida["version_tls"] == "TLSv1.3"
    assert recibida["authorization"] == "Bearer token-servicio-m04"
    assert b'"id_paquetes_inferencia": 99' in recibida["cuerpo"]


def test_lote_viaja_en_una_sola_solicitud(servidores, pki):
    m04 = servidores(tls=_tls_servidor(pki["valido"]))
    assert _cliente(m04.url(host="localhost"), pki).enviar_lote([_paquete(), _paquete()]) is True
    assert len(m04.recibidas) == 1 and m04.recibidas[0]["cuerpo"].count(b"id_paquetes_inferencia") == 2

# ---------------------------------------------------------------- HTTP plano

def test_url_http_plana_se_rechaza_sin_generar_trafico(servidores, pki):
    m04 = servidores()  # servidor HTTP plano escuchando
    with pytest.raises(CanalInferenciaInseguroError) as exc:
        _cliente(m04.url("http"), pki)
    assert exc.value.code == "CANAL_INFERENCIA_INSEGURO"
    assert m04.recibidas == []


def test_servidor_sin_tls_detras_de_url_https_se_rechaza(servidores, pki):
    m04 = servidores()  # responde en claro: el handshake TLS no se completa
    with pytest.raises(CanalInferenciaNoDisponibleError, match="WRONG_VERSION_NUMBER"):
        _cliente(m04.url(), pki).enviar_paquete(_paquete())
    assert m04.recibidas == []


def test_redireccion_hacia_http_no_se_sigue(servidores, pki):
    plano = servidores()
    m04 = servidores(tls=_tls_servidor(pki["valido"]), estado=307, location=plano.url("http"))
    assert _cliente(m04.url(), pki).enviar_paquete(_paquete()) is False
    assert len(m04.recibidas) == 1 and plano.recibidas == []

# ---------------------------------------------------------------- TLS obsoleto

@pytest.mark.parametrize("version", [ssl.TLSVersion.TLSv1, ssl.TLSVersion.TLSv1_1, ssl.TLSVersion.TLSv1_2],
                         ids=["TLSv1.0", "TLSv1.1", "TLSv1.2"])
def test_servidor_con_tls_anterior_al_minimo_se_rechaza(servidores, pki, version):
    try:
        tls = _tls_servidor(pki["valido"], minimo=version, maximo=version)
    except (ssl.SSLError, ValueError) as exc:  # pragma: no cover - depende del OpenSSL local
        pytest.skip(f"El OpenSSL local no permite levantar un servidor {version.name}: {exc}")
    m04 = servidores(tls=tls)
    with pytest.raises(CanalInferenciaNoDisponibleError, match="PROTOCOL_VERSION|UNSUPPORTED_PROTOCOL"):
        _cliente(m04.url(), pki).enviar_paquete(_paquete())
    assert m04.recibidas == []


def test_control_el_rechazo_de_tls12_lo_causa_el_minimo_del_cliente(servidores, pki):
    """El mismo servidor TLS 1.2 se acepta si el mínimo configurado es 1.2: el servidor funciona."""
    m04 = servidores(tls=_tls_servidor(pki["valido"], minimo=ssl.TLSVersion.TLSv1_2, maximo=ssl.TLSVersion.TLSv1_2))
    assert _cliente(m04.url(), pki, minimo="1.2").enviar_paquete(_paquete()) is True
    assert m04.recibidas[0]["version_tls"] == "TLSv1.2"


@pytest.mark.parametrize("minimo", ["1.0", "1.1", "", "TLSv1.3"])
def test_minimo_tls_no_admitido_se_rechaza(minimo):
    with pytest.raises(CanalInferenciaInseguroError):
        contexto_tls(minimo)


def test_contexto_que_admite_tls_obsoleto_o_no_verifica_se_rechaza():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        obsoleto = ssl.create_default_context()
        obsoleto.minimum_version = ssl.TLSVersion.TLSv1_1
    sin_verificar = ssl.create_default_context()
    sin_verificar.check_hostname = False
    sin_verificar.verify_mode = ssl.CERT_NONE
    for contexto in (obsoleto, sin_verificar):
        with pytest.raises(CanalInferenciaInseguroError):
            MotorInferenciaHttpAdapter("https://127.0.0.1:1/x", contexto)

# ---------------------------------------------------------------- certificados

@pytest.mark.parametrize("certificado,motivo", [("no_confiable", "unable to get local issuer"),
                                                ("otro_nombre", "mismatch")])
def test_certificado_no_confiable_o_con_otro_nombre_se_rechaza(servidores, pki, certificado, motivo):
    m04 = servidores(tls=_tls_servidor(pki[certificado]))
    with pytest.raises(CanalInferenciaNoDisponibleError, match=f"CERTIFICATE_VERIFY_FAILED.*{motivo}"):
        _cliente(m04.url(), pki).enviar_paquete(_paquete())
    assert m04.recibidas == []

# ---------------------------------------------------------------- respuesta de M04

def test_respuesta_no_exitosa_de_m04_es_intento_fallido(servidores, pki):
    m04 = servidores(tls=_tls_servidor(pki["valido"]), estado=503)
    assert _cliente(m04.url(), pki).enviar_paquete(_paquete()) is False

# ---------------------------------------------------------------- configuración por entorno

def _entorno(monkeypatch, **valores):
    for nombre in ("IOT_INFERENCIA_M04_URL", "IOT_INFERENCIA_M04_TOKEN", "IOT_INFERENCIA_TLS_MIN",
                   "IOT_INFERENCIA_CA_FILE"):
        monkeypatch.delenv(nombre, raising=False)
    for nombre, valor in valores.items():
        monkeypatch.setenv(nombre, valor)


def test_sin_url_de_m04_se_sigue_con_el_stub(monkeypatch):
    _entorno(monkeypatch)
    assert motor_inferencia_http_desde_entorno() is None


@pytest.mark.parametrize("valores", [{"IOT_INFERENCIA_M04_URL": "http://m04.interno/paquetes"},
                                     {"IOT_INFERENCIA_M04_URL": "https://m04.interno/paquetes",
                                      "IOT_INFERENCIA_TLS_MIN": "1.1"}],
                         ids=["http_plano", "tls_obsoleto"])
def test_configuracion_insegura_no_se_usa(monkeypatch, caplog, valores):
    _entorno(monkeypatch, **valores)
    with caplog.at_level(logging.CRITICAL):
        assert motor_inferencia_http_desde_entorno() is None
    assert any(r.levelno == logging.CRITICAL for r in caplog.records)


def test_configuracion_segura_por_entorno_envia_por_tls13(monkeypatch, servidores, pki):
    m04 = servidores(tls=_tls_servidor(pki["valido"]))
    _entorno(monkeypatch, IOT_INFERENCIA_M04_URL=m04.url(), IOT_INFERENCIA_CA_FILE=pki["ca"],
             IOT_INFERENCIA_M04_TOKEN="t")
    cliente = motor_inferencia_http_desde_entorno()
    assert isinstance(cliente, MotorInferenciaHttpAdapter)
    assert cliente.enviar_paquete(_paquete()) is True
    assert m04.recibidas[0]["version_tls"] == "TLSv1.3"
