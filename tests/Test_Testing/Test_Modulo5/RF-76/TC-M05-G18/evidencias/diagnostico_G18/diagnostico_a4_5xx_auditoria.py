"""Diagnostico A4 (TC-M05-G18): reproduccion controlada de 5xx en TEST (sin retiro) y verificacion de auditoria."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import time
from typing import Any, Callable, Optional
import uuid

from dotenv import dotenv_values
import requests

try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
    try:
        _ZONA_BOGOTA = ZoneInfo("America/Bogota")
    except ZoneInfoNotFoundError:
        _ZONA_BOGOTA = timezone(timedelta(hours=-5), "America/Bogota")
except ImportError:
    _ZONA_BOGOTA = timezone(timedelta(hours=-5), "America/Bogota")

ACTIVO_ID = 853
CICLO_ID = 5


def cargar_env_test() -> dict[str, str]:
    repo = Path(__file__).resolve().parents[7]
    env_path = repo / ".env.test"
    if not env_path.exists():
        raise FileNotFoundError(f"Falta .env.test en {repo}")
    vals = dotenv_values(env_path)
    cfg: dict[str, str] = {}
    for k in ("TEST_BASE_URL", "TEST_SANDBOX_SECRET", "TEST_ADMIN_EMAIL", "TEST_ADMIN_PASSWORD", "TEST_M05_ACTIVO_ID"):
        v = (os.environ.get(k) or vals.get(k) or "").strip()
        if v:
            cfg[k] = v
    return cfg


def login_sandbox_r2(session: requests.Session, base_url: str, email: str, pwd: str) -> None:
    """Un login por run_id con reintento cada 30 s hasta 200 s ante 423/429/5xx o error de red."""
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
            raise RuntimeError(f"Login Admin fallo en TEST HTTP {resp.status_code}")
        token = (resp.json() or {}).get("token")
        if not token:
            raise RuntimeError("Login Admin no devolvio token")
        session.headers["Authorization"] = f"Bearer {token}"
        return
    raise RuntimeError("Login Admin agoto ventana de reintentos (200 s)")


def query_sandbox(session: requests.Session, base_url: str, sql: str) -> list[dict[str, Any]]:
    resp = session.post(f"{base_url}/test-control/query", json={"query": sql}, timeout=45)
    if resp.status_code != 200:
        raise RuntimeError(f"/test-control/query HTTP {resp.status_code}: {resp.text[:250]}")
    return (resp.json() or {}).get("data") or []


def ejecutar_corrida_sandbox(
    base_url: str,
    secret: str,
    run_id: str,
    fn: Callable[[requests.Session], Any],
) -> tuple[Any, str]:
    session = requests.Session()
    session.headers.update(
        {
            "X-Test-Run-Id": run_id,
            "X-Sandbox-Secret": secret,
            "X-Zona-Horaria": "America/Bogota",
        }
    )
    exc_capturada: Optional[BaseException] = None
    resultado: Any = None
    try:
        resultado = fn(session)
    except BaseException as exc:
        exc_capturada = exc
    finally:
        cierre = "NO_INICIADO"
        try:
            r_del = session.delete(f"{base_url}/test-control/runs/{run_id}", timeout=45)
            cierre = f"HTTP {r_del.status_code}"
        except Exception as exc_del:
            cierre = f"ERROR {type(exc_del).__name__}: {exc_del}"
        finally:
            session.close()
        if exc_capturada is not None:
            raise RuntimeError(f"Error en {run_id} (cierre={cierre}): {exc_capturada}") from exc_capturada
    return resultado, cierre


def consultar_tablas_auditoria(
    session: requests.Session, base_url: str, hora_utc_iso: str, activo_id: int
) -> dict[str, Any]:
    ev_cnt = query_sandbox(
        session,
        base_url,
        f"SELECT count(*) AS total FROM modulo1.eventos WHERE fecha_evento >= '{hora_utc_iso}'::timestamptz",
    )
    ev_m5_rows = query_sandbox(
        session,
        base_url,
        (
            "SELECT id_evento, tipo_evento, fecha_evento, modulo, resultado, categoria, estado, descripcion "
            "FROM modulo1.eventos "
            f"WHERE fecha_evento >= '{hora_utc_iso}'::timestamptz "
            "ORDER BY id_evento DESC LIMIT 20"
        ),
    )
    sum_cnt = query_sandbox(
        session,
        base_url,
        (
            "SELECT count(*) AS total FROM modulo5.auditorias_suministros "
            f"WHERE fecha_evento >= '{hora_utc_iso}'::timestamptz "
            f"AND (entidad_afectada ILIKE '%medicamento%' OR id_activo_biologico = {activo_id})"
        ),
    )
    sum_all_cnt = query_sandbox(
        session,
        base_url,
        (
            "SELECT count(*) AS total FROM modulo5.auditorias_suministros "
            f"WHERE fecha_evento >= '{hora_utc_iso}'::timestamptz"
        ),
    )
    sum_rows = query_sandbox(
        session,
        base_url,
        (
            "SELECT id_auditoria_suministro, entidad_afectada, tipo_operacion, resultado, fecha_evento, id_activo_biologico, detalle_causa "
            "FROM modulo5.auditorias_suministros "
            f"WHERE fecha_evento >= '{hora_utc_iso}'::timestamptz "
            "ORDER BY id_auditoria_suministro DESC LIMIT 20"
        ),
    )
    return {
        "modulo1_eventos_desde_hora_count": int(ev_cnt[0]["total"]),
        "modulo1_eventos_desde_hora_filas": ev_m5_rows,
        "modulo5_auditorias_medicamento_o_activo_count": int(sum_cnt[0]["total"]),
        "modulo5_auditorias_total_desde_hora_count": int(sum_all_cnt[0]["total"]),
        "modulo5_auditorias_filas": sum_rows,
    }


def main() -> None:
    cfg = cargar_env_test()
    base_url = cfg["TEST_BASE_URL"].rstrip("/")
    secret = cfg["TEST_SANDBOX_SECRET"]
    email = cfg["TEST_ADMIN_EMAIL"]
    pwd = cfg["TEST_ADMIN_PASSWORD"]
    activo_id = int(cfg.get("TEST_M05_ACTIVO_ID") or ACTIVO_ID)

    run1_id = f"diag-g18-a4-r1-{uuid.uuid4().hex[:8]}"
    estado_r1: dict[str, Any] = {}

    def _cuerpo_r1(s1: requests.Session) -> dict[str, Any]:
        login_sandbox_r2(s1, base_url, email, pwd)
        now_row = query_sandbox(
            s1, base_url, "SELECT to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM-DD\"T\"HH24:MI:SS.US\"Z\"') AS ahora_utc"
        )
        hora_utc = str(now_row[0]["ahora_utc"])

        antes = consultar_tablas_auditoria(s1, base_url, hora_utc, activo_id)

        r_fases = s1.get(f"{base_url}/activos-biologicos/{activo_id}/fases", timeout=45)
        if r_fases.status_code == 200:
            activas = [f for f in (r_fases.json().get("fases") or []) if f.get("es_activa") is True]
            if not activas:
                s1.post(
                    f"{base_url}/activos-biologicos/{activo_id}/fases",
                    json={"id_ciclo_productiva": CICLO_ID, "motivo_cambio": "Diagnostico A4 G18"},
                    timeout=45,
                )

        hoy_bogota = datetime.now(_ZONA_BOGOTA).date()
        payload = {
            "id_activo_biologico": activo_id,
            "nombre_medicamento": f"DiagA4Med-{uuid.uuid4().hex[:6]}",
            "fecha_aplicacion": hoy_bogota.isoformat(),
            "hora_aplicacion": "11:15",
            "via_administracion": "INTRAMUSCULAR",
            "dosis_aplicada": 0.0004,
            "unidad_dosis": "ml",
            "periodo_retiro_dias": 0,
            "motivo_aplicacion": "Diagnostico A4 G18 reproduccion controlada sin retiro",
            "costo_unitario": 25000,
            "nombre_veterinario": "Dra. Ana Veterinaria",
            "id_evento_sanitario": None,
        }
        r_post = s1.post(f"{base_url}/suministros/medicamentos", json=payload, timeout=45)
        post_info: dict[str, Any] = {
            "status_code": r_post.status_code,
            "x_request_id": r_post.headers.get("X-Request-ID"),
            "error_code": None,
            "message": None,
        }
        try:
            body = r_post.json()
            if isinstance(body, dict):
                post_info["error_code"] = body.get("error_code") or body.get("code")
                post_info["message"] = body.get("message") or body.get("detail")
        except Exception:
            post_info["message"] = r_post.text[:250]

        durante = None
        if 500 <= r_post.status_code < 600:
            durante = consultar_tablas_auditoria(s1, base_url, hora_utc, activo_id)

        return {
            "run_id": run1_id,
            "activo_id": activo_id,
            "hora_utc_anotada": hora_utc,
            "antes": antes,
            "post": post_info,
            "durante": durante,
        }

    estado_r1, cierre_r1 = ejecutar_corrida_sandbox(base_url, secret, run1_id, _cuerpo_r1)
    estado_r1["cierre"] = cierre_r1

    resultado_final: dict[str, Any] = {"corrida_1": estado_r1, "corrida_2": None}

    if 500 <= int(estado_r1["post"]["status_code"]) < 600:
        run2_id = f"diag-g18-a4-r2-{uuid.uuid4().hex[:8]}"
        hora_utc = estado_r1["hora_utc_anotada"]

        def _cuerpo_r2(s2: requests.Session) -> dict[str, Any]:
            login_sandbox_r2(s2, base_url, email, pwd)
            despues = consultar_tablas_auditoria(s2, base_url, hora_utc, activo_id)
            return {"run_id": run2_id, "despues": despues}

        estado_r2, cierre_r2 = ejecutar_corrida_sandbox(base_url, secret, run2_id, _cuerpo_r2)
        estado_r2["cierre"] = cierre_r2
        resultado_final["corrida_2"] = estado_r2

    out_path = Path(__file__).resolve().parent / "a4_resultado.json"
    out_path.write_text(json.dumps(resultado_final, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    print(json.dumps(resultado_final, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
