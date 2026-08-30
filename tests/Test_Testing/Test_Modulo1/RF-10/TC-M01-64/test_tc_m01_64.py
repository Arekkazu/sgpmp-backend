# -*- coding: utf-8 -*-
"""
TC-M01-064 - Detectar un registro de auditoría cuyo hash no coincida

RF-10 / CU07 - Consultar Historial y Auditoría
Nivel de prueba: Backend / Base de datos (Pytest, conexión directa a BD).

Objetivo:
1. Generar un evento real de auditoría mediante login de Administrador.
2. Consultar directamente en la BD el evento generado.
3. Guardar su hash_integridad original.
4. Alterar temporalmente el hash_integridad por otro valor hexadecimal
   de 64 caracteres diferente al original.
5. Consultar el historial de auditoría mediante la API.
6. Verificar que el registro:
   - sigue existiendo;
   - no fue eliminado ni ocultado;
   - es marcado como comprometido mediante integridad_ok = false.
7. Restaurar el hash original incluso si la prueba falla.

IMPORTANTE:
Esta prueba modifica temporalmente información en la base de datos TEST.
El hash original se restaura en un bloque finally.

Requisitos:
pip install pytest psycopg2-binary requests --break-system-packages

Variables de entorno esperadas:
DB_USER
DB_PASSWORD

Opcionales:
ADMIN_EMAIL
ADMIN_PASSWORD
DB_HOST
DB_PORT
DB_NAME
"""

import base64
import json
import os
import time

import psycopg2
import psycopg2.extras
import pytest
import requests


# ============================================================
# CONFIGURACIÓN
# ============================================================

BASE_URL = (
    "http://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io"
    "/api-sgpmp-test"
)

ADMIN_EMAIL = os.environ.get(
    "ADMIN_EMAIL",
    "admin@pecuaria.co"
)

ADMIN_PASSWORD = os.environ.get(
    "ADMIN_PASSWORD",
    "Test1234!"
)

DB_HOST = os.environ.get(
    "DB_HOST",
    "158.69.200.27"
)

DB_PORT = os.environ.get(
    "DB_PORT",
    "5448"
)

DB_NAME = os.environ.get(
    "DB_NAME",
    "sgpmp_test"
)

DB_USER = os.environ["DB_USER"]
DB_PASSWORD = os.environ["DB_PASSWORD"]


# ============================================================
# FUNCIONES AUXILIARES
# ============================================================

def _decode_jwt_sub(token):
    """
    Decodifica el payload de un JWT sin verificar la firma
    y devuelve el claim 'sub'.
    """

    payload_b64 = token.split(".")[1]

    padding = "=" * (-len(payload_b64) % 4)

    payload_json = base64.urlsafe_b64decode(
        payload_b64 + padding
    )

    payload = json.loads(payload_json)

    return int(payload["sub"])


def _generar_hash_alterado(hash_original):
    """
    Genera un hash hexadecimal válido de 64 caracteres
    pero diferente al hash original.

    Se modifica únicamente el primer carácter hexadecimal.
    """

    primer_caracter = hash_original[0].lower()

    if primer_caracter != "0":
        nuevo_primer_caracter = "0"
    else:
        nuevo_primer_caracter = "1"

    return nuevo_primer_caracter + hash_original[1:]


# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture(scope="module")
def login_event():
    """
    Genera un login real mediante la API.

    Devuelve:
    - token
    - id_usuario
    - timestamp anterior al login
    """

    timestamp_antes = time.time()

    response = requests.post(
        f"{BASE_URL}/sesiones/",
        json={
            "correo_electronico": ADMIN_EMAIL,
            "contrasena": ADMIN_PASSWORD
        },
        timeout=15,
    )

    assert response.status_code == 200, (
        f"Precondición fallida: no se pudo iniciar sesión "
        f"como Administrador ({response.status_code}): "
        f"{response.text}"
    )

    respuesta = response.json()

    assert "token" in respuesta, (
        "La respuesta del login no contiene el token."
    )

    token = respuesta["token"]

    id_usuario = _decode_jwt_sub(token)

    return {
        "token": token,
        "id_usuario": id_usuario,
        "timestamp_antes": timestamp_antes,
    }


@pytest.fixture(scope="module")
def db_connection():
    """
    Crea una conexión directa a PostgreSQL.
    """

    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )

    yield conn

    conn.close()


# ============================================================
# CASO DE PRUEBA TC-M01-064
# ============================================================

def test_tc_m01_64_detectar_hash_alterado(
    login_event,
    db_connection
):

    token = login_event["token"]
    id_usuario = login_event["id_usuario"]
    timestamp_antes = login_event["timestamp_antes"]

    registro = None
    hash_original = None
    hash_alterado = None

    try:

        # ====================================================
        # PASO 1 - Buscar el evento de auditoría generado
        # ====================================================

        with db_connection.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        ) as cur:

            cur.execute(
                """
                SELECT
                    id_evento,
                    id_usuario,
                    hash_integridad,
                    fecha_evento,
                    descripcion,
                    nombre_usuario
                FROM modulo1.eventos
                WHERE id_usuario = %s
                  AND categoria = 'AUTENTICACION'
                  AND descripcion = 'LOGIN_EXITOSO'
                  AND fecha_evento >= to_timestamp(%s)
                ORDER BY fecha_evento DESC
                LIMIT 1;
                """,
                (
                    id_usuario,
                    timestamp_antes - 2,
                ),
            )

            registro = cur.fetchone()

        assert registro is not None, (
            "No se encontró en modulo1.eventos el evento de "
            "auditoría generado por el login de esta prueba."
        )

        id_evento = registro["id_evento"]

        hash_original = registro["hash_integridad"]

        assert hash_original is not None and hash_original != "", (
            "El evento seleccionado no tiene hash_integridad."
        )

        print("\n==============================================")
        print("TC-M01-064 - REGISTRO ORIGINAL")
        print("==============================================")
        print(f"id_evento: {id_evento}")
        print(f"id_usuario: {registro['id_usuario']}")
        print(f"usuario: {registro['nombre_usuario']}")
        print(f"fecha_evento: {registro['fecha_evento']}")
        print(f"descripcion: {registro['descripcion']}")
        print(f"hash original: {hash_original}")

        # ====================================================
        # PASO 2 - Alterar temporalmente el hash
        # ====================================================

        hash_alterado = _generar_hash_alterado(
            hash_original
        )

        assert hash_alterado != hash_original, (
            "No fue posible generar un hash diferente."
        )

        with db_connection.cursor() as cur:

            cur.execute(
                """
                UPDATE modulo1.eventos
                SET hash_integridad = %s
                WHERE id_evento = %s;
                """,
                (
                    hash_alterado,
                    id_evento,
                ),
            )

        db_connection.commit()

        print("\n==============================================")
        print("TC-M01-064 - HASH ALTERADO")
        print("==============================================")
        print(f"id_evento alterado: {id_evento}")
        print(f"hash original: {hash_original}")
        print(f"hash alterado: {hash_alterado}")

        # ====================================================
        # PASO 3 - Consultar auditoría mediante API
        # ====================================================

        response = requests.get(
            f"{BASE_URL}/auditoria/",
            headers={
                "Authorization": f"Bearer {token}"
            },
            params={
                "categoria": "AUTENTICACION",
                "pagina": 1,
                "tamano": 100,
            },
            timeout=15,
        )

        print("\n==============================================")
        print("TC-M01-064 - RESPUESTA API")
        print("==============================================")
        print(f"HTTP Status: {response.status_code}")
        print(response.text)

        # ====================================================
        # PASO 4 - Verificar respuesta HTTP
        # ====================================================

        assert response.status_code == 200, (
            "La consulta del historial de auditoría no respondió "
            f"HTTP 200. Recibido: {response.status_code}. "
            f"Respuesta: {response.text}"
        )

        respuesta_api = response.json()

        # ====================================================
        # PASO 5 - Verificar estructura
        # ====================================================

        assert "items" in respuesta_api, (
            "La respuesta de auditoría no contiene 'items'."
        )

        assert isinstance(
            respuesta_api["items"],
            list
        ), (
            "El campo 'items' no es una lista."
        )

        # ====================================================
        # PASO 6 - Buscar el registro alterado
        # ====================================================

        registro_api = next(
            (
                item
                for item in respuesta_api["items"]
                if item.get("id_evento") == id_evento
            ),
            None,
        )

        # ====================================================
        # VALIDACIÓN 1:
        # El registro NO debe desaparecer
        # ====================================================

        assert registro_api is not None, (
            "TC-M01-064 FALLÓ: el registro cuyo hash fue alterado "
            "no aparece en el historial. El requisito establece "
            "que un registro comprometido no debe ocultarse ni eliminarse."
        )

        print("\n==============================================")
        print("TC-M01-064 - REGISTRO COMPROMETIDO ENCONTRADO")
        print("==============================================")
        print(f"id_evento encontrado: {id_evento}")

        # ====================================================
        # VALIDACIÓN 2:
        # Debe existir integridad_ok
        # ====================================================

        assert "integridad_ok" in registro_api, (
            "TC-M01-064: el registro de auditoría no contiene "
            "el campo 'integridad_ok', por lo que el sistema no "
            "está exponiendo el estado de integridad."
        )

        print(
            f"integridad_ok: "
            f"{registro_api['integridad_ok']}"
        )

        # ====================================================
        # VALIDACIÓN 3:
        # El hash alterado debe detectarse como comprometido
        # ====================================================

        assert registro_api["integridad_ok"] is False, (
            "TC-M01-064 FALLÓ: el registro tiene un hash alterado "
            "pero el sistema no lo marcó como comprometido. "
            f"Valor recibido en integridad_ok: "
            f"{registro_api['integridad_ok']}"
        )

        print("\n==============================================")
        print("RESULTADO TC-M01-064")
        print("==============================================")
        print(
            "APROBADO: El registro comprometido permanece "
            "visible y fue marcado con integridad_ok = false."
        )

    finally:

        # ====================================================
        # PASO FINAL - RESTAURAR HASH ORIGINAL
        # ====================================================

        if registro is not None and hash_original is not None:

            try:

                with db_connection.cursor() as cur:

                    cur.execute(
                        """
                        UPDATE modulo1.eventos
                        SET hash_integridad = %s
                        WHERE id_evento = %s;
                        """,
                        (
                            hash_original,
                            registro["id_evento"],
                        ),
                    )

                db_connection.commit()

                print("\n==============================================")
                print("RESTAURACIÓN DE BASE DE DATOS")
                print("==============================================")
                print(
                    f"Hash original restaurado correctamente "
                    f"para id_evento={registro['id_evento']}"
                )

            except Exception as error:

                db_connection.rollback()

                print(
                    "\nERROR CRÍTICO: no fue posible restaurar "
                    f"el hash original: {error}"
                )

                raise