import requests, uuid
from dotenv import dotenv_values

env = dotenv_values(".env.test")
run_id = f"diag-list-{uuid.uuid4()}"
s = requests.Session()
s.headers.update({"X-Test-Run-Id": run_id, "X-Sandbox-Secret": env["TEST_SANDBOX_SECRET"], "X-Zona-Horaria": "America/Bogota"})
r = s.post(env["TEST_BASE_URL"] + "/sesiones/", json={"correo_electronico": env["TEST_ADMIN_EMAIL"], "contrasena": env["TEST_ADMIN_PASSWORD"]})
token = r.json()["token"]
s.headers["Authorization"] = f"Bearer {token}"

# Buscar AISLADOS (id_estado = 4)
resp_aislados = s.get(f"{env['TEST_BASE_URL']}/activos-biologicos?id_estado=4&por_pagina=10")
print("Activos id_estado=4 HTTP:", resp_aislados.status_code)
if resp_aislados.status_code == 200:
    items = resp_aislados.json().get("items", [])
    print("Aislados encontrados:", [(i['id_activo_biologico'], i['tipo'], i['nombre_estado']) for i in items[:5]])

# Buscar POBLACIONALES
resp_pob = s.get(f"{env['TEST_BASE_URL']}/activos-biologicos?tipo=POBLACIONAL&por_pagina=20")
print("Activos POBLACIONALES HTTP:", resp_pob.status_code)
if resp_pob.status_code == 200:
    items = resp_pob.json().get("items", [])
    print("POBLACIONALES total:", resp_pob.json().get("total"))
    for i in items[:10]:
        print(f"ID={i['id_activo_biologico']} | Estado={i.get('nombre_estado')}({i.get('id_estado')}) | detalle_poblacional={i.get('detalle_poblacional')}")

s.delete(env["TEST_BASE_URL"] + f"/test-control/runs/{run_id}", headers={"X-Sandbox-Secret": env["TEST_SANDBOX_SECRET"]})

