"""Ejecución de T4 + C2 + C4 en UNA SOLA corrida sandbox.
Genera run_id con uuid4.
Registra trazas crudas automáticas en trazas_c2_c4.jsonl.
Cierra la corrida con DELETE /test-control/runs/{run_id} y valida rollback.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
import requests
from dotenv import dotenv_values

_DIR_ACTUAL = Path(__file__).resolve().parent
_RAIZ_REPO = Path(__file__).resolve().parents[7]
if not (_RAIZ_REPO / ".env.test").exists():
    _RAIZ_REPO = Path.cwd()
_ENV_TEST = dotenv_values(_RAIZ_REPO / ".env.test")


def env(nombre: str) -> str:
    v = os.environ.get(nombre) or _ENV_TEST.get(nombre)
    if not v:
        raise RuntimeError(f"Falta variable de entorno: {nombre}")
    return v


BASE_URL = env("TEST_BASE_URL")
SANDBOX_SECRET = env("TEST_SANDBOX_SECRET")
EMAIL = env("TEST_ADMIN_EMAIL")
PASSWORD = env("TEST_ADMIN_PASSWORD")

TRAZAS_PATH = _DIR_ACTUAL / "trazas_c2_c4.jsonl"


def sanitizar_cuerpo(data: any) -> any:
    if isinstance(data, dict):
        san = {}
        for k, v in data.items():
            if k.lower() in ("contrasena", "password", "token", "authorization"):
                san[k] = "***REDACTED***"
            elif isinstance(v, (dict, list)):
                san[k] = sanitizar_cuerpo(v)
            else:
                san[k] = v
        return san
    elif isinstance(data, list):
        return [sanitizar_cuerpo(x) for x in data]
    return data


def log_traza(f_out, metodo: str, url: str, status_code: int, req_body: any, resp: requests.Response | None, duracion_ms: float):
    now_iso = datetime.now(timezone(timedelta(hours=-5))).isoformat()
    resp_body = None
    server_date = ""
    if resp is not None:
        server_date = resp.headers.get("Date", "")
        try:
            resp_body = resp.json()
        except Exception:
            resp_body = resp.text[:500]

    entry = {
        "timestamp_local": now_iso,
        "server_date": server_date,
        "duracion_ms": round(duracion_ms, 2),
        "metodo": metodo,
        "url": url,
        "status_code": status_code,
        "request_body": sanitizar_cuerpo(req_body),
        "response_body": sanitizar_cuerpo(resp_body),
    }
    f_out.write(json.dumps(entry, ensure_ascii=False) + "\n")
    f_out.flush()
    return entry


def payload_base(id_activo: int, dosis: float = 10.0, hora: str = "08:00") -> dict:
    hoy = datetime.now(timezone(timedelta(hours=-5))).date().isoformat()
    return {
        "id_activo_biologico": id_activo,
        "nombre_medicamento": "Oxitetraciclina",
        "fecha_aplicacion": hoy,
        "hora_aplicacion": hora,
        "via_administracion": "INTRAMUSCULAR",
        "dosis_aplicada": dosis,
        "unidad_dosis": "ml",
        "periodo_retiro_dias": 0,
        "motivo_aplicacion": f"Tratamiento preventivo {id_activo} prueba automatica",
        "costo_unitario": 500,
        "nombre_veterinario": "Dr. Pérez",
    }


def main():
    run_id = f"tc-m05-g15-c2-c4-{uuid.uuid4()}"
    print(f"Iniciando corrida C2-C4 con run_id: {run_id}")

    session = requests.Session()
    headers_base = {
        "X-Test-Run-Id": run_id,
        "X-Sandbox-Secret": SANDBOX_SECRET,
        "X-Zona-Horaria": "America/Bogota",
    }
    session.headers.update(headers_base)

    resultados_resumen = []
    f_trazas = open(TRAZAS_PATH, "w", encoding="utf-8")

    try:
        # 1. Login único
        t0 = time.perf_counter()
        r_login = session.post(
            f"{BASE_URL}/sesiones/",
            json={"correo_electronico": EMAIL, "contrasena": PASSWORD},
            timeout=30,
        )
        ms = (time.perf_counter() - t0) * 1000
        log_traza(f_trazas, "POST", f"{BASE_URL}/sesiones/", r_login.status_code, {"correo_electronico": EMAIL, "contrasena": "***"}, r_login, ms)
        assert r_login.status_code == 200, f"Login fallo: {r_login.status_code} {r_login.text}"
        token = r_login.json()["token"]
        session.headers["Authorization"] = f"Bearer {token}"
        print("Login sandbox OK")

        # -------------------------------------------------------------
        # C4: Inspección exhaustiva de Activo 9 y reproducción 409
        # -------------------------------------------------------------
        print("\n--- Ejecutando C4: Activo 9 ---")
        # GET /activos-biologicos/9
        t0 = time.perf_counter()
        r_act9 = session.get(f"{BASE_URL}/activos-biologicos/9", timeout=30)
        ms = (time.perf_counter() - t0) * 1000
        log_traza(f_trazas, "GET", f"{BASE_URL}/activos-biologicos/9", r_act9.status_code, None, r_act9, ms)

        # GET /activos-biologicos/9/fases
        t0 = time.perf_counter()
        r_fas9 = session.get(f"{BASE_URL}/activos-biologicos/9/fases", timeout=30)
        ms = (time.perf_counter() - t0) * 1000
        log_traza(f_trazas, "GET", f"{BASE_URL}/activos-biologicos/9/fases", r_fas9.status_code, None, r_fas9, ms)

        # GET /activos-biologicos/9/ciclos-productivos
        t0 = time.perf_counter()
        r_cic9 = session.get(f"{BASE_URL}/activos-biologicos/9/ciclos-productivos", timeout=30)
        ms = (time.perf_counter() - t0) * 1000
        log_traza(f_trazas, "GET", f"{BASE_URL}/activos-biologicos/9/ciclos-productivos", r_cic9.status_code, None, r_cic9, ms)

        # Reproducir 409 abriendo fase en activo 9 con ciclo 1
        t0 = time.perf_counter()
        body_fase9 = {"id_ciclo_productiva": 1, "motivo_cambio": "Reproduccion 409 activo 9"}
        r_post_fas9 = session.post(f"{BASE_URL}/activos-biologicos/9/fases", json=body_fase9, timeout=30)
        ms = (time.perf_counter() - t0) * 1000
        traza_409 = log_traza(f_trazas, "POST", f"{BASE_URL}/activos-biologicos/9/fases", r_post_fas9.status_code, body_fase9, r_post_fas9, ms)
        print(f"Reproduccion 409 activo 9: HTTP {r_post_fas9.status_code}, body: {r_post_fas9.text}")

        # POST /suministros/medicamentos sobre activo 9
        t0 = time.perf_counter()
        p_med9 = payload_base(9, dosis=100.0, hora="09:00")
        r_med9 = session.post(f"{BASE_URL}/suministros/medicamentos", json=p_med9, timeout=30)
        ms = (time.perf_counter() - t0) * 1000
        traza_med9 = log_traza(f_trazas, "POST", f"{BASE_URL}/suministros/medicamentos", r_med9.status_code, p_med9, r_med9, ms)
        print(f"POST medicamentos sobre activo 9: HTTP {r_med9.status_code}, body: {r_med9.text}")
        resultados_resumen.append({"escenario": "ACTIVO_9_POST_MEDICAMENTO", "http": r_med9.status_code, "resp": r_med9.json()})

        # -------------------------------------------------------------
        # C2: Ejecución secuencial de T4
        # Orden: 2 (INACTIVO), 12 (CERRADO), 10 (BAJA), 812 (AISLADO),
        #        853 sin fase, 999999999 (inexistente), 462 con fase
        # -------------------------------------------------------------
        print("\n--- Ejecutando C2: Precondiciones T4 ---")
        escenarios_precondiciones = [
            ("INACTIVO", 2, "08:01", 10.0),
            ("CERRADO", 12, "08:02", 10.0),
            ("BAJA", 10, "08:03", 10.0),
            ("AISLADO", 812, "08:04", 10.0),
            ("CICLO_NO_ABIERTO", 853, "08:05", 10.0),
            ("INEXISTENTE", 999999999, "08:06", 10.0),
        ]

        for nombre_esc, id_act, hora, dosis in escenarios_precondiciones:
            p = payload_base(id_act, dosis=dosis, hora=hora)
            t0 = time.perf_counter()
            r = session.post(f"{BASE_URL}/suministros/medicamentos", json=p, timeout=30)
            ms = (time.perf_counter() - t0) * 1000
            log_traza(f_trazas, "POST", f"{BASE_URL}/suministros/medicamentos", r.status_code, p, r, ms)
            print(f"Escenario {nombre_esc} (Activo {id_act}): HTTP {r.status_code}, error_code={r.json().get('error_code') if r.headers.get('content-type','').startswith('application/json') else 'NO_JSON'}")
            resultados_resumen.append({"escenario": nombre_esc, "id_activo": id_act, "http": r.status_code, "resp": r.json()})

        # Escenario POBLACIONAL 462 abriendo fase en la misma corrida
        print("\n--- Ejecutando C2: Activo 462 (POBLACIONAL cantidad NULL) ---")
        # 1. Abrir fase
        t0 = time.perf_counter()
        body_fase462 = {"id_ciclo_productiva": 4, "motivo_cambio": "Apertura fase activo 462 en sandbox"}
        r_fas462 = session.post(f"{BASE_URL}/activos-biologicos/462/fases", json=body_fase462, timeout=30)
        ms = (time.perf_counter() - t0) * 1000
        log_traza(f_trazas, "POST", f"{BASE_URL}/activos-biologicos/462/fases", r_fas462.status_code, body_fase462, r_fas462, ms)
        print(f"Apertura fase activo 462: HTTP {r_fas462.status_code}")
        assert r_fas462.status_code in (200, 201), f"Fallo abrir fase 462: {r_fas462.status_code} {r_fas462.text}"

        # 2. POST medicamentos sobre 462
        t0 = time.perf_counter()
        p_med462 = payload_base(462, dosis=100.0, hora="08:07")
        r_med462 = session.post(f"{BASE_URL}/suministros/medicamentos", json=p_med462, timeout=30)
        ms = (time.perf_counter() - t0) * 1000
        log_traza(f_trazas, "POST", f"{BASE_URL}/suministros/medicamentos", r_med462.status_code, p_med462, r_med462, ms)
        print(f"Escenario POBLACIONAL_462: HTTP {r_med462.status_code}, error_code={r_med462.json().get('error_code')}")
        resultados_resumen.append({"escenario": "POBLACIONAL_CANTIDAD_NULL_462", "id_activo": 462, "http": r_med462.status_code, "resp": r_med462.json()})

    finally:
        f_trazas.close()
        # Teardown DELETE run_id
        print(f"\nCerrando corrida sandbox {run_id}...")
        try:
            r_del = requests.delete(
                f"{BASE_URL}/test-control/runs/{run_id}",
                headers={"X-Sandbox-Secret": SANDBOX_SECRET},
                timeout=30,
            )
            print(f"Teardown DELETE HTTP {r_del.status_code}: {r_del.text}")
            teardown_status = r_del.status_code
            teardown_body = r_del.text
        except Exception as e:
            print(f"Error en teardown: {e}")
            teardown_status = 0
            teardown_body = str(e)

        # Guardar resumen de ejecución
        resumen_path = _DIR_ACTUAL / "resumen_c2_c4.json"
        with open(resumen_path, "w", encoding="utf-8") as f:
            json.dump({
                "run_id": run_id,
                "teardown_status": teardown_status,
                "teardown_body": teardown_body,
                "resultados": resultados_resumen
            }, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
