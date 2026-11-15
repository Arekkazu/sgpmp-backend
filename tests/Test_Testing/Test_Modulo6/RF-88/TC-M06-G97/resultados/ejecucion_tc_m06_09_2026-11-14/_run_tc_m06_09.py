# Ejecucion formal TC-M06-09 (solo GET + login). No modifica TEST ni WIP ajeno.
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
AID = 1858
FECHA = "2027-11-12"
ESPERADO = {
    "depreciacion_anual": Decimal("340000"),
    "depreciacion_acumulada": Decimal("340000"),
    "valor_contable": Decimal("1360000"),
    "depreciacion_registrada": Decimal("0"),
    "meses_transcurridos": 12,
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
    }
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode()
            resp_h = {
                k: r.headers.get(k)
                for k in ("content-type", "date", "server", "x-request-id")
                if r.headers.get(k)
            }
            payload = json.loads(raw) if raw else None
            return r.status, payload, meta, resp_h
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            payload = json.loads(raw)
        except Exception:
            payload = {"message": raw[:800]}
        resp_h = {
            k: e.headers.get(k) for k in ("content-type", "date") if e.headers.get(k)
        }
        return e.code, payload, meta, resp_h
    except Exception as e:
        return None, {"error": type(e).__name__, "message": str(e)[:300]}, meta, {}


def D(x):
    if x is None:
        return None
    return Decimal(str(x))


def eq_dec(a, b):
    if a is None or b is None:
        return False
    return D(a) == D(b)


def main() -> int:
    correo = os.environ.get("QA_CORREO")
    clave = os.environ.get("QA_CONTRASENA")
    if not correo or not clave:
        print("Faltan QA_CORREO/QA_CONTRASENA")
        return 2

    pre = {}
    st, login, _, _ = pedir(
        "POST", "/sesiones/", {"correo_electronico": correo, "contrasena": clave}
    )
    token = None
    if isinstance(login, dict):
        token = login.get("access_token") or login.get("token")
    pre["auth"] = {"http": st, "ok": bool(token), "nota": "unico POST: login"}
    if not token:
        (OUT / "estado_ejecucion_G97.json").write_text(
            json.dumps({"detenido": True, "motivo": "auth", "pre": pre}, indent=2),
            encoding="utf-8",
        )
        return 3

    st, perm, _, _ = pedir("GET", "/sesiones/me/permisos", token=token)
    tiene_vpc = False
    if isinstance(perm, dict):
        for p in perm.get("permisos") or []:
            if p.get("nombre_recurso") == "valoracion_por_costo" and p.get("id_accion") == 2:
                tiene_vpc = True
    pre["permiso_valoracion_por_costo_R"] = tiene_vpc
    if not tiene_vpc:
        (OUT / "estado_ejecucion_G97.json").write_text(
            json.dumps({"detenido": True, "motivo": "permiso", "pre": pre}, indent=2),
            encoding="utf-8",
        )
        return 4

    st, det, _, _ = pedir("GET", f"/finanzas/activos/{AID}", token=token)
    pre["get_activo"] = {"http": st}
    if st != 200 or not isinstance(det, dict):
        (OUT / "estado_ejecucion_G97.json").write_text(
            json.dumps({"detenido": True, "motivo": "activo", "pre": pre}, indent=2),
            encoding="utf-8",
        )
        return 5

    vc = det.get("valoracion_costo") or {}
    activo = det.get("activo") or {}
    baseline = {
        "id_activo_biologico": AID,
        "identificador": activo.get("identificador"),
        "especie": activo.get("especie"),
        "costos_adquisicion": vc.get("costos_adquisicion"),
        "vida_util_meses": vc.get("vida_util_meses"),
        "depreciacion_acumulada_registrada": vc.get("depreciacion_acumulada"),
        "deterioro_acumulado": vc.get("deterioro_acumulado"),
        "valor_contable_por_costo": vc.get("valor_contable_por_costo"),
        "es_activa": vc.get("es_activa"),
        "escenario_activacion": vc.get("escenario_activacion"),
        "id_valoracion_por_costo": vc.get("id_valoracion_por_costo"),
        "lineas_count_antes": len(det.get("lineas") or []),
    }
    pre["baseline"] = baseline
    if not vc or not vc.get("es_activa"):
        (OUT / "estado_ejecucion_G97.json").write_text(
            json.dumps(
                {"detenido": True, "motivo": "sin_valoracion_costo", "pre": pre},
                indent=2,
                ensure_ascii=False,
                default=str,
            ),
            encoding="utf-8",
        )
        return 6

    st0, hoy, _, _ = pedir("GET", f"/finanzas/activos/{AID}/depreciacion", token=token)
    pre["get_depreciacion_hoy"] = {"http": st0}
    if st0 != 200 or not isinstance(hoy, dict):
        (OUT / "estado_ejecucion_G97.json").write_text(
            json.dumps(
                {"detenido": True, "motivo": "dep_hoy", "pre": pre, "hoy": hoy},
                indent=2,
                ensure_ascii=False,
                default=str,
            ),
            encoding="utf-8",
        )
        return 7

    prep_ok = (
        eq_dec(hoy.get("costo_adquisicion"), "1700000")
        and int(hoy.get("vida_util_meses") or 0) == 60
        and str(hoy.get("fecha_adquisicion"))[:10] == "2026-11-12"
        and eq_dec(hoy.get("depreciacion_registrada"), "0")
    )
    pre["coincide_preparacion"] = {
        "ok": prep_ok,
        "costo_adquisicion": hoy.get("costo_adquisicion"),
        "vida_util_meses": hoy.get("vida_util_meses"),
        "fecha_adquisicion": hoy.get("fecha_adquisicion"),
        "depreciacion_registrada": hoy.get("depreciacion_registrada"),
    }
    pre["fecha_consulta"] = FECHA
    if not prep_ok:
        (OUT / "respuesta_precondicion_hoy.json").write_text(
            json.dumps(hoy, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
        )
        (OUT / "estado_ejecucion_G97.json").write_text(
            json.dumps(
                {
                    "detenido": True,
                    "motivo": "precondiciones_diferentes_a_preparacion",
                    "precondiciones": pre,
                },
                indent=2,
                ensure_ascii=False,
                default=str,
            ),
            encoding="utf-8",
        )
        print("PRECOND_CHANGED", json.dumps(pre["coincide_preparacion"], default=str))
        return 8

    # Ejecucion formal
    t0 = datetime.now(timezone.utc)
    st, body, meta, rh = pedir(
        "GET", f"/finanzas/activos/{AID}/depreciacion?fecha={FECHA}", token=token
    )
    t1 = datetime.now(timezone.utc)

    aserciones = []

    def assert_(nombre, ok, obtenido, esperado, detalle=""):
        aserciones.append(
            {
                "id": nombre,
                "ok": bool(ok),
                "obtenido": obtenido,
                "esperado": esperado,
                "detalle": detalle,
            }
        )

    assert_("A1_HTTP_exitoso", st == 200, st, 200)
    assert_(
        "A2_depreciacion_anual",
        eq_dec((body or {}).get("depreciacion_anual"), ESPERADO["depreciacion_anual"]),
        (body or {}).get("depreciacion_anual"),
        str(ESPERADO["depreciacion_anual"]),
    )
    assert_(
        "A3_depreciacion_acumulada",
        eq_dec(
            (body or {}).get("depreciacion_acumulada"), ESPERADO["depreciacion_acumulada"]
        ),
        (body or {}).get("depreciacion_acumulada"),
        str(ESPERADO["depreciacion_acumulada"]),
    )
    assert_(
        "A4_valor_contable",
        eq_dec((body or {}).get("valor_contable"), ESPERADO["valor_contable"]),
        (body or {}).get("valor_contable"),
        str(ESPERADO["valor_contable"]),
    )
    assert_(
        "A5_depreciacion_registrada",
        eq_dec(
            (body or {}).get("depreciacion_registrada"),
            ESPERADO["depreciacion_registrada"],
        ),
        (body or {}).get("depreciacion_registrada"),
        str(ESPERADO["depreciacion_registrada"]),
    )
    assert_(
        "A6_meses_transcurridos",
        int((body or {}).get("meses_transcurridos") or -1)
        == ESPERADO["meses_transcurridos"],
        (body or {}).get("meses_transcurridos"),
        ESPERADO["meses_transcurridos"],
    )

    st2, det2, _, _ = pedir("GET", f"/finanzas/activos/{AID}", token=token)
    vc2 = (det2 or {}).get("valoracion_costo") or {}
    after = {
        "depreciacion_acumulada_registrada": vc2.get("depreciacion_acumulada"),
        "valor_contable_por_costo": vc2.get("valor_contable_por_costo"),
        "deterioro_acumulado": vc2.get("deterioro_acumulado"),
        "lineas_count_despues": len((det2 or {}).get("lineas") or []),
        "http": st2,
    }
    sin_side = (
        st2 == 200
        and eq_dec(
            after["depreciacion_acumulada_registrada"],
            baseline["depreciacion_acumulada_registrada"],
        )
        and eq_dec(after["valor_contable_por_costo"], baseline["valor_contable_por_costo"])
        and eq_dec(after["deterioro_acumulado"], baseline["deterioro_acumulado"])
        and after["lineas_count_despues"] == baseline["lineas_count_antes"]
    )
    assert_(
        "A7_sin_efectos_secundarios",
        sin_side,
        after,
        {
            "depreciacion_acumulada_registrada": baseline[
                "depreciacion_acumulada_registrada"
            ],
            "valor_contable_por_costo": baseline["valor_contable_por_costo"],
            "deterioro_acumulado": baseline["deterioro_acumulado"],
            "lineas_count": baseline["lineas_count_antes"],
        },
        "Consulta no debe registrar depreciacion ni nuevas lineas",
    )

    aprobadas = [a for a in aserciones if a["ok"]]
    fallidas = [a for a in aserciones if not a["ok"]]
    resultado_09 = "APROBADO" if st == 200 and not fallidas else "FALLIDO"

    (OUT / "respuesta_depreciacion_1858.json").write_text(
        json.dumps(
            {
                "metodo": "GET",
                "url": meta["url"],
                "inicio_utc": t0.isoformat(),
                "fin_utc": t1.isoformat(),
                "http": st,
                "request_headers": meta["request_headers"],
                "response_headers": rh,
                "body": body,
                "baseline_antes": baseline,
                "baseline_despues": after,
            },
            indent=2,
            ensure_ascii=False,
            default=str,
        ),
        encoding="utf-8",
    )

    estado = {
        "caso": "TC-M06-G97",
        "fecha": datetime.now().astimezone().isoformat(timespec="seconds"),
        "commit": "3995b923",
        "rama": "laura",
        "ambiente": BASE,
        "estado_general": "PARCIALMENTE_EJECUTADO",
        "aprobado_grupo": False,
        "tc_m06_09": {
            "resultado": resultado_09,
            "activo": AID,
            "fecha_consulta": FECHA,
            "aserciones_ok": len(aprobadas),
            "aserciones_fail": len(fallidas),
            "aserciones": aserciones,
        },
        "tc_m06_08": {
            "resultado": "NO_EJECUTADO",
            "motivo": "Pendiente fixture limpia VIDA_UTIL_NO_CONFIGURADA y autorizacion de escritura",
        },
        "precondiciones": pre,
        "ejecucion": {
            "metodo": "GET",
            "url": meta["url"],
            "inicio_utc": t0.isoformat(),
            "fin_utc": t1.isoformat(),
            "http": st,
        },
        "restricciones": {
            "sin_escrituras_negocio": True,
            "sin_tc_m06_08": True,
            "sin_commit_push": True,
            "no_aprobar_g97_solo_por_09": True,
        },
    }
    (OUT / "estado_ejecucion_G97.json").write_text(
        json.dumps(estado, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )

    nombres = {
        "A1_HTTP_exitoso": "HTTP exitoso",
        "A2_depreciacion_anual": "depreciacion_anual == 340000",
        "A3_depreciacion_acumulada": "depreciacion_acumulada == 340000",
        "A4_valor_contable": "valor_contable == 1360000",
        "A5_depreciacion_registrada": "depreciacion_registrada == 0",
        "A6_meses_transcurridos": "meses_transcurridos == 12",
        "A7_sin_efectos_secundarios": "Sin side-effect en valoracion/lineas",
    }
    lines = [
        "# Aserciones TC-M06-09",
        "",
        f"**Activo:** {AID}  ",
        f"**Fecha consulta:** {FECHA}  ",
        f"**Resultado escenario:** **{resultado_09}**  ",
        f"**UTC:** {t0.isoformat()} → {t1.isoformat()}",
        "",
        "| ID | Aserción | Esperado | Obtenido | Resultado |",
        "|---|---|---|---|---|",
    ]
    for a in aserciones:
        lines.append(
            "| {id} | {nom} | `{esp}` | `{obt}` | {res} |".format(
                id=a["id"],
                nom=nombres.get(a["id"], a["id"]),
                esp=a["esperado"],
                obt=a["obtenido"],
                res=("PASS" if a["ok"] else "FAIL"),
            )
        )
    lines += ["", f"Aprobadas: **{len(aprobadas)}/{len(aserciones)}**", ""]
    (OUT / "ASERCIONES_TC-M06-09.md").write_text("\n".join(lines), encoding="utf-8")

    vals = body if isinstance(body, dict) else {}
    md = f"""# Resultado TC-M06-09

**Caso:** TC-M06-G97 / TC-M06-09  
**Fecha ejecución (UTC):** {t0.isoformat()}  
**Commit:** `3995b923` · rama `laura`  
**Ambiente:** `{BASE}`  
**Resultado:** **{resultado_09}**

## Solicitud

| Campo | Valor |
|---|---|
| Método | GET |
| URL | `{meta['url']}` |
| Headers | `Accept: application/json`, `X-Zona-Horaria: America/Bogota`, `Authorization: Bearer ***` |
| HTTP | **{st}** |

## Precondiciones

- Activo **1858** presente, valoración al costo activa.
- Costo **1700000**, vida **60**, adquisición **2026-11-12**, registrada **0**.
- Permiso `valoracion_por_costo` R confirmado.
- Baseline registrada: depreciación `{baseline['depreciacion_acumulada_registrada']}`, líneas `{baseline['lineas_count_antes']}`.

## Valores obtenidos

| Campo | Valor |
|---|---|
| depreciacion_anual | {vals.get('depreciacion_anual')} |
| depreciacion_acumulada | {vals.get('depreciacion_acumulada')} |
| valor_contable | {vals.get('valor_contable')} |
| depreciacion_registrada | {vals.get('depreciacion_registrada')} |
| meses_transcurridos | {vals.get('meses_transcurridos')} |
| fecha_adquisicion | {vals.get('fecha_adquisicion')} |
| fecha_calculo | {vals.get('fecha_calculo')} |
| vida_util_meses | {vals.get('vida_util_meses')} |
| costo_adquisicion | {vals.get('costo_adquisicion')} |

## Side-effect

| Campo | Antes | Después |
|---|---|---|
| depreciacion_acumulada (persistida) | {baseline['depreciacion_acumulada_registrada']} | {after['depreciacion_acumulada_registrada']} |
| valor_contable_por_costo | {baseline['valor_contable_por_costo']} | {after['valor_contable_por_costo']} |
| lineas contables | {baseline['lineas_count_antes']} | {after['lineas_count_despues']} |

## Aserciones

Ver `ASERCIONES_TC-M06-09.md` — {len(aprobadas)} PASS / {len(fallidas)} FAIL.

## Alcance G97

- TC-M06-09: **{resultado_09}**
- TC-M06-08: **NO EJECUTADO**
- Estado grupo: **PARCIALMENTE_EJECUTADO** (no APROBADO)
"""
    (OUT / "RESULTADO_TC-M06-09.md").write_text(md, encoding="utf-8")

    print("RESULTADO", resultado_09)
    print("ASSERT", [(a["id"], a["ok"]) for a in aserciones])
    return 0 if resultado_09 == "APROBADO" else 1


if __name__ == "__main__":
    raise SystemExit(main())
