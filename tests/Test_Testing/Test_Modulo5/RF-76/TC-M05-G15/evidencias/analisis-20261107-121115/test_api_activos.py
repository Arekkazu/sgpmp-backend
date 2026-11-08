import requests, uuid
from dotenv import dotenv_values

env = dotenv_values(".env.test")
run_id = f"diag-api-{uuid.uuid4()}"
s = requests.Session()
s.headers.update({"X-Test-Run-Id": run_id, "X-Sandbox-Secret": env["TEST_SANDBOX_SECRET"], "X-Zona-Horaria": "America/Bogota"})
r = s.post(env["TEST_BASE_URL"] + "/sesiones/", json={"correo_electronico": env["TEST_ADMIN_EMAIL"], "contrasena": env["TEST_ADMIN_PASSWORD"]})
token = r.json()["token"]
s.headers["Authorization"] = f"Bearer {token}"

for aid in [10, 12, 2, 4, 853, 5]:
    resp = s.get(f"{env['TEST_BASE_URL']}/activos-biologicos/{aid}")
    print(f"Activo {aid}: HTTP {resp.status_code}")
    if resp.status_code == 200:
        d = resp.json()
        print(f"  Tipo={d.get('tipo')} | Estado={d.get('nombre_estado')}({d.get('id_estado')}) | CicloInicio={d.get('fecha_inicio_ciclo')}")
        # ver fases
        rf = s.get(f"{env['TEST_BASE_URL']}/activos-biologicos/{aid}/fases")
        fases = rf.json().get('fases', []) if rf.status_code == 200 else []
        activas = [f for f in fases if f.get('es_activa')]
        print(f"  Fases activas: {len(activas)}")

s.delete(env["TEST_BASE_URL"] + f"/test-control/runs/{run_id}", headers={"X-Sandbox-Secret": env["TEST_SANDBOX_SECRET"]})

