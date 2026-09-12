# -*- coding: utf-8 -*-
"""
TC-M01-064 - Detectar un registro de auditoría cuyo hash no coincida

RF-10 / CU07 - Consultar Historial y Auditoría
Nivel de prueba: Backend / Base de datos (Pytest, conexión directa a BD).

CORREGIDO respecto a la version anterior de este archivo (dos problemas
de fondo que le habrian impedido pasar):

1. La version anterior hacia UPDATE sobre un evento YA EXISTENTE para
   alterar su hash. Se confirmo que modulo1.eventos tiene un trigger
   (trg_proteger_auditoria_update) que bloquea CUALQUIER UPDATE, sin
   excepcion -- ni con privilegios de administrador, ni por SQL directo.
   Es el mismo mecanismo que ya valida TC-M01-065/066 (auditoria
   inmutable). Ese UPDATE simplemente fallaria con
   "IMMUTABLE_RECORD: Los registros de auditoria no pueden ser
   modificados ni eliminados".

   La forma correcta -- y la que el propio codigo ya anticipa, ver el
   docstring de crear_evento_db() en tests/integration/conftest.py -- es
   INSERTAR un evento NUEVO con un hash_integridad que no corresponda a
   su contenido. El trigger de inmutabilidad NO bloquea INSERT, solo
   UPDATE/DELETE.

2. La version anterior esperaba HTTP 200 con un campo `integridad_ok:
   false` en el item afectado. Revisando consultar_auditoria_use_case.py
   (lineas 126-140): si CUALQUIER item de la pagina resulta clasificado
   "MANIPULADO", el use case lanza InfrastructureError ANTES de devolver
   la respuesta -- es decir, toda la consulta responde HTTP 500 con
   error_code INTEGRIDAD_AUDITORIA_VIOLADA, no un 200 con un item
   marcado. Esto coincide exactamente con el flujo alterno de RF-10
   ("Fallo de integridad del registro (Hash Mismatch)... HTTP 500").

ADVERTENCIA: este script inserta un registro de auditoria PERMANENTE en
la tabla compartida del entorno TEST (no se puede borrar despues, por el
mismo trigger de inmutabilidad -- es intencional, la auditoria es
append-only). El registro queda claramente etiquetado como prueba de QA
en nombre_usuario/detalle para que cualquiera que lo vea despues sepa
que fue intencional.

Requisitos:
    pip install pytest psycopg2-binary requests

Como correrlo:
    pytest test_tc_m01_64.py -v \
        --html=reporte-TC-M01-064.html --self-contained-html

Variables de entorno opcionales (si no se definen, usa las credenciales
QA de solo consulta ya conocidas del entorno TEST):
    BASE_URL, DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME,
    ADMIN_EMAIL, ADMIN_PASSWORD
"""
import os
from datetime import datetime, timezone

import psycopg2
import psycopg2.extras
import pytest
import requests

BASE_URL = os.environ.get(
    "BASE_URL",
    "https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test",
)
DB_HOST = os.environ.get("DB_HOST", "158.69.200.27")
DB_PORT = os.environ.get("DB_PORT", "5448")
DB_NAME = os.environ.get("DB_NAME", "sgpmp_test")
DB_USER = os.environ.get("DB_USER", "member_qa")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "qaSGP2026")

ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@pecuaria.co")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Test1234!")

# ingeniero@pecuaria.co -- cuenta de prueba conocida, para no asociar el
# registro manipulado a la cuenta admin compartida.
ID_USUARIO_PRUEBA = 4
TIPO_EVENTO_LOGIN_EXITOSO = 3
HASH_INVALIDO = "0" * 64


@pytest.fixture(scope="module")
def db_connection():
    conn = psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def token_admin():
    response = requests.post(
        f"{BASE_URL}/sesiones/",
        json={"correo_electronico": ADMIN_EMAIL, "contrasena": ADMIN_PASSWORD},
        timeout=15,
    )
    assert response.status_code == 200, (
        f"Precondición fallida: no se pudo iniciar sesión como Administrador "
        f"({response.status_code}): {response.text}"
    )
    return response.json()["token"]


@pytest.fixture(scope="module")
def evento_manipulado(db_connection):
    """Inserta (NO modifica) un evento nuevo con hash_integridad invalido.

    Es un INSERT deliberado, no un UPDATE sobre un registro existente: el
    trigger de inmutabilidad de modulo1.eventos bloquea UPDATE/DELETE pero
    no INSERT, y es la unica forma de producir el escenario que pide la
    ficha sin depender de violar esa proteccion.
    """
    ahora = datetime.now(timezone.utc)
    detalle = (
        '{"motivo": "TC-M01-064: registro de prueba con hash invalido a '
        'proposito, para verificar deteccion de manipulacion (RF-10)"}'
    )
    with db_connection.cursor() as cur:
        cur.execute(
            """
            INSERT INTO modulo1.eventos (
                tipo_evento, fecha_evento, modulo, resultado, detalle,
                id_usuario, categoria, estado, hash_integridad,
                nombre_usuario, direccion_ip, user_agent
            ) VALUES (
                %s, %s, 'MODULO1',
                CAST('exitoso' AS modulo1.enum_evento_resultado),
                %s::jsonb, %s, 'AUTENTICACION', 'PROCESADO', %s, %s, %s, %s
            )
            RETURNING id_evento
            """,
            (
                TIPO_EVENTO_LOGIN_EXITOSO,
                ahora,
                detalle,
                ID_USUARIO_PRUEBA,
                HASH_INVALIDO,
                "QA - TC-M01-064 (registro de prueba, hash invalido intencional)",
                "203.0.113.10",
                "QA-TC-M01-064",
            ),
        )
        id_evento = cur.fetchone()[0]
    db_connection.commit()

    print("\n==============================================")
    print("TC-M01-064 - EVENTO DE PRUEBA INSERTADO")
    print("==============================================")
    print(f"id_evento: {id_evento}")
    print(f"hash_integridad (invalido a proposito): {HASH_INVALIDO}")

    return {"id_evento": id_evento, "fecha": ahora}


class TestTCM01064HashManipulado:
    """Suite de pruebas para TC-M01-064."""

    def test_consulta_de_auditoria_detecta_el_registro_manipulado(
        self, evento_manipulado, token_admin
    ):
        """RF-10: ante un registro con hash que no coincide, la consulta
        debe responder HTTP 500 con el codigo y mensaje del flujo
        alterno "Fallo de integridad del registro (Hash Mismatch)"."""
        fecha_desde = evento_manipulado["fecha"].strftime("%Y-%m-%dT00:00:00")

        response = requests.get(
            f"{BASE_URL}/auditoria/",
            headers={"Authorization": f"Bearer {token_admin}"},
            params={
                "id_usuario": ID_USUARIO_PRUEBA,
                "fecha_desde": fecha_desde,
                "pagina": 1,
                "tamano": 50,
            },
            timeout=15,
        )

        print("\n==============================================")
        print("TC-M01-064 - RESPUESTA API")
        print("==============================================")
        print(f"HTTP Status: {response.status_code}")
        print(response.text)

        assert response.status_code == 500, (
            f"RF-10 exige HTTP 500 cuando se detecta un registro "
            f"manipulado; se obtuvo {response.status_code}: {response.text}"
        )

        cuerpo = response.json()
        assert cuerpo.get("error_code") == "INTEGRIDAD_AUDITORIA_VIOLADA", (
            f"error_code inesperado: {cuerpo.get('error_code')}"
        )
        assert str(evento_manipulado["id_evento"]) in cuerpo.get("message", ""), (
            f"El mensaje deberia mencionar el id_evento manipulado "
            f"({evento_manipulado['id_evento']}): {cuerpo.get('message')}"
        )

        print("\n==============================================")
        print("RESULTADO TC-M01-064 (checkpoint 1)")
        print("==============================================")
        print("APROBADO: la consulta respondio 500 INTEGRIDAD_AUDITORIA_VIOLADA.")

    def test_el_registro_manipulado_no_se_oculta_ni_se_elimina(
        self, evento_manipulado, db_connection
    ):
        """El sistema debe reportar el incidente, no ocultar ni borrar el
        registro comprometido (RF-10: la auditoria es append-only)."""
        with db_connection.cursor() as cur:
            cur.execute(
                "SELECT hash_integridad FROM modulo1.eventos WHERE id_evento = %s",
                (evento_manipulado["id_evento"],),
            )
            fila = cur.fetchone()

        assert fila is not None, (
            "El registro manipulado desaparecio de la tabla -- no deberia "
            "ocultarse ni eliminarse."
        )
        assert fila[0] == HASH_INVALIDO, (
            "El hash_integridad del registro cambio -- deberia permanecer "
            "exactamente como quedo (evidencia del incidente)."
        )

        print("\n==============================================")
        print("RESULTADO TC-M01-064 (checkpoint 2)")
        print("==============================================")
        print("APROBADO: el registro sigue existiendo, sin ocultarse ni eliminarse.")
