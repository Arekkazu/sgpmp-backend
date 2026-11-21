import requests, uuid
from dotenv import dotenv_values

env = dotenv_values(".env.test")
run_id = f"diag-list3-{uuid.uuid4()}"
s = requests.Session()
s.headers.update({"X-Test-Run-Id": run_id, "X-Sandbox-Secret": env["TEST_SANDBOX_SECRET"], "X-Zona-Horaria": "America/Bogota"})
r = s.post(env["TEST_BASE_URL"] + "/sesiones/", json={"correo_electronico": env["TEST_ADMIN_EMAIL"], "contrasena": env["TEST_ADMIN_PASSWORD"]})
token = r.json()["token"]
s.headers["Authorization"] = f"Bearer {token}"

r1 = s.get(f"{env['TEST_BASE_URL']}/activos-biologicos?registros_por_pagina=100")
print("Status:", r1.status_code)
body = r1.json()
print("total_registros:", body.get("total_registros"))
registros = body.get("registros", [])
print("registros len:", len(registros))

estados_vistos = set()
tipos_vistos = set()
for reg in registros:
    estados_vistos.add((reg.get("id_estado"), reg.get("nombre_estado")))
    tipos_vistos.add(reg.get("tipo"))
    if reg.get("tipo") == "POBLACIONAL":
        print("POBLACIONAL:", reg.get("id_activo_biologico"), reg.get("nombre_estado"), reg.get("cantidad_actual"))

print("Estados vistos:", estados_vistos)
print("Tipos vistos:", tipos_vistos)

s.delete(env["TEST_BASE_URL"] + f"/test-control/runs/{run_id}", headers={"X-Sandbox-Secret": env["TEST_SANDBOX_SECRET"]})
