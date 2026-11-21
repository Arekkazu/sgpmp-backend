import requests, uuid
from dotenv import dotenv_values

env = dotenv_values(".env.test")
run_id = f"diag-check9-{uuid.uuid4()}"
s = requests.Session()
s.headers.update({"X-Test-Run-Id": run_id, "X-Sandbox-Secret": env["TEST_SANDBOX_SECRET"], "X-Zona-Horaria": "America/Bogota"})
r = s.post(env["TEST_BASE_URL"] + "/sesiones/", json={"correo_electronico": env["TEST_ADMIN_EMAIL"], "contrasena": env["TEST_ADMIN_PASSWORD"]})
token = r.json()["token"]
s.headers["Authorization"] = f"Bearer {token}"

try:
    for aid in [9, 20, 462]:
        det = s.get(f"{env['TEST_BASE_URL']}/activos-biologicos/{aid}").json()
        dp = det.get("detalle_poblacional")
        fases = s.get(f"{env['TEST_BASE_URL']}/activos-biologicos/{aid}/fases").json().get("fases", [])
        activas = [f for f in fases if f.get("es_activa")]
        ciclos = s.get(f"{env['TEST_BASE_URL']}/activos-biologicos/{aid}/ciclos-productivos").json().get("items", [])
        ciclos_con_fases = [c for c in ciclos if c.get("fases")]
        print(f"Activo {aid}: Estado={det.get('nombre_estado')}({det.get('id_estado')}) | Tipo={det.get('tipo')} | cant_actual={dp.get('cantidad_actual') if dp else None} | fases_activas={len(activas)} | ciclos_con_fases={len(ciclos_con_fases)}")

finally:
    s.delete(env["TEST_BASE_URL"] + f"/test-control/runs/{run_id}", headers={"X-Sandbox-Secret": env["TEST_SANDBOX_SECRET"]})
    s.close()

