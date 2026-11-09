# | Fecha      | Nombre                   | Que se hizo                                               |
# |------------|--------------------------|-----------------------------------------------------------|
# | 2026-11-07 | Juan Sebastian Gutierrez | TC-M05-G15 FASE 1: ejecucion T3 Camino Feliz Activo 853   |
import os
import uuid
import json
import time
from datetime import datetime, timezone, timedelta
import requests
from dotenv import dotenv_values

env = dotenv_values(".env.test")
BASE_URL = env["TEST_BASE_URL"].rstrip("/")
ADMIN_EMAIL = env["TEST_ADMIN_EMAIL"]
ADMIN_PASSWORD = env["TEST_ADMIN_PASSWORD"]
SANDBOX_SECRET = env["TEST_SANDBOX_SECRET"]

ZONA_BOGOTA = timezone(timedelta(hours=-5))
hoy_bogota = datetime.now(ZONA_BOGOTA).date().isoformat()
hora_unica = datetime.now(ZONA_BOGOTA).strftime("%H:%M:%S")

def main():
    run_id = f"tc-m05-g15-t3-feliz-{uuid.uuid4()}"
    s = requests.Session()
    s.headers.update({
        "X-Test-Run-Id": run_id,
        "X-Sandbox-Secret": SANDBOX_SECRET,
        "X-Zona-Horaria": "America/Bogota",
    })

    print(f"=== T3: Camino Feliz sobre Activo 853 [run_id={run_id}] ===")
    try:
        # 1. Login
        t0 = time.perf_counter()
        r_login = s.post(f"{BASE_URL}/sesiones/", json={"correo_electronico": ADMIN_EMAIL, "contrasena": ADMIN_PASSWORD}, timeout=45)
        assert r_login.status_code == 200, f"Login fallo: HTTP {r_login.status_code}"
        token = r_login.json()["token"]
        s.headers["Authorization"] = f"Bearer {token}"
        print(f"[OK] Login exitoso en {round((time.perf_counter()-t0)*1000, 1)} ms")

        # 2. Conteo base antes de cualquier accion
        r_conteo_base = s.get(f"{BASE_URL}/suministros/medicamentos?id_activo_biologico=853")
        assert r_conteo_base.status_code == 200, f"Conteo base fallo: HTTP {r_conteo_base.status_code}"
        conteo_base = r_conteo_base.json().get("total")
        print(f"[OK] Conteo base medicamentos Activo 853: {conteo_base}")

        # 3. Preparacion de fase en Activo 853
        r_ciclos = s.get(f"{BASE_URL}/activos-biologicos/853/ciclos-productivos")
        assert r_ciclos.status_code == 200, f"Listar ciclos fallo: HTTP {r_ciclos.status_code}"
        con_fases = [c for c in r_ciclos.json().get("items", []) if c.get("fases")]
        assert len(con_fases) > 0, "No hay ciclos con fases para especie de 853"
        id_ciclo = con_fases[0]["id_ciclo_productivo"]

        r_fase = s.post(f"{BASE_URL}/activos-biologicos/853/fases", json={
            "id_ciclo_productiva": id_ciclo,
            "motivo_cambio": "TC-M05-G15: apertura de fase sandbox T3 camino feliz",
        })
        assert r_fase.status_code == 201, f"Abrir fase fallo: HTTP {r_fase.status_code}: {r_fase.text}"
        print(f"[OK] Fase abierta en Activo 853 (id_ciclo={id_ciclo})")

        # 4. POST /suministros/medicamentos valido
        payload = {
            "id_activo_biologico": 853,
            "nombre_medicamento": "Oxitetraciclina",
            "fecha_aplicacion": hoy_bogota,
            "hora_aplicacion": hora_unica[:5],  # HH:MM
            "via_administracion": "INTRAMUSCULAR",
            "dosis_aplicada": 10,
            "unidad_dosis": "ml",
            "periodo_retiro_dias": 0,
            "motivo_aplicacion": "Tratamiento de infección respiratoria",
            "costo_unitario": 500,
            "nombre_veterinario": "Dr. Pérez",
        }
        t_post = time.perf_counter()
        r_post = s.post(f"{BASE_URL}/suministros/medicamentos", json=payload)
        lat_post = round((time.perf_counter() - t_post) * 1000, 1)

        print(f"[POST /suministros/medicamentos] HTTP {r_post.status_code} en {lat_post} ms")
        print(f"Respuesta JSON:\n{json.dumps(r_post.json(), indent=2, ensure_ascii=False)}")

        assert r_post.status_code == 201, f"Esperado 201, recibido {r_post.status_code}: {r_post.text}"
        data = r_post.json()
        med = data.get("medicamento", {})
        id_med = med.get("id_registro_medicamento")
        estado_reg = med.get("estado_registro")
        print(f"[OK] Medicamento registrado con id={id_med}, estado_registro={estado_reg}")

        # 5. Conteo dentro del sandbox (debe ser base + 1)
        r_conteo_sb = s.get(f"{BASE_URL}/suministros/medicamentos?id_activo_biologico=853")
        conteo_sb = r_conteo_sb.json().get("total")
        print(f"[OK] Conteo dentro del sandbox: {conteo_sb} (base + 1)")
        assert conteo_sb == conteo_base + 1, f"Conteo en sandbox debio ser {conteo_base+1}, fue {conteo_sb}"

    finally:
        # 6. Teardown
        del_resp = s.delete(f"{BASE_URL}/test-control/runs/{run_id}", headers={"X-Sandbox-Secret": SANDBOX_SECRET})
        print(f"[TEARDOWN] status={del_resp.status_code}, body={del_resp.text}")
        assert del_resp.status_code == 200, f"Teardown fallo con HTTP {del_resp.status_code}"
        assert "Rollback exitoso" in del_resp.json().get("status", "")
        s.close()

    # 7. Verificacion de inocuidad en nueva conexion independiente
    run_id_check = f"tc-m05-g15-check-{uuid.uuid4()}"
    s2 = requests.Session()
    s2.headers.update({
        "X-Test-Run-Id": run_id_check,
        "X-Sandbox-Secret": SANDBOX_SECRET,
        "X-Zona-Horaria": "America/Bogota",
    })
    try:
        r_login2 = s2.post(f"{BASE_URL}/sesiones/", json={"correo_electronico": ADMIN_EMAIL, "contrasena": ADMIN_PASSWORD}, timeout=45)
        s2.headers["Authorization"] = f"Bearer {r_login2.json()['token']}"
        r_final = s2.get(f"{BASE_URL}/suministros/medicamentos?id_activo_biologico=853")
        conteo_final = r_final.json().get("total")
        print(f"[INOCUIDAD] Conteo final tras rollback: {conteo_final} (conteo base: {conteo_base})")
        assert conteo_final == conteo_base, f"Fallo de inocuidad: base={conteo_base}, final={conteo_final}"
        print("[EXITO TOTAL T3] Camino feliz verificado y base de datos 100% inocua.")
    finally:
        s2.delete(f"{BASE_URL}/test-control/runs/{run_id_check}", headers={"X-Sandbox-Secret": SANDBOX_SECRET})
        s2.close()

if __name__ == "__main__":
    main()

