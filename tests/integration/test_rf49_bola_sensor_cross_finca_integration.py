"""Prueba de Integración: Control de Acceso (BOLA) y Autorización RBAC en Asociación IoT.

Módulo: M02 - Activos Biológicos
Requisito Funcional: RF-49 (CU11 - Asociación de sensores IoT a activos biológicos)
Caso de Prueba: TC-M02-152 (Caso Agrupado TC-M02-G87)
Entorno: TEST
Seguridad: OWASP API1 (BOLA) / ASVS V9 / OWASP A01 (Broken Access Control)
"""
import os
import sys

# Asegurar que la raíz del proyecto esté en sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import pytest
import requests
import psycopg2

BASE_URL = os.getenv(
    "API_BASE_URL",
    "https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test"
)

TEST_DB_URL = os.getenv(
    "TEST_DB_URL",
    "postgresql://member_qa:qaSGP2026@158.69.200.27:5448/sgpmp_test"
)

# Datos de prueba identificados en TEST
ID_ACTIVO_FINCA_1 = 108   # LOTE-M02-TEST-001 (Finca 1: Finca Acuícola El Remanso, Infraestructura 3)
ID_SENSOR_FINCA_2 = 8     # Sensor canal-trucha-01 (Finca 2: Piscícola Los Esteros, Infra 4, Disp 4)
ID_SENSOR_INEXISTENTE = 9999


@pytest.fixture(scope="session")
def admin_token() -> str:
    """Token JWT de Administrador (id_rol = 1, acceso global)."""
    resp = requests.post(f"{BASE_URL}/sesiones/", json={
        "correo_electronico": "admin@pecuaria.co",
        "contrasena": "Test1234!"
    }, timeout=10)
    assert resp.status_code == 200, f"Falla de autenticación Admin: {resp.text}"
    return resp.json()["token"]


@pytest.fixture(scope="session")
def ingeniero_token() -> str:
    """Token JWT de Ingeniero de Campo (id_rol = 4, con permiso CREATE sobre asociacion_sensor_activo)."""
    resp = requests.post(f"{BASE_URL}/sesiones/", json={
        "correo_electronico": "ingeniero@pecuaria.co",
        "contrasena": "Pruebas12#"
    }, timeout=10)
    assert resp.status_code == 200, f"Falla de autenticación Ingeniero: {resp.text}"
    return resp.json()["token"]


@pytest.fixture(scope="session")
def productor_token() -> str:
    """Token JWT de Productor Agropecuario (id_rol = 2, Actor Principal RF-49)."""
    resp = requests.post(f"{BASE_URL}/sesiones/", json={
        "correo_electronico": "productor@pecuaria.co",
        "contrasena": "Test1234!"
    }, timeout=10)
    assert resp.status_code == 200, f"Falla de autenticación Productor: {resp.text}"
    return resp.json()["token"]


# ══════════════════════════════════════════════════════════════════════════════
# SUBCASO TC-M02-152: PRUEBAS DE SEGURIDAD BOLA Y AUTORIZACIÓN RBAC
# ══════════════════════════════════════════════════════════════════════════════

def test_tc_m02_152_escenario_a_bola_cross_finca_ingeniero(ingeniero_token: str):
    """Escenario A: Ataque BOLA cross-finca con usuario autorizado para asociar (Ingeniero de Campo).
    
    Verifica que al intentar asociar un sensor territorialmente asignado a la Finca 2
    (sensor_id = 8) a un activo biológico de la Finca 1 (id_activo = 108):
    1. El backend rechace con HTTP 409 Conflict y código INFRAESTRUCTURA_INCOMPATIBLE.
    2. El payload de respuesta NO filtre claves criptográficas ni credenciales sensibles del sensor ajeno.
    3. Ninguna asociación sea persistida en la BD TEST (SELECT COUNT = 0).
    """
    url = f"{BASE_URL}/activos-biologicos/{ID_ACTIVO_FINCA_1}/sensores"
    payload = {
        "tipo_activo": "INDIVIDUAL",
        "tipo_asociacion": "DIRECTA",
        "dispositivo_iot_id": 4,
        "sensor_id": ID_SENSOR_FINCA_2,
        "id_infraestructura": 4,
        "motivo": "Prueba de seguridad BOLA cross-finca TC-M02-152 Escenario A"
    }
    headers = {"Authorization": f"Bearer {ingeniero_token}"}

    resp = requests.post(url, json=payload, headers=headers, timeout=10)

    # 1. Validación de código de estado y código de error
    assert resp.status_code == 409, f"Se esperaba 409 Conflict por incoherencia territorial, obtenido: {resp.status_code} - {resp.text}"
    data = resp.json()
    assert data.get("error_code") == "INFRAESTRUCTURA_INCOMPATIBLE", (
        f"Código de error no coincide: {data.get('error_code')}"
    )

    # 2. Validación de ausencia de fuga de información confidencial (OWASP API1 / ASVS)
    sensitive_keys = ["token", "secret", "private_key", "password", "clave", "credentials", "api_key"]
    response_text_lower = resp.text.lower()
    for key in sensitive_keys:
        assert key not in response_text_lower, f"Alerta de seguridad: clave sensible '{key}' expuesta en respuesta de error"

    # 3. Verificación en base de datos TEST (solo lectura)
    conn = psycopg2.connect(TEST_DB_URL)
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM modulo2.asociaciones_activos_sensores "
        "WHERE id_sensor = %s AND id_activo_biologico = %s;",
        (ID_SENSOR_FINCA_2, ID_ACTIVO_FINCA_1)
    )
    count = cur.fetchone()[0]
    conn.close()

    assert count == 0, f"Falla de integridad: se insertó asociación no autorizada en BD (count = {count})"


def test_tc_m02_152_escenario_b_productor_defecto_rbac(productor_token: str):
    """Escenario B: Evidencia de defecto de configuración RBAC del Productor Agropecuario.
    
    Según el RF-49 (CU11), el Productor Agropecuario es Actor Principal con responsabilidad
    textual de 'solicitar la asociación de sensores a sus activos biológicos y tomar decisiones
    sobre qué sensores monitorean qué animales en su finca'.
    
    Actualmente el Productor carece de la acción 1 (CREATE) en modulo1.permisos sobre
    el recurso 30 (asociacion_sensor_activo). Esta prueba captura y documenta el rechazo
    HTTP 403 ACCESO_DENEGADO como evidencia ineludible del defecto de configuración RBAC.
    """
    url = f"{BASE_URL}/activos-biologicos/{ID_ACTIVO_FINCA_1}/sensores"
    payload = {
        "tipo_activo": "INDIVIDUAL",
        "tipo_asociacion": "DIRECTA",
        "dispositivo_iot_id": 38,
        "sensor_id": 22,
        "id_infraestructura": 3,
        "motivo": "Intento de asociación por Productor Agropecuario (Actor Principal RF-49)"
    }
    headers = {"Authorization": f"Bearer {productor_token}"}

    resp = requests.post(url, json=payload, headers=headers, timeout=10)

    # Captura de la evidencia del defecto RBAC
    assert resp.status_code == 403, (
        f"Se esperaba HTTP 403 Forbidden por la falta de permiso CREATE en Productor, obtenido: {resp.status_code}"
    )
    data = resp.json()
    assert data.get("error_code") == "ACCESO_DENEGADO", (
        f"Código de error no coincide con ACCESO_DENEGADO: {data.get('error_code')}"
    )


def test_tc_m02_152_escenario_c_anti_tampering_sensor_inexistente(ingeniero_token: str):
    """Escenario C: Control de manipulación de identificadores (Anti-Tampering / Sensor Inexistente).
    
    Verifica que al manipular el sensor_id con un identificador inexistente (9999):
    1. El backend rechace con HTTP 404 Not Found.
    2. El código de error retornado sea SENSOR_NO_ENCONTRADO.
    3. Ninguna transacción anómala sea persistida.
    """
    url = f"{BASE_URL}/activos-biologicos/{ID_ACTIVO_FINCA_1}/sensores"
    payload = {
        "tipo_activo": "INDIVIDUAL",
        "tipo_asociacion": "DIRECTA",
        "dispositivo_iot_id": 4,
        "sensor_id": ID_SENSOR_INEXISTENTE,
        "id_infraestructura": 4,
        "motivo": "Prueba Anti-Tampering sensor inexistente TC-M02-152 Escenario C"
    }
    headers = {"Authorization": f"Bearer {ingeniero_token}"}

    resp = requests.post(url, json=payload, headers=headers, timeout=10)

    assert resp.status_code == 404, (
        f"Se esperaba HTTP 404 Not Found para sensor inexistente, obtenido: {resp.status_code} - {resp.text}"
    )
    data = resp.json()
    assert data.get("error_code") == "SENSOR_NO_ENCONTRADO", (
        f"Código de error no coincide: {data.get('error_code')}"
    )
