import requests, uuid
from dotenv import dotenv_values

env = dotenv_values(".env.test")
run_id = f"diag-dp-{uuid.uuid4()}"
s = requests.Session()
s.headers.update({"X-Test-Run-Id": run_id, "X-Sandbox-Secret": env["TEST_SANDBOX_SECRET"], "X-Zona-Horaria": "America/Bogota"})
r = s.post(env["TEST_BASE_URL"] + "/sesiones/", json={"correo_electronico": env["TEST_ADMIN_EMAIL"], "contrasena": env["TEST_ADMIN_PASSWORD"]})
s.headers["Authorization"] = f"Bearer {r.json()['token']}"

q = s.post(env["TEST_BASE_URL"] + "/test-control/query", json={"query": "SELECT count(*) as total FROM modulo2.detalles_activos_biologicos_poblacionales"})
print("Total detalles poblacionales:", q.json())

# Ver si hay alguno con cantidad_actual
q2 = s.post(env["TEST_BASE_URL"] + "/test-control/query", json={"query": "SELECT id_activo_biologico, cantidad_actual, cantidad_inicial FROM modulo2.detalles_activos_biologicos_poblacionales LIMIT 10"})
print("Muestra detalles:", q2.json())

s.delete(env["TEST_BASE_URL"] + f"/test-control/runs/{run_id}", headers={"X-Sandbox-Secret": env["TEST_SANDBOX_SECRET"]})

