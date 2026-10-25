"""TC-M02-G16 rev2 — inyeccion y abuso de recursos en POST /activos-biologicos.

No modifica rev1, backend ni BD via SQL. Restaura via PATCH /estado.
"""
from __future__ import annotations

import json
import os
import time
import urllib3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pytest
import requests

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DIR = Path(__file__).resolve().parent
RESULTADOS = DIR / "Resultados"
ENV_PATH = DIR / "environment-g16-rev2.json"

with ENV_PATH.open(encoding="utf-8") as fh:
    ENV = json.load(fh)

BASE_URL = ENV["baseUrl"].rstrip("/")
CORREO_ADMIN = ENV["correo_admin"]
CORREO_PROD = ENV["correo_productor"]
ESPECIE = int(ENV["especie_id"])
INFRA = int(ENV["infraestructura_id"])
TIMEOUT = 45
VERIFY_SSL = False
STAMP = datetime.now(timezone.utc).strftime("%H%M%S%f")[:12]

EVIDENCIA: dict = {
    "caso": "TC-M02-G16",
    "revision": 2,
    "rf": "RF-33",
    "cu": "CU01",
    "ambiente": "TEST",
    "base_url": BASE_URL,
    "fecha_utc": datetime.now(timezone.utc).isoformat(),
    "revision_codigo": {
        "POST_registro": "require_permission recurso 29 accion 1. Sin Depends(rate_limit).",
        "identificador": "str; requerido INDIVIDUAL; columna String(50); unicidad parametrizada lower().",
        "atributos_dinamicos": "Optional[dict] JSONB; tipos TEXTO/NUMERICO/ENTERO/BOOLEANO via metricas M09.",
        "rate_limit": (
            "src.shared.rate_limit existe. POST /activos-biologicos NO lo usa. "
            "GET /activos-biologicos/{id}/datos-consolidados usa rate_limit(100, 60). "
            "OpenAPI local de POST registro declara 201/400/401/403/409/422. No declara 429."
        ),
        "k6": "No instalado en PATH. Rafaga 032 en pytest con cuerpos validos + restauracion API.",
    },
    "subcasos": {},
    "ids_creados": [],
    "estado_global": "PENDIENTE",
    "auditoria": "Rev1 no modificada. Sin DML. Sin cambios productivos. Sin commit/push.",
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
    return text[:n] + "...[TRUNCATED]" if len(text) > n else text


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


def _login(correo: str):
    r = requests.post(
        f"{BASE_URL}/sesiones/",
        json={"correo_electronico": correo, "contrasena": _password()},
        timeout=TIMEOUT,
        verify=VERIFY_SSL,
    )
    body = _json(r)
    token = None
    if isinstance(body, dict):
        token = body.get("token") or (body.get("data") or {}).get("token")
    return r.status_code, body, token


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _quota(r: requests.Response) -> dict:
    out = {}
    for k, v in r.headers.items():
        lk = k.lower()
        if "ratelimit" in lk or lk in ("retry-after", "x-ratelimit-limit", "x-ratelimit-remaining"):
            out[k] = v
    return out


def _payload_individual(identificador: str, atributos: dict | None = None) -> dict:
    return {
        "tipo_activo": "INDIVIDUAL",
        "id_especie": ESPECIE,
        "fecha_inicio_ciclo": "2026-09-09",
        "origen_financiero": "nacimiento",
        "costo_adquisicion": None,
        "soporte_documental": None,
        "id_infraestructura": INFRA,
        "atributos_dinamicos": atributos if atributos is not None else {},
        "identificador": identificador,
        "raza": "QA-G16-R2",
        "sexo": "Macho",
        "fecha_nacimiento": "2025-01-15T00:00:00Z",
        "peso_inicial": 2.5,
    }


def _post(token: str, payload: dict):
    r = requests.post(
        f"{BASE_URL}/activos-biologicos",
        headers={**_auth(token), "Content-Type": "application/json"},
        json=payload,
        timeout=TIMEOUT,
        verify=VERIFY_SSL,
    )
    return r


def _get(token: str, aid: int):
    return requests.get(
        f"{BASE_URL}/activos-biologicos/{aid}",
        headers=_auth(token),
        timeout=TIMEOUT,
        verify=VERIFY_SSL,
    )


def _restaurar(token: str, aid: int, motivo: str) -> dict:
    r = requests.patch(
        f"{BASE_URL}/activos-biologicos/{aid}/estado",
        headers={**_auth(token), "Content-Type": "application/json"},
        json={
            "estado_nuevo": "INACTIVO",
            "fecha_cambio_estado": "2026-09-26",
            "motivo_cambio": motivo,
        },
        timeout=TIMEOUT,
        verify=VERIFY_SSL,
    )
    g = _get(token, aid)
    gb = _json(g)
    estado = None
    if isinstance(gb, dict):
        estado = gb.get("nombre_estado") or gb.get("estado")
    return {"id": aid, "http_estado": r.status_code, "http_get": g.status_code, "estado": estado}


def _captura(r: requests.Response) -> dict:
    body = _json(r)
    aid = None
    if r.status_code == 201 and isinstance(body, dict):
        aid = body.get("id_activo_biologico") or body.get("id")
    return {
        "http": r.status_code,
        "content_type": r.headers.get("Content-Type"),
        "error_code": body.get("error_code") if isinstance(body, dict) else None,
        "message": body.get("message") if isinstance(body, dict) else None,
        "id_creado": aid,
        "quota": _quota(r),
        "body": _trunc(body, 1200),
    }


def _escribir():
    RESULTADOS.mkdir(parents=True, exist_ok=True)
    payload = _redact(EVIDENCIA)
    (RESULTADOS / "TC-M02-G16-rev2.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    subs = payload.get("subcasos") or {}
    lineas = [
        "TC-M02-G16 rev2 — RF-33 / CU01 — TEST",
        f"Fecha UTC: {payload.get('fecha_utc')}",
        f"Global: {payload.get('estado_global')}",
        "",
        f"TC-M02-029: {(subs.get('TC-M02-029') or {}).get('resultado')}",
        f"TC-M02-030: {(subs.get('TC-M02-030') or {}).get('resultado')}",
        f"TC-M02-032: {(subs.get('TC-M02-032') or {}).get('resultado')}",
        "",
        json.dumps(subs, ensure_ascii=False, indent=2, default=str),
        "",
        payload.get("auditoria"),
        "Password/JWT: [REDACTED]. Rev1 no modificada.",
    ]
    (RESULTADOS / "TC-M02-G16-rev2.txt").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    bloques = []
    for k, v in subs.items():
        bloques.append(
            f"<h2>{k}</h2><p>Resultado: {v.get('resultado')}</p>"
            f"<pre>{json.dumps(v, ensure_ascii=False, indent=2, default=str)}</pre>"
        )
    (RESULTADOS / "TC-M02-G16-rev2-evidencia.html").write_text(
        "<!DOCTYPE html><html lang='es'><head><meta charset='utf-8'>"
        "<title>TC-M02-G16 rev2</title></head><body>"
        "<h1>TC-M02-G16 rev2</h1>"
        f"<p>Global: {payload.get('estado_global')}</p>"
        + "".join(bloques)
        + "<p>Sin secretos. Rev1 intacta.</p></body></html>",
        encoding="utf-8",
    )


@pytest.fixture(scope="session")
def sesion():
    _password()
    http_a, _, tok_a = _login(CORREO_ADMIN)
    http_p, _, tok_p = _login(CORREO_PROD)
    data = {
        "admin": {"http": http_a, "ok": bool(tok_a), "token": tok_a, "correo": CORREO_ADMIN},
        "productor": {"http": http_p, "ok": bool(tok_p), "token": tok_p, "correo": CORREO_PROD},
        "control_ok": False,
        "control": None,
    }
    EVIDENCIA["logins"] = {
        "admin": {"correo": CORREO_ADMIN, "http": http_a, "ok": bool(tok_a)},
        "productor": {"correo": CORREO_PROD, "http": http_p, "ok": bool(tok_p)},
    }
    if tok_p:
        ident = f"QAG16R2C{STAMP}"[:50]
        r = _post(tok_p, _payload_individual(ident))
        cap = _captura(r)
        data["control"] = cap
        EVIDENCIA["precheck_post_valido"] = cap
        if cap["http"] == 201 and cap["id_creado"]:
            data["control_ok"] = True
            EVIDENCIA["ids_creados"].append(cap["id_creado"])
            rest = _restaurar(tok_p, int(cap["id_creado"]), "Restauracion control TC-M02-G16 rev2")
            cap["restauracion"] = rest
    yield data
    _escribir()


def test_tc_m02_029_injection_identificador(sesion):
    out = {
        "resultado": "BLOQUEADO",
        "endpoint": "POST /activos-biologicos",
        "precondiciones": {
            "usuario": CORREO_PROD,
            "especie": ESPECIE,
            "infraestructura": INFRA,
            "post_control": sesion.get("control"),
        },
        "intentos": [],
        "ids_creados": [],
        "restauraciones": [],
        "conclusion": "",
    }
    EVIDENCIA["subcasos"]["TC-M02-029"] = out
    if not sesion["productor"]["ok"]:
        out["conclusion"] = f"BLOQUEADO: login Productor HTTP {sesion['productor']['http']}."
        pytest.skip(out["conclusion"])
    if not sesion["control_ok"]:
        ctrl = sesion.get("control") or {}
        out["conclusion"] = (
            f"BLOQUEADO: POST valido HTTP {ctrl.get('http')} {ctrl.get('error_code')}. "
            "No se atribuye inyeccion; el control tambien fallo (historico 500)."
        )
        pytest.skip(out["conclusion"])

    tok = sesion["productor"]["token"]
    payloads = [
        "BOV-1'; DROP TABLE activos;--",
        "BOV-1' OR '1'='1",
        'BOV-1"; DROP TABLE activos;--',
        "BOV-1{$ne:1}",
    ]
    hubo_500 = False
    for i, ident in enumerate(payloads):
        r = _post(tok, _payload_individual(ident))
        cap = _captura(r)
        cap["identificador_enviado"] = ident
        if cap["http"] == 201 and cap["id_creado"]:
            gid = int(cap["id_creado"])
            out["ids_creados"].append(gid)
            EVIDENCIA["ids_creados"].append(gid)
            g = _get(tok, gid)
            gb = _json(g)
            stored = gb.get("identificador") if isinstance(gb, dict) else None
            cap["identificador_persistido"] = stored
            cap["persistido_como_texto"] = stored == ident
            cap["restauracion"] = _restaurar(tok, gid, f"Restauracion 029 payload {i} TC-M02-G16 rev2")
            out["restauraciones"].append(cap["restauracion"])
        if cap["http"] == 500:
            hubo_500 = True
        out["intentos"].append(cap)

    r_obj = requests.post(
        f"{BASE_URL}/activos-biologicos",
        headers={**_auth(tok), "Content-Type": "application/json"},
        json=_payload_individual("x") | {"identificador": {"$gt": ""}},
        timeout=TIMEOUT,
        verify=VERIFY_SSL,
    )
    out["nosql_objeto"] = _captura(r_obj)

    r_list = requests.get(
        f"{BASE_URL}/activos-biologicos",
        params={"pagina": 1, "page_size": 1},
        headers=_auth(tok),
        timeout=TIMEOUT,
        verify=VERIFY_SSL,
    )
    out["listado_post_inyeccion_http"] = r_list.status_code

    if hubo_500:
        out["resultado"] = "RECHAZADO"
        out["conclusion"] = (
            "POST de control fue 201, pero un payload de inyeccion como texto produjo HTTP 500."
        )
        pytest.fail(out["conclusion"])

    persistidos = [x for x in out["intentos"] if x.get("http") == 201]
    for p in persistidos:
        if p.get("identificador_persistido") != p.get("identificador_enviado"):
            out["resultado"] = "RECHAZADO"
            out["conclusion"] = "El identificador persistido no coincide con el texto enviado."
            pytest.fail(out["conclusion"])

    out["resultado"] = "APROBADO"
    out["conclusion"] = (
        "Control 201. Payloads de inyeccion tratados como texto o rechazados por validacion; "
        f"sin HTTP 500. Listado HTTP {r_list.status_code}. "
        f"Creados {len(out['ids_creados'])} y restaurados via PATCH /estado."
    )


def test_tc_m02_030_xss_atributos(sesion):
    out = {
        "resultado": "BLOQUEADO",
        "endpoint": "POST /activos-biologicos",
        "metricas": {},
        "atributo_texto": None,
        "intentos": [],
        "conclusion": "",
    }
    EVIDENCIA["subcasos"]["TC-M02-030"] = out
    if not sesion["admin"]["ok"]:
        out["conclusion"] = f"BLOQUEADO: login Admin HTTP {sesion['admin']['http']}."
        pytest.skip(out["conclusion"])
    if not sesion["productor"]["ok"]:
        out["conclusion"] = "BLOQUEADO: sin Productor."
        pytest.skip(out["conclusion"])
    if not sesion["control_ok"]:
        out["conclusion"] = "BLOQUEADO: POST valido de control no funciona; no se evalua XSS."
        pytest.skip(out["conclusion"])

    tok_a = sesion["admin"]["token"]
    tok_p = sesion["productor"]["token"]
    r_m = requests.get(
        f"{BASE_URL}/configuracion/metricas",
        params={"id_especie": ESPECIE},
        headers=_auth(tok_a),
        timeout=TIMEOUT,
        verify=VERIFY_SSL,
    )
    body_m = _json(r_m)
    out["metricas"] = {
        "endpoint": f"GET /configuracion/metricas?id_especie={ESPECIE}",
        "http": r_m.status_code,
        "error_code": body_m.get("error_code") if isinstance(body_m, dict) else None,
        "body": _trunc(body_m, 1600),
    }
    if r_m.status_code == 500:
        out["conclusion"] = (
            f"BLOQUEADO: GET metricas especie {ESPECIE} HTTP 500 (historico). "
            "No se construye 030."
        )
        pytest.skip(out["conclusion"])
    if r_m.status_code != 200:
        out["conclusion"] = f"BLOQUEADO: GET metricas HTTP {r_m.status_code}."
        pytest.skip(out["conclusion"])

    items = []
    if isinstance(body_m, dict):
        items = body_m.get("items") or _registros(body_m)
    texto = None
    for it in items:
        if not isinstance(it, dict):
            continue
        td = str(it.get("tipo_dato") or "").upper()
        aplica = str(it.get("aplica_a_tipo_activo") or "").upper()
        if td == "TEXTO" and it.get("es_activo") is not False and aplica in ("INDIVIDUAL", "AMBOS", ""):
            texto = it
            break
    out["metricas_n"] = len(items)
    out["tipos_vistos"] = sorted({str(i.get("tipo_dato")) for i in items if isinstance(i, dict)})
    if not texto:
        out["conclusion"] = (
            f"BLOQUEADO: especie {ESPECIE} GET metricas 200 pero sin metrica TEXTO activa "
            f"para INDIVIDUAL. tipos={out['tipos_vistos']}. No se inventa la metrica."
        )
        pytest.skip(out["conclusion"])

    nombre = texto.get("nombre")
    out["atributo_texto"] = {"id": texto.get("id_metrica_produccion"), "nombre": nombre, "tipo": texto.get("tipo_dato")}
    xss = "<script>alert(1)</script>"
    ident = f"QAG16R2X{STAMP}"[:50]
    r = _post(tok_p, _payload_individual(ident, {nombre: xss}))
    cap = _captura(r)
    cap["payload_atributo"] = {nombre: xss}
    out["intentos"].append(cap)
    if cap["http"] == 500:
        out["resultado"] = "RECHAZADO"
        out["conclusion"] = "HTTP 500 atribuible al payload XSS en atributos_dinamicos."
        pytest.fail(out["conclusion"])

    if cap["http"] == 201 and cap["id_creado"]:
        aid = int(cap["id_creado"])
        EVIDENCIA["ids_creados"].append(aid)
        g = _get(tok_p, aid)
        gb = _json(g)
        attrs = gb.get("atributos_dinamicos") if isinstance(gb, dict) else None
        cap["get_http"] = g.status_code
        cap["content_type_get"] = g.headers.get("Content-Type")
        cap["atributos_get"] = attrs
        cap["reflejado"] = isinstance(attrs, dict) and attrs.get(nombre) == xss
        cap["html_sin_json"] = "html" in (g.headers.get("Content-Type") or "").lower()
        cap["restauracion"] = _restaurar(tok_p, aid, "Restauracion 030 XSS TC-M02-G16 rev2")
        if cap.get("html_sin_json"):
            out["resultado"] = "RECHAZADO"
            out["conclusion"] = "GET devolvio HTML; riesgo de reflexion XSS."
            pytest.fail(out["conclusion"])
        out["resultado"] = "APROBADO"
        out["conclusion"] = (
            f"Atributo '{nombre}' TEXTO. POST HTTP {cap['http']}. Valor persistido como dato JSON "
            f"(reflejado={cap['reflejado']}, content-type={cap['content_type_get']}). "
            f"Restaurado HTTP {cap['restauracion']['http_estado']} estado={cap['restauracion']['estado']}."
        )
        return

    # operador JSON como valor (sigue siendo string de prueba)
    ident2 = f"QAG16R2J{STAMP}"[:50]
    r2 = _post(tok_p, _payload_individual(ident2, {nombre: '{"$gt":""}'}))
    cap2 = _captura(r2)
    cap2["payload_atributo"] = {nombre: '{"$gt":""}'}
    out["intentos"].append(cap2)
    if cap2["http"] == 201 and cap2["id_creado"]:
        EVIDENCIA["ids_creados"].append(int(cap2["id_creado"]))
        cap2["restauracion"] = _restaurar(
            tok_p, int(cap2["id_creado"]), "Restauracion 030 json-op TC-M02-G16 rev2"
        )
    if cap2["http"] == 500:
        out["resultado"] = "RECHAZADO"
        out["conclusion"] = "HTTP 500 con operador JSON como texto."
        pytest.fail(out["conclusion"])

    out["resultado"] = "APROBADO"
    out["conclusion"] = (
        f"XSS POST HTTP {cap['http']} {cap.get('error_code')}; operador JSON HTTP {cap2['http']}. "
        "Sin 500. Rechazo o dato; no ejecucion."
    )


def test_tc_m02_032_rate_limit(sesion):
    out = {
        "resultado": "BLOQUEADO",
        "endpoint": "POST /activos-biologicos",
        "criterio_caso": ">100 POST/minuto -> HTTP 429",
        "contrato_openapi_post": "201,400,401,403,409,422 (sin 429)",
        "codigo_rate_limit_en_post": False,
        "rate_limit_documentado_otro": "GET datos-consolidados rate_limit(100, 60)",
        "k6": False,
        "n_enviados": 0,
        "n_429": 0,
        "http_counts": {},
        "ids_creados": [],
        "restauraciones_ok": 0,
        "conclusion": "",
    }
    EVIDENCIA["subcasos"]["TC-M02-032"] = out
    if not sesion["control_ok"]:
        out["conclusion"] = "BLOQUEADO: no hay POST valido; no se lanza rafaga de 101 altas."
        pytest.skip(out["conclusion"])
    tok = sesion["productor"]["token"]
    n = 101
    counts: Counter = Counter()
    ids = []
    muestra_headers = {}
    t0 = time.perf_counter()
    for i in range(n):
        ident = f"G16R2{STAMP}{i:03d}"[:50]
        r = _post(tok, _payload_individual(ident))
        counts[str(r.status_code)] += 1
        cap = _captura(r)
        if i in (0, 50, 100):
            muestra_headers[f"req_{i}"] = {"http": r.status_code, "quota": cap["quota"], "error_code": cap["error_code"]}
        if cap["id_creado"]:
            ids.append(int(cap["id_creado"]))
            EVIDENCIA["ids_creados"].append(int(cap["id_creado"]))
    segundos = round(time.perf_counter() - t0, 3)
    out["n_enviados"] = n
    out["segundos"] = segundos
    out["rps"] = round(n / segundos, 2) if segundos else None
    out["http_counts"] = dict(counts)
    out["n_429"] = int(counts.get("429", 0))
    out["n_2xx"] = int(counts.get("201", 0) + counts.get("200", 0))
    out["n_4xx"] = sum(int(counts[k]) for k in counts if k.startswith("4"))
    out["n_5xx"] = sum(int(counts[k]) for k in counts if k.startswith("5"))
    out["dentro_de_un_minuto"] = segundos <= 60
    out["headers_cuota_muestra"] = muestra_headers
    out["ids_creados"] = ids

    restauraciones = []
    for aid in ids:
        restauraciones.append(_restaurar(tok, aid, "Restauracion rafaga 032 TC-M02-G16 rev2"))
    out["restauraciones_ok"] = sum(1 for x in restauraciones if str(x.get("estado") or "").upper() == "INACTIVO")
    out["restauracion_muestra"] = restauraciones[:3] + restauraciones[-2:]
    ping = requests.get(
        f"{BASE_URL}/activos-biologicos",
        params={"pagina": 1, "page_size": 1},
        headers=_auth(tok),
        timeout=TIMEOUT,
        verify=VERIFY_SSL,
    )
    out["servicio_despues_http"] = ping.status_code

    if not out["dentro_de_un_minuto"]:
        out["conclusion"] = f"BLOQUEADO: rafaga {segundos}s > 60s. No se evalua umbral por minuto."
        pytest.skip(out["conclusion"])
    if out["n_5xx"]:
        out["resultado"] = "RECHAZADO"
        out["conclusion"] = f"Rafaga produjo 5xx={out['n_5xx']}. Degradacion/error interno."
        pytest.fail(out["conclusion"])

    # Criterio del caso: 429 al superar 100/min. Contrato OpenAPI no documenta 429 en este POST;
    # codigo no aplica limiter. No hay otra politica oficial para ESTE endpoint.
    if out["n_429"] == 0:
        out["resultado"] = "RECHAZADO"
        out["conclusion"] = (
            f"{n} POST validos en {segundos}s ({out['rps']} rps), 201={out['n_2xx']}, "
            f"429=0, headers cuota vacios. OpenAPI del POST no declara 429 y el router no usa "
            f"rate_limit. El caso exige 429; no hay umbral alterno documentado para este endpoint. "
            f"Restaurados {out['restauraciones_ok']}/{len(ids)} a INACTIVO. "
            f"GET listado posterior HTTP {ping.status_code}."
        )
        pytest.fail(out["conclusion"])
    out["resultado"] = "APROBADO"
    out["conclusion"] = f"Se observo HTTP 429 ({out['n_429']}) dentro de {segundos}s."


def test_zz_estado_global(sesion):
    subs = EVIDENCIA.get("subcasos") or {}
    estados = [v.get("resultado") for v in subs.values()]
    if "RECHAZADO" in estados:
        EVIDENCIA["estado_global"] = "RECHAZADO"
    elif estados and all(e == "APROBADO" for e in estados):
        EVIDENCIA["estado_global"] = "APROBADO"
    else:
        EVIDENCIA["estado_global"] = "BLOQUEADO"
    assert EVIDENCIA["estado_global"] in ("APROBADO", "RECHAZADO", "BLOQUEADO")
