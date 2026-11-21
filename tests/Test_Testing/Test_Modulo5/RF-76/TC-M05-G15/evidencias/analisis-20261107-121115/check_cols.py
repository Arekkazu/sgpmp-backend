import requests, uuid
from dotenv import dotenv_values

env = dotenv_values(".env.test")
run_id = f"diag-col-{uuid.uuid4()}"
s = requests.Session()
s.headers.update({"X-Test-Run-Id": run_id, "X-Sandbox-Secret": env["TEST_SANDBOX_SECRET"], "X-Zona-Horaria": "America/Bogota"})
r = s.post(env["TEST_BASE_URL"] + "/sesiones/", json={"correo_electronico": env["TEST_ADMIN_EMAIL"], "contrasena": env["TEST_ADMIN_PASSWORD"]})
s.headers["Authorization"] = f"Bearer {r.json()['token']}"

q2 = s.post(env["TEST_BASE_URL"] + "/test-control/query", json={"query": "SELECT tipo::text, count(*) as c FROM modulo2.activos_biologicos GROUP BY tipo::text"})
print("q2 status:", q2.status_code, q2.text)

q3 = s.post(env["TEST_BASE_URL"] + "/test-control/query", json={"query": "SELECT id_estado, tipo::text, count(*) as c FROM modulo2.activos_biologicos GROUP BY id_estado, tipo::text ORDER BY id_estado, tipo::text"})
print("q3 status:", q3.status_code, q3.text)

s.delete(env["TEST_BASE_URL"] + f"/test-control/runs/{run_id}", headers={"X-Sandbox-Secret": env["TEST_SANDBOX_SECRET"]})
