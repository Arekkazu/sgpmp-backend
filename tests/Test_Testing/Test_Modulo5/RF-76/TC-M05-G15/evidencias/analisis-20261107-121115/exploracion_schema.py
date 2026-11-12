# | Fecha      | Nombre                   | Que se hizo                                               |
# |------------|--------------------------|-----------------------------------------------------------|
# | 2026-11-07 | Juan Sebastian Gutierrez | TC-M05-G15 FASE 1: script consulta esquema modulo2        |
"""Consulta esquema real de modulo2 en PostgreSQL."""
import os
import uuid
import requests
from pathlib import Path
from dotenv import dotenv_values

REPO_ROOT = Path(__file__).resolve().parents[7]
ENV_PATH = REPO_ROOT / ".env.test"
ENV = dotenv_values(ENV_PATH) if ENV_PATH.exists() else {}

def get_env(k: str) -> str:
    v = os.environ.get(k) or ENV.get(k)
    return v or ""

BASE_URL = get_env("TEST_BASE_URL").rstrip("/")
ADMIN_EMAIL = get_env("TEST_ADMIN_EMAIL")
ADMIN_PASSWORD = get_env("TEST_ADMIN_PASSWORD")
SANDBOX_SECRET = get_env("TEST_SANDBOX_SECRET")

def main():
    run_id = f"diag-schema-{uuid.uuid4()}"
    s = requests.Session()
    s.headers.update({
        "X-Test-Run-Id": run_id,
        "X-Sandbox-Secret": SANDBOX_SECRET,
        "X-Zona-Horaria": "America/Bogota",
    })
    try:
        r = s.post(f"{BASE_URL}/sesiones/", json={"correo_electronico": ADMIN_EMAIL, "contrasena": ADMIN_PASSWORD}, timeout=45)
        if r.status_code != 200:
            print("Login failed")
            return
        s.headers["Authorization"] = f"Bearer {r.json().get('token')}"
        
        # Consultar tablas de modulo2
        q1 = s.post(f"{BASE_URL}/test-control/query", json={"query": "SELECT table_name FROM information_schema.tables WHERE table_schema = 'modulo2'"}, timeout=45)
        print("Tablas modulo2:", [row['table_name'] for row in q1.json().get("rows", [])])
        
        # Columnas de estados_activos_biologicos
        q2 = s.post(f"{BASE_URL}/test-control/query", json={"query": "SELECT column_name, data_type FROM information_schema.columns WHERE table_schema = 'modulo2' AND table_name = 'estados_activos_biologicos'"}, timeout=45)
        print("Columnas estados_activos_biologicos:", q2.json().get("rows", []))

        # Columnas de activos_biologicos
        q3 = s.post(f"{BASE_URL}/test-control/query", json={"query": "SELECT column_name, data_type FROM information_schema.columns WHERE table_schema = 'modulo2' AND table_name = 'activos_biologicos'"}, timeout=45)
        print("Columnas activos_biologicos:", [c['column_name'] for c in q3.json().get("rows", [])])

    finally:
        s.delete(f"{BASE_URL}/test-control/runs/{run_id}", headers={"X-Sandbox-Secret": SANDBOX_SECRET}, timeout=45)
        s.close()

if __name__ == "__main__":
    main()

