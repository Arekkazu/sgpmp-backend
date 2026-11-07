"""TC-M02-G16 — primera evaluacion RF-33 / CU01.

Ataques de inyeccion y abuso de recursos en POST /activos-biologicos.
Caja negra contra TEST. No modifica backend ni historicos de otros casos.
"""
from __future__ import annotations

import json
import os
import shutil
import time
import urllib3
from datetime import datetime, timezone
from pathlib import Path

import pytest
import requests

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DIR = Path(__file__).resolve().parent
RESULTADOS = DIR / "Resultados"
ENV_PATH = DIR / "environment-g16.json"

with ENV_PATH.open(encoding="utf-8") as fh:
    ENV = json.load(fh)

BASE_URL = ENV["baseUrl"].rstrip("/")
CORREO = ENV["correo_admin"]
TIMEOUT = 45
VERIFY_SSL = False

EVIDENCIA: dict = {
    "caso": "TC-M02-G16",
    "evaluacion": "primera",
    "rf": "RF-33",
    "cu": "CU01",
    "ambiente": "TEST",
    "base_url": BASE_URL,
    "fecha_utc": datetime.now(timezone.utc).isoformat(),
    "prechecks": {},
    "revision_codigo": {
        "identificador": "str opcional; requerido si INDIVIDUAL; columna String(50); unicidad ORM lower()",
        "atributos_dinamicos": "Optional[dict] -> JSONB; validacion por metricas TEXTO/NUMERICO/ENTERO/BOOLEANO",
        "consultas": "SQLAlchemy parametrizado (existe_identificador, guardar). No hay concatenacion SQL del identificador.",
        "rate_limit_post": (
            "POST /activos-biologicos NO usa src.shared.rate_limit. "
            "Solo datos-consolidados tiene rate_limit(100, 60). OpenAPI del POST no declara 429."
        ),
        "middlewares": "CORS + RequestContextMiddleware. Sin WAF/ZAP en el proceso de esta prueba.",
        "zap": "No instalado en la estacion QA. No se declara PASS de ZAP.",
        "k6": "No instalado; rafaga 032 se ejecuta en pytest con 101 POST invalidos.",
    },
    "subcasos": {},
    "ids_creados": [],
    "estado_global": "PENDIENTE",
    "auditoria": "Backend no modificado. Sin commit ni push. Primera evaluacion (no reevaluacion).",
}


def _password() -> str:
    valor = os.environ.get("SGPMP_TEST_PASSWORD") or os.environ.get("CONTRASENA") or ""
    if not valor:
        pytest.skip("BLOQUEADO: definir SGPMP_TEST_PASSWORD o CONTRASENA.")
    return valor


def _redact(obj):
    if obj is None:
        return None
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            kl = str(k).lower()
            if kl in ("token", "password", "contrasena", "authorization", "jwt", "access_token") or kl.endswith("_token"):
                out[k] = "[REDACTED]"
            else:
                out[k] = _redact(v)
        return out
    if isinstance(obj, list):
        return [_redact(x) for x in obj]
    if isinstance(obj, str) and obj.startswith("eyJ"):
        return "[REDACTED]"
    return obj


def _trunc(obj, n=1800):
    text = json.dumps(_redact(obj), ensure_ascii=False, default=str)
    if len(text) > n:
        return text[:n] + "...[TRUNCATED]"
    return text


def _json(r):
    try:
        return r.json()
    except Exception:
        return {"raw": (r.text or "")[:500]}


def _registros(body) -> list:
    if isinstance(body, list):
        return body
    if isinstance(body, dict):
        for k in ("registros", "items", "data"):
            v = body.get(k)
            if isinstance(v, list):
                return v
    return []


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _headers_quota(r: requests.Response) -> dict:
    out = {}
    for k, v in r.headers.items():
        lk = k.lower()
        if "ratelimit" in lk or lk in ("retry-after", "x-ratelimit-limit", "x-ratelimit-remaining"):
            out[k] = v
    return out


def _escribir() -> None:
    RESULTADOS.mkdir(parents=True, exist_ok=True)
    payload = _redact(EVIDENCIA)
    (RESULTADOS / "TC-M02-G16.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    lineas = [
        "TC-M02-G16 — primera evaluacion TEST",
        f"Fecha UTC: {payload.get('fecha_utc')}",
        f"Global: {payload.get('estado_global')}",
        "",
        "Subcasos:",
    ]
    for k, v in (payload.get("subcasos") or {}).items():
        lineas.append(f"- {k}: {v.get('resultado')}")
    lineas.append("")
    lineas.append(json.dumps(payload.get("subcasos"), ensure_ascii=False, indent=2, default=str))
    lineas.append("")
    lineas.append(payload.get("auditoria") or "")
    (RESULTADOS / "TC-M02-G16.txt").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    bloques = []
    for k, v in (payload.get("subcasos") or {}).items():
        bloques.append(
            f"<h2>{k}: {v.get('resultado')}</h2>"
            f"<pre>{json.dumps(v, ensure_ascii=False, indent=2, default=str)}</pre>"
        )
    (RESULTADOS / "TC-M02-G16-evidencia.html").write_text(
        "<!DOCTYPE html><html lang='es'><head><meta charset='utf-8'>"
        "<title>TC-M02-G16</title></head><body>"
        f"<h1>TC-M02-G16 primera evaluacion</h1><p>Global: {payload.get('estado_global')}</p>"
        + "".join(bloques)
        + "<p>Sin JWT/passwords. ZAP no ejecutado.</p></body></html>",
        encoding="utf-8",
    )
    (RESULTADOS / "TC-M02-G16-resumen.txt").write_text(
        "\n".join(lineas[:20]) + "\n",
        encoding="utf-8",
    )


def _base_individual(especie_id: int, infra_id: int, identificador: str, atributos=None) -> dict:
    return {
        "tipo_activo": "INDIVIDUAL",
        "id_especie": especie_id,
        "fecha_inicio_ciclo": "2026-09-09",
        "origen_financiero": "nacimiento",
        "id_infraestructura": infra_id,
        "atributos_dinamicos": atributos if atributos is not None else {},
        "identificador": identificador,
        "raza": "QA-G16",
        "sexo": "Macho",
        "fecha_nacimiento": "2025-01-15T00:00:00Z",
        "peso_inicial": 2.5,
        "costo_adquisicion": None,
        "soporte_documental": None,
    }


@pytest.fixture(scope="session")
def ctx():
    pwd = _password()
    openapi = requests.get(f"{BASE_URL}/openapi.json", timeout=TIMEOUT, verify=VERIFY_SSL)
    post_spec = {}
    if openapi.status_code == 200:
        spec = openapi.json()
        post_spec = (spec.get("paths") or {}).get("/activos-biologicos", {}).get("post") or {}
    EVIDENCIA["prechecks"]["openapi_http"] = openapi.status_code
    EVIDENCIA["prechecks"]["post_declara_429"] = "429" in str((post_spec.get("responses") or {}).keys())
    EVIDENCIA["prechecks"]["k6_en_path"] = bool(shutil.which("k6"))
    EVIDENCIA["prechecks"]["zap_en_path"] = bool(shutil.which("zap") or shutil.which("zap.sh"))

    login = requests.post(
        f"{BASE_URL}/sesiones/",
        json={"correo_electronico": CORREO, "contrasena": pwd},
        timeout=TIMEOUT,
        verify=VERIFY_SSL,
    )
    body = _json(login)
    token = body.get("token") if isinstance(body, dict) else None
    EVIDENCIA["prechecks"]["login_http"] = login.status_code
    if login.status_code != 200 or not token:
        _escribir()
        pytest.skip(f"BLOQUEADO: login HTTP {login.status_code}")
    headers = _auth(token)

    r_esp = requests.get(
        f"{BASE_URL}/configuracion/especies",
        headers=headers,
        timeout=TIMEOUT,
        verify=VERIFY_SSL,
    )
    especies = _registros(_json(r_esp)) if r_esp.status_code == 200 else []
    r_inf = requests.get(
        f"{BASE_URL}/configuracion/infraestructuras",
        params={"finca_id": 1, "solo_activas": True},
        headers=headers,
        timeout=TIMEOUT,
        verify=VERIFY_SSL,
    )
    infras = _registros(_json(r_inf)) if r_inf.status_code == 200 else []
    especie = next(
        (e for e in especies if e.get("id_especie") == 4),
        especies[0] if especies else None,
    )
    infra = infras[0] if infras else None
    EVIDENCIA["prechecks"]["especies_http"] = r_esp.status_code
    EVIDENCIA["prechecks"]["infra_http"] = r_inf.status_code
    EVIDENCIA["prechecks"]["especie_id"] = (especie or {}).get("id_especie") or (especie or {}).get("id")
    EVIDENCIA["prechecks"]["infra_id"] = (infra or {}).get("id_infraestructura") or (infra or {}).get("id")

    r_list = requests.get(
        f"{BASE_URL}/activos-biologicos",
        params={"pagina": 1, "page_size": 5},
        headers=headers,
        timeout=TIMEOUT,
        verify=VERIFY_SSL,
    )
    EVIDENCIA["prechecks"]["listado_inicial_http"] = r_list.status_code
    EVIDENCIA["prechecks"]["listado_inicial_n"] = len(_registros(_json(r_list))) if r_list.status_code == 200 else None

    data = {
        "headers": headers,
        "especie_id": EVIDENCIA["prechecks"]["especie_id"],
        "infra_id": EVIDENCIA["prechecks"]["infra_id"],
        "especies": especies,
    }
    yield data
    estados = [v.get("resultado") for v in (EVIDENCIA.get("subcasos") or {}).values()]
    if "RECHAZADO" in estados:
        EVIDENCIA["estado_global"] = "RECHAZADO"
    elif estados and all(e == "APROBADO" for e in estados):
        EVIDENCIA["estado_global"] = "APROBADO"
    elif estados and all(e == "BLOQUEADO" for e in estados):
        EVIDENCIA["estado_global"] = "BLOQUEADO"
    elif "BLOQUEADO" in estados and "RECHAZADO" not in estados:
        EVIDENCIA["estado_global"] = "BLOQUEADO"
    else:
        EVIDENCIA["estado_global"] = EVIDENCIA.get("estado_global") or "BLOQUEADO"
    _escribir()


def test_tc_m02_029_inyeccion_identificador(ctx):
    out = {
        "resultado": "BLOQUEADO",
        "endpoint": "POST /activos-biologicos",
        "intentos": [],
        "ids_creados": [],
    }
    EVIDENCIA["subcasos"]["TC-M02-029"] = out
    if not ctx["especie_id"] or not ctx["infra_id"]:
        out["explicacion"] = "BLOQUEADO: no hay especie/infraestructura activa para armar POST."
        pytest.skip(out["explicacion"])
    especie_id = int(ctx["especie_id"])
    infra_id = int(ctx["infra_id"])
    control_id = f"QA-G16-{int(time.time())}"[:50]
    r_ctrl = requests.post(
        f"{BASE_URL}/activos-biologicos",
        headers={**ctx["headers"], "Content-Type": "application/json"},
        json=_base_individual(especie_id, infra_id, control_id),
        timeout=TIMEOUT,
        verify=VERIFY_SSL,
    )
    b_ctrl = _json(r_ctrl)
    out["control"] = {
        "identificador": control_id,
        "http": r_ctrl.status_code,
        "content_type": r_ctrl.headers.get("Content-Type"),
        "error_code": b_ctrl.get("error_code") if isinstance(b_ctrl, dict) else None,
        "respuesta": _trunc(b_ctrl, 900),
    }
    if r_ctrl.status_code == 201:
        aid = b_ctrl.get("id_activo_biologico") or b_ctrl.get("id")
        out["ids_creados"].append(aid)
        EVIDENCIA["ids_creados"].append({"id": aid, "origen": "control_029"})

    payloads = [
        "BOV-1'; DROP TABLE activos;--",
        "BOV-1' OR '1'='1",
        'BOV-1"; DROP TABLE activos;--',
    ]
    for ident in payloads:
        r = requests.post(
            f"{BASE_URL}/activos-biologicos",
            headers={**ctx["headers"], "Content-Type": "application/json"},
            json=_base_individual(especie_id, infra_id, ident),
            timeout=TIMEOUT,
            verify=VERIFY_SSL,
        )
        body = _json(r)
        item = {
            "payload": ident,
            "http": r.status_code,
            "content_type": r.headers.get("Content-Type"),
            "error_code": body.get("error_code") if isinstance(body, dict) else None,
            "respuesta": _trunc(body, 700),
        }
        if r.status_code == 201:
            aid = body.get("id_activo_biologico") or body.get("id")
            item["id_creado"] = aid
            out["ids_creados"].append(aid)
            EVIDENCIA["ids_creados"].append({"id": aid, "origen": "029", "identificador": ident})
            g = requests.get(
                f"{BASE_URL}/activos-biologicos/{aid}",
                headers=ctx["headers"],
                timeout=TIMEOUT,
                verify=VERIFY_SSL,
            )
            gb = _json(g)
            item["get_http"] = g.status_code
            item["identificador_persistido"] = gb.get("identificador") if isinstance(gb, dict) else None
            item["persistido_como_texto"] = item["identificador_persistido"] == ident
        out["intentos"].append(item)

    r_ns = requests.post(
        f"{BASE_URL}/activos-biologicos",
        headers={**ctx["headers"], "Content-Type": "application/json"},
        json=_base_individual(especie_id, infra_id, "x") | {"identificador": {"$ne": None}},
        timeout=TIMEOUT,
        verify=VERIFY_SSL,
    )
    out["nosql_identificador_objeto"] = {
        "http": r_ns.status_code,
        "error_code": (_json(r_ns) or {}).get("error_code") if isinstance(_json(r_ns), dict) else None,
        "respuesta": _trunc(_json(r_ns), 600),
    }

    r_list = requests.get(
        f"{BASE_URL}/activos-biologicos",
        params={"pagina": 1, "page_size": 5},
        headers=ctx["headers"],
        timeout=TIMEOUT,
        verify=VERIFY_SSL,
    )
    out["integridad_listado_http"] = r_list.status_code
    out["tabla_disponible"] = r_list.status_code == 200

    https = [x["http"] for x in out["intentos"]]
    hay_500_iny = any(h == 500 for h in https)
    hay_201_iny = any(h == 201 for h in https)
    ctrl_500 = r_ctrl.status_code == 500
    nosql_ok = r_ns.status_code in (400, 422)

    if not out["tabla_disponible"]:
        out["resultado"] = "RECHAZADO"
        out["explicacion"] = (
            f"GET /activos-biologicos HTTP {r_list.status_code} tras payloads. "
            "No se demuestra integridad de la tabla."
        )
        pytest.fail(out["explicacion"])

    if ctrl_500 and hay_500_iny and not hay_201_iny:
        out["resultado"] = "BLOQUEADO"
        out["explicacion"] = (
            "POST valido de control y POST con payloads de inyeccion responden HTTP 500 "
            "ERROR_INTERNO. No se puede atribuir el 500 al contenido malicioso ni declarar "
            "proteccion. Residuo: ninguno si no hubo 201."
        )
        pytest.skip(out["explicacion"])

    if hay_500_iny and not ctrl_500:
        out["resultado"] = "RECHAZADO"
        out["explicacion"] = (
            "Un payload de identificador provo HTTP 500 y el control no. "
            "Posible fallo al interpretar el valor."
        )
        pytest.fail(out["explicacion"])

    if hay_201_iny:
        mal = [x for x in out["intentos"] if x.get("http") == 201 and not x.get("persistido_como_texto")]
        if mal:
            out["resultado"] = "RECHAZADO"
            out["explicacion"] = "Se creo activo pero el identificador no persiste como el texto enviado."
            pytest.fail(out["explicacion"])
        out["resultado"] = "APROBADO"
        out["explicacion"] = (
            "Payloads tratados como texto (201) o rechazados por validacion. "
            f"NoSQL objeto HTTP {r_ns.status_code}. Listado HTTP 200. "
            f"Residuo ids={out['ids_creados']} (sin DELETE: no hay mecanismo seguro)."
        )
        if not nosql_ok:
            out["resultado"] = "RECHAZADO"
            out["explicacion"] = (
                f"identificador como objeto {{$ne}} HTTP {r_ns.status_code}, esperado 400/422."
            )
            pytest.fail(out["explicacion"])
        return

    rechazos = all(h in (400, 409, 422) for h in https)
    if rechazos and nosql_ok and out["tabla_disponible"]:
        out["resultado"] = "APROBADO"
        out["explicacion"] = (
            "Identificadores de inyeccion rechazados por validacion (no 500). "
            f"NoSQL objeto HTTP {r_ns.status_code}. Listado HTTP 200. "
            f"Control HTTP {r_ctrl.status_code}."
        )
        return

    out["resultado"] = "RECHAZADO"
    out["explicacion"] = f"Combinacion HTTP no clasificable como proteccion: control={r_ctrl.status_code} iny={https}."
    pytest.fail(out["explicacion"])


def test_tc_m02_030_xss_atributos(ctx):
    out = {
        "resultado": "BLOQUEADO",
        "endpoint": "POST /activos-biologicos",
        "precondicion_texto": None,
        "intentos": [],
    }
    EVIDENCIA["subcasos"]["TC-M02-030"] = out
    if not ctx["especie_id"] or not ctx["infra_id"]:
        out["explicacion"] = "BLOQUEADO: sin especie/infra."
        pytest.skip(out["explicacion"])

    texto = None
    metricas_http = []
    for esp in (ctx.get("especies") or [])[:12]:
        eid = esp.get("id_especie") or esp.get("id")
        if eid is None:
            continue
        rm = requests.get(
            f"{BASE_URL}/configuracion/metricas",
            params={"id_especie": int(eid)},
            headers=ctx["headers"],
            timeout=TIMEOUT,
            verify=VERIFY_SSL,
        )
        metricas_http.append({"id_especie": int(eid), "http": rm.status_code})
        if rm.status_code != 200:
            continue
        body = _json(rm)
        items = _registros(body)
        if not items and isinstance(body, dict):
            items = body.get("metricas") or body.get("registros") or []
        for m in items:
            tipo = str(m.get("tipo_dato") or "").upper()
            nombre = m.get("nombre")
            aplica = str(m.get("aplica_a_tipo_activo") or "").upper()
            activo = m.get("es_activo")
            if tipo == "TEXTO" and nombre and activo is not False:
                if aplica in ("INDIVIDUAL", "AMBOS", ""):
                    texto = {
                        "id_especie": int(eid),
                        "nombre": nombre,
                        "aplica": aplica,
                        "obligatorio": m.get("es_obligatorio"),
                    }
                    break
        if texto:
            break

    out["metricas_http_muestra"] = metricas_http[:8]
    out["precondicion_texto"] = texto
    if texto is None:
        out["explicacion"] = (
            "BLOQUEADO: no hay especie con metrica activa tipo TEXTO visible por "
            "GET /configuracion/metricas. "
            f"Muestra HTTP={metricas_http[:5]}. No se inventa la metrica ni se crea en M09."
        )
        pytest.skip(out["explicacion"])

    especie_id = texto["id_especie"]
    nombre = texto["nombre"]
    infra_id = int(ctx["infra_id"])
    xss_payloads = [
        "<script>alert(1)</script>",
        "<img src=x onerror=alert(1)>",
        "' OR '1'='1",
        '"; DROP TABLE activos;--',
    ]
    for val in xss_payloads:
        ident = f"G16X{int(time.time()*1000)}"[-20:]
        r = requests.post(
            f"{BASE_URL}/activos-biologicos",
            headers={**ctx["headers"], "Content-Type": "application/json"},
            json=_base_individual(especie_id, infra_id, ident, {nombre: val}),
            timeout=TIMEOUT,
            verify=VERIFY_SSL,
        )
        body = _json(r)
        item = {
            "campo": nombre,
            "payload": val,
            "http": r.status_code,
            "content_type": r.headers.get("Content-Type"),
            "error_code": body.get("error_code") if isinstance(body, dict) else None,
            "respuesta": _trunc(body, 700),
            "html_sin_encoding": (
                "text/html" in (r.headers.get("Content-Type") or "").lower()
                and "<script" in (r.text or "").lower()
            ),
        }
        if r.status_code == 201:
            aid = body.get("id_activo_biologico") or body.get("id")
            item["id_creado"] = aid
            EVIDENCIA["ids_creados"].append({"id": aid, "origen": "030"})
            g = requests.get(
                f"{BASE_URL}/activos-biologicos/{aid}",
                headers=ctx["headers"],
                timeout=TIMEOUT,
                verify=VERIFY_SSL,
            )
            gb = _json(g)
            attrs = (gb.get("atributos_dinamicos") or {}) if isinstance(gb, dict) else {}
            item["get_http"] = g.status_code
            item["get_content_type"] = g.headers.get("Content-Type")
            item["valor_persistido"] = attrs.get(nombre)
            item["igual_texto"] = attrs.get(nombre) == val
            item["get_es_html"] = "text/html" in (g.headers.get("Content-Type") or "").lower()
        out["intentos"].append(item)

    r_ne = requests.post(
        f"{BASE_URL}/activos-biologicos",
        headers={**ctx["headers"], "Content-Type": "application/json"},
        json=_base_individual(
            especie_id, infra_id, f"G16N{int(time.time())}"[-20:], {nombre: {"$ne": None}}
        ),
        timeout=TIMEOUT,
        verify=VERIFY_SSL,
    )
    out["operador_ne"] = {
        "http": r_ne.status_code,
        "error_code": (_json(r_ne) or {}).get("error_code") if isinstance(_json(r_ne), dict) else None,
        "respuesta": _trunc(_json(r_ne), 600),
    }

    if any(x.get("html_sin_encoding") for x in out["intentos"]):
        out["resultado"] = "RECHAZADO"
        out["explicacion"] = "Respuesta HTML refleja <script> sin evidencia de encoding."
        pytest.fail(out["explicacion"])
    if any(x.get("http") == 500 for x in out["intentos"]):
        out["resultado"] = "RECHAZADO"
        out["explicacion"] = "HTTP 500 ante payload XSS/inyeccion en atributos_dinamicos."
        pytest.fail(out["explicacion"])
    if r_ne.status_code == 201:
        out["resultado"] = "RECHAZADO"
        out["explicacion"] = "Se acepto operador {$ne} como valor TEXTO (deberia fallar tipo)."
        pytest.fail(out["explicacion"])
    if r_ne.status_code == 500:
        out["resultado"] = "RECHAZADO"
        out["explicacion"] = "HTTP 500 ante operador NoSQL en atributos_dinamicos."
        pytest.fail(out["explicacion"])

    creados = [x for x in out["intentos"] if x.get("http") == 201]
    if creados and any(not x.get("igual_texto") for x in creados):
        out["resultado"] = "RECHAZADO"
        out["explicacion"] = "Valor XSS persistido distinto al texto enviado."
        pytest.fail(out["explicacion"])
    if creados and any(x.get("get_es_html") for x in creados):
        out["resultado"] = "RECHAZADO"
        out["explicacion"] = "GET de ficha devolvio HTML."
        pytest.fail(out["explicacion"])

    out["resultado"] = "APROBADO"
    out["explicacion"] = (
        f"Campo TEXTO '{nombre}' especie {especie_id}. Payloads como texto o validacion "
        f"sin 500. Operador $ne HTTP {r_ne.status_code}. Residuo ids "
        f"{[x.get('id_creado') for x in creados]}."
    )


def test_tc_m02_032_rate_limit(ctx):
    out = {
        "resultado": "BLOQUEADO",
        "endpoint": "POST /activos-biologicos",
        "criterio": ">100 solicitudes/minuto -> HTTP 429",
        "k6_disponible": bool(shutil.which("k6")),
        "codigo_limitador_en_post": False,
        "http_counts": {},
        "headers_cuota_muestra": {},
        "n_enviados": 0,
        "n_429": 0,
    }
    EVIDENCIA["subcasos"]["TC-M02-032"] = out
    n = 101
    counts: dict[str, int] = {}
    t0 = time.monotonic()
    last = None
    for i in range(n):
        r = requests.post(
            f"{BASE_URL}/activos-biologicos",
            headers={**ctx["headers"], "Content-Type": "application/json"},
            json={},
            timeout=TIMEOUT,
            verify=VERIFY_SSL,
        )
        key = str(r.status_code)
        counts[key] = counts.get(key, 0) + 1
        last = r
        if i == 0 or r.status_code == 429:
            out["headers_cuota_muestra"][f"req_{i}"] = {
                "http": r.status_code,
                "quota": _headers_quota(r),
                "error_code": (_json(r) or {}).get("error_code") if isinstance(_json(r), dict) else None,
            }
        if r.status_code in (200, 201):
            body = _json(r)
            aid = body.get("id_activo_biologico") if isinstance(body, dict) else None
            if aid:
                EVIDENCIA["ids_creados"].append({"id": aid, "origen": "032_inesperado"})
    elapsed = time.monotonic() - t0
    out["n_enviados"] = n
    out["segundos"] = round(elapsed, 3)
    out["http_counts"] = counts
    out["n_429"] = counts.get("429", 0)
    out["ultima"] = {
        "http": last.status_code if last is not None else None,
        "quota": _headers_quota(last) if last is not None else {},
        "body": _trunc(_json(last), 400) if last is not None else None,
    }
    out["dentro_de_un_minuto"] = elapsed < 60
    if elapsed >= 60:
        out["resultado"] = "BLOQUEADO"
        out["explicacion"] = f"La rafaga tardo {elapsed:.1f}s (>=60). No se evalua el umbral por minuto."
        pytest.skip(out["explicacion"])
    if out["n_429"] > 0:
        out["resultado"] = "APROBADO"
        out["explicacion"] = f"Aparecio HTTP 429 ({out['n_429']} de {n}) en {elapsed:.1f}s."
        return
    out["resultado"] = "RECHAZADO"
    out["explicacion"] = (
        f"101 POST invalidos en {elapsed:.1f}s sin ningun 429. Conteos={counts}. "
        "POST /activos-biologicos no aplica rate_limit en codigo. "
        "k6 no estaba instalado; la rafaga se ejecuto en pytest. "
        "No se crearon activos (cuerpo vacio)."
    )
    pytest.fail(out["explicacion"])


def test_zz_integridad_y_global(ctx):
    r = requests.get(
        f"{BASE_URL}/activos-biologicos",
        params={"pagina": 1, "page_size": 5},
        headers=ctx["headers"],
        timeout=TIMEOUT,
        verify=VERIFY_SSL,
    )
    EVIDENCIA["postcheck_listado_http"] = r.status_code
    EVIDENCIA["postcheck_tabla_disponible"] = r.status_code == 200
    assert EVIDENCIA.get("subcasos")
