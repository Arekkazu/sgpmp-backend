"""Fase 1 Task C (Smoke Camino Feliz en TEST con periodo_retiro_dias=0) para TC-M05-G18."""
from __future__ import annotations

import json
import os
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests
from dotenv import dotenv_values

try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    try:
        ZONA_USUARIO = ZoneInfo("America/Bogota")
    except ZoneInfoNotFoundError:
        ZONA_USUARIO = timezone(timedelta(hours=-5), "America/Bogota")
except ImportError:
    ZONA_USUARIO = timezone(timedelta(hours=-5), "America/Bogota")

RAIZ = Path(__file__).resolve().parents[7]
if not (RAIZ / ".env.test").exists():
    RAIZ = Path.cwd()
ENV_TEST = dotenv_values(RAIZ / ".env.test") if (RAIZ / ".env.test").exists() else {}
OUT_JSON = Path(__file__).resolve().parent / "c_resultado.json"

ACTIVO_ID = 853
CICLO_ID = 5


def _env(nombre: str) -> str:
    return (os.environ.get(nombre) or ENV_TEST.get(nombre) or "").strip()


def _secretos() -> list[str]:
    return [
        v
        for k in ("TEST_SANDBOX_SECRET", "TEST_ADMIN_PASSWORD", "TEST_ADMIN_EMAIL")
        if (v := _env(k))
    ]


def _sanitizar(obj: Any) -> Any:
    if isinstance(obj, str):
        s = obj
        for sec in _secretos():
            s = s.replace(sec, "***")
        jwt_pref = "ey" + "J"
        if jwt_pref in s:
            s = s.replace(jwt_pref, "[JWT_OMITIDO]")
        return s
    if isinstance(obj, list):
        return [_sanitizar(x) for x in obj]
    if isinstance(obj, dict):
        return {str(k): _sanitizar(v) for k, v in obj.items()}
    return obj


def _login(s: requests.Session, base: str, email: str, pwd: str) -> dict[str, Any]:
    for intento in range(7):
        r = s.post(
            f"{base}/sesiones/",
            json={"correo_electronico": email, "contrasena": pwd},
            timeout=45,
        )
        if r.status_code in (423, 429) and intento < 6:
            time.sleep(30)
            continue
        break
    body = {}
    try:
        body = r.json()
    except ValueError:
        pass
    token = body.get("token")
    assert r.status_code == 200 and token, f"Login fallo HTTP {r.status_code}: {r.text[:200]}"
    s.headers["Authorization"] = f"Bearer {token}"
    return {"http": r.status_code, "tiene_token": True}


def _query(s: requests.Session, base: str, sql: str) -> dict[str, Any]:
    r = s.post(f"{base}/test-control/query", json={"query": sql}, timeout=45)
    try:
        body = r.json()
    except ValueError:
        body = {"raw": r.text[:300]}
    return {"http": r.status_code, "body": body}


def _cerrar(s: requests.Session, base: str, run_id: str) -> dict[str, Any]:
    r = s.delete(f"{base}/test-control/runs/{run_id}", timeout=45)
    try:
        body = r.json()
    except ValueError:
        body = {"raw": r.text[:200]}
    return {"http": r.status_code, "body": body}


def main() -> None:
    base = _env("TEST_BASE_URL").rstrip("/")
    secret = _env("TEST_SANDBOX_SECRET")
    email = _env("TEST_ADMIN_EMAIL")
    pwd = _env("TEST_ADMIN_PASSWORD")
    assert base and secret and email and pwd, "Faltan variables requeridas en .env.test"

    hoy_bogota: date = datetime.now(ZONA_USUARIO).date()
    hace_6_dias: date = hoy_bogota - timedelta(days=6)

    evidencia: dict[str, Any] = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "timestamp_bogota": datetime.now(ZONA_USUARIO).isoformat(),
        "activo_id": ACTIVO_ID,
        "hoy_bogota": hoy_bogota.isoformat(),
        "fecha_hace_6_dias": hace_6_dias.isoformat(),
        "corrida_2_smoke": {},
        "corrida_3_inocuidad": {},
    }

    # --- CORRIDA 2: SMOKE (SIEMPRE periodo_retiro_dias = 0) ---
    run2 = f"tc-m05-g18-fase1-smoke-{uuid.uuid4().hex[:8]}"
    s2 = requests.Session()
    s2.headers.update(
        {
            "X-Test-Run-Id": run2,
            "X-Sandbox-Secret": secret,
            "X-Zona-Horaria": "America/Bogota",
        }
    )
    c2: dict[str, Any] = {"run_id": run2}
    try:
        c2["login"] = _login(s2, base, email, pwd)

        # C1: linea base y apertura de fase si hace falta
        c2["base_api_get"] = s2.get(
            f"{base}/suministros/medicamentos",
            params={"id_activo_biologico": ACTIVO_ID},
            timeout=45,
        ).json()
        c2["base_sql_cnt"] = _query(
            s2,
            base,
            f"SELECT count(*) AS total FROM modulo5.registros_medicamentos WHERE id_activo_biologico = {ACTIVO_ID}",
        )

        fases = s2.get(f"{base}/activos-biologicos/{ACTIVO_ID}/fases", timeout=45).json()
        activas = [f for f in fases.get("fases") or [] if f.get("es_activa") is True]
        if not activas:
            rf = s2.post(
                f"{base}/activos-biologicos/{ACTIVO_ID}/fases",
                json={
                    "id_ciclo_productiva": CICLO_ID,
                    "motivo_cambio": "TC-M05-G18 Fase 1 smoke: apertura de fase en sandbox",
                },
                timeout=45,
            )
            c2["abrir_fase"] = {"http": rf.status_code, "body": rf.json()}
            assert rf.status_code == 201, f"Abrir fase fallo HTTP {rf.status_code}"
        else:
            c2["abrir_fase"] = {"ya_abierta": True, "count": len(activas)}

        # C2: POST medicamento valido con periodo_retiro_dias = 0 (OBLIGATORIO en Fase 1)
        payload_hoy = {
            "id_activo_biologico": ACTIVO_ID,
            "nombre_medicamento": "SmokeG18Hoy",
            "fecha_aplicacion": hoy_bogota.isoformat(),
            "hora_aplicacion": "10:11",
            "via_administracion": "INTRAMUSCULAR",
            "dosis_aplicada": 5,
            "unidad_dosis": "ml",
            "periodo_retiro_dias": 0,
            "motivo_aplicacion": "Smoke Fase 1 TC-M05-G18 camino feliz sin retiro",
            "costo_unitario": 1200,
            "nombre_veterinario": "Dra. Ana Ruiz",
            "id_evento_sanitario": None,
        }
        assert payload_hoy["periodo_retiro_dias"] == 0
        r_post_hoy = s2.post(f"{base}/suministros/medicamentos", json=payload_hoy, timeout=45)
        try:
            b_post_hoy = r_post_hoy.json()
        except ValueError:
            b_post_hoy = {"raw": r_post_hoy.text[:400]}
        c2["post_hoy"] = {"http": r_post_hoy.status_code, "body": b_post_hoy}
        assert r_post_hoy.status_code == 201, f"POST hoy fallo HTTP {r_post_hoy.status_code}: {b_post_hoy}"

        r_get_hoy = s2.get(
            f"{base}/suministros/medicamentos",
            params={"id_activo_biologico": ACTIVO_ID},
            timeout=45,
        )
        c2["get_tras_post_hoy"] = {"http": r_get_hoy.status_code, "body": r_get_hoy.json()}

        # C3: POST retroactivo (hoy - 6 dias, periodo_retiro_dias = 0) para verificar viabilidad S1
        payload_retro = {
            "id_activo_biologico": ACTIVO_ID,
            "nombre_medicamento": "SmokeG18Retro6d",
            "fecha_aplicacion": hace_6_dias.isoformat(),
            "hora_aplicacion": "10:12",
            "via_administracion": "ORAL",
            "dosis_aplicada": 3,
            "unidad_dosis": "ml",
            "periodo_retiro_dias": 0,
            "motivo_aplicacion": "Smoke Fase 1 TC-M05-G18 prueba fecha retroactiva -6d",
            "costo_unitario": 900,
            "nombre_veterinario": "Dra. Ana Ruiz",
            "id_evento_sanitario": None,
        }
        assert payload_retro["periodo_retiro_dias"] == 0
        r_post_retro = s2.post(f"{base}/suministros/medicamentos", json=payload_retro, timeout=45)
        try:
            b_post_retro = r_post_retro.json()
        except ValueError:
            b_post_retro = {"raw": r_post_retro.text[:400]}
        c2["post_retro_6d"] = {"http": r_post_retro.status_code, "body": b_post_retro}

        # C4: conteo dentro del sandbox antes de cerrar
        c2["post_sql_cnt_en_sandbox"] = _query(
            s2,
            base,
            f"SELECT count(*) AS total FROM modulo5.registros_medicamentos WHERE id_activo_biologico = {ACTIVO_ID}",
        )
    finally:
        c2["close"] = _cerrar(s2, base, run2)
        s2.close()
    evidencia["corrida_2_smoke"] = c2

    # --- CORRIDA 3: VERIFICACION DE INOCUIDAD POST-ROLLBACK ---
    run3 = f"tc-m05-g18-fase1-inoc-{uuid.uuid4().hex[:8]}"
    s3 = requests.Session()
    s3.headers.update(
        {
            "X-Test-Run-Id": run3,
            "X-Sandbox-Secret": secret,
            "X-Zona-Horaria": "America/Bogota",
        }
    )
    c3: dict[str, Any] = {"run_id": run3}
    try:
        c3["login"] = _login(s3, base, email, pwd)
        c3["final_sql_cnt"] = _query(
            s3,
            base,
            f"SELECT count(*) AS total FROM modulo5.registros_medicamentos WHERE id_activo_biologico = {ACTIVO_ID}",
        )
        rg = s3.get(
            f"{base}/suministros/medicamentos",
            params={"id_activo_biologico": ACTIVO_ID},
            timeout=45,
        )
        c3["final_api_get"] = {"http": rg.status_code, "body": rg.json()}
    finally:
        c3["close"] = _cerrar(s3, base, run3)
        s3.close()
    evidencia["corrida_3_inocuidad"] = c3

    OUT_JSON.write_text(
        json.dumps(_sanitizar(evidencia), indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print(f"OK escrito {OUT_JSON}")
    print("Run2 close:", c2.get("close"))
    print("Run3 close:", c3.get("close"))


if __name__ == "__main__":
    main()

