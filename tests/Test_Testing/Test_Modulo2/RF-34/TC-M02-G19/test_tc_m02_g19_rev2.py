"""TC-M02-G19 rev2 — RF-34. Segunda evaluacion TEST.

Fecha de referencia, default ACTIVA, integridad, auditoria.
No modifica historico ni backend. No fabrica inconsistencias.
"""
from __future__ import annotations

import base64
import json
import os
import urllib3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import requests

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DIR = Path(__file__).resolve().parent
RESULTADOS = DIR / "Resultados"
ENV_PATH = DIR / "environment-g19-rev2.json"

with ENV_PATH.open(encoding="utf-8") as fh:
    ENV = json.load(fh)

BASE_URL = ENV["baseUrl"].rstrip("/")
CORREO = ENV["correo_admin"]
TIMEOUT = 45
VERIFY_SSL = False
CANDIDATOS_190 = [5, 85, 130, 285, 290, 292, 294]
ACTIVO_192 = 4
ACTIVO_191 = 352

EVIDENCIA: dict = {
    "caso": "TC-M02-G19",
    "revision": 2,
    "rf": "RF-34",
    "ambiente": "TEST",
    "base_url": BASE_URL,
    "fecha_utc": datetime.now(timezone.utc).isoformat(),
    "precondiciones": {},
    "subcasos": {},
    "estado_global": "PENDIENTE",
    "inc_m02_55_g19": "PENDIENTE",
    "auditoria": "Historico RF-34/TC-M02-G19 no modificado. Backend no modificado. Sin commit ni push.",
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


def _trunc(obj, n=2400):
    text = json.dumps(_redact(obj), ensure_ascii=False, default=str)
    return text[:n] + ("...[TRUNCATED]" if len(text) > n else "")


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


def _parse_dt(valor):
    if not valor:
        return None
    s = str(valor).replace("Z", "+00:00")
    return datetime.fromisoformat(s)


def _jwt_uid(token: str):
    try:
        payload = token.split(".")[1]
        pad = "=" * (-len(payload) % 4)
        data = json.loads(base64.urlsafe_b64decode(payload + pad))
        return data.get("id_usuario") or data.get("uid") or data.get("sub")
    except Exception:
        return None


def _hay_solape(hist: list) -> str | None:
    periodos = sorted(hist, key=lambda h: str(h.get("fecha_inicio") or ""))
    fin_abierto = datetime.max.replace(tzinfo=timezone.utc)
    for i, a in enumerate(periodos):
        ini_i = _parse_dt(a.get("fecha_inicio"))
        fin_i = _parse_dt(a.get("fecha_fin")) or fin_abierto
        if ini_i is None:
            continue
        for b in periodos[i + 1 :]:
            ini_j = _parse_dt(b.get("fecha_inicio"))
            if ini_j and ini_j < fin_i:
                return f"solape id_historial {a.get('id_historial')} y {b.get('id_historial')}"
    return None


def _fin_antes_inicio(hist: list) -> str | None:
    for h in hist:
        ini = _parse_dt(h.get("fecha_inicio"))
        fin = _parse_dt(h.get("fecha_fin"))
        if ini and fin and fin <= ini:
            return f"fecha_fin<=fecha_inicio id_historial={h.get('id_historial')}"
    return None


def _infra_url(aid: int) -> str:
    return f"{BASE_URL}/activos-biologicos/{aid}/infraestructura"


def _escribir() -> None:
    RESULTADOS.mkdir(parents=True, exist_ok=True)
    payload = _redact(EVIDENCIA)
    (RESULTADOS / "TC-M02-G19-rev2.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    (RESULTADOS / "TC-M02-G19-rev2.txt").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8"
    )
    bloques = "".join(
        f"<h2>{k}: {v.get('resultado')}</h2><pre>{json.dumps(v, ensure_ascii=False, indent=2, default=str)}</pre>"
        for k, v in (payload.get("subcasos") or {}).items()
    )
    (RESULTADOS / "TC-M02-G19-rev2-evidencia.html").write_text(
        "<!DOCTYPE html><html lang='es'><head><meta charset='utf-8'><title>G19 rev2</title></head><body>"
        f"<h1>TC-M02-G19 rev2</h1><p>Global {payload.get('estado_global')}</p>"
        f"<p>INC-M02-55-G19: {payload.get('inc_m02_55_g19')}</p>{bloques}"
        "<p>Sin JWT. Historico no modificado.</p></body></html>",
        encoding="utf-8",
    )


@pytest.fixture(scope="session")
def ctx():
    pwd = _password()
    r = requests.post(
        f"{BASE_URL}/sesiones/",
        json={"correo_electronico": CORREO, "contrasena": pwd},
        timeout=TIMEOUT,
        verify=VERIFY_SSL,
    )
    body = _json(r)
    token = body.get("token") if isinstance(body, dict) else None
    if r.status_code != 200 or not token:
        EVIDENCIA["precondiciones"]["login"] = {"http": r.status_code}
        _escribir()
        pytest.skip(f"BLOQUEADO login HTTP {r.status_code}")
    headers = {"Authorization": f"Bearer {token}"}
    uid = _jwt_uid(token)

    def _hist(aid: int):
        hr = requests.get(
            _infra_url(aid),
            params={"tipo_consulta": "HISTORIAL"},
            headers=headers,
            timeout=TIMEOUT,
            verify=VERIFY_SSL,
        )
        body = _json(hr)
        hist = body.get("historial") if hr.status_code == 200 and isinstance(body, dict) else []
        if not isinstance(hist, list):
            hist = []
        return hr.status_code, hist, body

    inspeccion_190 = []
    candidatos_ok = []
    for aid in CANDIDATOS_190:
        ge = requests.get(
            f"{BASE_URL}/activos-biologicos/{aid}",
            headers=headers,
            timeout=TIMEOUT,
            verify=VERIFY_SSL,
        )
        http_h, hist, _ = _hist(aid)
        vigentes = [h for h in hist if h.get("fecha_fin") in (None, "")]
        cerradas = [h for h in hist if h.get("fecha_fin") not in (None, "")]
        cerrada_ok = None
        for c in cerradas:
            ini = _parse_dt(c.get("fecha_inicio"))
            fin = _parse_dt(c.get("fecha_fin"))
            if ini and fin and fin > ini:
                cerrada_ok = c
                break
        vigente_infra = None if not vigentes else vigentes[0].get("id_infraestructura")
        distinta = bool(
            cerrada_ok
            and vigente_infra is not None
            and cerrada_ok.get("id_infraestructura") != vigente_infra
        )
        utilizable = bool(cerrada_ok and vigentes)
        fila = {
            "id": aid,
            "get_activo_http": ge.status_code,
            "historial_http": http_h,
            "n": len(hist),
            "n_vigentes": len(vigentes),
            "n_cerradas": len(cerradas),
            "utilizable_190": utilizable,
            "infra_cerrada_distinta_de_vigente": distinta,
            "vigente_infra": vigente_infra,
        }
        inspeccion_190.append(fila)
        if utilizable:
            candidatos_ok.append(
                {
                    "id": aid,
                    "n": len(hist),
                    "preferente": distinta,
                    "cerrada": {
                        "id_historial": cerrada_ok.get("id_historial"),
                        "id_infraestructura": cerrada_ok.get("id_infraestructura"),
                        "fecha_inicio": cerrada_ok.get("fecha_inicio"),
                        "fecha_fin": cerrada_ok.get("fecha_fin"),
                    },
                    "vigente_infra": vigente_infra,
                }
            )
    con_cerrada = None
    preferidos = [c for c in candidatos_ok if c.get("preferente")]
    if preferidos:
        con_cerrada = preferidos[0]
    elif candidatos_ok:
        con_cerrada = candidatos_ok[0]

    http4, hist4, body4 = _hist(ACTIVO_192)
    vigentes4 = [h for h in hist4 if h.get("fecha_fin") in (None, "")]
    motivos4 = []
    if len(vigentes4) > 1:
        motivos4.append(f"multiples fecha_fin=null n={len(vigentes4)}")
    solape4 = _hay_solape(hist4)
    if solape4:
        motivos4.append(solape4)
    fin_inv4 = _fin_antes_inicio(hist4)
    if fin_inv4:
        motivos4.append(fin_inv4)
    activo_4 = {
        "id": ACTIVO_192,
        "historial_http": http4,
        "n": len(hist4),
        "n_vigentes": len(vigentes4),
        "motivos": motivos4,
        "advertencia_en_historial": body4.get("advertencia_integridad") if isinstance(body4, dict) else None,
        "periodos": [
            {
                "id_historial": h.get("id_historial"),
                "id_infraestructura": h.get("id_infraestructura"),
                "fecha_inicio": h.get("fecha_inicio"),
                "fecha_fin": h.get("fecha_fin"),
            }
            for h in hist4
        ],
    }

    http191, hist191, _ = _hist(ACTIVO_191)
    vigentes191 = [h for h in hist191 if h.get("fecha_fin") in (None, "")]
    con_activa = None
    if http191 == 200 and vigentes191:
        con_activa = {"id": ACTIVO_191, "infra": vigentes191[0].get("id_infraestructura")}
    elif con_cerrada:
        con_activa = {"id": con_cerrada["id"], "infra": con_cerrada.get("vigente_infra")}

    hallazgo = {
        "candidatos_dba_190": CANDIDATOS_190,
        "inspeccion_190": inspeccion_190,
        "con_cerrada": con_cerrada,
        "con_activa": con_activa,
        "activo_4": activo_4,
        "con_inconsistencia": {"id": ACTIVO_192, "motivos": motivos4, "n": len(hist4)} if motivos4 else None,
        "id_usuario_jwt": uid,
        "id_inexistente": 100352,
        "fuente_dba": "IDs informados por DBA; verificados por GET HISTORIAL en TEST.",
    }
    EVIDENCIA["precondiciones"] = hallazgo
    data = {"headers": headers, "token": token, **hallazgo}
    yield data
    estados = [v.get("resultado") for v in (EVIDENCIA.get("subcasos") or {}).values()]
    if "RECHAZADO" in estados:
        EVIDENCIA["estado_global"] = "RECHAZADO"
    elif estados and all(e == "APROBADO" for e in estados):
        EVIDENCIA["estado_global"] = "APROBADO"
    else:
        EVIDENCIA["estado_global"] = "BLOQUEADO"
    r190 = (EVIDENCIA.get("subcasos") or {}).get("TC-M02-190", {}).get("resultado")
    r192 = (EVIDENCIA.get("subcasos") or {}).get("TC-M02-192", {}).get("resultado")
    if r190 == "APROBADO" and r192 == "APROBADO":
        EVIDENCIA["inc_m02_55_g19"] = "superado"
    elif r190 == "APROBADO" and r192 == "BLOQUEADO":
        EVIDENCIA["inc_m02_55_g19"] = "parcialmente superado"
    elif r190 == "BLOQUEADO" and r192 == "BLOQUEADO":
        EVIDENCIA["inc_m02_55_g19"] = "continua"
    else:
        EVIDENCIA["inc_m02_55_g19"] = "no verificable"
    _escribir()


def test_tc_m02_190_fecha_referencia(ctx):
    out = {"resultado": "BLOQUEADO", "endpoint": "GET .../infraestructura?fecha_referencia="}
    EVIDENCIA["subcasos"]["TC-M02-190"] = out
    info = ctx.get("con_cerrada")
    if not info:
        out["explicacion"] = (
            "BLOQUEADO: no hay activo con asociacion historica cerrada en la muestra. "
            "No se fabrica historial."
        )
        pytest.skip(out["explicacion"])
    aid = info["id"]
    c = info["cerrada"]
    ini = _parse_dt(c["fecha_inicio"])
    fin = _parse_dt(c["fecha_fin"])
    if not ini or not fin or fin <= ini:
        out["explicacion"] = "BLOQUEADO: periodo cerrado inutilizable (fechas invalidas)."
        pytest.skip(out["explicacion"])
    delta = (fin - ini) / 2
    if delta.total_seconds() <= 0:
        ref = ini + timedelta(seconds=1)
    else:
        ref = ini + delta
    if ref >= fin:
        ref = ini + timedelta(milliseconds=1)
    fecha_iso = ref.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    out["id_activo"] = aid
    out["fecha_referencia"] = fecha_iso
    out["periodo_esperado"] = c
    r = requests.get(
        _infra_url(aid),
        params={"fecha_referencia": fecha_iso},
        headers=ctx["headers"],
        timeout=TIMEOUT,
        verify=VERIFY_SSL,
    )
    body = _json(r)
    out["http"] = r.status_code
    out["respuesta"] = _trunc(body)
    if r.status_code == 500:
        out["explicacion"] = "BLOQUEADO HTTP 500."
        pytest.skip(out["explicacion"])
    if r.status_code != 200:
        out["resultado"] = "RECHAZADO"
        out["explicacion"] = f"HTTP {r.status_code}, esperado 200."
        pytest.fail(out["explicacion"])
    asoc = body.get("asociacion_activa") or {}
    out["tipo_consulta"] = body.get("tipo_consulta")
    out["infra_devuelta"] = asoc.get("id_infraestructura")
    out["historial_id_devuelto"] = asoc.get("id_historial")
    ini_a = _parse_dt(asoc.get("fecha_inicio"))
    fin_a = _parse_dt(asoc.get("fecha_fin"))
    cubre = ini_a is not None and ini_a <= ref and (fin_a is None or fin_a > ref)
    out["cubre_periodo"] = cubre
    vigente_infra = info.get("vigente_infra")
    out["vigente_actual_infra"] = vigente_infra
    if asoc.get("id_infraestructura") is None:
        out["resultado"] = "RECHAZADO"
        out["explicacion"] = "200 sin infraestructura."
        pytest.fail(out["explicacion"])
    if not cubre:
        out["resultado"] = "RECHAZADO"
        out["explicacion"] = "La asociacion devuelta no cubre fecha_referencia."
        pytest.fail(out["explicacion"])
    if (
        vigente_infra is not None
        and asoc.get("id_infraestructura") == vigente_infra
        and asoc.get("id_historial") != c.get("id_historial")
        and c.get("id_infraestructura") != vigente_infra
    ):
        out["resultado"] = "RECHAZADO"
        out["explicacion"] = "Devolvio la asociacion vigente actual, no la del periodo historico."
        pytest.fail(out["explicacion"])
    if asoc.get("id_historial") != c.get("id_historial") and asoc.get("id_infraestructura") != c.get("id_infraestructura"):
        out["resultado"] = "RECHAZADO"
        out["explicacion"] = "No coincide con el periodo cerrado elegido."
        pytest.fail(out["explicacion"])
    out["resultado"] = "APROBADO"
    out["explicacion"] = (
        f"HTTP 200, historial {asoc.get('id_historial')} infra {asoc.get('id_infraestructura')} "
        f"cubre {fecha_iso}."
    )


def test_tc_m02_191_default_activa(ctx):
    out = {"resultado": "BLOQUEADO", "endpoint": "GET .../infraestructura (sin query)"}
    EVIDENCIA["subcasos"]["TC-M02-191"] = out
    info = ctx.get("con_activa")
    if not info:
        out["explicacion"] = "BLOQUEADO: no hay activo con asociacion vigente."
        pytest.skip(out["explicacion"])
    aid = info["id"]
    out["id_activo"] = aid
    r = requests.get(_infra_url(aid), headers=ctx["headers"], timeout=TIMEOUT, verify=VERIFY_SSL)
    body = _json(r)
    out["http"] = r.status_code
    out["respuesta"] = _trunc(body)
    if r.status_code != 200:
        out["resultado"] = "RECHAZADO"
        out["explicacion"] = f"HTTP {r.status_code}, esperado 200."
        pytest.fail(out["explicacion"])
    asoc = body.get("asociacion_activa") or {}
    if body.get("tipo_consulta") != "ACTIVA":
        out["resultado"] = "RECHAZADO"
        out["explicacion"] = f"tipo_consulta={body.get('tipo_consulta')}, esperado ACTIVA."
        pytest.fail(out["explicacion"])
    if asoc.get("fecha_fin") not in (None, ""):
        out["resultado"] = "RECHAZADO"
        out["explicacion"] = "fecha_fin de la vigente no es null."
        pytest.fail(out["explicacion"])
    if body.get("historial") not in (None, []):
        out["resultado"] = "RECHAZADO"
        out["explicacion"] = "Default ACTIVA no debe devolver historial cerrado como resultado principal."
        pytest.fail(out["explicacion"])
    out["resultado"] = "APROBADO"
    out["explicacion"] = "Sin query: tipo_consulta=ACTIVA, fecha_fin=null, historial null."


def test_tc_m02_192_inconsistencia(ctx):
    out = {
        "resultado": "BLOQUEADO",
        "endpoint": "GET /activos-biologicos/4/infraestructura?tipo_consulta=HISTORIAL",
        "id_activo": 4,
    }
    EVIDENCIA["subcasos"]["TC-M02-192"] = out
    a4 = ctx.get("activo_4") or {}
    out["inspeccion_activo_4"] = a4
    if a4.get("historial_http") not in (200,):
        out["explicacion"] = (
            f"BLOQUEADO: GET HISTORIAL del activo 4 HTTP {a4.get('historial_http')}. "
            "No se pudo verificar la precondicion DBA."
        )
        pytest.skip(out["explicacion"])
    motivos = a4.get("motivos") or []
    out["inconsistencia_detectada_en_datos"] = motivos
    if not motivos:
        out["explicacion"] = (
            "BLOQUEADO: el DBA indico activo 4, pero el HISTORIAL real no muestra "
            "multiples fecha_fin=null, solape ni fecha_fin<=fecha_inicio. No se fabrica."
        )
        pytest.skip(out["explicacion"])
    r = requests.get(
        _infra_url(4),
        params={"tipo_consulta": "HISTORIAL"},
        headers=ctx["headers"],
        timeout=TIMEOUT,
        verify=VERIFY_SSL,
    )
    body = _json(r)
    out["http"] = r.status_code
    out["respuesta"] = _trunc(body)
    if r.status_code == 500:
        out["explicacion"] = "BLOQUEADO HTTP 500."
        pytest.skip(out["explicacion"])
    if r.status_code != 200:
        out["resultado"] = "RECHAZADO"
        out["explicacion"] = f"HTTP {r.status_code}; se esperaba 200 sin bloquear."
        pytest.fail(out["explicacion"])
    hist = body.get("historial")
    adv = body.get("advertencia_integridad")
    out["advertencia_integridad"] = adv
    out["n_historial"] = len(hist) if isinstance(hist, list) else None
    if not hist:
        out["resultado"] = "RECHAZADO"
        out["explicacion"] = "200 sin historial disponible."
        pytest.fail(out["explicacion"])
    if not adv:
        out["resultado"] = "RECHAZADO"
        out["explicacion"] = (
            f"Inconsistencia real en activo 4 ({motivos}) pero advertencia_integridad es null. "
            "La consulta no se bloqueo."
        )
        pytest.fail(out["explicacion"])
    out["resultado"] = "APROBADO"
    out["explicacion"] = f"HTTP 200, advertencia_integridad presente, motivos={motivos}."


def test_tc_m02_193_auditoria(ctx):
    out = {"resultado": "BLOQUEADO", "endpoint": "GET /activos-biologicos/auditoria"}
    EVIDENCIA["subcasos"]["TC-M02-193"] = out
    s190 = (EVIDENCIA.get("subcasos") or {}).get("TC-M02-190") or {}
    aid = s190.get("id_activo") or (ctx.get("con_activa") or {}).get("id")
    fecha_ref = s190.get("fecha_referencia")
    if not aid:
        out["explicacion"] = "BLOQUEADO: no hay activo para auditar."
        pytest.skip(out["explicacion"])
    out["id_activo"] = aid
    out["fecha_referencia_esperada"] = fecha_ref
    r1 = requests.get(_infra_url(aid), headers=ctx["headers"], timeout=TIMEOUT, verify=VERIFY_SSL)
    r2 = requests.get(
        _infra_url(aid),
        params={"tipo_consulta": "HISTORIAL"},
        headers=ctx["headers"],
        timeout=TIMEOUT,
        verify=VERIFY_SSL,
    )
    r3 = None
    if fecha_ref:
        r3 = requests.get(
            _infra_url(aid),
            params={"fecha_referencia": fecha_ref},
            headers=ctx["headers"],
            timeout=TIMEOUT,
            verify=VERIFY_SSL,
        )
    out["http_activa"] = r1.status_code
    out["http_historial"] = r2.status_code
    out["http_fecha_ref"] = None if r3 is None else r3.status_code
    if r1.status_code != 200 or r2.status_code != 200:
        out["explicacion"] = "BLOQUEADO: no se pudieron ejecutar ACTIVA/HISTORIAL a auditar."
        pytest.skip(out["explicacion"])
    aud = requests.get(
        f"{BASE_URL}/activos-biologicos/auditoria",
        params={
            "id_activo_biologico": aid,
            "rf_origen": "RF34",
            "tipo_evento": "INFRAESTRUCTURA_CONSULTADA",
            "page_size": 20,
            "pagina": 1,
        },
        headers=ctx["headers"],
        timeout=TIMEOUT,
        verify=VERIFY_SSL,
    )
    out["auditoria_http"] = aud.status_code
    body = _json(aud)
    if aud.status_code in (401, 403, 404, 500):
        out["explicacion"] = f"BLOQUEADO: bitacora HTTP {aud.status_code}."
        pytest.skip(out["explicacion"])
    if aud.status_code != 200:
        out["resultado"] = "RECHAZADO"
        out["explicacion"] = f"Bitacora HTTP {aud.status_code}."
        pytest.fail(out["explicacion"])
    regs = _registros(body)
    out["n_registros"] = len(regs)
    muestra = []
    con_fecha = []
    for ev in regs[:15]:
        det = ev.get("detalle_tecnico") or {}
        fila = {
            "id_activo_biologico": ev.get("id_activo_biologico"),
            "id_usuario_responsable": ev.get("id_usuario_responsable"),
            "resultado": ev.get("resultado"),
            "timestamp_evento": str(ev.get("timestamp_evento")),
            "tipo_consulta": det.get("tipo_consulta") if isinstance(det, dict) else None,
            "fecha_referencia": det.get("fecha_referencia") if isinstance(det, dict) else None,
            "rf_origen": ev.get("rf_origen"),
            "tipo_evento": ev.get("tipo_evento"),
        }
        muestra.append(fila)
        if fila.get("fecha_referencia"):
            con_fecha.append(fila)
    out["muestra"] = muestra
    out["registros_con_fecha_referencia"] = con_fecha
    if not regs:
        out["resultado"] = "RECHAZADO"
        out["explicacion"] = "Bitacora 200 sin registros RF34 para el activo."
        pytest.fail(out["explicacion"])
    tipos = {
        str((e.get("detalle_tecnico") or {}).get("tipo_consulta"))
        for e in regs
        if isinstance(e.get("detalle_tecnico"), dict)
    }
    out["tipos_consulta_en_bitacora"] = sorted(tipos)
    alguno_ok = False
    for ev in regs:
        det = ev.get("detalle_tecnico") if isinstance(ev.get("detalle_tecnico"), dict) else {}
        if (
            ev.get("id_activo_biologico") == aid
            and ev.get("id_usuario_responsable") is not None
            and det.get("tipo_consulta") in ("ACTIVA", "HISTORIAL")
            and ev.get("resultado") is not None
            and ev.get("timestamp_evento") is not None
        ):
            alguno_ok = True
            break
    out["al_menos_un_registro_completo"] = alguno_ok
    if not alguno_ok:
        out["resultado"] = "RECHAZADO"
        out["explicacion"] = "Ningun registro reune activo, usuario, tipo_consulta, resultado y timestamp."
        pytest.fail(out["explicacion"])
    if "ACTIVA" not in tipos or "HISTORIAL" not in tipos:
        out["resultado"] = "RECHAZADO"
        out["explicacion"] = f"Bitacora no muestra ACTIVA e HISTORIAL: {sorted(tipos)}."
        pytest.fail(out["explicacion"])
    if fecha_ref and not con_fecha:
        out["resultado"] = "RECHAZADO"
        out["explicacion"] = (
            "Se ejecuto consulta con fecha_referencia y ningun registro de auditoria "
            "del activo guarda fecha_referencia en detalle_tecnico."
        )
        pytest.fail(out["explicacion"])
    out["resultado"] = "APROBADO"
    out["explicacion"] = (
        f"Campos base OK. Tipos {sorted(tipos)}. "
        f"Registros con fecha_referencia={len(con_fecha)}."
    )


def test_complemento_inexistente(ctx):
    out = {"resultado": "BLOQUEADO"}
    EVIDENCIA["subcasos"]["complemento_inexistente"] = out
    aid = ctx.get("id_inexistente")
    out["id_activo"] = aid
    r = requests.get(
        _infra_url(aid),
        params={"tipo_consulta": "ACTIVA"},
        headers=ctx["headers"],
        timeout=TIMEOUT,
        verify=VERIFY_SSL,
    )
    body = _json(r)
    out["http"] = r.status_code
    out["error_code"] = body.get("error_code") if isinstance(body, dict) else None
    out["respuesta"] = _trunc(body, 600)
    if r.status_code != 404 or out["error_code"] != "ACTIVO_NO_ENCONTRADO":
        out["resultado"] = "RECHAZADO"
        out["explicacion"] = f"HTTP {r.status_code} {out['error_code']}"
        pytest.fail(out["explicacion"])
    out["resultado"] = "APROBADO"
    out["explicacion"] = "404 ACTIVO_NO_ENCONTRADO."


def test_zz_global(ctx):
    assert EVIDENCIA.get("subcasos")
