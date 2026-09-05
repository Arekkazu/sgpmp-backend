"""
TC-M01-016 - Validar que la contrasena se almacene mediante hash bcrypt
y que no exista en ningun punto en texto plano en la base de datos.

RF relacionado: RF-01
Categoria: Persistencia / Seguridad

Este test:
1. Registra un usuario nuevo por la API del entorno TEST desplegado,
   con una contrasena conocida en texto plano.
2. Se conecta directamente a la base de datos (solo lectura) y trae
   el valor almacenado en la columna contrasena_cifrada.
3. Verifica:
   - Que el valor almacenado NO sea igual a la contrasena en texto plano.
   - Que el valor tenga el formato de un hash bcrypt ($2a$/$2b$/$2y$).
   - Que bcrypt.checkpw() confirme que el hash SI corresponde
     matematicamente a la contrasena original (no basta con "parecer"
     un hash bcrypt, tiene que ser el hash correcto).

Requisitos:
    pip install pytest pytest-html requests psycopg2-binary bcrypt

Como correrlo:
    pytest test_tc_m01_016_password_hash.py -v \
        --html=reporte-TC-M01-016.html --self-contained-html

Las credenciales de BD y la URL del backend se pueden sobreescribir
con variables de entorno (DB_HOST, DB_PORT, DB_USER, DB_PASSWORD,
DB_NAME, BASE_URL); si no se definen, usa los valores del entorno
TEST que ya conocemos.
"""
import os
import uuid

import bcrypt
import psycopg2
import pytest
import requests

BASE_URL = os.getenv(
    "BASE_URL",
    "http://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test",
)
DB_HOST = os.getenv("DB_HOST", "158.69.200.27")
DB_PORT = os.getenv("DB_PORT", "5448")
DB_USER = os.getenv("DB_USER", "member_qa")
DB_PASSWORD = os.getenv("DB_PASSWORD", "qaSGP2026")
DB_NAME = os.getenv("DB_NAME", "sgpmp_test")

CONTRASENA_PLANA = "Abcd12#3"


@pytest.fixture(scope="module")
def usuario_registrado():
    """Registra un usuario nuevo y unico para esta corrida, via API."""
    sufijo = uuid.uuid4().hex[:8]
    correo = f"tc016.{sufijo}.qa@sgpmp-test.com"
    identificacion = str(uuid.uuid4().int)[:9]

    payload = {
        "correo_electronico": correo,
        "telefono": "3125550599",
        "tipo_identificacion": "CC",
        "numero_identificacion": identificacion,
        "nombre": "Prueba",
        "apellidos": "Hash Bcrypt",
        "fecha_nacimiento": "1998-04-12",
        "genero": "F",
        "contrasena": CONTRASENA_PLANA,
        "confirmar_contrasena": CONTRASENA_PLANA,
        "direccion": "Cl 10 #8-20, Neiva",
    }

    resp = requests.post(f"{BASE_URL}/usuarios/", json=payload, timeout=15)
    assert resp.status_code == 201, (
        f"No se pudo registrar el usuario de prueba: "
        f"{resp.status_code} - {resp.text}"
    )

    return {"correo": correo, "contrasena_plana": CONTRASENA_PLANA}


@pytest.fixture(scope="module")
def conexion_db():
    """Conexion de solo lectura a la base de datos de TEST."""
    conn = psycopg2.connect(
        host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD, dbname=DB_NAME
    )
    conn.set_session(readonly=True)
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def hash_almacenado(usuario_registrado, conexion_db):
    """Trae el hash de contrasena guardado en BD para el usuario registrado."""
    with conexion_db.cursor() as cur:
        cur.execute(
            "SELECT contrasena_cifrada FROM modulo1.usuarios WHERE correo_electronico = %s",
            (usuario_registrado["correo"],),
        )
        fila = cur.fetchone()
    assert fila is not None, "No se encontro el usuario registrado en la BD."
    return fila[0]


class TestTCM01016PasswordHashBcrypt:
    """Suite de pruebas para TC-M01-016."""

    def test_no_se_almacena_en_texto_plano(self, hash_almacenado, usuario_registrado):
        """La columna NO debe contener la contrasena tal cual se envio."""
        assert hash_almacenado != usuario_registrado["contrasena_plana"], (
            "CRITICO: la contrasena esta almacenada en texto plano en la BD."
        )
        # Tampoco debe contener la contrasena como substring de nada obvio.
        assert usuario_registrado["contrasena_plana"] not in hash_almacenado

    def test_tiene_formato_de_hash_bcrypt(self, hash_almacenado):
        """El valor debe iniciar con el identificador de algoritmo bcrypt."""
        prefijos_bcrypt_validos = ("$2a$", "$2b$", "$2y$")
        assert hash_almacenado.startswith(prefijos_bcrypt_validos), (
            f"El valor almacenado no tiene formato bcrypt reconocible: "
            f"{hash_almacenado[:10]}..."
        )
        # Un hash bcrypt estandar mide 60 caracteres.
        assert len(hash_almacenado) == 60, (
            f"Longitud inesperada para un hash bcrypt: {len(hash_almacenado)} "
            f"(se esperaban 60 caracteres)."
        )

    def test_el_hash_corresponde_matematicamente_a_la_contrasena_real(
        self, hash_almacenado, usuario_registrado
    ):
        """
        Verificacion fuerte: no basta con que "parezca" un hash bcrypt,
        debe ser EL hash correcto de la contrasena que se envio al
        registrarse (usando la funcion de verificacion real de bcrypt).
        """
        coincide = bcrypt.checkpw(
            usuario_registrado["contrasena_plana"].encode("utf-8"),
            hash_almacenado.encode("utf-8"),
        )
        assert coincide, (
            "El hash almacenado en BD no corresponde a la contrasena "
            "con la que se registro el usuario."
        )

    def test_una_contrasena_incorrecta_no_verifica_contra_el_hash(
        self, hash_almacenado
    ):
        """Control negativo: una contrasena distinta NO debe pasar la verificacion."""
        coincide = bcrypt.checkpw(
            b"ContrasenaIncorrecta#1", hash_almacenado.encode("utf-8")
        )
        assert not coincide