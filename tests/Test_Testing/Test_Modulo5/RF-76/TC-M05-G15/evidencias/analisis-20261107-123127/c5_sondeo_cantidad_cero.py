"""Sondeo acotado de cantidad_actual=0 (C5).
Ejecuta hasta 10 intentos por API real dentro de una corrida sandbox propia.
Registra trazas crudas automáticas en trazas_c5_sondeo.jsonl.
Cierra la corrida con DELETE /test-control/runs/{run_id}.
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

TRAZAS_PATH = _DIR_ACTUAL / "trazas_c5_sondeo.jsonl"


def sanitizar(data: any) -> any:
    if isinstance(data, dict):
        san = {}
        for k, v in data.items():
            if k.lower() in ("contrasena", "password", "token", "authorization"):
                san[k] = "***REDACTED***"
            elif isinstance(v, (dict, list)):
                san[k] = sanitizar(v)
            else:
                san[k] = v
        return san
    elif isinstance(data, list):
        return [sanitizar(x) for x in data]
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
        "request_body": sanitizar(req_body),
        "response_body": sanitizar(resp_body),
    }
    f_out.write(json.dumps(entry, ensure_ascii=False) + "\n")
    f_out.flush()
    return entry


def hoy_str() -> str:
    return datetime.now(timezone(timedelta(hours=-5))).date().isoformat()


def main():
    run_id = f"tc-m05-g15-c5-{uuid.uuid4()}"
    print(f"Iniciando corrida C5 con run_id: {run_id}")

    session = requests.Session()
    headers_base = {
        "X-Test-Run-Id": run_id,
        "X-Sandbox-Secret": SANDBOX_SECRET,
        "X-Zona-Horaria": "America/Bogota",
    }
    session.headers.update(headers_base)

    f_trazas = open(TRAZAS_PATH, "w", encoding="utf-8")
    intentos_reporte = []

    try:
        # Login
        t0 = time.perf_counter()
        r_login = session.post(f"{BASE_URL}/sesiones/", json={"correo_electronico": EMAIL, "contrasena": PASSWORD}, timeout=30)
        ms = (time.perf_counter() - t0) * 1000
        log_traza(f_trazas, "POST", f"{BASE_URL}/sesiones/", r_login.status_code, {"correo_electronico": EMAIL, "contrasena": "***"}, r_login, ms)
        assert r_login.status_code == 200, f"Login fallo: {r_login.status_code}"
        token = r_login.json()["token"]
        session.headers["Authorization"] = f"Bearer {token}"
        print("Login OK")

        # -----------------------------------------------------------------
        # INTENTO 1: Reactivar/abrir ciclo en Activo 9
        # -----------------------------------------------------------------
        print("\n--- Intento 1: Reactivar / abrir ciclo en Activo 9 ---")
        body_patch9 = {
            "estado_nuevo": "ACTIVO",
            "fecha_cambio_estado": hoy_str(),
            "motivo_cambio": "Intento de reactivacion activo 9"
        }
        t0 = time.perf_counter()
        r1 = session.patch(f"{BASE_URL}/activos-biologicos/9/estado", json=body_patch9, timeout=30)
        ms = (time.perf_counter() - t0) * 1000
        log_traza(f_trazas, "PATCH", f"{BASE_URL}/activos-biologicos/9/estado", r1.status_code, body_patch9, r1, ms)
        print(f"1.1 PATCH /activos-biologicos/9/estado: HTTP {r1.status_code}, body: {r1.text}")

        body_fase9 = {"id_ciclo_productiva": 3, "motivo_cambio": "Apertura fase ciclo 3"}
        t0 = time.perf_counter()
        r1_2 = session.post(f"{BASE_URL}/activos-biologicos/9/fases", json=body_fase9, timeout=30)
        ms = (time.perf_counter() - t0) * 1000
        log_traza(f_trazas, "POST", f"{BASE_URL}/activos-biologicos/9/fases", r1_2.status_code, body_fase9, r1_2, ms)
        print(f"1.2 POST /activos-biologicos/9/fases: HTTP {r1_2.status_code}, body: {r1_2.text}")
        intentos_reporte.append({
            "intento": 1,
            "descripcion": "Reactivar y abrir fase en activo 9",
            "endpoint": "PATCH /activos-biologicos/9/estado y POST /activos-biologicos/9/fases",
            "http_status": [r1.status_code, r1_2.status_code],
            "resultado": r1_2.text[:200]
        })

        # -----------------------------------------------------------------
        # INTENTO 2: Crear POBLACIONAL con cantidad_inicial = 0
        # -----------------------------------------------------------------
        print("\n--- Intento 2: Crear POBLACIONAL con cantidad_inicial = 0 ---")
        body_crear_cero = {
            "tipo_activo": "POBLACIONAL",
            "id_especie": 1,
            "fecha_inicio_ciclo": hoy_str(),
            "origen_financiero": "nacimiento",
            "id_infraestructura": 2,
            "cantidad_inicial": 0,
            "descripcion": "Lote prueba cantidad 0"
        }
        t0 = time.perf_counter()
        r2 = session.post(f"{BASE_URL}/activos-biologicos", json=body_crear_cero, timeout=30)
        ms = (time.perf_counter() - t0) * 1000
        log_traza(f_trazas, "POST", f"{BASE_URL}/activos-biologicos", r2.status_code, body_crear_cero, r2, ms)
        print(f"Intento 2: HTTP {r2.status_code}, body: {r2.text}")
        intentos_reporte.append({
            "intento": 2,
            "descripcion": "Crear POBLACIONAL con cantidad_inicial = 0",
            "endpoint": "POST /activos-biologicos",
            "http_status": r2.status_code,
            "resultado": r2.text[:200]
        })

        # -----------------------------------------------------------------
        # INTENTO 3: Crear POBLACIONAL válido con cantidad_inicial = 10 y abrir fase
        # -----------------------------------------------------------------
        print("\n--- Intento 3: Crear POBLACIONAL con cantidad_inicial = 10 y abrir fase ---")
        body_crear_10 = {
            "tipo_activo": "POBLACIONAL",
            "id_especie": 1,
            "fecha_inicio_ciclo": hoy_str(),
            "origen_financiero": "nacimiento",
            "id_infraestructura": 2,
            "cantidad_inicial": 10,
            "descripcion": "Lote prueba sondeo cantidad 0 sandbox"
        }
        t0 = time.perf_counter()
        r3 = session.post(f"{BASE_URL}/activos-biologicos", json=body_crear_10, timeout=30)
        ms = (time.perf_counter() - t0) * 1000
        log_traza(f_trazas, "POST", f"{BASE_URL}/activos-biologicos", r3.status_code, body_crear_10, r3, ms)
        print(f"Intento 3 Creacion: HTTP {r3.status_code}, body: {r3.text}")
        assert r3.status_code == 201, f"Fallo crear lote: {r3.status_code} {r3.text}"
        nuevo_id = r3.json()["id_activo_biologico"]
        print(f"Lote creado con ID: {nuevo_id}")

        # Abrir fase en el lote nuevo
        body_fase_nuevo = {"id_ciclo_productiva": 1, "motivo_cambio": "Apertura fase lote nuevo"}
        t0 = time.perf_counter()
        r3_fase = session.post(f"{BASE_URL}/activos-biologicos/{nuevo_id}/fases", json=body_fase_nuevo, timeout=30)
        ms = (time.perf_counter() - t0) * 1000
        log_traza(f_trazas, "POST", f"{BASE_URL}/activos-biologicos/{nuevo_id}/fases", r3_fase.status_code, body_fase_nuevo, r3_fase, ms)
        print(f"Intento 3 Apertura fase: HTTP {r3_fase.status_code}, body: {r3_fase.text}")
        assert r3_fase.status_code in (200, 201), f"Fallo abrir fase: {r3_fase.status_code}"
        intentos_reporte.append({
            "intento": 3,
            "descripcion": f"Crear POBLACIONAL ID={nuevo_id} (cantidad=10) y abrir fase ciclo 1",
            "endpoint": f"POST /activos-biologicos y POST /activos-biologicos/{nuevo_id}/fases",
            "http_status": [r3.status_code, r3_fase.status_code],
            "resultado": f"Lote {nuevo_id} ACTIVO con fase abierta exitosamente"
        })

        # -----------------------------------------------------------------
        # INTENTO 4: Baja con cantidad_afectada = 0
        # -----------------------------------------------------------------
        print("\n--- Intento 4: Baja con cantidad_afectada = 0 ---")
        body_baja_cero = {
            "tipo_baja": "muerte",
            "fecha_baja": hoy_str(),
            "motivo_baja": "Intento de baja con cantidad 0",
            "cantidad_afectada": 0
        }
        t0 = time.perf_counter()
        r4 = session.post(f"{BASE_URL}/activos-biologicos/{nuevo_id}/eventos/baja", json=body_baja_cero, timeout=30)
        ms = (time.perf_counter() - t0) * 1000
        log_traza(f_trazas, "POST", f"{BASE_URL}/activos-biologicos/{nuevo_id}/eventos/baja", r4.status_code, body_baja_cero, r4, ms)
        print(f"Intento 4: HTTP {r4.status_code}, body: {r4.text}")
        intentos_reporte.append({
            "intento": 4,
            "descripcion": "Baja con cantidad_afectada = 0",
            "endpoint": f"POST /activos-biologicos/{nuevo_id}/eventos/baja",
            "http_status": r4.status_code,
            "resultado": r4.text[:200]
        })

        # -----------------------------------------------------------------
        # INTENTO 5: Intento de PATCH directo en detalle poblacional
        # -----------------------------------------------------------------
        print("\n--- Intento 5: PATCH directo /detalle-poblacional ---")
        t0 = time.perf_counter()
        r5 = session.patch(f"{BASE_URL}/activos-biologicos/{nuevo_id}/detalle-poblacional", json={"cantidad_actual": 0}, timeout=30)
        ms = (time.perf_counter() - t0) * 1000
        log_traza(f_trazas, "PATCH", f"{BASE_URL}/activos-biologicos/{nuevo_id}/detalle-poblacional", r5.status_code, {"cantidad_actual": 0}, r5, ms)
        print(f"Intento 5: HTTP {r5.status_code}, body: {r5.text}")
        intentos_reporte.append({
            "intento": 5,
            "descripcion": "PATCH directo /detalle-poblacional",
            "endpoint": f"PATCH /activos-biologicos/{nuevo_id}/detalle-poblacional",
            "http_status": r5.status_code,
            "resultado": r5.text[:200]
        })

        # -----------------------------------------------------------------
        # INTENTO 6: Intento de PATCH /activos-biologicos/{id} (RF-35)
        # -----------------------------------------------------------------
        print("\n--- Intento 6: PATCH /activos-biologicos/{id} ---")
        t0 = time.perf_counter()
        r6 = session.patch(f"{BASE_URL}/activos-biologicos/{nuevo_id}", json={"cantidad_actual": 0}, timeout=30)
        ms = (time.perf_counter() - t0) * 1000
        log_traza(f_trazas, "PATCH", f"{BASE_URL}/activos-biologicos/{nuevo_id}", r6.status_code, {"cantidad_actual": 0}, r6, ms)
        print(f"Intento 6: HTTP {r6.status_code}, body: {r6.text}")
        intentos_reporte.append({
            "intento": 6,
            "descripcion": "PATCH /activos-biologicos/{id} sobre POBLACIONAL",
            "endpoint": f"PATCH /activos-biologicos/{nuevo_id}",
            "http_status": r6.status_code,
            "resultado": r6.text[:200]
        })

        # -----------------------------------------------------------------
        # INTENTO 7: Baja parcial de 9 individuos (dejando 1 individuo)
        # -----------------------------------------------------------------
        print("\n--- Intento 7: Baja parcial de 9 individuos (dejando 1) ---")
        body_baja_9 = {
            "tipo_baja": "muerte",
            "fecha_baja": hoy_str(),
            "motivo_baja": "Mortalidad parcial de 9 individuos",
            "cantidad_afectada": 9
        }
        t0 = time.perf_counter()
        r7 = session.post(f"{BASE_URL}/activos-biologicos/{nuevo_id}/eventos/baja", json=body_baja_9, timeout=30)
        ms = (time.perf_counter() - t0) * 1000
        log_traza(f_trazas, "POST", f"{BASE_URL}/activos-biologicos/{nuevo_id}/eventos/baja", r7.status_code, body_baja_9, r7, ms)
        print(f"Intento 7: HTTP {r7.status_code}")
        assert r7.status_code == 201, f"Fallo baja parcial: {r7.status_code} {r7.text}"

        # Releer estado tras baja parcial
        r7_act = session.get(f"{BASE_URL}/activos-biologicos/{nuevo_id}", timeout=30)
        data7 = r7_act.json()
        dp7 = data7.get("detalle_poblacional") or {}
        print(f"Estado tras baja parcial: id_estado={data7.get('id_estado')}, cantidad_actual={dp7.get('cantidad_actual')}")
        intentos_reporte.append({
            "intento": 7,
            "descripcion": "Baja parcial de 9 individuos dejando 1 individuo",
            "endpoint": f"POST /activos-biologicos/{nuevo_id}/eventos/baja",
            "http_status": r7.status_code,
            "resultado": f"id_estado={data7.get('id_estado')}, cantidad_actual={dp7.get('cantidad_actual')}"
        })

        # -----------------------------------------------------------------
        # INTENTO 8: Baja final de 1 individuo (alcanzando cantidad_actual = 0)
        # -----------------------------------------------------------------
        print("\n--- Intento 8: Baja final de 1 individuo (alcanzando 0) ---")
        body_baja_1 = {
            "tipo_baja": "muerte",
            "fecha_baja": hoy_str(),
            "motivo_baja": "Mortalidad de 1 individuo restante",
            "cantidad_afectada": 1
        }
        t0 = time.perf_counter()
        r8 = session.post(f"{BASE_URL}/activos-biologicos/{nuevo_id}/eventos/baja", json=body_baja_1, timeout=30)
        ms = (time.perf_counter() - t0) * 1000
        log_traza(f_trazas, "POST", f"{BASE_URL}/activos-biologicos/{nuevo_id}/eventos/baja", r8.status_code, body_baja_1, r8, ms)
        print(f"Intento 8: HTTP {r8.status_code}")
        assert r8.status_code == 201, f"Fallo baja final: {r8.status_code} {r8.text}"

        # Releer estado y fases tras alcanzar cantidad 0
        r8_act = session.get(f"{BASE_URL}/activos-biologicos/{nuevo_id}", timeout=30)
        data8 = r8_act.json()
        dp8 = data8.get("detalle_poblacional") or {}
        r8_fas = session.get(f"{BASE_URL}/activos-biologicos/{nuevo_id}/fases", timeout=30)
        fases8 = r8_fas.json().get("fases") or []
        fases_activas8 = [f for f in fases8 if f.get("es_activa") is True]

        print(f"Estado tras alcanzar 0: id_estado={data8.get('id_estado')} ({data8.get('nombre_estado')}), cantidad_actual={dp8.get('cantidad_actual')}, fases_activas={len(fases_activas8)}")
        intentos_reporte.append({
            "intento": 8,
            "descripcion": "Baja final de 1 individuo alcanzando cantidad_actual = 0",
            "endpoint": f"POST /activos-biologicos/{nuevo_id}/eventos/baja",
            "http_status": r8.status_code,
            "resultado": f"id_estado={data8.get('id_estado')} ({data8.get('nombre_estado')}), cantidad_actual={dp8.get('cantidad_actual')}, fases_activas={len(fases_activas8)}"
        })

        # -----------------------------------------------------------------
        # INTENTO 9: Intentar reactivar lote (PATCH estado) o abrir fase estando en 0
        # -----------------------------------------------------------------
        print("\n--- Intento 9: Intentar reactivar lote o abrir fase estando en cantidad 0 ---")
        t0 = time.perf_counter()
        body_patch_reactivar = {
            "estado_nuevo": "ACTIVO",
            "fecha_cambio_estado": hoy_str(),
            "motivo_cambio": "Reactivar lote en 0"
        }
        r9_estado = session.patch(f"{BASE_URL}/activos-biologicos/{nuevo_id}/estado", json=body_patch_reactivar, timeout=30)
        ms = (time.perf_counter() - t0) * 1000
        log_traza(f_trazas, "PATCH", f"{BASE_URL}/activos-biologicos/{nuevo_id}/estado", r9_estado.status_code, body_patch_reactivar, r9_estado, ms)
        print(f"Intento 9.1 PATCH estado: HTTP {r9_estado.status_code}, body: {r9_estado.text}")

        t0 = time.perf_counter()
        body_fase_reabrir = {"id_ciclo_productiva": 1, "motivo_cambio": "Abrir fase en lote en 0"}
        r9_fase = session.post(f"{BASE_URL}/activos-biologicos/{nuevo_id}/fases", json=body_fase_reabrir, timeout=30)
        ms = (time.perf_counter() - t0) * 1000
        log_traza(f_trazas, "POST", f"{BASE_URL}/activos-biologicos/{nuevo_id}/fases", r9_fase.status_code, body_fase_reabrir, r9_fase, ms)
        print(f"Intento 9.2 POST fases: HTTP {r9_fase.status_code}, body: {r9_fase.text}")
        intentos_reporte.append({
            "intento": 9,
            "descripcion": "Intentar reactivar lote (PATCH estado=1) o abrir fase estando en 0",
            "endpoint": f"PATCH /activos-biologicos/{nuevo_id}/estado y POST /activos-biologicos/{nuevo_id}/fases",
            "http_status": [r9_estado.status_code, r9_fase.status_code],
            "resultado": f"Reactivar HTTP {r9_estado.status_code} ({r9_estado.text[:100]}); Abrir fase HTTP {r9_fase.status_code} ({r9_fase.text[:100]})"
        })

        # -----------------------------------------------------------------
        # INTENTO 10: POST /suministros/medicamentos sobre lote con cantidad 0
        # -----------------------------------------------------------------
        print("\n--- Intento 10: POST /suministros/medicamentos sobre lote con cantidad 0 ---")
        p_med = {
            "id_activo_biologico": nuevo_id,
            "nombre_medicamento": "Oxitetraciclina",
            "fecha_aplicacion": hoy_str(),
            "hora_aplicacion": "08:10",
            "via_administracion": "INTRAMUSCULAR",
            "dosis_aplicada": 100,
            "unidad_dosis": "ml",
            "periodo_retiro_dias": 0,
            "motivo_aplicacion": "Tratamiento sobre lote con cantidad 0",
            "costo_unitario": 500,
            "nombre_veterinario": "Dr. Pérez",
        }
        t0 = time.perf_counter()
        r10 = session.post(f"{BASE_URL}/suministros/medicamentos", json=p_med, timeout=30)
        ms = (time.perf_counter() - t0) * 1000
        log_traza(f_trazas, "POST", f"{BASE_URL}/suministros/medicamentos", r10.status_code, p_med, r10, ms)
        print(f"Intento 10: HTTP {r10.status_code}, body: {r10.text}")
        intentos_reporte.append({
            "intento": 10,
            "descripcion": "POST /suministros/medicamentos sobre lote que alcanzó cantidad_actual = 0",
            "endpoint": "POST /suministros/medicamentos",
            "http_status": r10.status_code,
            "resultado": r10.text[:200]
        })

    finally:
        f_trazas.close()
        # Cerrar corrida sandbox
        print(f"\nCerrando corrida sandbox C5 {run_id}...")
        try:
            r_del = requests.delete(
                f"{BASE_URL}/test-control/runs/{run_id}",
                headers={"X-Sandbox-Secret": SANDBOX_SECRET},
                timeout=30,
            )
            print(f"Teardown C5 DELETE HTTP {r_del.status_code}: {r_del.text}")
            teardown_status = r_del.status_code
            teardown_body = r_del.text
        except Exception as e:
            print(f"Error en teardown C5: {e}")
            teardown_status = 0
            teardown_body = str(e)

        with open(_DIR_ACTUAL / "resumen_c5_sondeo.json", "w", encoding="utf-8") as f:
            json.dump({
                "run_id": run_id,
                "teardown_status": teardown_status,
                "teardown_body": teardown_body,
                "intentos": intentos_reporte
            }, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
