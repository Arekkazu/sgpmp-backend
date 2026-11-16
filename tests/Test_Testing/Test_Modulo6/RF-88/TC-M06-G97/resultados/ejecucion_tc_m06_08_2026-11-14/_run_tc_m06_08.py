# Ejecucion formal TC-M06-08 — POST autorizado solo activo 2553.
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

BASE = "https://api.inmero.co/api-sgpmp-test"
ZONA = "America/Bogota"
OUT = Path(__file__).resolve().parent
AID = 2553
ESPECIE = 718
NIT = "901777118"
ESPERADO_IDENT = "QA-M06-G97-SIN-VIDA"
ESPERADO_COSTO = Decimal("900000")
AUTORIZACION = {
    "origen": "Usuario QA en chat Cursor",
    "alcance": "POST /finanzas/reconocimientos/2553 unicamente en TEST para TC-M06-08",
    "fecha_local": "2026-11-14",
}


def pedir(method, path, body=None, token=None, timeout=60):
    data = None if body is None else json.dumps(body).encode()
    h = {"Accept": "application/json", "X-Zona-Horaria": ZONA}
    if body is not None:
        h["Content-Type"] = "application/json"
    if token:
        h["Authorization"] = "Bearer " + token
    req = urllib.request.Request(BASE + path, data=data, headers=h, method=method)
    meta = {
        "url": BASE + path,
        "method": method,
        "request_headers": {
            k: ("Bearer ***" if k == "Authorization" else v) for k, v in h.items()
        },
        "request_body": body,
    }
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode()
            rh = {
                k: r.headers.get(k)
                for k in ("content-type", "date", "x-request-id")
                if r.headers.get(k)
            }
            return r.status, (json.loads(raw) if raw else None), meta, rh
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            payload = json.loads(raw)
        except Exception:
            payload = {"message": raw[:800]}
        rh = {
            k: e.headers.get(k) for k in ("content-type", "date", "x-request-id") if e.headers.get(k)
        }
        return e.code, payload, meta, rh
    except Exception as e:
        return None, {"error": type(e).__name__, "message": str(e)[:300]}, meta, {}


def D(x):
    if x is None:
        return None
    return Decimal(str(x))


def snapshot(token):
    st_p, prop, _, _ = pedir("GET", f"/finanzas/reconocimientos/propuestas/{AID}", token=token)
    st_f, fin, _, _ = pedir("GET", f"/finanzas/activos/{AID}", token=token)
    st_per, periodos, _, _ = pedir(
        "GET", f"/finanzas/periodos?numero_id_tributaria={NIT}", token=token
    )
    st_cfg, cfg, _, _ = pedir("GET", "/finanzas/configuracion", token=token)
    especie = None
    if isinstance(cfg, dict):
        for e in cfg.get("especies") or []:
            if isinstance(e, dict) and e.get("id_especie") == ESPECIE:
                especie = {
                    "id_especie": e.get("id_especie"),
                    "especie": e.get("especie"),
                    "clasificacion": e.get("clasificacion"),
                    "vida_util_meses": e.get("vida_util_meses"),
                }
                break
    activo = (fin or {}).get("activo") if isinstance(fin, dict) else None
    return {
        "propuesta": {"http": st_p, "body": prop},
        "finanzas_activo": {
            "http": st_f,
            "activo": {
                "id_activo_biologico": (activo or {}).get("id_activo_biologico"),
                "identificador": (activo or {}).get("identificador"),
                "estado": (activo or {}).get("estado"),
                "id_especie": (activo or {}).get("id_especie"),
                "especie": (activo or {}).get("especie"),
                "id_finca": (activo or {}).get("id_finca"),
                "costo_adquisicion": (activo or {}).get("costo_adquisicion"),
                "origen_financiero": (activo or {}).get("origen_financiero"),
            }
            if isinstance(activo, dict)
            else None,
            "reconocimientos_count": len((fin or {}).get("reconocimientos") or [])
            if isinstance(fin, dict)
            else None,
            "valoracion_costo": (fin or {}).get("valoracion_costo")
            if isinstance(fin, dict)
            else None,
            "lineas_count": len((fin or {}).get("lineas") or []) if isinstance(fin, dict) else None,
            "calculos_count": len((fin or {}).get("calculos") or [])
            if isinstance(fin, dict)
            else None,
        },
        "periodos_nit": {
            "http": st_per,
            "count": len(periodos) if isinstance(periodos, list) else None,
        },
        "especie_config": especie,
    }


def main() -> int:
    correo = os.environ.get("QA_CORREO")
    clave = os.environ.get("QA_CONTRASENA")
    if not correo or not clave:
        print("NO_AUTH_ENV")
        return 2

    st, login, _, _ = pedir(
        "POST", "/sesiones/", {"correo_electronico": correo, "contrasena": clave}
    )
    token = None
    if isinstance(login, dict):
        token = login.get("access_token") or login.get("token")
    if not token:
        print("AUTH_FAIL", st)
        return 3

    previo = snapshot(token)
    (OUT / "estado_previo_2553.json").write_text(
        json.dumps(
            {
                "captura_utc": datetime.now(timezone.utc).isoformat(),
                "autorizacion": AUTORIZACION,
                **previo,
            },
            indent=2,
            ensure_ascii=False,
            default=str,
        ),
        encoding="utf-8",
    )

    # Gate precondiciones
    prop = (previo.get("propuesta") or {}).get("body") or {}
    bloqueos = prop.get("bloqueos") or []
    codigos = [b.get("codigo") for b in bloqueos if isinstance(b, dict)]
    fin = previo.get("finanzas_activo") or {}
    activo = fin.get("activo") or {}
    pre_ok = (
        previo["propuesta"]["http"] == 200
        and codigos == ["VIDA_UTIL_NO_CONFIGURADA"]
        and activo.get("identificador") == ESPERADO_IDENT
        and activo.get("id_especie") == ESPECIE
        and D(activo.get("costo_adquisicion")) == ESPERADO_COSTO
        and fin.get("reconocimientos_count") == 0
        and not fin.get("valoracion_costo")
        and (previo.get("especie_config") or {}).get("clasificacion") == "PRODUCCION"
        and not (previo.get("especie_config") or {}).get("vida_util_meses")
    )
    if not pre_ok:
        print("PRECOND_FAIL", json.dumps({"codigos": codigos, "activo": activo, "fin": fin}, default=str))
        return 8

    # POST autorizado
    t0 = datetime.now(timezone.utc)
    http, body, meta, rh = pedir(
        "POST", f"/finanzas/reconocimientos/{AID}", body={}, token=token
    )
    t1 = datetime.now(timezone.utc)

    (OUT / "respuesta_reconocimiento_2553.json").write_text(
        json.dumps(
            {
                "autorizacion": AUTORIZACION,
                "inicio_utc": t0.isoformat(),
                "fin_utc": t1.isoformat(),
                "metodo": "POST",
                "url": meta["url"],
                "request_headers": meta["request_headers"],
                "request_body": {},
                "response_headers": rh,
                "http": http,
                "body": body,
            },
            indent=2,
            ensure_ascii=False,
            default=str,
        ),
        encoding="utf-8",
    )

    posterior = snapshot(token)
    (OUT / "estado_posterior_2553.json").write_text(
        json.dumps(
            {
                "captura_utc": datetime.now(timezone.utc).isoformat(),
                **posterior,
            },
            indent=2,
            ensure_ascii=False,
            default=str,
        ),
        encoding="utf-8",
    )

    aserciones = []

    def assert_(i, nombre, ok, obtenido, esperado, detalle=""):
        aserciones.append(
            {
                "id": i,
                "nombre": nombre,
                "ok": bool(ok),
                "obtenido": obtenido,
                "esperado": esperado,
                "detalle": detalle,
            }
        )

    assert_("A1", "Activo 2553 existe antes", True, ESPERADO_IDENT, ESPERADO_IDENT)
    assert_("A2", "Especie asociada 718", activo.get("id_especie") == ESPECIE, activo.get("id_especie"), ESPECIE)
    assert_(
        "A3",
        "Vida util vacia",
        not (previo.get("especie_config") or {}).get("vida_util_meses"),
        (previo.get("especie_config") or {}).get("vida_util_meses"),
        None,
    )
    assert_(
        "A4",
        "Clasificacion PRODUCCION",
        (previo.get("especie_config") or {}).get("clasificacion") == "PRODUCCION",
        (previo.get("especie_config") or {}).get("clasificacion"),
        "PRODUCCION",
    )
    assert_("A5", "Propuesta bloqueo VIDA_UTIL_NO_CONFIGURADA", codigos == ["VIDA_UTIL_NO_CONFIGURADA"], codigos, ["VIDA_UTIL_NO_CONFIGURADA"])
    assert_("A6", "POST HTTP 422", http == 422, http, 422)

    # error code extraction
    err_code = None
    if isinstance(body, dict):
        err_code = body.get("error_code") or body.get("code") or body.get("codigo")
        if not err_code and isinstance(body.get("detail"), dict):
            err_code = body["detail"].get("error_code") or body["detail"].get("code")
        if not err_code and isinstance(body.get("detail"), str):
            err_code = body.get("detail")
    assert_(
        "A7",
        "Codigo exacto VIDA_UTIL_NO_CONFIGURADA",
        err_code == "VIDA_UTIL_NO_CONFIGURADA",
        err_code,
        "VIDA_UTIL_NO_CONFIGURADA",
        json.dumps(body, ensure_ascii=False, default=str)[:500] if body else "",
    )

    post_fin = posterior.get("finanzas_activo") or {}
    post_per = posterior.get("periodos_nit") or {}
    post_prop = (posterior.get("propuesta") or {}).get("body") or {}
    post_codigos = [b.get("codigo") for b in (post_prop.get("bloqueos") or []) if isinstance(b, dict)]

    assert_(
        "A8",
        "Activo sigue sin reconocer",
        post_fin.get("reconocimientos_count") == 0 and not post_fin.get("valoracion_costo"),
        {
            "reconocimientos": post_fin.get("reconocimientos_count"),
            "valoracion_costo": post_fin.get("valoracion_costo"),
        },
        {"reconocimientos": 0, "valoracion_costo": None},
    )
    assert_(
        "A9",
        "Sin movimientos contables nuevos",
        post_fin.get("lineas_count") == fin.get("lineas_count") == 0
        and post_fin.get("calculos_count") == fin.get("calculos_count"),
        {
            "lineas_antes": fin.get("lineas_count"),
            "lineas_despues": post_fin.get("lineas_count"),
            "calculos_antes": fin.get("calculos_count"),
            "calculos_despues": post_fin.get("calculos_count"),
        },
        "sin cambio / cero",
    )
    assert_(
        "A10",
        "Sin periodos ni reconocimientos nuevos",
        post_per.get("count") == 0 and post_fin.get("reconocimientos_count") == 0,
        {"periodos": post_per.get("count"), "reconocimientos": post_fin.get("reconocimientos_count")},
        {"periodos": 0, "reconocimientos": 0},
    )
    assert_(
        "A11",
        "Sin modificaciones inesperadas (bloqueo/costo/especie)",
        post_codigos == ["VIDA_UTIL_NO_CONFIGURADA"]
        and D((post_fin.get("activo") or {}).get("costo_adquisicion")) == ESPERADO_COSTO
        and (post_fin.get("activo") or {}).get("id_especie") == ESPECIE
        and (posterior.get("especie_config") or {}).get("vida_util_meses") is None,
        {
            "bloqueos": post_codigos,
            "costo": (post_fin.get("activo") or {}).get("costo_adquisicion"),
            "especie": (post_fin.get("activo") or {}).get("id_especie"),
            "vida": (posterior.get("especie_config") or {}).get("vida_util_meses"),
        },
        "invariantes preservados",
    )

    ok_n = sum(1 for a in aserciones if a["ok"])
    fail_n = len(aserciones) - ok_n
    resultado_08 = "APROBADO" if fail_n == 0 else "FALLIDO"
    g97_aprobado = resultado_08 == "APROBADO"  # 09 ya APROBADO

    # ASERCIONES md
    lines = [
        "# Aserciones TC-M06-08",
        "",
        f"**Resultado escenario:** **{resultado_08}**  ",
        f"**Activo:** {AID} (`{ESPERADO_IDENT}`)  ",
        f"**UTC:** {t0.isoformat()} → {t1.isoformat()}  ",
        f"**HTTP POST:** {http}  ",
        "",
        "| ID | Aserción | Esperado | Obtenido | Resultado |",
        "|---|---|---|---|---|",
    ]
    for a in aserciones:
        lines.append(
            "| {id} | {nom} | `{esp}` | `{obt}` | {res} |".format(
                id=a["id"],
                nom=a["nombre"],
                esp=a["esperado"],
                obt=a["obtenido"],
                res=("PASS" if a["ok"] else "FAIL"),
            )
        )
    lines += ["", f"Aprobadas: **{ok_n}/{len(aserciones)}**", ""]
    (OUT / "ASERCIONES_TC-M06-08.md").write_text("\n".join(lines), encoding="utf-8")

    md = f"""# Resultado TC-M06-08

**Caso:** TC-M06-G97 / TC-M06-08 — Obligatoriedad de vida útil (RF-88)  
**Fecha ejecución (UTC):** {t0.isoformat()}  
**Commit:** `3995b923` · rama `laura`  
**Ambiente:** `{BASE}`  
**Resultado:** **{resultado_08}**

## Autorización

- Origen: {AUTORIZACION['origen']}
- Alcance: {AUTORIZACION['alcance']}
- Limitación: solo activo 2553; sin otras escrituras.

## Solicitud

| Campo | Valor |
|---|---|
| Método | POST |
| URL | `{meta['url']}` |
| Body | `{{}}` |
| Headers | `Accept`, `Content-Type`, `X-Zona-Horaria`, `Authorization: Bearer ***` |
| HTTP | **{http}** |
| error_code | `{err_code}` |

## Fixture

| Campo | Valor |
|---|---|
| Activo | 2553 / QA-M06-G97-SIN-VIDA |
| Especie | 718 / Caprino Sin Vida Util Qa |
| Clasificación | PRODUCCION |
| Vida útil | vacía |
| Costo | 900000 |

## Side-effects

| Campo | Antes | Después |
|---|---|---|
| reconocimientos | {fin.get('reconocimientos_count')} | {post_fin.get('reconocimientos_count')} |
| valoracion_costo | {fin.get('valoracion_costo')} | {post_fin.get('valoracion_costo')} |
| lineas | {fin.get('lineas_count')} | {post_fin.get('lineas_count')} |
| periodos NIT | {previo.get('periodos_nit',{}).get('count')} | {post_per.get('count')} |

## Aserciones

Ver `ASERCIONES_TC-M06-08.md` — {ok_n} PASS / {fail_n} FAIL.

## Estado G97

| Escenario | Estado |
|---|---|
| TC-M06-08 | **{resultado_08}** |
| TC-M06-09 | **APROBADO** (previo) |
| G97 | **{'APROBADO' if g97_aprobado else 'PARCIALMENTE_EJECUTADO / FALLIDO'}** |
"""
    (OUT / "RESULTADO_TC-M06-08.md").write_text(md, encoding="utf-8")

    estado = {
        "caso": "TC-M06-G97",
        "rf": "RF-88",
        "fecha": datetime.now().astimezone().isoformat(timespec="seconds"),
        "commit": "3995b923",
        "rama": "laura",
        "ambiente": BASE,
        "estado_general": "APROBADO" if g97_aprobado else "PARCIALMENTE_EJECUTADO",
        "aprobado_grupo": g97_aprobado,
        "autorizacion_escritura_08": AUTORIZACION,
        "tc_m06_08": {
            "resultado": resultado_08,
            "post_ejecutado": True,
            "activo": AID,
            "http": http,
            "error_code": err_code,
            "aserciones_ok": ok_n,
            "aserciones_fail": fail_n,
            "aserciones": aserciones,
            "endpoint": f"POST /finanzas/reconocimientos/{AID}",
            "inicio_utc": t0.isoformat(),
            "fin_utc": t1.isoformat(),
        },
        "tc_m06_09": {
            "resultado": "APROBADO",
            "fuente": "resultados/ejecucion_tc_m06_09_2026-11-14/",
            "activo": 1858,
        },
        "restricciones": {
            "solo_activo_2553": True,
            "sin_cierres": True,
            "sin_modificar_fixture": True,
            "sin_commit_push": True,
            "evidencia_09_intacta": True,
        },
    }
    (OUT / "estado_ejecucion_G97.json").write_text(
        json.dumps(estado, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )

    print("RESULTADO_08", resultado_08)
    print("HTTP", http, "CODE", err_code)
    print("ASSERT", [(a["id"], a["ok"]) for a in aserciones])
    print("G97", "APROBADO" if g97_aprobado else "NO")
    return 0 if resultado_08 == "APROBADO" else 1


if __name__ == "__main__":
    raise SystemExit(main())
