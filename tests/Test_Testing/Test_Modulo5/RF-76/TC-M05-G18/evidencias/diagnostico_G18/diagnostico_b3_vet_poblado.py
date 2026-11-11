"""Diagnostico B3 (TC-M05-G18): conteo en TEST de registros de medicamento con retiro y veterinario."""
from __future__ import annotations

import json
import os
from pathlib import Path
import time
from typing import Any
import uuid

from dotenv import dotenv_values
import requests


def cargar_env_test() -> dict[str, str]:
    repo = Path(__file__).resolve().parents[7]
    env_path = repo / ".env.test"
    vals = dotenv_values(env_path)
    cfg: dict[str, str] = {}
    for k in ("TEST_BASE_URL", "TEST_SANDBOX_SECRET", "TEST_ADMIN_EMAIL", "TEST_ADMIN_PASSWORD"):
        v = (os.environ.get(k) or vals.get(k) or "").strip()
        if v:
            cfg[k] = v
    return cfg


def login_sandbox_r2(session: requests.Session, base_url: str, email: str, pwd: str) -> None:
    inicio = time.monotonic()
    for _ in range(7):
        try:
            resp = session.post(
                f"{base_url}/sesiones/",
                json={"correo_electronico": email, "contrasena": pwd},
                timeout=90,
            )
            if resp.status_code in (423, 429, 502, 503, 504) and (time.monotonic() - inicio) < 200:
                time.sleep(30)
                continue
        except requests.RequestException:
            if (time.monotonic() - inicio) < 200:
                time.sleep(30)
                continue
            raise
        if resp.status_code != 200:
            raise RuntimeError(f"Login Admin fallo HTTP {resp.status_code}")
        token = (resp.json() or {}).get("token")
        if not token:
            raise RuntimeError("Login Admin no devolvio token")
        session.headers["Authorization"] = f"Bearer {token}"
        return
    raise RuntimeError("Login Admin agoto reintentos")


def main() -> None:
    cfg = cargar_env_test()
    base_url = cfg["TEST_BASE_URL"].rstrip("/")
    secret = cfg["TEST_SANDBOX_SECRET"]
    email = cfg["TEST_ADMIN_EMAIL"]
    pwd = cfg["TEST_ADMIN_PASSWORD"]

    run_id = f"diag-g18-b3-{uuid.uuid4().hex[:8]}"
    session = requests.Session()
    session.headers.update(
        {
            "X-Test-Run-Id": run_id,
            "X-Sandbox-Secret": secret,
            "X-Zona-Horaria": "America/Bogota",
        }
    )

    exc_capturada: BaseException | None = None
    resultado: dict[str, Any] = {}
    cierre = "NO_INICIADO"
    try:
        login_sandbox_r2(session, base_url, email, pwd)
        sql = (
            "SELECT "
            "count(*) AS total_validados_con_retiro, "
            "count(id_usuario_veterinario) AS con_id_usuario_veterinario, "
            "count(*) - count(id_usuario_veterinario) AS sin_id_usuario_veterinario "
            "FROM modulo5.registros_medicamentos "
            "WHERE estado_registro = 'VALIDADO' AND fecha_fin_retiro IS NOT NULL"
        )
        r_q = session.post(f"{base_url}/test-control/query", json={"query": sql}, timeout=45)
        if r_q.status_code != 200:
            raise RuntimeError(f"/test-control/query HTTP {r_q.status_code}: {r_q.text[:250]}")
        rows = (r_q.json() or {}).get("data") or []
        resultado = {"run_id": run_id, "conteos": rows[0] if rows else {}}
    except BaseException as exc:
        exc_capturada = exc
    finally:
        try:
            r_del = session.delete(f"{base_url}/test-control/runs/{run_id}", timeout=45)
            cierre = f"HTTP {r_del.status_code}"
        except Exception as exc_del:
            cierre = f"ERROR {type(exc_del).__name__}: {exc_del}"
        finally:
            session.close()
        if exc_capturada is not None:
            raise RuntimeError(f"Error en {run_id} (cierre={cierre}): {exc_capturada}") from exc_capturada

    resultado["cierre"] = cierre
    out_path = Path(__file__).resolve().parent / "b3_resultado.json"
    out_path.write_text(json.dumps(resultado, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(resultado, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
