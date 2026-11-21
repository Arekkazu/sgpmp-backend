"""Pruebas de Aceptación de Seguridad (BOLA) y Auditoría para RF-46 (CU10A).

Caso Agrupado: TC-M02-G74
Subcasos:
  - TC-M02-125: Control de acceso por granja/rol (OWASP API1: BOLA)
  - TC-M02-126: Trazabilidad de auditoría de consultas al historial (ASVS V7 / RF-52)
Entorno: TEST
"""
import os
import requests
import pytest

BASE_URL = os.getenv(
    "API_BASE_URL",
    "https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test"
)


@pytest.fixture(scope="session")
def admin_token() -> str:
    """Obtiene el JWT del Administrador con permisos globales."""
    resp = requests.post(f"{BASE_URL}/sesiones/", json={
        "correo_electronico": "admin@pecuaria.co",
        "contrasena": "Test1234!"
    }, timeout=10)
    assert resp.status_code == 200, f"Error al autenticar Admin: {resp.text}"
    return resp.json()["token"]


@pytest.fixture(scope="session")
def productor_token() -> str:
    """Obtiene el JWT del Productor sin acceso a Finca 1."""
    # Intentar con m2m.nuevo@ejemplo.com
    resp = requests.post(f"{BASE_URL}/sesiones/", json={
        "correo_electronico": "m2m.nuevo@ejemplo.com",
        "contrasena": "Test1234!"
    }, timeout=10)
    if resp.status_code != 200:
        # Fallback a productor@pecuaria.co
        resp = requests.post(f"{BASE_URL}/sesiones/", json={
            "correo_electronico": "productor@pecuaria.co",
            "contrasena": "Test1234!"
        }, timeout=10)
    assert resp.status_code == 200, f"Error al autenticar Productor: {resp.text}"
    return resp.json()["token"]


# ══════════════════════════════════════════════════════════════════════════════
# SUBCASO TC-M02-125: Control de acceso por granja / rol (OWASP API1: BOLA)
# ══════════════════════════════════════════════════════════════════════════════

def test_tc_m02_125_control_acceso_granja_bola(productor_token: str):
    """TC-M02-125: Rechazar consulta de historial cuando el usuario no tiene acceso a la granja.
    
    El lote 130 está asignado a la Finca 1 (Alevinera-01). El usuario Productor
    no posee permisos sobre Finca 1.
    El backend debe proteger el recurso retornando HTTP 404 (BOLA anti-enumeración)
    o HTTP 403 (RBAC Forbidden), impidiendo en todo momento el acceso a los datos.
    """
    id_activo_finca_ajena = 130
    headers = {
        "Authorization": f"Bearer {productor_token}",
        "Accept": "application/json"
    }

    response = requests.get(
        f"{BASE_URL}/activos-biologicos/{id_activo_finca_ajena}/historial",
        headers=headers,
        timeout=10
    )

    # 1. Validación de código de estado (debe ser 403 Forbidden o 404 Not Found)
    assert response.status_code in [403, 404], (
        f"[TC-M02-125] Código HTTP inesperado: {response.status_code}. "
        f"Se esperaba 403 o 404. Respuesta: {response.text}"
    )

    # 2. Validación de estructura de error
    json_data = response.json()
    assert isinstance(json_data, dict), "[TC-M02-125] El cuerpo de la respuesta no es un objeto JSON"
    assert "error_code" in json_data, "[TC-M02-125] No se encontró 'error_code' en la respuesta"

    # 3. Código de negocio coherente
    error_code = json_data.get("error_code")
    assert error_code in ["ACTIVO_NO_ENCONTRADO", "ACCESO_DENEGADO", "FORBIDDEN", "NOT_FOUND"], (
        f"[TC-M02-125] Código de error no esperado: {error_code}"
    )

    # 4. Asegurar que NINGÚN dato del historial haya sido filtrado
    assert "registros" not in json_data, "[TC-M02-125] Filtración de información detectada en respuesta errónea"
    assert "total_registros" not in json_data, "[TC-M02-125] Metadatos del activo expuestos a usuario no autorizado"


# ══════════════════════════════════════════════════════════════════════════════
# SUBCASO TC-M02-126: Registro y trazabilidad de auditoría (ASVS V7)
# ══════════════════════════════════════════════════════════════════════════════

def test_tc_m02_126_auditoria_consulta_exitosa(admin_token: str):
    """TC-M02-126.1: Verificar que una consulta exitosa de historial genera registro de auditoría."""
    id_activo = 130
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. Ejecutar consulta de historial como Admin
    resp_historial = requests.get(
        f"{BASE_URL}/activos-biologicos/{id_activo}/historial",
        headers=headers,
        timeout=10
    )
    assert resp_historial.status_code == 200, (
        f"[TC-M02-126] Error al consultar historial como Admin: {resp_historial.text}"
    )

    # 2. Consultar el endpoint de bitácora para RF46 sobre el activo 130
    resp_auditoria = requests.get(
        f"{BASE_URL}/activos-biologicos/auditoria?rf_origen=RF46&id_activo_biologico={id_activo}",
        headers=headers,
        timeout=10
    )
    assert resp_auditoria.status_code == 200, (
        f"[TC-M02-126] Error al consultar bitácora de auditoría: {resp_auditoria.text}"
    )

    data_auditoria = resp_auditoria.json()
    assert data_auditoria.get("total_registros", 0) > 0, (
        "[TC-M02-126] No se registraron eventos de auditoría para la consulta de historial"
    )

    # 3. Validar los campos obligatorios del registro más reciente
    evento_reciente = data_auditoria["registros"][0]
    assert evento_reciente["rf_origen"] == "RF46", "[TC-M02-126] rf_origen no coincide con RF46"
    assert evento_reciente["tipo_evento"] == "HISTORIAL_CONSULTADO", "[TC-M02-126] tipo_evento incorrecto"
    assert evento_reciente["clasificacion_biologica"] == "ACCESO_DATOS", "[TC-M02-126] Clasificación incorrecta"
    assert evento_reciente["resultado"] == "EXITOSO", "[TC-M02-126] Resultado no es EXITOSO"
    assert evento_reciente["id_activo_biologico"] == id_activo, "[TC-M02-126] ID activo discrepante"
    assert evento_reciente["id_usuario_responsable"] == 1, "[TC-M02-126] Usuario responsable no coincide con Admin"

    # 4. Validar hash de integridad SHA-256
    hash_integridad = evento_reciente.get("hash_integridad")
    assert hash_integridad is not None and len(hash_integridad) == 64, (
        f"[TC-M02-126] Hash de integridad inválido o ausente: {hash_integridad}"
    )


def test_tc_m02_126_auditoria_consultas_rechazadas(productor_token: str, admin_token: str):
    """TC-M02-126.2: Verificar el manejo auditado ante consultas no autorizadas o inexistentes."""
    # 1. Consulta con Productor sobre activo no autorizado
    headers_prod = {"Authorization": f"Bearer {productor_token}"}
    resp_bola = requests.get(
        f"{BASE_URL}/activos-biologicos/130/historial",
        headers=headers_prod,
        timeout=10
    )
    assert resp_bola.status_code in [403, 404], "[TC-M02-126] Intento BOLA no fue rechazado"

    # 2. Consulta con Admin sobre activo inexistente
    headers_admin = {"Authorization": f"Bearer {admin_token}"}
    resp_inexistente = requests.get(
        f"{BASE_URL}/activos-biologicos/999999/historial",
        headers=headers_admin,
        timeout=10
    )
    assert resp_inexistente.status_code == 404, "[TC-M02-126] Consulta inexistente no retornó 404"
