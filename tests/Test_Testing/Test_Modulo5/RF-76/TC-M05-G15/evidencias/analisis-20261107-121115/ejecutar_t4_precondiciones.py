# | Fecha      | Nombre                   | Que se hizo                                               |
# |------------|--------------------------|-----------------------------------------------------------|
# | 2026-11-07 | Juan Sebastian Gutierrez | TC-M05-G15 FASE 1: ejecucion T4 Precondiciones            |
"""
Ejecuta las pruebas reales de cada precondicion de T4 en corridas sandbox estrictamente secuenciales.
Escenarios:
1) INACTIVO (Activo 2)
2) CERRADO (Activo 12)
3) BAJA (Activo 10)
4) SIN_CICLO (Activo 853 sin abrir fase)
5) ID_INEXISTENTE (Id 999999999)
6) POBLACIONAL_CANTIDAD_0 (Activo 9 con fase abierta en sandbox, dosis=100)
7) POBLACIONAL_CANTIDAD_NULL (Activo 462 con fase abierta en sandbox, dosis=100)
8) AISLADO (Activo 812, diagnostico)
"""
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

def correr_escenario(nombre_escenario: str, id_activo: int, dosis: float = 10.0, hora_str: str = "10:00", abrir_fase: bool = False) -> dict:
    run_id = f"tc-m05-g15-t4-{nombre_escenario.lower()}-{uuid.uuid4()}"
    s = requests.Session()
    s.headers.update({
        "X-Test-Run-Id": run_id,
        "X-Sandbox-Secret": SANDBOX_SECRET,
        "X-Zona-Horaria": "America/Bogota",
    })

    print(f"\n=======================================================")
    print(f"--- Iniciando Escenario: {nombre_escenario} [Activo {id_activo}] ---")
    print(f"Run ID: {run_id}")

    resultado = {
        "escenario": nombre_escenario,
        "id_activo": id_activo,
        "run_id": run_id,
        "dosis": dosis,
        "hora": hora_str,
    }

    try:
        # 1. Login unico
        r_login = s.post(f"{BASE_URL}/sesiones/", json={"correo_electronico": ADMIN_EMAIL, "contrasena": ADMIN_PASSWORD}, timeout=45)
        assert r_login.status_code == 200, f"Login fallo: {r_login.status_code}"
        token = r_login.json()["token"]
        s.headers["Authorization"] = f"Bearer {token}"

        # 2. Conteo base de medicamentos y estado del activo (si existe)
        conteo_base = None
        estado_inicial = None
        if id_activo != 999999999:
            r_act = s.get(f"{BASE_URL}/activos-biologicos/{id_activo}")
            if r_act.status_code == 200:
                act_data = r_act.json()
                estado_inicial = (act_data.get("id_estado"), act_data.get("nombre_estado"))
                resultado["estado_inicial"] = estado_inicial

            r_conteo = s.get(f"{BASE_URL}/suministros/medicamentos?id_activo_biologico={id_activo}")
            if r_conteo.status_code == 200:
                conteo_base = r_conteo.json().get("total")
                resultado["conteo_base"] = conteo_base

        # 3. Abrir fase si aplica
        if abrir_fase:
            r_ciclos = s.get(f"{BASE_URL}/activos-biologicos/{id_activo}/ciclos-productivos")
            ciclos = [c for c in r_ciclos.json().get("items", []) if c.get("fases")]
            assert len(ciclos) > 0, f"No hay ciclos con fases para activo {id_activo}"
            id_ciclo = ciclos[0]["id_ciclo_productivo"]
            r_fase = s.post(f"{BASE_URL}/activos-biologicos/{id_activo}/fases", json={
                "id_ciclo_productiva": id_ciclo,
                "motivo_cambio": f"TC-M05-G15 FASE 1: apertura fase sandbox {nombre_escenario}",
            })
            print(f"Apertura de fase: HTTP {r_fase.status_code}")
            assert r_fase.status_code == 201, f"Fallo abrir fase: {r_fase.text}"
            resultado["fase_abierta"] = id_ciclo

        # 4. Enviar POST /suministros/medicamentos
        payload = {
            "id_activo_biologico": id_activo,
            "nombre_medicamento": "Oxitetraciclina",
            "fecha_aplicacion": hoy_bogota,
            "hora_aplicacion": hora_str,
            "via_administracion": "INTRAMUSCULAR",
            "dosis_aplicada": dosis,
            "unidad_dosis": "ml",
            "periodo_retiro_dias": 0,
            "motivo_aplicacion": "Tratamiento de infección respiratoria",
            "costo_unitario": 500,
            "nombre_veterinario": "Dr. Pérez",
        }
        resultado["payload_enviado"] = payload

        t0 = time.perf_counter()
        r_post = s.post(f"{BASE_URL}/suministros/medicamentos", json=payload)
        lat_ms = round((time.perf_counter() - t0) * 1000, 1)

        resultado["http_status"] = r_post.status_code
        resultado["latencia_ms"] = lat_ms
        try:
            body_json = r_post.json()
        except Exception:
            body_json = {"raw": r_post.text}
        resultado["response_body"] = body_json
        resultado["error_code"] = body_json.get("error_code")
        resultado["message"] = body_json.get("message")
        resultado["fields"] = body_json.get("fields")

        print(f"[RESPUESTA POST] HTTP {r_post.status_code} | error_code={resultado['error_code']} en {lat_ms} ms")
        print(f"Mensaje: {resultado['message']}")
        if resultado["fields"]:
            print(f"Fields: {resultado['fields']}")

        # 5. Conteo dentro del sandbox (debe seguir siendo igual al base)
        if conteo_base is not None:
            r_conteo_sb = s.get(f"{BASE_URL}/suministros/medicamentos?id_activo_biologico={id_activo}")
            conteo_sb = r_conteo_sb.json().get("total") if r_conteo_sb.status_code == 200 else None
            resultado["conteo_en_sandbox"] = conteo_sb
            print(f"Conteo medicamentos en sandbox: {conteo_sb} (base={conteo_base})")

        # 6. Verificar que el estado del activo no cambio
        if id_activo != 999999999:
            r_act_post = s.get(f"{BASE_URL}/activos-biologicos/{id_activo}")
            if r_act_post.status_code == 200:
                act_post = r_act_post.json()
                estado_post = (act_post.get("id_estado"), act_post.get("nombre_estado"))
                resultado["estado_post_post"] = estado_post
                print(f"Estado del activo antes: {estado_inicial} | tras intento: {estado_post}")

    finally:
        # 7. Teardown obligatorio
        del_r = s.delete(f"{BASE_URL}/test-control/runs/{run_id}", headers={"X-Sandbox-Secret": SANDBOX_SECRET})
        print(f"[TEARDOWN] status={del_r.status_code}")
        assert del_r.status_code == 200, f"Teardown fallo con HTTP {del_r.status_code}"
        assert "Rollback exitoso" in del_r.json().get("status", "")
        resultado["teardown_status"] = del_r.status_code
        resultado["teardown_body"] = del_r.json()
        s.close()

    # 8. Verificacion de inocuidad final tras teardown
    if conteo_base is not None:
        run_id_verif = f"tc-m05-g15-verif-{uuid.uuid4()}"
        s_v = requests.Session()
        s_v.headers.update({
            "X-Test-Run-Id": run_id_verif,
            "X-Sandbox-Secret": SANDBOX_SECRET,
            "X-Zona-Horaria": "America/Bogota",
        })
        try:
            r_lv = s_v.post(f"{BASE_URL}/sesiones/", json={"correo_electronico": ADMIN_EMAIL, "contrasena": ADMIN_PASSWORD}, timeout=45)
            s_v.headers["Authorization"] = f"Bearer {r_lv.json()['token']}"
            r_cf = s_v.get(f"{BASE_URL}/suministros/medicamentos?id_activo_biologico={id_activo}")
            conteo_final = r_cf.json().get("total") if r_cf.status_code == 200 else None
            resultado["conteo_final"] = conteo_final
            print(f"[INOCUIDAD] Conteo final tras rollback: {conteo_final} (base={conteo_base})")
            assert conteo_final == conteo_base, f"Fallo inocuidad: base={conteo_base}, final={conteo_final}"
        finally:
            s_v.delete(f"{BASE_URL}/test-control/runs/{run_id_verif}", headers={"X-Sandbox-Secret": SANDBOX_SECRET})
            s_v.close()

    return resultado

def main():
    escenarios = [
        ("INACTIVO", 2, 10.0, "10:01", False),
        ("CERRADO", 12, 10.0, "10:02", False),
        ("BAJA", 10, 10.0, "10:03", False),
        ("SIN_CICLO", 853, 10.0, "10:04", False),
        ("ID_INEXISTENTE", 999999999, 10.0, "10:05", False),
        ("POBLACIONAL_CANTIDAD_0", 9, 100.0, "10:06", True),
        ("POBLACIONAL_CANTIDAD_NULL", 462, 100.0, "10:07", True),
        ("AISLADO", 812, 10.0, "10:08", False),
    ]

    resultados_totales = []
    for nombre, aid, dos, hora, abrir_f in escenarios:
        res = correr_escenario(nombre, aid, dos, hora, abrir_f)
        resultados_totales.append(res)
        time.sleep(1) # pausa preventiva

    # Guardar trazas en JSON en la carpeta de evidencias
    archivo_res = Path(__file__).parent / "resultados_t4_precondiciones.json"
    with open(archivo_res, "w", encoding="utf-8") as fh:
        json.dump(resultados_totales, fh, indent=2, ensure_ascii=False)
    print(f"\nResultados guardados en {archivo_res}")

if __name__ == "__main__":
    main()

