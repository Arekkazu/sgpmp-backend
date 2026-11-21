# | Fecha      | Nombre                   | Que se hizo                                               |
# |------------|--------------------------|-----------------------------------------------------------|
# | 2026-11-07 | Juan Sebastian Gutierrez | TC-M05-G15 FASE 1: debug queries candidatos               |
import os
import uuid
import json
import requests
from dotenv import dotenv_values

env = dotenv_values(".env.test")
BASE_URL = env["TEST_BASE_URL"].rstrip("/")
ADMIN_EMAIL = env["TEST_ADMIN_EMAIL"]
ADMIN_PASSWORD = env["TEST_ADMIN_PASSWORD"]
SANDBOX_SECRET = env["TEST_SANDBOX_SECRET"]

run_id = f"diag-debug-{uuid.uuid4()}"
s = requests.Session()
s.headers.update({"X-Test-Run-Id": run_id, "X-Sandbox-Secret": SANDBOX_SECRET, "X-Zona-Horaria": "America/Bogota"})
r = s.post(f"{BASE_URL}/sesiones/", json={"correo_electronico": ADMIN_EMAIL, "contrasena": ADMIN_PASSWORD}, timeout=45)
s.headers["Authorization"] = f"Bearer {r.json()['token']}"

try:
    for estado, nombre in [(5, "CERRADO"), (6, "BAJA"), (4, "AISLADO")]:
        sql = f"SELECT id_activo_biologico, tipo::text, id_estado, fecha_inicio_ciclo FROM modulo2.activos_biologicos WHERE id_estado = {estado} AND id_activo_biologico NOT IN (930, 900, 901, 825) LIMIT 5"
        resp = s.post(f"{BASE_URL}/test-control/query", json={"query": sql}, timeout=45)
        print(f"Estado {nombre} ({estado}) status: {resp.status_code}")
        print(resp.json())

    # Ver fases activas
    sql_gf = "SELECT id_gestion_fases, id_activo_biologico, es_activa FROM modulo2.gestiones_fases LIMIT 5"
    resp_gf = s.post(f"{BASE_URL}/test-control/query", json={"query": sql_gf}, timeout=45)
    print(f"Gestiones fases status: {resp_gf.status_code}")
    print(resp_gf.json())

    # Ver detalles poblacionales
    sql_dp = "SELECT id_detalle_activo_biologico_poblacional, id_activo_biologico, cantidad_actual FROM modulo2.detalles_activos_biologicos_poblacionales LIMIT 5"
    resp_dp = s.post(f"{BASE_URL}/test-control/query", json={"query": sql_dp}, timeout=45)
    print(f"Detalles poblacionales status: {resp_dp.status_code}")
    print(resp_dp.json())

finally:
    s.delete(f"{BASE_URL}/test-control/runs/{run_id}", headers={"X-Sandbox-Secret": SANDBOX_SECRET}, timeout=45)
    s.close()

