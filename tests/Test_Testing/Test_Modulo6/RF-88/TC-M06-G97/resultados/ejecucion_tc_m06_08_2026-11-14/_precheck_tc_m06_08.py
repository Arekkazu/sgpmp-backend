# Precheck readonly TC-M06-08. Sin POST de reconocimiento.
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
ESPECIE_ID = 718
NIT = "901777118"
FINCA_ID = 489
ESPERADO_IDENT = "QA-M06-G97-SIN-VIDA"
ESPERADO_COSTO = Decimal("900000")


def pedir(method, path, body=None, token=None, timeout=60):
    data = None if body is None else json.dumps(body).encode()
    h = {"Accept": "application/json", "X-Zona-Horaria": ZONA}
    if body is not None:
        h["Content-Type"] = "application/json"
    if token:
        h["Authorization"] = "Bearer " + token
    req = urllib.request.Request(BASE + path, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode()
            return r.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            payload = json.loads(raw)
        except Exception:
            payload = {"message": raw[:800]}
        return e.code, payload
    except Exception as e:
        return None, {"error": type(e).__name__, "message": str(e)[:300]}


def D(x):
    if x is None:
        return None
    return Decimal(str(x))


def main() -> int:
    correo = os.environ.get("QA_CORREO")
    clave = os.environ.get("QA_CONTRASENA")
    if not correo or not clave:
        print("NO_AUTH_ENV")
        return 2

    st, login = pedir(
        "POST",
        "/sesiones/",
        {"correo_electronico": correo, "contrasena": clave},
    )
    token = None
    if isinstance(login, dict):
        token = login.get("access_token") or login.get("token")
    if not token:
        print("AUTH_FAIL", st)
        return 3

    consultas = []
    estado = {
        "fase": "precheck_readonly_tc_m06_08",
        "fecha_utc": datetime.now(timezone.utc).isoformat(),
        "ambiente": BASE,
        "fixture_reportada_samuel": {
            "id_activo": AID,
            "identificador": ESPERADO_IDENT,
            "id_especie": ESPECIE_ID,
            "nit": NIT,
            "id_finca": FINCA_ID,
            "costo": str(ESPERADO_COSTO),
        },
        "auth": {"http": st, "ok": True, "nota": "POST /sesiones/ solo login; sin token en evidencia"},
        "precondiciones": {},
        "autorizacion_post": {
            "encontrada": False,
            "origen": None,
            "motivo": (
                "No hay autorizacion expresa y verificable para POST de reconocimiento. "
                "La preparacion de Samuel y este prompt de ejecucion con Fase 2 de freno "
                "no se interpretan como autorizacion de escritura."
            ),
        },
        "post_ejecutado": False,
        "endpoint_correcto_codigo": "POST /finanzas/reconocimientos/{id_activo_biologico}",
        "endpoint_indicado_en_prompt": "POST /finanzas/reconocimientos/propuestas/2553",
        "nota_endpoint": "El router M06 confirma POST /finanzas/reconocimientos/{id}, no /propuestas/{id}.",
    }

    # Permisos reconocimiento
    st, perm = pedir("GET", "/sesiones/me/permisos", token=token)
    consultas.append({"GET": "/sesiones/me/permisos", "http": st})
    acciones_rec = []
    if isinstance(perm, dict):
        for p in perm.get("permisos") or []:
            if p.get("nombre_recurso") == "reconocimiento_inicial":
                acciones_rec.append(p.get("id_accion"))
    estado["precondiciones"]["permiso_reconocimiento_inicial"] = {
        "acciones_id": acciones_rec,
        "tiene_R": 2 in acciones_rec,
        "tiene_C": 1 in acciones_rec,
    }

    # Propuesta
    ruta_prop = f"/finanzas/reconocimientos/propuestas/{AID}"
    st, prop = pedir("GET", ruta_prop, token=token)
    consultas.append({"GET": ruta_prop, "http": st})
    estado["precondiciones"]["propuesta"] = {"http": st, "body": prop}

    # Config especies
    st, cfg = pedir("GET", "/finanzas/configuracion", token=token)
    consultas.append({"GET": "/finanzas/configuracion", "http": st})
    especie_cfg = None
    if isinstance(cfg, dict):
        for e in cfg.get("especies") or []:
            if isinstance(e, dict) and e.get("id_especie") == ESPECIE_ID:
                especie_cfg = e
                break
    estado["precondiciones"]["especie_config"] = especie_cfg

    # Activo biologico M02
    st, ab = pedir("GET", f"/activos-biologicos/{AID}", token=token)
    consultas.append({"GET": f"/activos-biologicos/{AID}", "http": st})
    # scrub potencial
    if isinstance(ab, dict):
        safe_ab = {
            k: ab.get(k)
            for k in (
                "id_activo",
                "id_activo_biologico",
                "identificador",
                "codigo",
                "estado",
                "tipo",
                "id_especie",
                "especie",
                "id_finca",
                "finca",
                "origen",
                "origen_financiero",
                "costo_adquisicion",
                "soporte_documental",
                "numero_id_tributaria",
                "razon_social",
            )
            if k in ab or True
        }
        # only keep existing keys with values of interest
        safe_ab = {k: ab.get(k) for k in ab.keys() if any(
            x in k.lower()
            for x in (
                "id",
                "ident",
                "codigo",
                "estado",
                "tipo",
                "especie",
                "finca",
                "origen",
                "costo",
                "soporte",
                "nit",
                "tribut",
                "razon",
            )
        )}
    else:
        safe_ab = ab
    estado["precondiciones"]["activo_biologico"] = {"http": st, "body": safe_ab}

    # Finanzas activo (puede 404 si no reconocido)
    st, fin = pedir("GET", f"/finanzas/activos/{AID}", token=token)
    consultas.append({"GET": f"/finanzas/activos/{AID}", "http": st})
    estado["precondiciones"]["finanzas_activo"] = {"http": st, "body": fin if st != 200 else {
        "indicador": (fin or {}).get("indicador_valoracion") if isinstance(fin, dict) else None,
        "reconocimientos": len((fin or {}).get("reconocimientos") or []) if isinstance(fin, dict) else None,
        "valoracion_costo": (fin or {}).get("valoracion_costo") if isinstance(fin, dict) else None,
        "lineas": len((fin or {}).get("lineas") or []) if isinstance(fin, dict) else None,
        "keys": sorted((fin or {}).keys()) if isinstance(fin, dict) else None,
    }}

    # Finca
    st, finca = pedir("GET", f"/configuracion/fincas/{FINCA_ID}", token=token)
    consultas.append({"GET": f"/configuracion/fincas/{FINCA_ID}", "http": st})
    if isinstance(finca, dict):
        finca_safe = {
            k: finca.get(k)
            for k in (
                "id_finca",
                "nombre",
                "area",
                "area_total",
                "numero_id_tributaria",
                "razon_social",
                "estado",
                "es_activo",
            )
        }
    else:
        finca_safe = finca
    estado["precondiciones"]["finca"] = {"http": st, "body": finca_safe}

    # Periodos del NIT
    st, periodos = pedir(
        "GET", f"/finanzas/periodos?numero_id_tributaria={NIT}", token=token
    )
    consultas.append({"GET": f"/finanzas/periodos?numero_id_tributaria={NIT}", "http": st})
    estado["precondiciones"]["periodos_nit"] = {
        "http": st,
        "count": len(periodos) if isinstance(periodos, list) else None,
        "body": periodos if isinstance(periodos, list) else periodos,
    }

    # Evaluacion checklist vs Samuel
    checks = []

    def chk(nombre, ok, detalle):
        checks.append({"id": nombre, "ok": bool(ok), "detalle": detalle})

    prop_ok = st_prop = None
    # re-extract from stored
    prop = estado["precondiciones"]["propuesta"]["body"]
    st_prop = estado["precondiciones"]["propuesta"]["http"]
    chk("P1_propuesta_http_200", st_prop == 200, f"http={st_prop}")

    if isinstance(prop, dict):
        bloqueos = prop.get("bloqueos") or []
        codigos = [b.get("codigo") for b in bloqueos if isinstance(b, dict)]
        chk(
            "P2_unico_bloqueo_VIDA_UTIL",
            codigos == ["VIDA_UTIL_NO_CONFIGURADA"],
            {"codigos": codigos, "bloqueos": bloqueos},
        )
        chk(
            "P3_es_confirmable_false",
            prop.get("es_confirmable") is False,
            prop.get("es_confirmable"),
        )
        chk(
            "P4_id_activo",
            prop.get("id_activo_biologico") == AID,
            prop.get("id_activo_biologico"),
        )
        chk(
            "P5_identificador",
            prop.get("identificador") == ESPERADO_IDENT,
            prop.get("identificador"),
        )
        chk(
            "P6_id_especie",
            prop.get("id_especie") == ESPECIE_ID,
            prop.get("id_especie"),
        )
        chk(
            "P7_costo_900000",
            D(prop.get("costo_adquisicion")) == ESPERADO_COSTO,
            prop.get("costo_adquisicion"),
        )
        chk(
            "P8_sin_indicador_valoracion",
            prop.get("indicador_valoracion") in (None, ""),
            prop.get("indicador_valoracion"),
        )
        especie_nombre = prop.get("especie")
        chk(
            "P9_nombre_especie",
            especie_nombre == "Caprino Sin Vida Util Qa",
            especie_nombre,
        )
        clasif = prop.get("clasificacion")
        chk(
            "P10_clasificacion_PRODUCCION",
            clasif == "PRODUCCION",
            clasif,
        )
    else:
        chk("P2_unico_bloqueo_VIDA_UTIL", False, "sin propuesta")

    esp = especie_cfg
    if isinstance(esp, dict):
        chk(
            "P11_especie_sin_vida_util",
            not esp.get("vida_util_meses"),
            esp.get("vida_util_meses"),
        )
        chk(
            "P12_especie_clasificacion",
            esp.get("clasificacion") == "PRODUCCION",
            esp.get("clasificacion"),
        )
    else:
        chk("P11_especie_sin_vida_util", False, "especie 718 no en GET configuracion")
        chk("P12_especie_clasificacion", False, "especie 718 no en GET configuracion")

    abody = estado["precondiciones"]["activo_biologico"]["body"]
    if isinstance(abody, dict) and estado["precondiciones"]["activo_biologico"]["http"] == 200:
        ident = abody.get("identificador") or abody.get("codigo")
        chk("P13_activo_existe", True, ident)
        chk(
            "P14_activo_identificador",
            ident == ESPERADO_IDENT,
            ident,
        )
        chk(
            "P15_activo_especie",
            abody.get("id_especie") == ESPECIE_ID,
            abody.get("id_especie"),
        )
        chk(
            "P16_activo_finca",
            abody.get("id_finca") == FINCA_ID,
            abody.get("id_finca"),
        )
        costo_ab = abody.get("costo_adquisicion")
        chk(
            "P17_activo_costo",
            D(costo_ab) == ESPERADO_COSTO if costo_ab is not None else False,
            costo_ab,
        )
    else:
        chk(
            "P13_activo_existe",
            False,
            estado["precondiciones"]["activo_biologico"],
        )

    fin_http = estado["precondiciones"]["finanzas_activo"]["http"]
    # sin reconocer: historial puede 404 o sin valoracion/reconocimientos
    sin_rec = False
    fin_body = estado["precondiciones"]["finanzas_activo"]["body"]
    if fin_http in (404, 422):
        sin_rec = True
    elif isinstance(fin_body, dict):
        recs = fin_body.get("reconocimientos")
        vc = fin_body.get("valoracion_costo")
        sin_rec = (recs in (0, None, []) or recs == 0) and not vc
    chk("P18_sin_reconocer", sin_rec, {"http": fin_http, "body": fin_body})

    per = estado["precondiciones"]["periodos_nit"]
    chk(
        "P19_sin_periodos_o_vacios",
        per.get("count") == 0 or per.get("http") in (404, 422),
        per,
    )

    chk(
        "P20_permiso_crear_reconocimiento",
        1 in acciones_rec,
        acciones_rec,
    )

    estado["checks"] = checks
    estado["consultas"] = consultas
    estado["todas_precondiciones_ok"] = all(c["ok"] for c in checks)
    estado["tc_m06_08"] = {
        "resultado": "NO_EJECUTADO_PENDIENTE_AUTORIZACION",
        "motivo": estado["autorizacion_post"]["motivo"],
    }
    estado["tc_m06_09"] = {"resultado": "APROBADO", "fuente": "ejecucion_tc_m06_09_2026-11-14"}
    estado["g97"] = {
        "estado_general": "PARCIALMENTE_EJECUTADO",
        "aprobado_grupo": False,
    }

    (OUT / "estado_previo_2553.json").write_text(
        json.dumps(
            {
                "captura_utc": estado["fecha_utc"],
                "propuesta": estado["precondiciones"]["propuesta"],
                "activo_biologico": estado["precondiciones"]["activo_biologico"],
                "finanzas_activo": estado["precondiciones"]["finanzas_activo"],
                "especie_config": estado["precondiciones"]["especie_config"],
                "finca": estado["precondiciones"]["finca"],
                "periodos_nit": estado["precondiciones"]["periodos_nit"],
            },
            indent=2,
            ensure_ascii=False,
            default=str,
        ),
        encoding="utf-8",
    )
    (OUT / "estado_ejecucion_G97.json").write_text(
        json.dumps(estado, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    print("PRECHECK_OK" if estado["todas_precondiciones_ok"] else "PRECHECK_FAIL")
    for c in checks:
        print(("PASS" if c["ok"] else "FAIL"), c["id"], c["detalle"])
    return 0 if estado["todas_precondiciones_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
