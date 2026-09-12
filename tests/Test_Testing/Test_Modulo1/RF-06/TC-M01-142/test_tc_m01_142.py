import os
from datetime import datetime, timedelta, timezone

import psycopg2
import pytest
import requests


BASE_URL = os.getenv(
    "TEST_BASE_URL",
    "http://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test",
)

DB_HOST = os.getenv("DB_HOST", "158.69.200.27")
DB_PORT = int(os.getenv("DB_PORT", "5448"))
DB_USER = os.getenv("DB_USER", "member_qa")
DB_PASSWORD = os.getenv("DB_PASSWORD", "qaSGP2026")
DB_NAME = os.getenv("DB_NAME", "sgpmp_test")

ID_USUARIO = 4
CORREO = "ingeniero@pecuaria.co"
CONTRASENA = "Test1234!"

ESTADO_ACTIVO = "Activo"
ESTADO_BLOQUEADO = "Bloqueado"


@pytest.fixture
def db_connection():
    connection = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        dbname=DB_NAME,
    )

    try:
        yield connection
    finally:
        connection.close()


def obtener_estado_id(connection, nombre_estado):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id_estado_cuenta
            FROM modulo1.estados_cuentas
            WHERE LOWER(nombre) = LOWER(%s)
            LIMIT 1;
            """,
            (nombre_estado,),
        )

        row = cursor.fetchone()

    assert row is not None, (
        f"No se encontró el estado '{nombre_estado}'."
    )

    return row[0]


def obtener_estado(connection):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT e.nombre
            FROM modulo1.cuentas_usuarios c
            JOIN modulo1.estados_cuentas e
              ON e.id_estado_cuenta = c.id_estado_cuenta
            WHERE c.id_usuario = %s;
            """,
            (ID_USUARIO,),
        )

        row = cursor.fetchone()

    assert row is not None, (
        f"No existe la cuenta del usuario {ID_USUARIO}."
    )

    return row[0]


def preparar_bloqueo(connection, bloqueado_hasta):
    id_bloqueado = obtener_estado_id(
        connection,
        ESTADO_BLOQUEADO,
    )

    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE modulo1.cuentas_usuarios
            SET id_estado_cuenta = %s,
                bloqueado_hasta = %s
            WHERE id_usuario = %s;
            """,
            (
                id_bloqueado,
                bloqueado_hasta,
                ID_USUARIO,
            ),
        )

        assert cursor.rowcount == 1, (
            f"No se pudo preparar la cuenta {ID_USUARIO}."
        )

    connection.commit()


def restaurar_cuenta(connection):
    id_activo = obtener_estado_id(
        connection,
        ESTADO_ACTIVO,
    )

    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE modulo1.cuentas_usuarios
            SET id_estado_cuenta = %s,
                bloqueado_hasta = NULL,
                intentos_fallidos = 0
            WHERE id_usuario = %s;
            """,
            (
                id_activo,
                ID_USUARIO,
            ),
        )

    connection.commit()


def login_usuario():
    return requests.post(
        f"{BASE_URL}/sesiones/",
        json={
            "correo_electronico": CORREO,
            "contrasena": CONTRASENA,
        },
        timeout=15,
    )


def test_tc_m01_142_desbloqueo_automatico_15_minutos(db_connection):
    """
    TC-M01-142

    Validar el desbloqueo automático de una cuenta bloqueada
    después de cumplir la ventana de 15 minutos.

    Escenarios:

    - Antes de 15 minutos:
        HTTP 423 + CUENTA_BLOQUEADA

    - Después de 15 minutos:
        HTTP 200 + JWT válido
        + cuenta ACTIVA
    """

    estado_original = obtener_estado(db_connection)

    print(f"\nEstado original: {estado_original}")

    try:
        # ==========================================================
        # 1. Simular bloqueo vigente
        # ==========================================================

        ahora = datetime.now(timezone.utc)

        bloqueado_hasta = ahora + timedelta(
            minutes=14,
            seconds=59,
        )

        preparar_bloqueo(
            db_connection,
            bloqueado_hasta,
        )

        print(
            "bloqueado_hasta:",
            bloqueado_hasta.isoformat(),
        )

        # ==========================================================
        # 2. Verificar comportamiento antes de 15 minutos
        # ==========================================================

        response_antes = login_usuario()

        print(
            "Respuesta antes de 15 minutos:",
            response_antes.status_code,
            response_antes.text,
        )

        assert response_antes.status_code == 423, (
            "Antes de cumplirse los 15 minutos la cuenta "
            f"debe continuar bloqueada. "
            f"HTTP obtenido: {response_antes.status_code}"
        )

        body_antes = response_antes.json()

        assert body_antes.get("error_code") == "CUENTA_BLOQUEADA", (
            "El backend debe reportar CUENTA_BLOQUEADA "
            f"antes de la expiración. Respuesta: {body_antes}"
        )

        assert obtener_estado(db_connection) == ESTADO_BLOQUEADO

        print("14:59 → BLOQUEADO ✅")

        # ==========================================================
        # 3. Simular que ya transcurrieron los 15 minutos
        # ==========================================================

        tiempo_expirado = ahora - timedelta(seconds=1)

        preparar_bloqueo(
            db_connection,
            tiempo_expirado,
        )

        print(
            "bloqueado_hasta expirado:",
            tiempo_expirado.isoformat(),
        )

        # ==========================================================
        # 4. Intentar iniciar sesión después de la expiración
        # ==========================================================

        inicio = datetime.now(timezone.utc)

        response_despues = login_usuario()

        fin = datetime.now(timezone.utc)

        tiempo_procesamiento_ms = (
            fin - inicio
        ).total_seconds() * 1000

        print(
            "Respuesta después de 15 minutos:",
            response_despues.status_code,
            response_despues.text,
        )

        print(
            f"Tiempo de procesamiento del login: "
            f"{tiempo_procesamiento_ms:.2f} ms"
        )

        assert response_despues.status_code == 200, (
            "Al cumplirse los 15 minutos la cuenta debería "
            f"desbloquearse automáticamente. "
            f"HTTP obtenido: {response_despues.status_code}. "
            f"Respuesta: {response_despues.text}"
        )

        body_despues = response_despues.json()

        assert body_despues.get("token"), (
            "Después del desbloqueo automático el backend "
            "debe emitir un JWT."
        )

        print("15:00 → LOGIN ACEPTADO ✅")

        # ==========================================================
        # 5. Verificar que la cuenta quedó ACTIVA
        # ==========================================================

        estado_final = obtener_estado(db_connection)

        print(
            "Estado final:",
            estado_final,
        )

        assert estado_final == ESTADO_ACTIVO, (
            "Después del vencimiento del bloqueo la cuenta "
            f"debe estar ACTIVA, pero quedó en '{estado_final}'."
        )

        print("15:00 → ACTIVO ✅")
        print("Desbloqueo automático → CORRECTO ✅")

        # ==========================================================
        # 6. Registrar resultado
        # ==========================================================

        print(
            "\nRESULTADO TC-M01-142:"
        )
        print(
            "14:59 → BLOQUEADO"
        )
        print(
            "15:00 → ACTIVO"
        )
        print(
            "Desbloqueo automático → APROBADO"
        )

    finally:
        # ==========================================================
        # Restaurar cuenta
        # ==========================================================

        restaurar_cuenta(db_connection)

        print(
            "Cuenta restaurada → ACTIVO ✅"
        )