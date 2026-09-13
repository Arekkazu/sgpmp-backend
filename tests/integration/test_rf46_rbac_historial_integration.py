"""Pruebas de Aceptación RBAC, Prevención de Escalación y BOLA para RF-46 (CU10A).

Caso Agrupado: TC-M02-G75
Subcasos:
  - TC-M02-206: Rechazar escalación de privilegios vía usuario_consulta_id (OWASP API5)
  - TC-M02-207: Veterinario consulta historial de activo de su propia finca (Funcional)
  - TC-M02-208: Rechazar consulta de Veterinario sobre activo de finca ajena (OWASP BOLA)
  - TC-M02-209: Administrador consulta cualquier activo del sistema (Acceso Global)
Entorno: TEST
"""
import os
import requests
import pytest
import psycopg2

BASE_URL = os.getenv(
    "API_BASE_URL",
    "https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test"
)

DB_URL = os.getenv(
    "TEST_DB_URL",
    "postgresql://member_qa:qaSGP2026@158.69.200.27:5448/sgpmp_test"
)


def _login(correo: str, password: str = "Test1234!") -> str:
    resp = requests.post(f"{BASE_URL}/sesiones/", json={
        "correo_electronico": correo,
        "contrasena": password
    }, timeout=10)
    assert resp.status_code == 200, f"Fallo de autenticación para {correo}: {resp.text}"
    return resp.json()["token"]


@pytest.fixture(scope="session")
def admin_token() -> str:
    return _login("admin@pecuaria.co")


@pytest.fixture(scope="session")
def productor_token() -> str:
    return _login("m2m.nuevo@ejemplo.com")


@pytest.fixture(scope="session")
def veterinario_token() -> str:
    try:
        return _login("juan.carlos.qa133@sgpmp-test.com")
    except AssertionError:
        try:
            return _login("juan.carlos@email.com")
        except AssertionError:
            return _login("veterinario@pecuaria.co")


@pytest.fixture(scope="function")
def veterinario_con_finca_temporal():
    """Fixture de función para asignar temporalmente la Finca 4 al Veterinario (id_usuario = 3)
    y garantizar la restitución del propietario original al finalizar la prueba (Setup / Teardown).
    """
    id_finca_target = 4
    id_veterinario = 3  # juan.carlos.qa133@sgpmp-test.com

    conn = psycopg2.connect(DB_URL)
    conn.autocommit = False
    cur = conn.cursor()

    # 1. Consultar y resguardar id_usuario original de la finca
    cur.execute("SELECT id_usuario FROM modulo9.fincas WHERE id_finca = %s;", (id_finca_target,))
    row = cur.fetchone()
    assert row is not None, f"Finca {id_finca_target} no encontrada en modulo9.fincas"
    id_usuario_original = row[0]

    # 2. Consultar activo biológico perteneciente a la infraestructura de la finca
    cur.execute("""
        SELECT ab.id_activo_biologico 
        FROM modulo2.activos_biologicos ab
        JOIN modulo9.infraestructuras i ON ab.id_infraestructura = i.id_infraestructura
        WHERE i.id_finca = %s
        ORDER BY ab.id_activo_biologico ASC
        LIMIT 1;
    """, (id_finca_target,))
    row_activo = cur.fetchone()
    assert row_activo is not None, f"No se encontraron activos biológicos en la finca {id_finca_target}"
    id_activo = row_activo[0]

    try:
        # 3. SETUP: Asignar temporalmente la finca al Veterinario
        cur.execute("UPDATE modulo9.fincas SET id_usuario = %s WHERE id_finca = %s;", (id_veterinario, id_finca_target))
        conn.commit()

        yield {
            "id_finca": id_finca_target,
            "id_activo_biologico": id_activo,
            "id_usuario_original": id_usuario_original
        }
    finally:
        # 4. TEARDOWN: Restaurar siempre el propietario original de la finca
        try:
            cur.execute("UPDATE modulo9.fincas SET id_usuario = %s WHERE id_finca = %s;", (id_usuario_original, id_finca_target))
            conn.commit()

            # Verificación estricta de restitución
            cur.execute("SELECT id_usuario FROM modulo9.fincas WHERE id_finca = %s;", (id_finca_target,))
            restored = cur.fetchone()[0]
            assert restored == id_usuario_original, (
                f"[TEARDOWN ERROR] No se restauró la finca {id_finca_target}. Esperado: {id_usuario_original}, Actual: {restored}"
            )
        finally:
            cur.close()
            conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# SUBCASO TC-M02-206: Rechazar escalación vía usuario_consulta_id (OWASP API5)
# ══════════════════════════════════════════════════════════════════════════════

def test_tc_m02_206_rechazar_escalacion_usuario_consulta_id(productor_token: str):
    """TC-M02-206: El Productor intenta acceder a lote 130 inyectando ?usuario_consulta_id=1.
    
    El backend debe ignorar el parámetro y aplicar el alcance real del Productor,
    rechazando la solicitud con HTTP 403 o 404. Nunca debe retornar 200 OK.
    """
    id_activo_finca_ajena = 130
    id_admin = 1
    headers = {
        "Authorization": f"Bearer {productor_token}",
        "Accept": "application/json"
    }

    response = requests.get(
        f"{BASE_URL}/activos-biologicos/{id_activo_finca_ajena}/historial?usuario_consulta_id={id_admin}",
        headers=headers,
        timeout=10
    )

    # Aserción principal de seguridad: NUNCA debe permitir acceso (no debe retornar 200)
    assert response.status_code in [403, 404], (
        f"[TC-M02-206] Vulnerabilidad de escalación detectada! Código: {response.status_code}. "
        f"Respuesta: {response.text}"
    )

    json_data = response.json()
    assert "registros" not in json_data, "[TC-M02-206] Exposición de datos del historial"
    assert json_data.get("error_code") in ["ACTIVO_NO_ENCONTRADO", "ACCESO_DENEGADO", "FORBIDDEN", "NOT_FOUND"]


# ══════════════════════════════════════════════════════════════════════════════
# SUBCASO TC-M02-207: Veterinario consulta activo de su propia finca
# ══════════════════════════════════════════════════════════════════════════════

def test_tc_m02_207_veterinario_consulta_propia_finca(veterinario_token: str, veterinario_con_finca_temporal: dict):
    """TC-M02-207: El Veterinario consulta un activo dentro de su ámbito autorizado (propia finca)."""
    headers = {
        "Authorization": f"Bearer {veterinario_token}",
        "Accept": "application/json"
    }

    id_activo_propio = veterinario_con_finca_temporal["id_activo_biologico"]
    resp_historial = requests.get(
        f"{BASE_URL}/activos-biologicos/{id_activo_propio}/historial",
        headers=headers,
        timeout=10
    )
    assert resp_historial.status_code == 200, (
        f"[TC-M02-207] Error consultando historial de activo propio: {resp_historial.text}"
    )
    historial = resp_historial.json()
    assert "registros" in historial, "[TC-M02-207] Campo 'registros' no encontrado en la respuesta"
    assert "total_registros" in historial, "[TC-M02-207] Campo 'total_registros' no encontrado"
    assert historial["id_activo_biologico"] == id_activo_propio
    assert isinstance(historial["registros"], list)


# ══════════════════════════════════════════════════════════════════════════════
# SUBCASO TC-M02-208: Veterinario consulta activo de finca ajena (OWASP BOLA)
# ══════════════════════════════════════════════════════════════════════════════

def test_tc_m02_208_veterinario_rechazo_finca_ajena_bola(veterinario_token: str):
    """TC-M02-208: El Veterinario no puede consultar activos de fincas no asignadas."""
    id_activo_finca_ajena = 130
    headers = {
        "Authorization": f"Bearer {veterinario_token}",
        "Accept": "application/json"
    }

    response = requests.get(
        f"{BASE_URL}/activos-biologicos/{id_activo_finca_ajena}/historial",
        headers=headers,
        timeout=10
    )

    assert response.status_code in [403, 404], (
        f"[TC-M02-208] Fallo de aislamiento BOLA para Veterinario. "
        f"Código obtenido: {response.status_code}"
    )
    assert "registros" not in response.json(), "[TC-M02-208] Fuga de historial hacia Veterinario"


# ══════════════════════════════════════════════════════════════════════════════
# SUBCASO TC-M02-209: Administrador consulta cualquier activo (Acceso Global)
# ══════════════════════════════════════════════════════════════════════════════

def test_tc_m02_209_admin_consulta_activo_global(admin_token: str):
    """TC-M02-209: El Administrador puede consultar el historial de cualquier activo."""
    id_activo = 130
    headers = {
        "Authorization": f"Bearer {admin_token}",
        "Accept": "application/json"
    }

    response = requests.get(
        f"{BASE_URL}/activos-biologicos/{id_activo}/historial",
        headers=headers,
        timeout=10
    )

    assert response.status_code == 200, f"[TC-M02-209] Administrador no pudo consultar activo: {response.text}"
    data = response.json()
    assert data["id_activo_biologico"] == id_activo
    assert "registros" in data
    assert "total_registros" in data
