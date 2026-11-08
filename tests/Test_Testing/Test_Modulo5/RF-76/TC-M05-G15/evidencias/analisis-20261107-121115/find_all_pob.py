import requests, uuid
from dotenv import dotenv_values

env = dotenv_values(".env.test")
run_id = f"diag-allpob-{uuid.uuid4()}"
s = requests.Session()
s.headers.update({"X-Test-Run-Id": run_id, "X-Sandbox-Secret": env["TEST_SANDBOX_SECRET"], "X-Zona-Horaria": "America/Bogota"})
r = s.post(env["TEST_BASE_URL"] + "/sesiones/", json={"correo_electronico": env["TEST_ADMIN_EMAIL"], "contrasena": env["TEST_ADMIN_PASSWORD"]})
token = r.json()["token"]
s.headers["Authorization"] = f"Bearer {token}"

try:
    cero_cands = []
    null_cands = []
    for pag in [1, 2]:
        resp = s.get(f"{env['TEST_BASE_URL']}/activos-biologicos?tipo=POBLACIONAL&page_size=100&pagina={pag}")
        regs = resp.json().get("registros", [])
        for reg in regs:
            aid = reg["id_activo_biologico"]
            det = s.get(f"{env['TEST_BASE_URL']}/activos-biologicos/{aid}").json()
            dp = det.get("detalle_poblacional")
            cant = dp.get("cantidad_actual") if dp else None
            st = det.get("id_estado")
            st_name = det.get("nombre_estado")
            if cant == 0:
                cero_cands.append((aid, st, st_name))
            elif cant is None:
                null_cands.append((aid, st, st_name))
    print(f"Candidatos cant=0 ({len(cero_cands)}):", cero_cands)
    print(f"Candidatos cant=None ({len(null_cands)}):", null_cands)

finally:
    s.delete(env["TEST_BASE_URL"] + f"/test-control/runs/{run_id}", headers={"X-Sandbox-Secret": env["TEST_SANDBOX_SECRET"]})
    s.close()

