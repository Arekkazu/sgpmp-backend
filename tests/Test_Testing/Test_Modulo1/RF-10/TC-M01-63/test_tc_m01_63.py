# -*- coding: utf-8 -*-
"""
TC-M01-63 - Verificar que cada registro de auditoria contenga un hash SHA-256 valido
RF-10 / CU07 - Consultar Historial y Auditoria
Nivel de prueba: Backend / Base de datos (Pytest, conexion directa a BD).

Flujo:
1. Genera un evento de auditoria real haciendo login por la API (usuario Administrador
   con permiso ver_auditoria: admin@pecuaria.co, id_usuario=1, Carlos Rodriguez Perez).
2. Consulta directamente en la base de datos (tabla modulo1.eventos) el registro de
   ese login y extrae la columna hash_integridad.
3. Verifica que el hash almacenado sea un SHA-256 valido: exactamente 64 caracteres
   hexadecimales.
4. Registra (imprime) el hash almacenado y el resultado de la verificacion como
   evidencia del caso.

Requisitos: pip install pytest psycopg2-binary requests --break-system-packages

Variables de entorno esperadas (no se hardcodea ninguna contrasena en el archivo):
  DB_USER, DB_PASSWORD          -> credenciales de conexion a la BD (rol con permisos
                                    sobre el esquema modulo1)
  ADMIN_EMAIL, ADMIN_PASSWORD   -> opcionales, por defecto usan las credenciales del
                                    Administrador ya validadas en TC-M01-61
"""

import base64
import json
import os
import re
import time

import psycopg2
import psycopg2.extras
import pytest
import requests

BASE_URL = "http://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test"

ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@pecuaria.co")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Test1234!")

DB_HOST = os.environ.get("DB_HOST", "158.69.200.27")
DB_PORT = os.environ.get("DB_PORT", "5448")
DB_NAME = os.environ.get("DB_NAME", "sgpmp_test")
DB_USER = os.environ["DB_USER"]
DB_PASSWORD = os.environ["DB_PASSWORD"]

SHA256_HEX_REGEX = re.compile(r"^[0-9a-fA-F]{64}$")


def _decode_jwt_sub(token):
    """Decodifica (sin verificar firma) el payload de un JWT y devuelve el claim 'sub'."""
    payload_b64 = token.split(".")[1]
    padding = "=" * (-len(payload_b64) % 4)
    payload_json = base64.urlsafe_b64decode(payload_b64 + padding)
    payload = json.loads(payload_json)
    return int(payload["sub"])


@pytest.fixture(scope="module")
def login_event():
    """Genera un login real via API y devuelve (id_usuario, timestamp_antes_del_login)."""
    timestamp_antes = time.time()

    response = requests.post(
        f"{BASE_URL}/sesiones/",
        json={"correo_electronico": ADMIN_EMAIL, "contrasena": ADMIN_PASSWORD},
        timeout=15,
    )
    assert response.status_code == 200, (
        f"Precondicion fallida: no se pudo iniciar sesion como Administrador "
        f"({response.status_code}): {response.text}"
    )

    token = response.json()["token"]
    id_usuario = _decode_jwt_sub(token)
    return id_usuario, timestamp_antes


@pytest.fixture(scope="module")
def db_connection():
    conn = psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )
    yield conn
    conn.close()


def test_tc_m01_63_hash_sha256_valido(login_event, db_connection):
    id_usuario, timestamp_antes = login_event

    with db_connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT id_evento, hash_integridad, fecha_evento, descripcion, nombre_usuario
            FROM modulo1.eventos
            WHERE id_usuario = %s
              AND categoria = 'AUTENTICACION'
              AND descripcion = 'LOGIN_EXITOSO'
              AND fecha_evento >= to_timestamp(%s)
            ORDER BY fecha_evento DESC
            LIMIT 1;
            """,
            (id_usuario, timestamp_antes - 2),
        )
        registro = cur.fetchone()

    assert registro is not None, (
        "No se encontro en modulo1.eventos el registro de auditoria del login "
        "generado por esta prueba."
    )

    hash_almacenado = registro["hash_integridad"]

    print("--- TC-M01-63: evidencia ---")
    print(f"id_evento: {registro['id_evento']}")
    print(f"usuario: {registro['nombre_usuario']} (id_usuario={id_usuario})")
    print(f"fecha_evento: {registro['fecha_evento']}")
    print(f"hash_integridad almacenado: {hash_almacenado}")
    print(f"longitud del hash: {len(hash_almacenado) if hash_almacenado else 0} caracteres")

    assert hash_almacenado is not None and hash_almacenado != "", (
        "El registro de auditoria no tiene un hash_integridad almacenado."
    )

    es_valido = bool(SHA256_HEX_REGEX.fullmatch(hash_almacenado))
    print(f"resultado de la verificacion: {'VALIDO (SHA-256, 64 hex)' if es_valido else 'INVALIDO'}")

    assert es_valido, (
        f"TC-M01-63: el hash almacenado '{hash_almacenado}' no es un SHA-256 valido "
        f"de 64 caracteres hexadecimales (longitud real: {len(hash_almacenado)})."
    )
