import requests, uuid
from dotenv import dotenv_values

env = dotenv_values(".env.test")
run_id = f"diag-pob462-{uuid.uuid4()}"
s = requests.Session()
s.headers.update({"X-Test-Run-Id": run_id, "X-Sandbox-Secret": env["TEST_SANDBOX_SECRET"], "X-Zona-Horaria": "America/Bogota"})
r = s.post(env["TEST_BASE_URL"] + "/sesiones/", json={"correo_electronico": env["TEST_ADMIN_EMAIL"], "contrasena": env["TEST_ADMIN_PASSWORD"]})
s.headers["Authorization"] = f"Bearer {r.json()['token']}"

try:
    # 1. Leer 462
    r_462 = s.get(f"{env['TEST_BASE_URL']}/activos-biologicos/462")
    print("Activo 462:", r_462.status_code, r_462.json())
    
    # 2. Leer fases de 462
    r_fases = s.get(f"{env['TEST_BASE_URL']}/activos-biologicos/462/fases")
    print("Fases 462:", r_fases.status_code, r_fases.json())

    # 3. Listar ciclos disponibles para 462
    r_ciclos = s.get(f"{env['TEST_BASE_URL']}/activos-biologicos/462/ciclos-productivos")
    print("Ciclos 462:", r_ciclos.status_code, r_ciclos.json())

    # 4. Probar abrir fase en 462 dentro del sandbox
    ciclos = [c for c in r_ciclos.json().get("items", []) if c.get("fases")]
    if ciclos:
        id_c = ciclos[0]["id_ciclo_productivo"]
        print(f"Intentando abrir fase con ciclo {id_c} en 462...")
        rf = s.post(f"{env['TEST_BASE_URL']}/activos-biologicos/462/fases", json={
            "id_ciclo_productiva": id_c,
            "motivo_cambio": "Prueba exploratoria TC-M05-G15",
        })
        print("Respuesta abrir fase:", rf.status_code, rf.json())
        
        # Releer 462 tras abrir fase
        r_releer = s.get(f"{env['TEST_BASE_URL']}/activos-biologicos/462")
        print("Relectura 462:", r_releer.status_code, r_releer.json())

finally:
    s.delete(env["TEST_BASE_URL"] + f"/test-control/runs/{run_id}", headers={"X-Sandbox-Secret": env["TEST_SANDBOX_SECRET"]})
    s.close()

