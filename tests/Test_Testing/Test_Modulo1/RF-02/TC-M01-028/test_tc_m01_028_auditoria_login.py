"""
TC-M01-028 - Validar que todo intento de autenticacion, exitoso o
fallido, quede registrado en el historial de auditoria.

RF relacionado: RF-02
Categoria: Auditoria

Este test:
1. Reinicia el contador de intentos fallidos de la cuenta de prueba.
2. Hace 3 intentos de login FALLIDOS + 1 EXITOSO, via API.
3. Consulta modulo1.eventos directamente en BD (no la respuesta HTTP)
   y confirma que los 4 intentos quedaron registrados, en el orden
   correcto, con el tipo_evento y resultado correctos.

Requisitos:
    pip install pytest pytest-html requests psycopg2-binary

Como correrlo:
    pytest test_tc_m01_028_auditoria_login.py -v \
        --html=reporte-TC-M01-028.html --self-contained-html

Variables de entorno opcionales para sobreescribir configuracion
(BASE_URL, DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME).
"""
import os
import time

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

CORREO_PRUEBA = "jmanuelgomen+tcm017@gmail.com"
CONTRASENA_CORRECTA = "Abcd12#3"
CONTRASENA_INCORRECTA = "ClaveErronea1#"

TIPO_EVENTO_LOGIN_EXITOSO = 3
TIPO_EVENTO_LOGIN_FALLIDO = 4


@pytest.fixture(scope="module")
def conexion_db():
    conn = psycopg2.connect(
        host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD, dbname=DB_NAME
    )
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def id_usuario(conexion_db):
    with conexion_db.cursor() as cur:
        cur.execute(
            "SELECT id_usuario FROM modulo1.usuarios WHERE correo_electronico = %s",
            (CORREO_PRUEBA,),
        )
        fila = cur.fetchone()
    assert fila is not None, f"No se encontro el usuario {CORREO_PRUEBA} en BD."
    return fila[0]


@pytest.fixture(scope="module")
def preparar_cuenta_y_marca_de_tiempo(conexion_db, id_usuario):
    """Reinicia intentos_fallidos/bloqueo, y guarda el id_evento maximo
    ANTES de generar actividad, para poder filtrar solo los eventos
    nuevos que produzca este test."""
    with conexion_db.cursor() as cur:
        cur.execute(
            """
            UPDATE modulo1.cuentas_usuarios
            SET intentos_fallidos = 0, bloqueado_hasta = NULL, id_estado_cuenta = 2
            WHERE id_usuario = %s
            """,
            (id_usuario,),
        )
        conexion_db.commit()

        cur.execute(
            "SELECT COALESCE(MAX(id_evento), 0) FROM modulo1.eventos WHERE id_usuario = %s",
            (id_usuario,),
        )
        id_evento_baseline = cur.fetchone()[0]

    return id_evento_baseline


@pytest.fixture(scope="module")
def generar_intentos_de_login(preparar_cuenta_y_marca_de_tiempo):
    """Genera exactamente 3 intentos fallidos y 1 exitoso, en ese orden."""
    for _ in range(3):
        resp = requests.post(
            f"{BASE_URL}/sesiones/",
            json={"correo_electronico": CORREO_PRUEBA, "contrasena": CONTRASENA_INCORRECTA},
            timeout=15,
        )
        assert resp.status_code == 401, f"Se esperaba 401, se obtuvo {resp.status_code}: {resp.text}"

    resp = requests.post(
        f"{BASE_URL}/sesiones/",
        json={"correo_electronico": CORREO_PRUEBA, "contrasena": CONTRASENA_CORRECTA},
        timeout=15,
    )
    assert resp.status_code == 200, f"Se esperaba 200, se obtuvo {resp.status_code}: {resp.text}"

    # Pequeno margen para que cualquier escritura asincrona de auditoria
    # (si la hubiera) alcance a persistirse antes de consultar.
    time.sleep(1)

    return True


@pytest.fixture(scope="module")
def eventos_nuevos(generar_intentos_de_login, conexion_db, id_usuario, preparar_cuenta_y_marca_de_tiempo):
    """Trae de BD todos los eventos generados DESPUES del baseline, en orden cronologico."""
    id_evento_baseline = preparar_cuenta_y_marca_de_tiempo
    with conexion_db.cursor() as cur:
        cur.execute(
            """
            SELECT id_evento, tipo_evento, resultado, categoria, descripcion, fecha_evento
            FROM modulo1.eventos
            WHERE id_usuario = %s AND id_evento > %s
            ORDER BY id_evento ASC
            """,
            (id_usuario, id_evento_baseline),
        )
        filas = cur.fetchall()
    return filas


class TestTCM01028AuditoriaLogin:
    """Suite de pruebas para TC-M01-028."""

    def test_se_registraron_exactamente_4_eventos_nuevos(self, eventos_nuevos):
        assert len(eventos_nuevos) == 4, (
            f"Se esperaban 4 eventos nuevos (3 fallidos + 1 exitoso), "
            f"se encontraron {len(eventos_nuevos)}: {eventos_nuevos}"
        )

    def test_los_primeros_3_eventos_son_login_fallido(self, eventos_nuevos):
        for i, (id_evento, tipo_evento, resultado, categoria, descripcion, fecha) in enumerate(
            eventos_nuevos[:3], start=1
        ):
            assert tipo_evento == TIPO_EVENTO_LOGIN_FALLIDO, (
                f"Evento #{i}: se esperaba tipo_evento={TIPO_EVENTO_LOGIN_FALLIDO} "
                f"(Inicio sesion fallido), se obtuvo {tipo_evento}"
            )
            assert resultado == "fallido", f"Evento #{i}: se esperaba resultado='fallido', se obtuvo '{resultado}'"
            assert categoria == "AUTENTICACION"

    def test_el_4to_evento_es_login_exitoso(self, eventos_nuevos):
        id_evento, tipo_evento, resultado, categoria, descripcion, fecha = eventos_nuevos[3]
        assert tipo_evento == TIPO_EVENTO_LOGIN_EXITOSO, (
            f"Se esperaba tipo_evento={TIPO_EVENTO_LOGIN_EXITOSO} (Inicio sesion exitoso), "
            f"se obtuvo {tipo_evento}"
        )
        assert resultado == "exitoso", f"Se esperaba resultado='exitoso', se obtuvo '{resultado}'"
        assert categoria == "AUTENTICACION"

    def test_los_eventos_quedaron_en_orden_cronologico_correcto(self, eventos_nuevos):
        fechas = [fila[5] for fila in eventos_nuevos]
        assert fechas == sorted(fechas), (
            "Los eventos no quedaron ordenados cronologicamente como se esperaba."
        )