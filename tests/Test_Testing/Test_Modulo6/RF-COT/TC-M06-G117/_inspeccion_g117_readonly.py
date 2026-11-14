"""Inspeccion solo-lectura TC-M06-G117. Sin POST de cotizaciones."""
from __future__ import annotations

import json
import os
import shutil
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://api.inmero.co/api-sgpmp-test"
ZONA = "America/Bogota"
ROOT = Path(__file__).resolve().parent
RES = ROOT / "resultados"
PRIMERA = RES / "primera_evaluacion"
PREP = RES / "preparacion"
ACTIVO = 1569
NIT = "900000003"
FINCA = 467
PERIODO = 220
SECRETOS = {
    "token", "access_token", "contrasena", "password", "hash_integridad",
    "numero_id_tributaria", "identificador", "finca", "correo_electronico", "nombre_usuario",
}


def pedir(metodo, ruta, cuerpo=None, token=None, timeout=30):
    datos = None if cuerpo is None else json.dumps(cuerpo).encode()
    headers = {"Accept": "application/json", "X-Zona-Horaria": ZONA}
    if cuerpo is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(BASE + ruta, data=datos, headers=headers, method=metodo)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode()
            return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"message": raw[:400]}
        return exc.code, payload
    except Exception as exc:
        return None, {"error": type(exc).__name__, "message": str(exc)[:200]}


def limpiar(v, d=0):
    if d > 8:
        return "..."
    if isinstance(v, dict):
        return {k: ({"omitido": True} if k in SECRETOS else limpiar(x, d + 1)) for k, x in v.items()}
    if isinstance(v, list):
        return [limpiar(x, d + 1) for x in v[:60]]
    if isinstance(v, str) and len(v) > 400:
        return v[:400]
    return v


def ultimo_calculo(calcs):
    if not isinstance(calcs, list) or not calcs:
        return None
    ordenados = sorted(
        [x for x in calcs if isinstance(x, dict)],
        key=lambda x: str(x.get("fecha_calculo") or x.get("fecha_creacion") or ""),
        reverse=True,
    )
    return ordenados[0] if ordenados else None


def preservar_historico():
    PRIMERA.mkdir(parents=True, exist_ok=True)
    for name in (
        "resumen_ejecucion_TC-M06-G117.json",
        "evidencia_peticiones_TC-M06-G117.json",
        "resultado_ejecucion_TC-M06-G117.html",
        "analisis_hallazgos_TC-M06-G117.md",
    ):
        src, dst = RES / name, PRIMERA / name
        if src.exists() and not dst.exists():
            shutil.copy2(src, dst)
            src.unlink()
        elif src.exists() and dst.exists() and src.read_bytes() == dst.read_bytes():
            src.unlink()


def main():
    correo, clave = os.environ.get("QA_CORREO"), os.environ.get("QA_CONTRASENA")
    if not correo or not clave:
        raise SystemExit("Defina QA_CORREO y QA_CONTRASENA")

    preservar_historico()
    PREP.mkdir(parents=True, exist_ok=True)

    informe = {
        "caso": "TC-M06-G117",
        "identificador_anterior": "TC-M06-G89",
        "issue": "#1020 / INC-M06-333-G89",
        "correccion_ambiente": "#1024",
        "subcasos": ["TC-M06-48", "TC-M06-49"],
        "fase": "inspeccion_preparacion_solo_lectura",
        "ambiente": BASE,
        "generado_en": datetime.now(timezone.utc).isoformat(),
        "restricciones": "Sin POST /finanzas/cotizaciones; solo GET + POST /sesiones/",
        "peticiones": [],
        "contrato": {},
        "discrepancias": [],
        "activo_1569": {},
        "periodo_220": {},
        "disponibilidad_test": {},
        "dictamen_preparacion": {},
    }

    def reg(metodo, ruta, codigo, payload, nota=None):
        e = {"metodo": metodo, "ruta": ruta, "codigo": codigo, "escritura": metodo != "GET",
             "en": datetime.now(timezone.utc).isoformat()}
        if nota:
            e["nota"] = nota
        e["respuesta"] = limpiar(payload)
        informe["peticiones"].append(e)

    # Health
    c, health = pedir("GET", "/health")
    reg("GET", "/health", c, health, "health")
    # Auth
    c, login = pedir("POST", "/sesiones/", {"correo_electronico": correo, "contrasena": clave})
    token = login.get("token") if isinstance(login, dict) else None
    reg("POST", "/sesiones/", c, {"ok": bool(token), "tipo": (login or {}).get("tipo") if isinstance(login, dict) else None}, "login")
    informe["disponibilidad_test"] = {
        "health_http": c if False else informe["peticiones"][0]["codigo"],
        "login_http": c,
        "login_ok": bool(token),
        "timeout": c is None,
    }
    # fix health from first peticion
    informe["disponibilidad_test"]["health_http"] = next(
        p["codigo"] for p in informe["peticiones"] if p.get("nota") == "health"
    )

    if not token:
        informe["dictamen_preparacion"] = {
            "categoria": "BLOQUEADO",
            "motivo": "TEST no autentico Contador",
            "listo_para_ejecutar": False,
            "escritura_cotizaciones": False,
        }
        _guardar(informe)
        raise SystemExit("SIN SESION")

    # OpenAPI CotizacionDTO
    c, openapi = pedir("GET", "/openapi.json")
    schemas = ((openapi or {}).get("components") or {}).get("schemas") or {} if isinstance(openapi, dict) else {}
    dto = schemas.get("CotizacionDTO") or {}
    props = dto.get("properties") or {}
    reg("GET", "/openapi.json", c, {
        "version": ((openapi or {}).get("info") or {}).get("version") if isinstance(openapi, dict) else None,
        "post_cotizaciones": "post" in (((openapi or {}).get("paths") or {}).get("/finanzas/cotizaciones") or {}),
        "CotizacionDTO": limpiar(props),
        "required": dto.get("required"),
    }, "openapi")

    # Auditoria filters as #1024 footprint (same as G116 diagnosis)
    params = (((openapi or {}).get("paths") or {}).get("/finanzas/auditoria") or {}).get("get", {}).get("parameters") or []
    names = sorted({p.get("name") for p in params if isinstance(p, dict)})
    footprint = {k: k in names for k in ("id_usuario", "origen_registro", "id_referencia")}
    informe["despliegue_1024_huella"] = {
        "filtros_auditoria_presentes": footprint,
        "todos": all(footprint.values()),
        "nota": "Huella OpenAPI del commit 29512934 (lote #1024). No prueba por si sola el FA-3 de periodo; si prueba presencia del lote en TEST.",
    }

    # Periodo 220
    c, periodos = pedir("GET", f"/finanzas/periodos?numero_id_tributaria={NIT}", token=token)
    p220 = next((p for p in (periodos or []) if isinstance(p, dict) and p.get("id_periodo_contable") == PERIODO), None)
    informe["periodo_220"] = {
        "encontrado": p220 is not None,
        "estado": (p220 or {}).get("estado"),
        "fecha_inicio": (p220 or {}).get("fecha_inicio"),
        "fecha_fin": (p220 or {}).get("fecha_fin"),
        "razon_social": (p220 or {}).get("razon_social"),
    }
    reg("GET", f"/finanzas/periodos?numero_id_tributaria={NIT}", c, {"periodo_220": informe["periodo_220"]})

    # Activo 1569
    c, det = pedir("GET", f"/finanzas/activos/{ACTIVO}", token=token)
    act = (det or {}).get("activo") if isinstance(det, dict) else None
    recs = (det or {}).get("reconocimientos") if isinstance(det, dict) else []
    calcs = (det or {}).get("calculos") if isinstance(det, dict) else []
    if not isinstance(recs, list):
        recs = []
    if not isinstance(calcs, list):
        calcs = []
    rec = next((r for r in recs if isinstance(r, dict) and r.get("estado") == "CONFIRMADO"), recs[0] if recs else None)
    calc = ultimo_calculo(calcs)
    vr = (calc or {}).get("valor_neto") if isinstance(calc, dict) else None
    informe["activo_1569"] = {
        "http": c,
        "estado": (act or {}).get("estado") if isinstance(act, dict) else None,
        "id_finca": (act or {}).get("id_finca") if isinstance(act, dict) else None,
        "razon_social": (act or {}).get("razon_social") if isinstance(act, dict) else None,
        "indicador_valoracion": (rec or {}).get("indicador_valoracion") if isinstance(rec, dict) else None,
        "tiene_calculo": calc is not None,
        "valor_razonable_neto": str(vr) if vr is not None else None,
    }
    apto = (
        c == 200
        and informe["activo_1569"]["estado"] == "ACTIVO"
        and informe["activo_1569"]["id_finca"] == FINCA
        and informe["activo_1569"]["indicador_valoracion"] == "VALOR_RAZONABLE"
        and informe["activo_1569"]["tiene_calculo"]
        and informe["periodo_220"].get("estado") == "ABIERTO"
    )
    informe["activo_1569"]["apto_para_g117"] = apto
    reg("GET", f"/finanzas/activos/{ACTIVO}", c, informe["activo_1569"])

    # Cotizaciones baseline (read only)
    c, cots = pedir("GET", "/finanzas/cotizaciones", token=token)
    lista = cots if isinstance(cots, list) else []
    ids = [x.get("id_cotizacion") for x in lista if isinstance(x, dict)]
    sobre = [x.get("id_cotizacion") for x in lista if isinstance(x, dict) and ACTIVO in (x.get("activos_cotizados") or [])]
    informe["baseline_cotizaciones"] = {"total": len(lista), "ids": ids, "sobre_1569": sobre}
    reg("GET", "/finanzas/cotizaciones", c, informe["baseline_cotizaciones"])

    # Contrato desde codigo + openapi
    informe["contrato"] = {
        "endpoint": "POST /finanzas/cotizaciones",
        "dto": "CotizacionDTO",
        "campos": {
            "activos_cotizados": "list[int] obligatorio min_length=1",
            "valor_cotizacion_propuesto": "Decimal gt=0 max_digits=18 decimal_places=4 (DTO)",
            "condiciones": "opcional",
            "fecha_vencimiento": "Optional[date] = None (DTO); opcional",
        },
        "fecha_emision": "No se envia; hoy_usuario() America/Bogota en el caso de uso",
        "validaciones_caso_uso": {
            "valor_propuesto_le_0": {"http": 422, "code": "VALOR_COTIZACION_INVALIDO", "alcanzable_via_api": False},
            "fecha_vencimiento_anterior": {"http": 422, "code": "FECHA_VENCIMIENTO_INVALIDA", "alcanzable_via_api": True},
            "fecha_vencimiento_omitida": {"permitido": True, "efecto": "persiste null; no vence automaticamente"},
        },
        "validacion_dto_antes_caso_uso": {
            "valor_0_o_negativo": {"http": 400, "code": "VAL_ENTRADA", "motivo": "Field(gt=0) en CotizacionDTO"},
        },
    }

    informe["discrepancias"] = [
        {
            "id": "DISC-G117-01",
            "tema": "TC-M06-48 esperado vs implementacion",
            "matriz_issue_1020": "HTTP 422 VALOR_COTIZACION_INVALIDO para valor 0 y -1",
            "implementacion": (
                "CotizacionDTO.valor_cotizacion_propuesto = Field(gt=0) rechaza 0/-1 en Pydantic; "
                "error_handlers -> HTTP 400 VAL_ENTRADA. La linea FA-6 del caso de uso (422 VALOR_COTIZACION_INVALIDO) "
                "no se alcanza por la API."
            ),
            "fuentes": [
                "src/financial_valuation/infrastructure/dto/m06_dto.py CotizacionDTO",
                "src/shared/error_handlers.py request_validation_error_handler",
                "registrar_cotizacion_use_case.py FA-6",
                "primera_evaluacion/resumen_ejecucion_TC-M06-G117.json contrato historico",
            ],
            "accion": "No se altera la matriz ni el backend. Requiere revision/autorizacion de expectativa.",
        },
        {
            "id": "DISC-G117-02",
            "tema": "RF-COT 5.3.b documental",
            "matriz": "Omitir fecha_vencimiento es valido (RF-COT 5.3.b)",
            "implementacion": "fecha_vencimiento Optional en DTO; caso de uso solo valida si viene y es < hoy",
            "especificacion_en_repo": "No se encontro documento RF-COT v1.1 con seccion 5.3.b en el repositorio",
            "respaldo_disponible": "Comentario Arekkazu en #1020 + DTO/use case + tabla (nullable)",
            "accion": "Conservar referencia issue #1020 + implementacion; 49b es escritura positiva y requiere autorizacion expresa",
        },
    ]

    riesgos = [
        "49b (omitir fecha_vencimiento) crea cotizacion y evento COTIZACION_REGISTRADA si se ejecuta: requiere autorizacion escrita.",
        "No cerrar periodo 220; no usar 219; no tocar cotizaciones 6/7/9/10 ni activos 1570/1571 para otros casos si se evita solape.",
        "DISC-G117-01: ejecutar 48a/48b con expectativa 422 puede producir FALLIDO por 400 VAL_ENTRADA.",
    ]

    listo = (
        informe["disponibilidad_test"]["login_ok"]
        and apto
        and informe["despliegue_1024_huella"]["todos"]
    )
    informe["riesgos"] = riesgos
    informe["dictamen_preparacion"] = {
        "categoria": "PREPARADO_CON_DISCREPANCIA" if listo else "BLOQUEADO",
        "motivo": (
            "TEST responde, activo 1569 apto, huella #1024 presente. "
            "DISC-G117-01 pendiente de decision (422 vs 400). "
            "49b no ejecutarse sin autorizacion (escritura)."
            if listo else "Faltan condiciones de disponibilidad o datos."
        ),
        "listo_para_ejecutar_negativos_48_49a": listo,
        "listo_para_ejecutar_49b_positivo": False,
        "requiere_decision_previa": ["DISC-G117-01 expectativa HTTP/code para valor 0 y -1"],
        "escritura_cotizaciones": False,
    }

    _guardar(informe)
    print("DICTAMEN", informe["dictamen_preparacion"]["categoria"])
    print("LOGIN", informe["disponibilidad_test"])
    print("ACTIVO", informe["activo_1569"])
    print("P220", informe["periodo_220"])
    print("1024", informe["despliegue_1024_huella"])
    return 0


def _guardar(informe: dict) -> None:
    PREP.mkdir(parents=True, exist_ok=True)
    (PREP / "inspeccion_preparacion_G117.json").write_text(
        json.dumps(informe, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8"
    )
    (PREP / "informe_inspeccion_preparacion_G117.md").write_text(_md(informe), encoding="utf-8")
    (PREP / "matriz_escenarios_G117.md").write_text(_matriz(), encoding="utf-8")
    (PREP / "datos_prueba_G117.md").write_text(_datos(), encoding="utf-8")
    print("OK", PREP)


def _matriz() -> str:
    return """# TC-M06-G117 — Matriz de escenarios (preparacion)

Endpoint: `POST /finanzas/cotizaciones`

| ID | Subcaso | Payload clave | Esperado (matriz/#1020) | Observacion implementacion |
|---|---|---|---|---|
| 48a | TC-M06-48 | `valor_cotizacion_propuesto: 0`, activo 1569 | 422 `VALOR_COTIZACION_INVALIDO` | **DISC-G117-01**: DTO `gt=0` -> 400 `VAL_ENTRADA` |
| 48b | TC-M06-48 | `valor_cotizacion_propuesto: -1`, activo 1569 | 422 `VALOR_COTIZACION_INVALIDO` | **DISC-G117-01**: idem |
| 49a | TC-M06-49 | `valor` > 0, `fecha_vencimiento` = ayer (America/Bogota) | 422 `FECHA_VENCIMIENTO_INVALIDA` | Alineado con FA-5 del caso de uso |
| 49b | TC-M06-49 | omitir `fecha_vencimiento`, `valor` > 0 | Valido (RF-COT 5.3.b / #1020) | **Escritura**: crea cotizacion + evento; requiere autorizacion |

Cuerpo base DTO: `activos_cotizados` (enteros), `valor_cotizacion_propuesto`, opcionales `condiciones`, `fecha_vencimiento`.
No enviar `fecha_emision` (la calcula el servidor).

**No ejecutar POST hasta autorizacion expresa.** Decidir DISC-G117-01 antes de calificar 48a/48b.
"""


def _datos() -> str:
    return """# TC-M06-G117 — Datos de prueba

| Campo | Valor |
|---|---|
| Activo | 1569 (`QA-M06O-VR-01`) |
| Titular | NIT 900000003 |
| Finca | 467 |
| Periodo | 220 (noviembre) ABIERTO |
| Valor propuesto valido (solo para 49a/49b) | `1000.0000` (dato de prueba; no es VR) |
| VR referencia esperado (si hubiera alta) | ultimo valor_neto del activo |

Restricciones: no cerrar 220; no usar 219; no modificar activos/VR; no usar titular 900000001; no alterar cotizaciones existentes.
"""


def _md(inf: dict) -> str:
    d = inf["dictamen_preparacion"]
    return "\n".join([
        "# TC-M06-G117 — Informe de inspeccion de preparacion",
        "",
        f"- Antecedente: {inf['identificador_anterior']} / {inf['issue']}",
        f"- Correccion ambiente: {inf['correccion_ambiente']}",
        f"- Generado: {inf['generado_en']}",
        f"- Dictamen: **{d.get('categoria')}**",
        "",
        d.get("motivo", ""),
        "",
        "## TEST y autenticacion",
        "",
        f"```json\n{json.dumps(inf.get('disponibilidad_test'), ensure_ascii=False, indent=2)}\n```",
        "",
        "## Activo 1569 y periodo 220",
        "",
        f"```json\n{json.dumps(inf.get('activo_1569'), ensure_ascii=False, indent=2)}\n```",
        f"```json\n{json.dumps(inf.get('periodo_220'), ensure_ascii=False, indent=2)}\n```",
        "",
        "## Contrato",
        "",
        f"```json\n{json.dumps(inf.get('contrato'), ensure_ascii=False, indent=2)}\n```",
        "",
        "## Discrepancias (sin autocorregir)",
        "",
        f"```json\n{json.dumps(inf.get('discrepancias'), ensure_ascii=False, indent=2)}\n```",
        "",
        "## Huella #1024 en TEST",
        "",
        f"```json\n{json.dumps(inf.get('despliegue_1024_huella'), ensure_ascii=False, indent=2)}\n```",
        "",
        "## Confirmacion",
        "",
        "**No se registro ninguna cotizacion ni se modificaron datos.** Solo health, login y GET.",
        "",
    ]) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
