# | Fecha      | Nombre      | Que se hizo |
# |------------|-------------|-------------|
# | 2026-11-17 | Laura López | TC-M07-G057 RF-102: exportación CSV/JSON de auditoría, consistencia, filtros, seguridad y permisos. |
"""TC-M07-G057 — exportación de registros de auditoría (CSV y JSON).

Contrato real (m07_router.exportar_auditoria + ConsultarAuditoriaIntegracionUseCase.exportar):
  GET /integracion/auditoria/exportar
  Query: formato=csv|json (default csv)
  Filtros: tipo_evento, id_cliente_externo, desde, hasta, endpoint, codigo_http, numero_id_tributaria
  Permiso: auditoria_integracion:E
  Content-Type: text/csv; charset=utf-8 | application/json
  Content-Disposition: attachment; filename="auditoria_integracion_YYYYMMDD_HHMMSS.{formato}"
  CSV: utf-8-sig + csv.DictWriter; dicts en celdas vía json.dumps
  JSON: lista de registros (vista completa, restringida=False)
  Límite interno: 50_000

Credenciales: QA_ADMIN_*, QA_AUDITOR_*, QA_SIN_PERMISO_*

    python tests/Test_Testing/Test_Modulo7/RF-102/TC-M07-G057/ejecutar_tc_m07_g57.py
"""
from __future__ import annotations

import csv
import hashlib
import html
import io
import json
import os
import re
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlencode

BASE = "https://api.inmero.co/api-sgpmp-test"
ZONA = "America/Bogota"
CASO = "TC-M07-G057"
RF = "RF-102"
CARPETA = Path(__file__).resolve().parent
RESULTADO = CARPETA / "Resultado"

ENDPOINT_EXPORT = "/integracion/auditoria/exportar"
ENDPOINT_AUDIT = "/integracion/auditoria"
FILTROS = (
    "tipo_evento",
    "id_cliente_externo",
    "desde",
    "hasta",
    "endpoint",
    "codigo_http",
    "numero_id_tributaria",
)
CAMPOS_CLAVE = (
    "id_evento_integracion",
    "tipo_evento",
    "fecha_evento",
    "id_cliente_externo",
    "endpoint",
    "codigo_http",
)
SENSITIVE_KEY_RE = re.compile(
    r"(password|contrasena|passwd|secret|api[_-]?key|client_secret|access_token|refresh_token|authorization|bearer|hmac|private[_-]?key)",
    re.I,
)
SENSITIVE_VALUE_RE = re.compile(
    r"(?i)(bearer\s+ey[A-Za-z0-9_-]+\.|eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]+\.|sk_live_|BEGIN (RSA |EC )?PRIVATE KEY)"
)


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def pedir(
    metodo: str,
    ruta: str,
    cuerpo: Any = None,
    token: Optional[str] = None,
    timeout: int = 120,
    raw: bool = False,
):
    datos = None if cuerpo is None else json.dumps(cuerpo).encode()
    headers = {"Accept": "*/*", "X-Zona-Horaria": ZONA}
    if cuerpo is not None:
        headers["Content-Type"] = "application/json"
        headers["Accept"] = "application/json"
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(BASE + ruta, data=datos, headers=headers, method=metodo)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            meta = {
                "http": resp.status,
                "content_type": resp.headers.get("Content-Type"),
                "content_disposition": resp.headers.get("Content-Disposition"),
                "bytes": len(body),
            }
            if raw:
                return resp.status, body, meta, None
            text = body.decode("utf-8", "replace")
            try:
                payload = json.loads(text) if text else None
            except json.JSONDecodeError:
                payload = {"_raw_preview": text[:400]}
            return resp.status, payload, meta, None
    except urllib.error.HTTPError as exc:
        body = exc.read()
        meta = {
            "http": exc.code,
            "content_type": exc.headers.get("Content-Type") if exc.headers else None,
            "content_disposition": exc.headers.get("Content-Disposition") if exc.headers else None,
            "bytes": len(body),
        }
        text = body.decode("utf-8", "replace")
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            payload = {"message": text[:800]}
        if raw:
            return exc.code, body, meta, None
        return exc.code, payload, meta, None
    except Exception as exc:  # noqa: BLE001
        return None, {"error": type(exc).__name__, "message": str(exc)[:300]}, {}, str(exc)


def limpiar(v: Any, d: int = 0) -> Any:
    if d > 12:
        return "..."
    if isinstance(v, dict):
        out = {}
        for k, x in v.items():
            kl = str(k).lower()
            if kl in ("token", "access_token", "client_secret", "contrasena", "password") or kl.endswith("_token"):
                out[k] = {"omitido": True}
            elif SENSITIVE_KEY_RE.search(str(k)):
                out[k] = {"omitido": True, "motivo": "clave_sensible"}
            else:
                out[k] = limpiar(x, d + 1)
        return out
    if isinstance(v, list):
        return [limpiar(x, d + 1) for x in v[:60]]
    if isinstance(v, str):
        if SENSITIVE_VALUE_RE.search(v):
            return {"omitido": True, "motivo": "valor_sensible"}
        if len(v) > 400:
            return v[:400] + "…"
    return v


def badge(estado: str) -> str:
    c = {"APROBADO": "#1b7a3d", "RECHAZADO": "#b00020", "BLOQUEADO": "#9a6b00", "NO APLICA": "#555"}.get(estado, "#333")
    return (
        f'<span style="display:inline-block;padding:2px 10px;border-radius:4px;'
        f'background:{c};color:#fff;font-weight:600">{html.escape(estado)}</span>'
    )


def code_of(body: Any) -> Optional[str]:
    if not isinstance(body, dict):
        return None
    if body.get("error_code"):
        return body.get("error_code")
    if body.get("code"):
        return body.get("code")
    detail = body.get("detail")
    if isinstance(detail, dict):
        return detail.get("error_code") or detail.get("code")
    return None


def cred(prefijo: str) -> tuple[Optional[str], Optional[str]]:
    aliases = {
        "ADMIN": ("QA_ADMIN_CORREO", "QA_ADMIN_CONTRASENA", "TEST_ADMIN_EMAIL", "TEST_ADMIN_PASSWORD"),
        "AUDITOR": ("QA_AUDITOR_CORREO", "QA_AUDITOR_CONTRASENA", "TEST_AUDITOR_EMAIL", "TEST_AUDITOR_PASSWORD"),
        "SIN": ("QA_SIN_PERMISO_CORREO", "QA_SIN_PERMISO_CONTRASENA", "TEST_SIN_PERMISO_EMAIL", "TEST_SIN_PERMISO_PASSWORD"),
    }
    keys = aliases[prefijo]
    return os.environ.get(keys[0]) or os.environ.get(keys[2]), os.environ.get(keys[1]) or os.environ.get(keys[3])


def login(correo: str, clave: str):
    return pedir("POST", "/sesiones/", {"correo_electronico": correo, "contrasena": clave})[:2]


def exportar(token: str, formato: str, **params):
    q = {"formato": formato, **{k: v for k, v in params.items() if v is not None}}
    ruta = ENDPOINT_EXPORT + "?" + urlencode(q)
    return pedir("GET", ruta, token=token, raw=True)


def consultar(token: str, **params):
    q = urlencode({k: v for k, v in params.items() if v is not None})
    ruta = ENDPOINT_AUDIT + (("?" + q) if q else "")
    return pedir("GET", ruta, token=token)[:2]


def parse_csv(data: bytes) -> list[dict]:
    text = data.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    return list(reader)


def parse_json_export(data: bytes) -> list[dict]:
    payload = json.loads(data.decode("utf-8"))
    if isinstance(payload, list):
        return payload
    raise ValueError("JSON de exportación no es lista")


def norm_val(v: Any) -> Any:
    if v is None or v == "":
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, str):
        s = v.strip()
        if s.lower() in ("null", "none"):
            return None
        # CSV puede traer dicts serializados
        if (s.startswith("{") and s.endswith("}")) or (s.startswith("[") and s.endswith("]")):
            try:
                return json.loads(s)
            except json.JSONDecodeError:
                pass
        return s
    if isinstance(v, dict):
        return {k: norm_val(x) for k, x in v.items()}
    if isinstance(v, list):
        return [norm_val(x) for x in v]
    return str(v)


def fila_clave(row: dict) -> dict:
    out = {}
    for k in CAMPOS_CLAVE:
        out[k] = norm_val(row.get(k))
    # normalizar codigo_http a int si posible
    ch = out.get("codigo_http")
    if isinstance(ch, str) and ch.isdigit():
        out["codigo_http"] = int(ch)
    ice = out.get("id_cliente_externo")
    if isinstance(ice, str) and ice.isdigit():
        out["id_cliente_externo"] = int(ice)
    return out


def ids_de(rows: list[dict]) -> list[str]:
    return [str(r.get("id_evento_integracion")) for r in rows if r.get("id_evento_integracion") not in (None, "")]


def estado_final_de(escenarios: list[dict]) -> str:
    estados = [e["estado"] for e in escenarios]
    if any(s == "RECHAZADO" for s in estados):
        return "RECHAZADO"
    if any(s == "BLOQUEADO" for s in estados):
        return "BLOQUEADO"
    if all(s == "NO APLICA" for s in estados):
        return "NO APLICA"
    if any(s == "APROBADO" for s in estados) and all(s in ("APROBADO", "NO APLICA") for s in estados):
        return "APROBADO"
    return "BLOQUEADO"


def muestra_redactada(rows: list[dict], n: int = 3) -> list[dict]:
    return [limpiar(r) for r in rows[:n]]


# Metadatos de auditoría que mencionan secretos/tokens sin exponer el valor vivo.
_META_OK = {
    "hash_integridad", "hash_contenido",
    "secreto_provisto",  # bool: indica si se entregó secreto, no el valor
    "ttl_token_canal_minutos",  # TTL numérico, no el token
}


def _valor_parece_secreto(v: Any) -> bool:
    if v is None or isinstance(v, (bool, int, float)):
        return False
    if isinstance(v, str):
        if SENSITIVE_VALUE_RE.search(v):
            return True
        # cadenas opacas largas tipo secret/token (evitar falsos positivos cortos)
        if len(v) >= 24 and re.fullmatch(r"[A-Za-z0-9_\-+/=]{24,}", v):
            return True
    return False


def scan_seguridad(rows: list[dict]) -> dict:
    hallazgos = []
    claves_examinadas = set()
    meta_documentados = []
    for i, row in enumerate(rows):
        for k, v in row.items():
            claves_examinadas.add(k)
            kl = str(k).lower()
            if kl in _META_OK:
                continue
            if SENSITIVE_KEY_RE.search(str(k)) and _valor_parece_secreto(v):
                hallazgos.append({"fila": i, "campo": k, "motivo": "valor_secreto_en_campo_sensible"})
            elif SENSITIVE_KEY_RE.search(str(k)) and _valor_parece_secreto(v) is False and v not in (None, ""):
                # nombre sensible pero valor no secreto → documentar, no fallar
                meta_documentados.append({"fila": i, "campo": k, "tipo": type(v).__name__})
            if isinstance(v, str) and SENSITIVE_VALUE_RE.search(v):
                hallazgos.append({"fila": i, "campo": k, "motivo": "patron_secreto_en_valor"})
            if isinstance(v, dict):
                blob = json.dumps(v, ensure_ascii=False)
                if SENSITIVE_VALUE_RE.search(blob):
                    hallazgos.append({"fila": i, "campo": k, "motivo": "patron_secreto_en_json_detalle"})
                for sk, sv in v.items():
                    skl = str(sk).lower()
                    if skl in _META_OK:
                        meta_documentados.append({
                            "fila": i, "campo": f"{k}.{sk}", "tipo": type(sv).__name__,
                            "nota": "metadato auditado sin valor secreto vivo",
                        })
                        continue
                    if SENSITIVE_KEY_RE.search(str(sk)) and _valor_parece_secreto(sv):
                        hallazgos.append({"fila": i, "campo": f"{k}.{sk}", "motivo": "secreto_vivo_anidado"})
                    elif SENSITIVE_KEY_RE.search(str(sk)):
                        meta_documentados.append({
                            "fila": i, "campo": f"{k}.{sk}", "tipo": type(sv).__name__,
                            "nota": "clave sensible sin valor secreto",
                        })
    return {
        "filas_examinadas": len(rows),
        "claves_examinadas": sorted(claves_examinadas),
        "hallazgos": hallazgos[:50],
        "total_hallazgos": len(hallazgos),
        "metadatos_sensibles_sin_secreto": meta_documentados[:30],
        "ok": len(hallazgos) == 0,
        "nota": (
            "Se rechaza solo exposición de secretos vivos (tokens JWT, API keys, client secrets, HMAC). "
            "hash_contenido/hash_integridad y flags como secreto_provisto=false son metadatos esperados."
        ),
    }


def render_html(data: dict) -> str:
    filas = []
    for e in data["escenarios"]:
        filas.append(
            "<tr>"
            f"<td>{html.escape(e['id'])}</td><td>{html.escape(e['nombre'])}</td>"
            f"<td>{badge(e['estado'])}</td>"
            f"<td>{html.escape(e.get('validacion',''))}</td>"
            f"<td>{html.escape(e.get('evidencia',''))}</td>"
            "</tr>"
        )
    det = []
    for e in data["escenarios"]:
        pasos = "".join(f"<li>{html.escape(p)}</li>" for p in (e.get("pasos") or []))
        det.append(
            f"<div class='card'><h3>{html.escape(e['id'])}: {html.escape(e['nombre'])} {badge(e['estado'])}</h3>"
            f"<p><strong>Esperado:</strong> {html.escape(e.get('esperado',''))}</p>"
            f"<p><strong>Obtenido:</strong> {html.escape(e.get('obtenido',''))}</p>"
            f"<p><strong>Evidencia:</strong> <code>{html.escape(e.get('evidencia',''))}</code></p>"
            f"<ul>{pasos}</ul>"
            f"<p><strong>Observaciones:</strong> {html.escape(e.get('observaciones',''))}</p></div>"
        )
    return f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8"/>
<title>{html.escape(CASO)} — {html.escape(RF)} — {html.escape(data['estado_final'])}</title>
<style>
body{{font-family:Segoe UI,Arial,sans-serif;margin:24px;background:#f7f7f5;color:#1a1a1a}}
.card{{background:#fff;border:1px solid #ddd;border-radius:8px;padding:16px;margin:16px 0}}
table{{border-collapse:collapse;width:100%;font-size:13px}} th,td{{border:1px solid #ddd;padding:8px;vertical-align:top;text-align:left}}
th{{background:#e8eef5}} .note{{background:#eef6ff;border-left:4px solid #2563eb;padding:10px;margin:12px 0}}
.lim{{background:#fff8e6;border-left:4px solid #9a6b00;padding:10px;margin:12px 0}}
.meta span{{display:inline-block;margin-right:16px;margin-bottom:6px}}
</style></head><body>
<h1>{html.escape(CASO)} — Exportación de registros de auditoría</h1>
<div class="card meta">
  <span><strong>RF-102 · CU07 · TC-M07-102-014</strong></span>
  <span><strong>Endpoint:</strong> GET {html.escape(ENDPOINT_EXPORT)}</span>
  <span><strong>Formatos:</strong> csv, json</span>
  <span><strong>Estado:</strong> {badge(data['estado_final'])}</span>
  <span><strong>UTC:</strong> {html.escape(data['fecha_ejecucion_utc'])}</span>
</div>
<div class="note">Permiso real: <code>auditoria_integracion:E</code>.
Filtros: {html.escape(', '.join(FILTROS))}.
Exportación siempre en vista completa (restringida=False). Límite 50.000.
Evidencias HTML/JSON redactan secretos; archivos originales en Resultado con hash SHA-256.</div>
<div class="card"><h2>Escenarios</h2>
<table><thead><tr><th>ID</th><th>Nombre</th><th>Estado</th><th>Validación</th><th>Evidencia</th></tr></thead>
<tbody>{''.join(filas)}</tbody></table></div>
{''.join(det)}
<div class="card"><h2>Diagnóstico</h2>
<pre>{html.escape(json.dumps(data.get('diagnostico', {}), ensure_ascii=False, indent=2))}</pre></div>
<div class="lim"><h3>Limitaciones</h3><pre>{html.escape(json.dumps(data.get('limitaciones', []), ensure_ascii=False, indent=2))}</pre></div>
<div class="card"><h3>Resumen</h3><pre>{html.escape(json.dumps(data.get('resumen', {}), ensure_ascii=False, indent=2))}</pre></div>
</body></html>"""


def main() -> int:
    RESULTADO.mkdir(parents=True, exist_ok=True)
    limitaciones: list[str] = []
    escenarios: list[dict] = []
    pet: list[dict] = []

    admin_c, admin_p = cred("ADMIN")
    aud_c, aud_p = cred("AUDITOR")
    sin_c, sin_p = cred("SIN")
    if not all([admin_c, admin_p, aud_c, aud_p, sin_c, sin_p]):
        data = {
            "caso": CASO, "fecha_ejecucion_utc": ahora(), "estado_final": "BLOQUEADO",
            "escenarios": [], "limitaciones": ["Faltan QA_ADMIN_*/QA_AUDITOR_*/QA_SIN_PERMISO_*"],
            "resumen": {"aprobados": 0, "rechazados": 0, "bloqueados": 6, "no_aplica": 0, "estado_final": "BLOQUEADO"},
            "diagnostico": {},
        }
        (RESULTADO / "evidencia_ejecucion_TC-M07-G057.json").write_text(
            json.dumps(limpiar(data), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (RESULTADO / "resultado_TC-M07-G057.html").write_text(render_html(data), encoding="utf-8")
        print(json.dumps({"caso": CASO, "estado_final": "BLOQUEADO"}, ensure_ascii=False, indent=2))
        return 2

    st_a, login_a = login(admin_c, admin_p)
    token_admin = (login_a or {}).get("token") if isinstance(login_a, dict) else None
    st_r, login_r = login(aud_c, aud_p)
    token_aud = (login_r or {}).get("token") if isinstance(login_r, dict) else None
    st_s, login_s = login(sin_c, sin_p)
    token_sin = (login_s or {}).get("token") if isinstance(login_s, dict) else None
    pet.append({"fase": "login", "admin": st_a, "auditor": st_r, "sin": st_s})
    if not token_admin or not token_aud or not token_sin:
        raise SystemExit(f"Login falló admin={st_a} auditor={st_r} sin={st_s}")

    # Baseline consulta
    st0, body0 = consultar(token_admin, pagina=1, tamano=100)
    total_ref = (body0 or {}).get("total") if isinstance(body0, dict) else None
    items0 = (body0 or {}).get("items") or [] if isinstance(body0, dict) else []
    pet.append({"fase": "baseline_consulta", "http": st0, "total": total_ref, "items": len(items0)})

    diagnostico = {
        "fecha_utc": ahora(),
        "endpoint": "GET " + ENDPOINT_EXPORT,
        "formatos": ["csv", "json"],
        "formato_default": "csv",
        "filtros": list(FILTROS),
        "permiso": "auditoria_integracion:E",
        "content_types": {
            "csv": "text/csv; charset=utf-8",
            "json": "application/json",
        },
        "content_disposition": 'attachment; filename="auditoria_integracion_YYYYMMDD_HHMMSS.{formato}"',
        "limite_exportacion": 50000,
        "vista": "completa (restringida=False)",
        "baseline_consulta_total": total_ref,
        "baseline_consulta_http": st0,
    }

    # ========== E1 CSV ==========
    st_csv, body_csv, meta_csv, _ = exportar(token_admin, "csv")
    e1_pasos = [f"GET {ENDPOINT_EXPORT}?formato=csv HTTP {st_csv}"]
    csv_ok = False
    rows_csv: list[dict] = []
    csv_path = RESULTADO / "export_original_csv_TC-M07-G057.csv"
    if st_csv == 200 and isinstance(body_csv, (bytes, bytearray)):
        csv_path.write_bytes(body_csv)
        ctype_ok = "text/csv" in (meta_csv.get("content_type") or "").lower()
        disp = meta_csv.get("content_disposition") or ""
        disp_ok = "attachment" in disp.lower() and ".csv" in disp.lower()
        has_bom = body_csv.startswith(b"\xef\xbb\xbf")
        try:
            rows_csv = parse_csv(body_csv)
            parse_ok = True
        except Exception as exc:  # noqa: BLE001
            parse_ok = False
            e1_pasos.append(f"parse error: {exc}")
        headers = list(rows_csv[0].keys()) if rows_csv else []
        no_vacio = len(rows_csv) > 0 if (total_ref or 0) > 0 else True
        ids = ids_de(rows_csv)
        dup = [i for i, n in Counter(ids).items() if n > 1]
        especiales = sum(
            1 for r in rows_csv for v in r.values()
            if isinstance(v, str) and any(ch in v for ch in (",", '"', "\n", "á", "é", "í", "ó", "ú", "ñ"))
        )
        e1_pasos.extend([
            f"Content-Type={meta_csv.get('content_type')} ok={ctype_ok}",
            f"Content-Disposition={disp} ok={disp_ok}",
            f"bytes={meta_csv.get('bytes')} sha256={sha256_bytes(body_csv)}",
            f"filas={len(rows_csv)} headers={len(headers)} duplicados_id={len(dup)} especiales≈{especiales}",
            f"utf8_bom={has_bom}",
        ])
        csv_ok = (
            ctype_ok and disp_ok and parse_ok and no_vacio and not dup
            and "id_evento_integracion" in headers and "tipo_evento" in headers
        )
        e1_estado = "APROBADO" if csv_ok else "RECHAZADO"
        e1_obt = (
            f"HTTP {st_csv}; ctype={meta_csv.get('content_type')}; filas={len(rows_csv)}; "
            f"dup={len(dup)}; headers={headers[:8]}…"
        )
    else:
        e1_estado = "RECHAZADO"
        e1_obt = f"HTTP {st_csv} meta={meta_csv}"
        parse_ok = False
        headers = []
        dup = []
        especiales = 0

    e1 = {
        "id": "E1", "nombre": "Exportación CSV por Administrador", "caso_original": "TC-M07-102-014",
        "estado": e1_estado, "validacion": "CSV válido descargable",
        "esperado": "HTTP 200, text/csv, Content-Disposition attachment, filas coherentes",
        "obtenido": e1_obt, "evidencia": "evidencia_e1_export_csv_TC-M07-G057.json",
        "pasos": e1_pasos,
        "observaciones": "Archivo original: export_original_csv_TC-M07-G057.csv",
    }
    escenarios.append(e1)
    (RESULTADO / e1["evidencia"]).write_text(json.dumps(limpiar({
        "fecha_utc": ahora(), "http": st_csv, "meta": meta_csv,
        "sha256": sha256_bytes(body_csv) if isinstance(body_csv, (bytes, bytearray)) else None,
        "archivo": csv_path.name if csv_path.exists() else None,
        "n_filas": len(rows_csv), "headers": headers if 'headers' in dir() else [],
        "duplicados_id": dup if isinstance(dup, list) else [],
        "campos_especiales_aproximados": especiales if isinstance(especiales, int) else 0,
        "muestra": muestra_redactada(rows_csv),
        "estado": e1_estado,
    }), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # ========== E2 JSON ==========
    st_json, body_json, meta_json, _ = exportar(token_admin, "json")
    e2_pasos = [f"GET {ENDPOINT_EXPORT}?formato=json HTTP {st_json}"]
    rows_json: list[dict] = []
    json_path = RESULTADO / "export_original_json_TC-M07-G057.json"
    if st_json == 200 and isinstance(body_json, (bytes, bytearray)):
        # No guardar JSON completo con IPs en evidencia HTML; sí archivo original para verificación
        json_path.write_bytes(body_json)
        ctype_ok = "application/json" in (meta_json.get("content_type") or "").lower()
        disp = meta_json.get("content_disposition") or ""
        disp_ok = "attachment" in disp.lower() and ".json" in disp.lower()
        try:
            rows_json = parse_json_export(body_json)
            # verificar no es error envuelto
            es_error = isinstance(rows_json, dict)  # type: ignore[unreachable]
            parse_ok = isinstance(rows_json, list)
        except Exception as exc:  # noqa: BLE001
            parse_ok = False
            e2_pasos.append(f"parse error: {exc}")
            es_error = True
        no_vacio = len(rows_json) > 0 if (total_ref or 0) > 0 else True
        ids = ids_de(rows_json)
        dup = [i for i, n in Counter(ids).items() if n > 1]
        claves = sorted(rows_json[0].keys()) if rows_json else []
        e2_pasos.extend([
            f"Content-Type={meta_json.get('content_type')} ok={ctype_ok}",
            f"Content-Disposition={disp} ok={disp_ok}",
            f"bytes={meta_json.get('bytes')} sha256={sha256_bytes(body_json)}",
            f"registros={len(rows_json)} duplicados={len(dup)} claves={len(claves)}",
        ])
        json_ok = ctype_ok and disp_ok and parse_ok and no_vacio and not dup and "id_evento_integracion" in claves
        e2_estado = "APROBADO" if json_ok else "RECHAZADO"
        e2_obt = f"HTTP {st_json}; registros={len(rows_json)}; dup={len(dup)}; ctype={meta_json.get('content_type')}"
    else:
        # podría ser JSON de error
        e2_estado = "RECHAZADO"
        e2_obt = f"HTTP {st_json} — posible error, no archivo"
        dup = []
        claves = []
        parse_ok = False

    e2 = {
        "id": "E2", "nombre": "Exportación JSON por Administrador", "caso_original": "TC-M07-102-014",
        "estado": e2_estado, "validacion": "JSON válido descargable",
        "esperado": "HTTP 200, application/json, lista de registros, no JSON de error",
        "obtenido": e2_obt, "evidencia": "evidencia_e2_export_json_TC-M07-G057.json",
        "pasos": e2_pasos,
        "observaciones": "Archivo original: export_original_json_TC-M07-G057.json (revisar fuera de HTML)",
    }
    escenarios.append(e2)
    (RESULTADO / e2["evidencia"]).write_text(json.dumps(limpiar({
        "fecha_utc": ahora(), "http": st_json, "meta": meta_json,
        "sha256": sha256_bytes(body_json) if isinstance(body_json, (bytes, bytearray)) else None,
        "archivo": json_path.name if json_path.exists() else None,
        "n_registros": len(rows_json), "claves": claves if 'claves' in dir() else [],
        "duplicados_id": dup if isinstance(dup, list) else [],
        "muestra": muestra_redactada(rows_json),
        "estado": e2_estado,
    }), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # ========== E3 Consistencia ==========
    e3_pasos = []
    if rows_csv and rows_json:
        map_csv = {str(r.get("id_evento_integracion")): fila_clave(r) for r in rows_csv}
        map_json = {str(r.get("id_evento_integracion")): fila_clave(r) for r in rows_json}
        set_c, set_j = set(map_csv), set(map_json)
        solo_csv = sorted(set_c - set_j)[:20]
        solo_json = sorted(set_j - set_c)[:20]
        comunes = set_c & set_j
        diffs = []
        for i in list(comunes)[:5000]:
            if map_csv[i] != map_json[i]:
                # detallar campos distintos
                dc = {k: (map_csv[i].get(k), map_json[i].get(k))
                      for k in CAMPOS_CLAVE if map_csv[i].get(k) != map_json[i].get(k)}
                diffs.append({"id": i, "diff": dc})
                if len(diffs) >= 20:
                    break
        # campos solo en un formato
        campos_csv = set(rows_csv[0].keys()) if rows_csv else set()
        campos_json = set(rows_json[0].keys()) if rows_json else set()
        e3_pasos = [
            f"CSV filas={len(rows_csv)} JSON registros={len(rows_json)}",
            f"ids iguales={set_c == set_j}",
            f"solo_csv={len(set_c - set_j)} solo_json={len(set_j - set_c)} diffs_campos_clave={len(diffs)}",
            f"campos_solo_csv={sorted(campos_csv - campos_json)}",
            f"campos_solo_json={sorted(campos_json - campos_csv)}",
        ]
        # Nota: CSV serializa todo a str; comparación usa norm_val
        e3_ok = set_c == set_j and len(diffs) == 0 and len(rows_csv) == len(rows_json)
        e3_estado = "APROBADO" if e3_ok else "RECHAZADO"
        e3_obt = (
            f"n_csv={len(rows_csv)} n_json={len(rows_json)} "
            f"ids_match={set_c == set_j} diffs={len(diffs)}"
        )
        e3_detail = {
            "n_csv": len(rows_csv), "n_json": len(rows_json),
            "ids_iguales": set_c == set_j,
            "solo_csv_muestra": solo_csv, "solo_json_muestra": solo_json,
            "diffs_muestra": diffs,
            "campos_solo_csv": sorted(campos_csv - campos_json),
            "campos_solo_json": sorted(campos_json - campos_csv),
        }
    else:
        e3_estado = "BLOQUEADO"
        e3_obt = "Sin ambas exportaciones parseadas"
        e3_detail = {}
        limitaciones.append("E3 bloqueado: faltó CSV o JSON válido")

    e3 = {
        "id": "E3", "nombre": "Consistencia CSV vs JSON", "caso_original": "TC-M07-102-014",
        "estado": e3_estado, "validacion": "Mismo conjunto de registros",
        "esperado": "Mismos ids y campos clave con mismos filtros (sin filtro)",
        "obtenido": e3_obt, "evidencia": "evidencia_e3_consistencia_TC-M07-G057.json",
        "pasos": e3_pasos,
        "observaciones": "Normalización: CSV→str; dicts JSON-en-celda; null/vacío equivalentes",
    }
    escenarios.append(e3)
    (RESULTADO / e3["evidencia"]).write_text(json.dumps(limpiar({
        "fecha_utc": ahora(), "estado": e3_estado, **e3_detail,
    }), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # ========== E4 Filtros ==========
    # tomar valores de muestra
    def primer(campo: str):
        for it in items0:
            v = it.get(campo)
            if v not in (None, ""):
                return v
        # fallback desde export json
        for it in rows_json:
            v = it.get(campo)
            if v not in (None, ""):
                return v
        return None

    vals = {
        "tipo_evento": primer("tipo_evento"),
        "codigo_http": primer("codigo_http"),
        "endpoint": primer("endpoint"),
        "id_cliente_externo": primer("id_cliente_externo"),
        "desde": (str(primer("fecha_evento") or "")[:10] or None),
        "hasta": (str(primer("fecha_evento") or "")[:10] or None),
        "numero_id_tributaria": primer("numero_id_tributaria"),
    }
    filtros_prueba = []
    # individual tipo_evento
    if vals["tipo_evento"]:
        filtros_prueba.append({"nombre": "tipo_evento", "params": {"tipo_evento": vals["tipo_evento"]}})
    if vals["tipo_evento"] and vals["codigo_http"] is not None:
        filtros_prueba.append({
            "nombre": "tipo_evento+codigo_http",
            "params": {"tipo_evento": vals["tipo_evento"], "codigo_http": vals["codigo_http"]},
        })
    if vals["desde"] and vals["hasta"]:
        filtros_prueba.append({"nombre": "desde+hasta", "params": {"desde": vals["desde"], "hasta": vals["hasta"]}})

    e4_resultados = []
    e4_ok = True
    e4_pasos = [f"Filtros contrato: {list(FILTROS)}", f"Valores muestra: { {k: vals[k] for k in vals if vals[k] is not None} }"]
    if not filtros_prueba:
        e4_estado = "BLOQUEADO"
        e4_obt = "Sin valores de filtro en muestra"
        limitaciones.append("E4: sin valores de filtro utilizables en baseline")
        e4_ok = False
    else:
        for fp in filtros_prueba:
            params = fp["params"]
            st_qc, body_qc = consultar(token_admin, pagina=1, tamano=100, **params)
            total_q = (body_qc or {}).get("total") if isinstance(body_qc, dict) else None
            items_q = (body_qc or {}).get("items") or [] if isinstance(body_qc, dict) else []

            st_fc, body_fc, meta_fc, _ = exportar(token_admin, "csv", **params)
            st_fj, body_fj, meta_fj, _ = exportar(token_admin, "json", **params)
            rows_fc = parse_csv(body_fc) if st_fc == 200 and isinstance(body_fc, (bytes, bytearray)) else []
            rows_fj = parse_json_export(body_fj) if st_fj == 200 and isinstance(body_fj, (bytes, bytearray)) else []

            # todos cumplen filtro
            def cumple(row, p):
                for k, v in p.items():
                    if k == "desde":
                        fe = str(row.get("fecha_evento") or "")[:10]
                        if not fe or fe < str(v):
                            return False
                    elif k == "hasta":
                        fe = str(row.get("fecha_evento") or "")[:10]
                        if not fe or fe > str(v):
                            return False
                    else:
                        rv = row.get(k)
                        if k == "codigo_http":
                            try:
                                if int(rv) != int(v):
                                    return False
                            except (TypeError, ValueError):
                                return False
                        elif k == "id_cliente_externo":
                            try:
                                if int(rv) != int(v):
                                    return False
                            except (TypeError, ValueError):
                                return False
                        elif str(rv) != str(v):
                            return False
                return True

            all_csv = all(cumple(r, params) for r in rows_fc) if rows_fc else st_fc == 200 and total_q == 0
            all_json = all(cumple(r, params) for r in rows_fj) if rows_fj else st_fj == 200 and total_q == 0
            count_match = (len(rows_fc) == len(rows_fj) == total_q) if total_q is not None else False
            # si total > 100, consulta no trae todos; comparar export vs total
            if total_q is not None and total_q > 100:
                count_match = len(rows_fc) == len(rows_fj) == total_q
            ids_match = set(ids_de(rows_fc)) == set(ids_de(rows_fj))
            ok = st_fc == 200 and st_fj == 200 and all_csv and all_json and count_match and ids_match
            if not ok:
                e4_ok = False
            e4_resultados.append({
                "filtro": fp["nombre"], "params": params,
                "consulta_http": st_qc, "consulta_total": total_q, "consulta_items_pagina": len(items_q),
                "csv_http": st_fc, "csv_filas": len(rows_fc), "csv_cumplen": all_csv,
                "json_http": st_fj, "json_regs": len(rows_fj), "json_cumplen": all_json,
                "conteos_iguales": count_match, "ids_csv_json_iguales": ids_match, "ok": ok,
            })
            e4_pasos.append(
                f"{fp['nombre']}: consulta_total={total_q} csv={len(rows_fc)} json={len(rows_fj)} ok={ok}"
            )
        e4_estado = "APROBADO" if e4_ok else "RECHAZADO"
        e4_obt = f"{sum(1 for r in e4_resultados if r['ok'])}/{len(e4_resultados)} filtros OK"

    e4 = {
        "id": "E4", "nombre": "Exportación con filtros", "caso_original": "TC-M07-102-014",
        "estado": e4_estado, "validacion": "Filtros respetados en CSV/JSON y vs consulta",
        "esperado": "Export filtrado = mismo conjunto; coherente con total de consulta",
        "obtenido": e4_obt, "evidencia": "evidencia_e4_filtros_TC-M07-G057.json",
        "pasos": e4_pasos,
        "observaciones": "Export no pagina; se compara n_export con total de GET /auditoria",
    }
    escenarios.append(e4)
    (RESULTADO / e4["evidencia"]).write_text(json.dumps(limpiar({
        "fecha_utc": ahora(), "filtros_contrato": list(FILTROS), "valores": vals,
        "resultados": e4_resultados, "estado": e4_estado,
    }), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # ========== E5 Seguridad ==========
    scan = scan_seguridad(rows_json or rows_csv)
    e5_pasos = [
        f"Filas examinadas={scan['filas_examinadas']}",
        f"Claves={scan['claves_examinadas']}",
        f"Hallazgos={scan['total_hallazgos']}",
        scan["nota"],
    ]
    e5_estado = "APROBADO" if scan["ok"] else "RECHAZADO"
    e5 = {
        "id": "E5", "nombre": "Protección de la información exportada", "caso_original": "TC-M07-102-014",
        "estado": e5_estado, "validacion": "Sin secretos vivos en exportación Admin",
        "esperado": "Sin passwords/tokens/API keys/client secrets/HMAC vivos; hashes de integridad permitidos",
        "obtenido": f"hallazgos={scan['total_hallazgos']}", "evidencia": "evidencia_e5_seguridad_TC-M07-G057.json",
        "pasos": e5_pasos,
        "observaciones": (
            "Admin exporta vista completa (ip_origen, json_detalle). "
            "Se valida ausencia de secretos de autenticación, no el ocultamiento de IP al Auditor."
        ),
    }
    escenarios.append(e5)
    (RESULTADO / e5["evidencia"]).write_text(json.dumps(limpiar({
        "fecha_utc": ahora(), "scan": scan, "estado": e5_estado,
    }), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # ========== E6 Permisos ==========
    st_ea, body_ea, meta_ea, _ = exportar(token_admin, "json")
    st_er, body_er, meta_er, _ = exportar(token_aud, "json")
    st_es, body_es, meta_es, _ = exportar(token_sin, "json")
    # parse error bodies
    def err_code(raw, st):
        if st == 200:
            return None
        try:
            return code_of(json.loads(raw.decode("utf-8"))) if isinstance(raw, (bytes, bytearray)) else code_of(raw)
        except Exception:  # noqa: BLE001
            return None

    code_er = err_code(body_er, st_er)
    code_es = err_code(body_es, st_es)
    e6_ok = st_ea == 200 and st_er == 403 and st_es == 403
    e6_pasos = [
        f"Admin export JSON HTTP {st_ea}",
        f"Auditor (Revisor Fiscal) HTTP {st_er} code={code_er}",
        f"Sin permisos (Contador) HTTP {st_es} code={code_es}",
        "401 no aplica: los tres perfiles autenticaron correctamente",
    ]
    e6 = {
        "id": "E6", "nombre": "Regresión de permisos de exportación", "caso_original": "TC-M07-102-014",
        "estado": "APROBADO" if e6_ok else "RECHAZADO",
        "validacion": "Admin 200 / Auditor 403 / Sin permiso 403",
        "esperado": "Solo auditoria_integracion:E puede exportar",
        "obtenido": f"admin={st_ea} auditor={st_er}/{code_er} sin={st_es}/{code_es}",
        "evidencia": "evidencia_e6_permisos_TC-M07-G057.json",
        "pasos": e6_pasos,
        "observaciones": "Regresión breve respecto a G056 E2b/E3",
    }
    escenarios.append(e6)
    (RESULTADO / e6["evidencia"]).write_text(json.dumps(limpiar({
        "fecha_utc": ahora(),
        "admin": {"http": st_ea, "meta": meta_ea},
        "auditor": {"http": st_er, "code": code_er, "meta": meta_er,
                    "body": json.loads(body_er.decode()) if st_er != 200 and isinstance(body_er, (bytes, bytearray)) else None},
        "sin_permisos": {"http": st_es, "code": code_es, "meta": meta_es,
                         "body": json.loads(body_es.decode()) if st_es != 200 and isinstance(body_es, (bytes, bytearray)) else None},
        "estado": e6["estado"],
    }), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    limitaciones.extend([
        "No se modificó BD ni roles. Credenciales solo por entorno.",
        "Archivos originales de exportación conservados en Resultado; evidencias JSON/HTML redactadas.",
        "Intentos 403 de E6 pueden incrementar ACCESO_AUDITORIA_DENEGADO / denegaciones de permiso.",
        "G052–G056 no modificados.",
    ])

    diagnostico.update({
        "export_csv": {"http": st_csv, "filas": len(rows_csv), "sha256": sha256_bytes(body_csv) if isinstance(body_csv, (bytes, bytearray)) else None},
        "export_json": {"http": st_json, "registros": len(rows_json), "sha256": sha256_bytes(body_json) if isinstance(body_json, (bytes, bytearray)) else None},
    })
    (RESULTADO / "diagnostico_exportacion_TC-M07-G057.json").write_text(
        json.dumps(limpiar(diagnostico), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    counts = {
        "aprobados": sum(1 for e in escenarios if e["estado"] == "APROBADO"),
        "rechazados": sum(1 for e in escenarios if e["estado"] == "RECHAZADO"),
        "bloqueados": sum(1 for e in escenarios if e["estado"] == "BLOQUEADO"),
        "no_aplica": sum(1 for e in escenarios if e["estado"] == "NO APLICA"),
    }
    final = estado_final_de(escenarios)
    counts["estado_final"] = final

    data = {
        "caso": CASO, "rf": RF, "fecha_ejecucion_utc": ahora(),
        "estado_final": final, "escenarios": escenarios,
        "diagnostico": diagnostico, "limitaciones": limitaciones,
        "resumen": counts, "peticiones": limpiar(pet),
        "registros_csv": len(rows_csv), "registros_json": len(rows_json),
        "endpoints_reales": {
            "exportacion": ENDPOINT_EXPORT,
            "consulta": ENDPOINT_AUDIT,
            "parametros": ["formato", *FILTROS],
        },
    }
    (RESULTADO / "evidencia_ejecucion_TC-M07-G057.json").write_text(
        json.dumps(limpiar(data), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (RESULTADO / "resultado_TC-M07-G057.html").write_text(render_html(data), encoding="utf-8")

    print("\n| Escenario | Validación | Resultado | Evidencia |")
    print("|---|---|---|---|")
    for e in escenarios:
        print(f"| {e['id']} | {e['validacion']} | {e['estado']} | {e['evidencia']} |")
    print(json.dumps({
        "caso": CASO, "estado_final": final, "resumen": counts,
        "registros_csv": len(rows_csv), "registros_json": len(rows_json),
    }, ensure_ascii=False, indent=2))
    return 0 if final in ("APROBADO", "NO APLICA") else (1 if final == "RECHAZADO" else 2)


if __name__ == "__main__":
    raise SystemExit(main())
