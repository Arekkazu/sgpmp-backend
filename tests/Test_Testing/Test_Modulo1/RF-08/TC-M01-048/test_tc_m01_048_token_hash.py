"""
TC-M01-048 - Validar que el token de recuperacion se almacene mediante hash
y no exista en texto plano en la base de datos.

RF relacionado: RF-08
Categoria: Persistencia / Seguridad

IMPORTANTE - correccion sobre la ficha original:
La ficha indica verificar con "SELECT token FROM tokens_recuperacion WHERE
usuario_id=...". Esa tabla NO EXISTE en el esquema (se confirmo consultando
information_schema.tables). El token de recuperacion en realidad se
almacena en modulo1.cuentas_usuarios.token_activacion_actual -- la misma
columna que reutiliza el sistema para activacion, reverificacion y
recuperacion (ver comentario de la columna en el modelo ORM). Este script
verifica el lugar correcto.

Este test:
1. Confirma que 'tokens_recuperacion' no existe (documenta el supuesto
   incorrecto de la ficha original).
2. Solicita una recuperacion de contrasena por la API del entorno TEST
   desplegado para una cuenta ya activa conocida.
3. Se conecta directamente a la base de datos (solo lectura) y trae el
   valor almacenado en cuentas_usuarios.token_activacion_actual.
4. Verifica que ese valor:
   - Tenga forma de hash SHA-256 (64 caracteres hexadecimales), que es
     el formato que produce calcular_hash_token() en el codigo.
   - NO tenga forma de token en texto plano (secrets.token_urlsafe(32):
     ~43 caracteres base64 url-safe, con mayusculas/minusculas mezcladas
     y posibles '-'/'_', nunca 64 hex).
   - Cambie tras cada solicitud nueva (evidencia de que se genera un
     valor fresco por request, no uno fijo).

Nota: no se puede verificar matematicamente que el hash corresponda al
token real enviado por correo (no tenemos acceso al buzón), a diferencia
de TC-M01-016 con bcrypt.checkpw(). La verificacion aqui es estructural:
formato de hash + cambio entre solicitudes.

Requisitos:
    pip install pytest pytest-html requests psycopg2-binary

Como correrlo:
    pytest test_tc_m01_048_token_hash.py -v \
        --html=reporte-TC-M01-048.html --self-contained-html

Las credenciales de BD, la URL del backend y el correo de prueba se
pueden sobreescribir con variables de entorno (DB_HOST, DB_PORT, DB_USER,
DB_PASSWORD, DB_NAME, BASE_URL, CORREO_PRUEBA); si no se definen, usa una
cuenta ya activa del entorno TEST que ya conocemos (admin@pecuaria.co).

El limite de RF-08 es de 3 solicitudes de recuperacion por hora por IP
(ver INC-M01-07-43): si ya se agoto para esta IP al correr esto varias
veces seguidas, la solicitud de este test devolvera 422 en vez de 202 --
el test lo detecta y verifica igual el ultimo token ya almacenado, en vez
de fallar.
"""
import os
import re
import time

import psycopg2
import pytest
import requests

BASE_URL = os.getenv(
    "BASE_URL",
    "https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test",
)
DB_HOST = os.getenv("DB_HOST", "158.69.200.27")
DB_PORT = os.getenv("DB_PORT", "5448")
DB_USER = os.getenv("DB_USER", "member_qa")
DB_PASSWORD = os.getenv("DB_PASSWORD", "qaSGP2026")
DB_NAME = os.getenv("DB_NAME", "sgpmp_test")
CORREO_PRUEBA = os.getenv("CORREO_PRUEBA", "admin@pecuaria.co")

PATRON_HASH_SHA256 = re.compile(r"^[0-9a-f]{64}$")
PATRON_TOKEN_URLSAFE_PLANO = re.compile(r"^[A-Za-z0-9\-_]{40,50}$")


@pytest.fixture(scope="module")
def conexion_db():
    """Conexion de solo lectura a la base de datos de TEST."""
    conn = psycopg2.connect(
        host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD, dbname=DB_NAME
    )
    conn.set_session(readonly=True, autocommit=True)
    yield conn
    conn.close()


def _token_actual(conn, correo):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT cu.token_activacion_actual, cu.fecha_cambio_estado
            FROM modulo1.cuentas_usuarios cu
            JOIN modulo1.usuarios u ON u.id_usuario = cu.id_usuario
            WHERE u.correo_electronico = %s
            """,
            (correo,),
        )
        fila = cur.fetchone()
    assert fila is not None, f"No se encontro la cuenta para {correo}"
    return fila  # (token_activacion_actual, fecha_cambio_estado)


@pytest.fixture(scope="module")
def solicitud_recuperacion(conexion_db):
    """Solicita una recuperacion real contra el backend TEST desplegado y
    trae el valor almacenado antes y despues de la solicitud."""
    token_antes, _ = _token_actual(conexion_db, CORREO_PRUEBA)

    resp = requests.post(
        f"{BASE_URL}/contrasena/recuperar",
        json={"correo_electronico": CORREO_PRUEBA},
        timeout=15,
    )
    limitado_por_tasa = resp.status_code == 422
    if not limitado_por_tasa:
        assert resp.status_code == 202, (
            f"Se esperaba 202 (o 422 por limite de RF-08 ya agotado), "
            f"se obtuvo {resp.status_code}: {resp.text}"
        )
        time.sleep(1)  # margen para que el commit del backend sea visible

    token_despues, fecha_despues = _token_actual(conexion_db, CORREO_PRUEBA)
    return {
        "token_antes": token_antes,
        "token_despues": token_despues,
        "limitado_por_tasa": limitado_por_tasa,
    }


class TestTCM01048TokenRecuperacionHash:
    """Suite de pruebas para TC-M01-048."""

    def test_la_tabla_tokens_recuperacion_de_la_ficha_no_existe(self, conexion_db):
        """
        Documenta el supuesto incorrecto de la ficha original: no hay tal
        tabla en el esquema. El token vive en cuentas_usuarios.
        """
        with conexion_db.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM information_schema.tables WHERE table_name = 'tokens_recuperacion'"
            )
            existe = cur.fetchone() is not None
        assert not existe, (
            "Inesperado: SI existe una tabla 'tokens_recuperacion' en el "
            "esquema actual; hay que revisar este test contra el nuevo "
            "diseño de BD."
        )

    def test_hay_un_token_almacenado_tras_la_solicitud(self, solicitud_recuperacion):
        assert solicitud_recuperacion["token_despues"] is not None, (
            "No hay ningun valor almacenado en cuentas_usuarios."
            "token_activacion_actual para esta cuenta."
        )

    def test_el_valor_almacenado_tiene_forma_de_hash_sha256(self, solicitud_recuperacion):
        valor = solicitud_recuperacion["token_despues"]
        assert PATRON_HASH_SHA256.match(valor), (
            f"El valor almacenado no tiene forma de hash SHA-256 (64 "
            f"caracteres hexadecimales): {valor!r} (longitud {len(valor)})."
        )

    def test_el_valor_almacenado_no_tiene_forma_de_token_en_texto_plano(
        self, solicitud_recuperacion
    ):
        """
        Control negativo: un token crudo de secrets.token_urlsafe(32) es
        base64 url-safe (~43 chars, mayus/minus mezcladas, puede tener
        '-'/'_'), nunca 64 caracteres hexadecimales en minuscula.
        """
        valor = solicitud_recuperacion["token_despues"]
        assert not PATRON_TOKEN_URLSAFE_PLANO.match(valor), (
            f"El valor almacenado parece un token en texto plano (formato "
            f"base64 url-safe), no un hash: {valor!r}"
        )

    def test_el_token_cambia_con_cada_solicitud_nueva(self, solicitud_recuperacion):
        """
        Si la solicitud de este run SI genero un token nuevo (no fue
        bloqueada por el limite de tasa), debe ser distinto al que habia
        antes -- evidencia de que se genera un valor fresco por request.
        """
        if solicitud_recuperacion["limitado_por_tasa"]:
            pytest.skip(
                "Limite de 3 solicitudes/hora (RF-08 / INC-M01-07-43) ya "
                "agotado para esta IP en esta corrida; no se genero un "
                "token nuevo que comparar. El resto de aserciones ya "
                "verificaron el ultimo token almacenado."
            )
        assert (
            solicitud_recuperacion["token_despues"]
            != solicitud_recuperacion["token_antes"]
        ), "El token no cambio tras la solicitud de recuperacion."
