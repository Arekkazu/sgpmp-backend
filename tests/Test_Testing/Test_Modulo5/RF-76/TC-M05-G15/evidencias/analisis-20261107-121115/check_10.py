import requests, uuid
from dotenv import dotenv_values

env = dotenv_values(".env.test")
run_id = f"diag-check10-{uuid.uuid4()}"
s = requests.Session()
s.headers.update({"X-Test-Run-Id": run_id, "X-Sandbox-Secret": env["TEST_SANDBOX_SECRET"], "X-Zona-Horaria": "America/Bogota"})
r = s.post(env["TEST_BASE_URL"] + "/sesiones/", json={"correo_electronico": env["TEST_ADMIN_EMAIL"], "contrasena": env["TEST_ADMIN_PASSWORD"]})
s.headers["Authorization"] = f"Bearer {r.json()['token']}"

q = s.post(env["TEST_BASE_URL"] + "/test-control/query", json={"query": "SELECT id_activo_biologico, tipo::text, id_estado FROM modulo2.activos_biologicos WHERE id_activo_biologico = 10"})
print("Activo 10:", q.json())

q2 = s.post(env["TEST_BASE_URL"] + "/test-control/query", json={"query": "SELECT id_activo_biologico, tipo::text, id_estado FROM modulo2.activos_biologicos WHERE id_estado = 6"})
print("Activos id_estado=6:", q2.json())

s.delete(env["TEST_BASE_URL"] + f"/test-control/runs/{run_id}", headers={"X-Sandbox-Secret": env["TEST_SANDBOX_SECRET"]})

