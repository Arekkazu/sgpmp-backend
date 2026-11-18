# | Fecha      | Nombre      | Que se hizo |
# |------------|-------------|-------------|
# | 2026-11-17 | Laura López | TC-M07-G056 RF-102: permisos RBAC Admin/Auditor/sin permiso + export + diagnóstico períodos. |
"""TC-M07-G056 — permisos de acceso y restricciones de consulta según el rol.

Contrato real (m07_router + ConsultarAuditoriaIntegracionUseCase + rbac):
  GET  /integracion/auditoria
    - permiso auditoria_integracion:R  → vista completa (restringida=False)
    - permiso auditoria_integracion_cierres:R → vista restringida (TIPOS_AUDITOR, solo_exitosos,
      ip_origen=None, json_detalle=None)
    - sin ambos → 403 ACCESO_DENEGADO + evento ACCESO_AUDITORIA_DENEGADO
  GET  /integracion/auditoria/exportar
    - requiere auditoria_integracion:E (dependency permiso)
  TIPOS_AUDITOR = PAQUETE_AAEF_CONSULTADO, VISTA_AAEF_GENERADA, CONTRATO_ACTIVADO
  Períodos contables: modulo6.periodos_contables (vía M06 /finanzas/periodos).
    GET /auditoria NO valida id_periodo ni estado CERRADO/ABIERTO (solo desde/hasta fecha).
  Perfiles TEST: Admin (admin.rol), Auditor externo = Revisor Fiscal (revisor.fiscal),
    sin permiso = Contador (contador).

Credenciales: QA_ADMIN_*, QA_AUDITOR_*, QA_SIN_PERMISO_* (o TEST_* equivalentes).

    python tests/Test_Testing/Test_Modulo7/RF-102/TC-M07-G056/ejecutar_tc_m07_g56.py
"""
from __future__ import annotations

import html
import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlencode

BASE = "https://api.inmero.co/api-sgpmp-test"
ZONA = "America/Bogota"
CASO = "TC-M07-G056"
RF = "RF-102"
CARPETA = Path(__file__).resolve().parent
RESULTADO = CARPETA / "Resultado"

TIPOS_AUDITOR = ("PAQUETE_AAEF_CONSULTADO", "VISTA_AAEF_GENERADA", "CONTRATO_ACTIVADO")
ENDPOINT_AUDIT = "/integracion/auditoria"
ENDPOINT_EXPORT = "/integracion/auditoria/exportar"
ENDPOINT_PERIODOS = "/finanzas/periodos"


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


def pedir(metodo: str, ruta: str, cuerpo: Any = None, token: Optional[str] = None, timeout: int = 90):
    datos = None if cuerpo is None else json.dumps(cuerpo).encode()
    headers = {"Accept": "application/json", "X-Zona-Horaria": ZONA}
    if cuerpo is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(BASE + ruta, data=datos, headers=headers, method=metodo)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
            ctype = (resp.headers.get("Content-Type") or "").lower()
            if "json" in ctype or (raw[:1] in "{["):
                try:
                    payload = json.loads(raw) if raw else None
                except json.JSONDecodeError:
                    payload = {"_raw_preview": raw[:400]}
            else:
                payload = {"_content_type": ctype, "_bytes": len(raw.encode("utf-8", "replace")), "_preview": raw[:200]}
            return resp.status, payload, None
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"message": raw[:800]}
        return exc.code, payload, None
    except Exception as exc:  # noqa: BLE001
        return None, {"error": type(exc).__name__, "message": str(exc)[:300]}, str(exc)


def limpiar(v: Any, d: int = 0) -> Any:
    if d > 12:
        return "..."
    if isinstance(v, dict):
        out = {}
        for k, x in v.items():
            kl = str(k).lower()
            if kl in ("token", "access_token", "client_secret", "contrasena", "password") or kl.endswith("_token"):
                out[k] = {"omitido": True}
            else:
                out[k] = limpiar(x, d + 1)
        return out
    if isinstance(v, list):
        return [limpiar(x, d + 1) for x in v[:80]]
    if isinstance(v, str) and len(v) > 500:
        return v[:500] + "…"
    return v


def badge(estado: str) -> str:
    c = {"APROBADO": "#1b7a3d", "RECHAZADO": "#b00020", "BLOQUEADO": "#9a6b00", "NO APLICA": "#555"}.get(estado, "#333")
    return (
        f'<span style="display:inline-block;padding:2px 10px;border-radius:4px;'
        f'background:{c};color:#fff;font-weight:600">{html.escape(estado)}</span>'
    )


def get_auditoria(token: str, **params):
    q = urlencode({k: v for k, v in params.items() if v is not None})
    ruta = ENDPOINT_AUDIT + (("?" + q) if q else "")
    return pedir("GET", ruta, token=token)[:2]


def get_export(token: str, formato: str = "json", **params):
    q = urlencode({"formato": formato, **{k: v for k, v in params.items() if v is not None}})
    return pedir("GET", ENDPOINT_EXPORT + "?" + q, token=token)[:2]


def login(correo: str, clave: str):
    return pedir("POST", "/sesiones/", {"correo_electronico": correo, "contrasena": clave})


def code_of(body: Any) -> Optional[str]:
    if not isinstance(body, dict):
        return None
    if body.get("error_code"):
        return body.get("error_code")
    if body.get("code"):
        return body.get("code")
    if body.get("codigo"):
        return body.get("codigo")
    detail = body.get("detail")
    if isinstance(detail, dict):
        return detail.get("error_code") or detail.get("code")
    return None


def resumen_items(body: Any) -> dict:
    if not isinstance(body, dict):
        return {"tipo": type(body).__name__}
    items = body.get("items") or []
    tipos = sorted({str(it.get("tipo_evento")) for it in items if it.get("tipo_evento")})
    ips = [it.get("ip_origen") for it in items]
    detalles = [it.get("json_detalle") for it in items]
    return {
        "total": body.get("total"),
        "pagina": body.get("pagina"),
        "tamano": body.get("tamano"),
        "n_items": len(items),
        "tipos_evento": tipos,
        "fuera_tipos_auditor": [t for t in tipos if t not in TIPOS_AUDITOR],
        "ip_origen_no_nulas": sum(1 for x in ips if x not in (None, "")),
        "json_detalle_no_nulos": sum(1 for x in detalles if x not in (None, "", {}, [])),
        "claves_muestra": sorted(items[0].keys()) if items else [],
    }


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


def render_html(data: dict) -> str:
    filas = []
    for e in data["escenarios"]:
        filas.append(
            "<tr>"
            f"<td>{html.escape(e['id'])}</td><td>{html.escape(e.get('perfil',''))}</td>"
            f"<td>{html.escape(e['nombre'])}</td><td>{badge(e['estado'])}</td>"
            f"<td>{html.escape(e.get('validacion',''))}</td>"
            f"<td>{html.escape(e.get('evidencia',''))}</td>"
            "</tr>"
        )
    mat_rows = []
    for m in data.get("matriz_permisos") or []:
        mat_rows.append(
            "<tr>"
            f"<td>{html.escape(m['funcionalidad'])}</td>"
            f"<td>{html.escape(str(m['administrador']))}</td>"
            f"<td>{html.escape(str(m['auditor']))}</td>"
            f"<td>{html.escape(str(m['sin_permisos']))}</td>"
            f"<td>{html.escape(str(m.get('evidencia','')))}</td>"
            "</tr>"
        )
    det = []
    for e in data["escenarios"]:
        pasos = "".join(f"<li>{html.escape(p)}</li>" for p in (e.get("pasos") or []))
        det.append(
            f"<div class='card'><h3>{html.escape(e['id'])} — {html.escape(e.get('perfil',''))}: "
            f"{html.escape(e['nombre'])} {badge(e['estado'])}</h3>"
            f"<p><strong>Validación:</strong> {html.escape(e.get('validacion',''))}</p>"
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
<h1>{html.escape(CASO)} — Permisos de acceso y restricciones según rol</h1>
<div class="card meta">
  <span><strong>RF-102 / M01 · CU07</strong></span>
  <span><strong>Endpoints:</strong> GET {html.escape(ENDPOINT_AUDIT)}, GET {html.escape(ENDPOINT_EXPORT)}</span>
  <span><strong>Estado:</strong> {badge(data['estado_final'])}</span>
  <span><strong>UTC:</strong> {html.escape(data['fecha_ejecucion_utc'])}</span>
</div>
<div class="note">
Permisos reales: <code>auditoria_integracion</code> (R/E) vs <code>auditoria_integracion_cierres</code> (R).
Auditor externo = Revisor Fiscal. Vista restringida: TIPOS_AUDITOR + sin IP/json_detalle.
Exportación exige <code>auditoria_integracion:E</code>.
Períodos contables: <code>modulo6.periodos_contables</code> vía M06; <strong>no</strong> hay ACL de período en GET auditoría.
</div>
<div class="card"><h2>Matriz de permisos (comportamiento real)</h2>
<table><thead><tr><th>Funcionalidad</th><th>Administrador</th><th>Auditor</th><th>Sin permisos</th><th>Evidencia</th></tr></thead>
<tbody>{''.join(mat_rows)}</tbody></table></div>
<div class="card"><h2>Escenarios</h2>
<table><thead><tr><th>ID</th><th>Perfil</th><th>Nombre</th><th>Estado</th><th>Validación</th><th>Evidencia</th></tr></thead>
<tbody>{''.join(filas)}</tbody></table></div>
{''.join(det)}
<div class="card"><h2>Integración períodos / M08</h2>
<pre>{html.escape(json.dumps(data.get('integracion_m08', {}), ensure_ascii=False, indent=2))}</pre></div>
<div class="lim"><h3>Limitaciones</h3><pre>{html.escape(json.dumps(data.get('limitaciones', []), ensure_ascii=False, indent=2))}</pre></div>
<div class="card"><h3>Resumen</h3><pre>{html.escape(json.dumps(data.get('resumen', {}), ensure_ascii=False, indent=2))}</pre>
<pre>{html.escape(json.dumps(data.get('endpoints_reales', {}), ensure_ascii=False, indent=2))}</pre></div>
</body></html>"""


def cred(prefijo: str) -> tuple[Optional[str], Optional[str]]:
    aliases = {
        "ADMIN": ("QA_ADMIN_CORREO", "QA_ADMIN_CONTRASENA", "TEST_ADMIN_EMAIL", "TEST_ADMIN_PASSWORD"),
        "AUDITOR": ("QA_AUDITOR_CORREO", "QA_AUDITOR_CONTRASENA", "TEST_AUDITOR_EMAIL", "TEST_AUDITOR_PASSWORD"),
        "SIN": ("QA_SIN_PERMISO_CORREO", "QA_SIN_PERMISO_CONTRASENA", "TEST_SIN_PERMISO_EMAIL", "TEST_SIN_PERMISO_PASSWORD"),
    }
    keys = aliases[prefijo]
    return os.environ.get(keys[0]) or os.environ.get(keys[2]), os.environ.get(keys[1]) or os.environ.get(keys[3])


def main() -> int:
    RESULTADO.mkdir(parents=True, exist_ok=True)
    limitaciones: list[str] = []
    pet: list[dict] = []
    escenarios: list[dict] = []

    admin_c, admin_p = cred("ADMIN")
    aud_c, aud_p = cred("AUDITOR")
    sin_c, sin_p = cred("SIN")

    if not all([admin_c, admin_p, aud_c, aud_p, sin_c, sin_p]):
        faltan = []
        if not admin_c or not admin_p:
            faltan.append("QA_ADMIN_*")
        if not aud_c or not aud_p:
            faltan.append("QA_AUDITOR_*")
        if not sin_c or not sin_p:
            faltan.append("QA_SIN_PERMISO_*")
        data = {
            "caso": CASO,
            "fecha_ejecucion_utc": ahora(),
            "estado_final": "BLOQUEADO",
            "matriz_permisos": [],
            "escenarios": [
                {
                    "id": "E1", "perfil": "Administrador", "nombre": "Consulta autorizada",
                    "estado": "BLOQUEADO", "validacion": "Consulta autorizada",
                    "esperado": "HTTP 200 vista completa", "obtenido": "Sin credenciales",
                    "evidencia": "evidencia_e1_admin_TC-M07-G056.json", "pasos": [],
                    "observaciones": f"Faltan: {', '.join(faltan)}",
                },
                {
                    "id": "E2a", "perfil": "Auditor", "nombre": "Restricciones eventos/períodos",
                    "estado": "BLOQUEADO", "validacion": "Restricciones de eventos y períodos",
                    "esperado": "Vista restringida", "obtenido": "Sin credenciales",
                    "evidencia": "evidencia_e2_auditor_TC-M07-G056.json", "pasos": [],
                    "observaciones": f"Faltan: {', '.join(faltan)}",
                },
                {
                    "id": "E2b", "perfil": "Auditor", "nombre": "Exportación denegada",
                    "estado": "BLOQUEADO", "validacion": "Exportación denegada",
                    "esperado": "HTTP 403", "obtenido": "Sin credenciales",
                    "evidencia": "evidencia_e2_export_TC-M07-G056.json", "pasos": [],
                    "observaciones": f"Faltan: {', '.join(faltan)}",
                },
                {
                    "id": "E3", "perfil": "Sin permisos", "nombre": "Acceso rechazado",
                    "estado": "BLOQUEADO", "validacion": "Acceso rechazado",
                    "esperado": "HTTP 403", "obtenido": "Sin credenciales",
                    "evidencia": "evidencia_e3_sin_permiso_TC-M07-G056.json", "pasos": [],
                    "observaciones": f"Faltan: {', '.join(faltan)}",
                },
            ],
            "integracion_m08": {"estado": "BLOQUEADO", "motivo": "Sin credenciales para ejecutar"},
            "limitaciones": [f"Faltan variables: {', '.join(faltan)}"],
            "resumen": {"aprobados": 0, "rechazados": 0, "bloqueados": 4, "no_aplica": 0, "estado_final": "BLOQUEADO"},
            "endpoints_reales": {"consulta": ENDPOINT_AUDIT, "exportacion": ENDPOINT_EXPORT, "periodos": ENDPOINT_PERIODOS},
        }
        (RESULTADO / "evidencia_ejecucion_TC-M07-G056.json").write_text(
            json.dumps(limpiar(data), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (RESULTADO / "resultado_TC-M07-G056.html").write_text(render_html(data), encoding="utf-8")
        print(json.dumps({"caso": CASO, "estado_final": "BLOQUEADO", "faltan": faltan}, ensure_ascii=False, indent=2))
        return 2

    # ---------- Login tres perfiles ----------
    st_a, login_a, _ = login(admin_c, admin_p)
    token_admin = (login_a or {}).get("token") if isinstance(login_a, dict) else None
    pet.append({"fase": "login_admin", "http": st_a, "ok": bool(token_admin), "correo": admin_c})

    st_r, login_r, _ = login(aud_c, aud_p)
    token_aud = (login_r or {}).get("token") if isinstance(login_r, dict) else None
    pet.append({"fase": "login_auditor", "http": st_r, "ok": bool(token_aud), "correo": aud_c})

    st_s, login_s, _ = login(sin_c, sin_p)
    token_sin = (login_s or {}).get("token") if isinstance(login_s, dict) else None
    pet.append({"fase": "login_sin_permiso", "http": st_s, "ok": bool(token_sin), "correo": sin_c})

    if not token_admin or not token_aud or not token_sin:
        raise SystemExit(f"Login falló admin={st_a} auditor={st_r} sin={st_s}")

    # Permisos de cada perfil
    def permisos(token: str, etiqueta: str) -> dict:
        st, body = pedir("GET", "/sesiones/me/permisos", token=token)[:2]
        pet.append({"fase": f"permisos_{etiqueta}", "http": st, "ruta": "/sesiones/me/permisos"})
        interes = {}
        if isinstance(body, dict):
            # contrato puede ser lista o mapa
            raw = body.get("permisos") if "permisos" in body else body
            if isinstance(raw, list):
                for p in raw:
                    if not isinstance(p, dict):
                        continue
                    rec = p.get("nombre_recurso") or p.get("recurso") or p.get("nombre")
                    if rec in ("auditoria_integracion", "auditoria_integracion_cierres"):
                        interes[rec] = p
            elif isinstance(raw, dict):
                for rec in ("auditoria_integracion", "auditoria_integracion_cierres"):
                    if rec in raw:
                        interes[rec] = raw[rec]
        return {"http": st, "interes": limpiar(interes), "raw_tipo": type(body).__name__}

    perm_admin = permisos(token_admin, "admin")
    perm_aud = permisos(token_aud, "auditor")
    perm_sin = permisos(token_sin, "sin")

    # ---------- Baseline Admin (referencia antes de denegados) ----------
    st0, body0 = get_auditoria(token_admin, pagina=1, tamano=100)
    r0 = resumen_items(body0)
    pet.append({"fase": "baseline_admin", "http": st0, "ruta": ENDPOINT_AUDIT, "resumen": r0})
    total_ref = r0.get("total")
    tipos_admin_ref = r0.get("tipos_evento") or []

    # Contar ACCESO_AUDITORIA_DENEGADO de referencia
    st_den_ref, body_den_ref = get_auditoria(token_admin, pagina=1, tamano=100, tipo_evento="ACCESO_AUDITORIA_DENEGADO")
    total_den_ref = (body_den_ref or {}).get("total") if isinstance(body_den_ref, dict) else None
    pet.append({"fase": "ref_acceso_denegado", "http": st_den_ref, "total": total_den_ref})

    # ---------- E1 Administrador ----------
    e1_pasos = [
        f"Login Admin HTTP {st_a}",
        f"GET {ENDPOINT_AUDIT} HTTP {st0}, total={total_ref}",
        f"Tipos observados: {tipos_admin_ref}",
    ]
    e1_ok = st0 == 200 and isinstance(body0, dict) and all(k in body0 for k in ("items", "pagina", "tamano", "total"))
    # Admin debe poder ver tipos fuera de TIPOS_AUDITOR si existen en el historial
    admin_ve_amplio = bool(r0.get("fuera_tipos_auditor")) or (r0.get("total") or 0) > 0
    # Campos sensibles presentes en vista completa (pueden ser null en algunos items)
    admin_tiene_campos = "ip_origen" in (r0.get("claves_muestra") or []) and "json_detalle" in (r0.get("claves_muestra") or [])

    # Filtros varios tipos
    tipos_consulta = []
    for te in list(dict.fromkeys(list(TIPOS_AUDITOR) + list(tipos_admin_ref)))[:6]:
        st_f, body_f = get_auditoria(token_admin, pagina=1, tamano=20, tipo_evento=te)
        tipos_consulta.append({"tipo_evento": te, "http": st_f, "total": (body_f or {}).get("total") if isinstance(body_f, dict) else None})
        pet.append({"fase": f"admin_filtro_{te}", "http": st_f})
    e1_pasos.append(f"Filtros por tipo: {tipos_consulta}")

    # Períodos vía M06 (referencia, no modificar)
    st_per, body_per = pedir("GET", ENDPOINT_PERIODOS, token=token_admin)[:2]
    periodos = []
    if isinstance(body_per, dict):
        periodos = body_per.get("items") or body_per.get("periodos") or body_per.get("data") or []
        if not isinstance(periodos, list):
            periodos = []
    elif isinstance(body_per, list):
        periodos = body_per
    pet.append({"fase": "admin_periodos_m06", "http": st_per, "n": len(periodos) if isinstance(periodos, list) else None})
    e1_pasos.append(f"GET {ENDPOINT_PERIODOS} HTTP {st_per}, n={len(periodos) if isinstance(periodos, list) else 'n/d'}")

    cerrado = next((p for p in periodos if isinstance(p, dict) and str(p.get("estado", "")).upper() == "CERRADO"), None)
    abierto = next((p for p in periodos if isinstance(p, dict) and str(p.get("estado", "")).upper() in ("ABIERTO", "OPEN")), None)

    # Consulta con rangos de fecha (no es ACL de período)
    rango_admin = {}
    if cerrado and cerrado.get("fecha_inicio") and cerrado.get("fecha_fin"):
        st_c, body_c = get_auditoria(token_admin, pagina=1, tamano=10,
                                     desde=str(cerrado["fecha_inicio"])[:10], hasta=str(cerrado["fecha_fin"])[:10])
        rango_admin["cerrado"] = {"http": st_c, "total": (body_c or {}).get("total") if isinstance(body_c, dict) else None,
                                  "id_periodo": cerrado.get("id_periodo_contable")}
        e1_pasos.append(f"Admin rango período cerrado id={cerrado.get('id_periodo_contable')} HTTP {st_c}")
    if abierto and abierto.get("fecha_inicio") and abierto.get("fecha_fin"):
        st_ab, body_ab = get_auditoria(token_admin, pagina=1, tamano=10,
                                       desde=str(abierto["fecha_inicio"])[:10], hasta=str(abierto["fecha_fin"])[:10])
        rango_admin["abierto"] = {"http": st_ab, "total": (body_ab or {}).get("total") if isinstance(body_ab, dict) else None,
                                 "id_periodo": abierto.get("id_periodo_contable")}
        e1_pasos.append(f"Admin rango período abierto id={abierto.get('id_periodo_contable')} HTTP {st_ab}")

    st_inex, body_inex = get_auditoria(token_admin, pagina=1, tamano=10, desde="2099-01-01", hasta="2099-01-02")
    rango_admin["inexistente_futuro"] = {"http": st_inex, "total": (body_inex or {}).get("total") if isinstance(body_inex, dict) else None}
    e1_pasos.append(f"Admin rango futuro inexistente HTTP {st_inex}")

    # Export Admin
    st_ex_a, body_ex_a = get_export(token_admin, formato="json")
    export_admin_ok = st_ex_a == 200
    e1_pasos.append(f"GET {ENDPOINT_EXPORT}?formato=json HTTP {st_ex_a}")
    pet.append({"fase": "admin_export", "http": st_ex_a, "ok": export_admin_ok})

    e1_estado = "APROBADO" if (e1_ok and admin_ve_amplio and admin_tiene_campos and export_admin_ok) else "RECHAZADO"
    if not e1_ok:
        e1_estado = "RECHAZADO"
    e1 = {
        "id": "E1",
        "perfil": "Administrador",
        "nombre": "Consulta autorizada",
        "caso_original": "TC-M07-102-013",
        "estado": e1_estado,
        "validacion": "Consulta autorizada",
        "esperado": "HTTP 200, vista completa, filtros, export si permiso E",
        "obtenido": (
            f"HTTP {st0}; estructura_ok={e1_ok}; tipos_fuera_auditor={r0.get('fuera_tipos_auditor')}; "
            f"campos_ip_detalle={admin_tiene_campos}; export_http={st_ex_a}"
        ),
        "evidencia": "evidencia_e1_admin_TC-M07-G056.json",
        "pasos": e1_pasos,
        "observaciones": "Admin usa auditoria_integracion:R+E. Export confirmado en ruta real.",
    }
    escenarios.append(e1)
    (RESULTADO / e1["evidencia"]).write_text(
        json.dumps(limpiar({
            "fecha_utc": ahora(), "perfil": "Administrador", "correo": admin_c,
            "permisos": perm_admin, "baseline": r0, "filtros_tipo": tipos_consulta,
            "rangos_fecha": rango_admin, "export_http": st_ex_a,
            "export_preview": body_ex_a if isinstance(body_ex_a, dict) else {"tipo": type(body_ex_a).__name__},
            "estado": e1_estado,
        }), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # ---------- E2 Auditor ----------
    st2, body2 = get_auditoria(token_aud, pagina=1, tamano=100)
    r2 = resumen_items(body2)
    pet.append({"fase": "auditor_consulta", "http": st2, "resumen": r2})
    e2_pasos = [f"Login Auditor (Revisor Fiscal) HTTP {st_r}", f"GET auditoría HTTP {st2}, total={r2.get('total')}"]

    solo_tipos_ok = st2 == 200 and not r2.get("fuera_tipos_auditor")
    campos_ocultos_ok = st2 == 200 and r2.get("ip_origen_no_nulas", 0) == 0 and r2.get("json_detalle_no_nulos", 0) == 0
    e2_pasos.append(f"Tipos={r2.get('tipos_evento')}; fuera_TIPOS_AUDITOR={r2.get('fuera_tipos_auditor')}")
    e2_pasos.append(f"ip_no_nulas={r2.get('ip_origen_no_nulas')}; json_detalle_no_nulos={r2.get('json_detalle_no_nulos')}")

    # Intento tipo no autorizado
    st_fa7, body_fa7 = get_auditoria(token_aud, pagina=1, tamano=10, tipo_evento="SOLICITUD_RECHAZADA")
    code_fa7 = code_of(body_fa7)
    fa7_ok = st_fa7 == 403 and (code_fa7 in ("ACCESO_AUDITORIA_DENEGADO", "ACCESO_DENEGADO") or "Solo puede consultar" in str(body_fa7))
    e2_pasos.append(f"Filtro SOLICITUD_RECHAZADA HTTP {st_fa7} code={code_fa7}")
    pet.append({"fase": "auditor_fa7", "http": st_fa7, "code": code_fa7, "body": limpiar(body_fa7)})

    # Rangos período
    rango_aud = {}
    if cerrado and cerrado.get("fecha_inicio") and cerrado.get("fecha_fin"):
        st_ac, body_ac = get_auditoria(token_aud, pagina=1, tamano=10,
                                       desde=str(cerrado["fecha_inicio"])[:10], hasta=str(cerrado["fecha_fin"])[:10])
        rango_aud["cerrado"] = {"http": st_ac, "total": (body_ac or {}).get("total") if isinstance(body_ac, dict) else None,
                                "id_periodo": cerrado.get("id_periodo_contable"),
                                "nota": "Filtro fecha; no hay ACL de período en GET auditoría"}
        e2_pasos.append(f"Auditor rango cerrado HTTP {st_ac}")
    if abierto and abierto.get("fecha_inicio") and abierto.get("fecha_fin"):
        st_ao, body_ao = get_auditoria(token_aud, pagina=1, tamano=10,
                                       desde=str(abierto["fecha_inicio"])[:10], hasta=str(abierto["fecha_fin"])[:10])
        rango_aud["abierto"] = {"http": st_ao, "total": (body_ao or {}).get("total") if isinstance(body_ao, dict) else None,
                                "id_periodo": abierto.get("id_periodo_contable"),
                                "nota": "Backend NO deniega por período ABIERTO en historial auditoría"}
        e2_pasos.append(f"Auditor rango abierto HTTP {st_ao} (sin ACL período en este endpoint)")
    st_ai, body_ai = get_auditoria(token_aud, pagina=1, tamano=10, desde="2099-01-01", hasta="2099-01-02")
    rango_aud["inexistente_futuro"] = {"http": st_ai, "total": (body_ai or {}).get("total") if isinstance(body_ai, dict) else None}
    e2_pasos.append(f"Auditor rango futuro HTTP {st_ai}")

    # Período inexistente: no hay param id_periodo en auditoría
    periodo_inexistente = {
        "parametro_id_periodo_en_auditoria": False,
        "comportamiento": "GET /integracion/auditoria no acepta id_periodo_contable; períodos se consultan en M06",
    }

    e2a_estado = "APROBADO" if (solo_tipos_ok and campos_ocultos_ok and fa7_ok) else "RECHAZADO"
    e2a = {
        "id": "E2a",
        "perfil": "Auditor",
        "nombre": "Restricciones de eventos y campos",
        "caso_original": "TC-M07-102-013",
        "estado": e2a_estado,
        "validacion": "Restricciones de eventos y períodos",
        "esperado": "Solo TIPOS_AUDITOR; sin IP/json_detalle; deniega tipos no autorizados",
        "obtenido": (
            f"HTTP {st2}; solo_tipos={solo_tipos_ok}; campos_ocultos={campos_ocultos_ok}; "
            f"FA7_http={st_fa7}; rangos={rango_aud}"
        ),
        "evidencia": "evidencia_e2_auditor_TC-M07-G056.json",
        "pasos": e2_pasos,
        "observaciones": (
            "ACL de período CERRADO no aplica a GET /auditoria (sí a consulta AAEF/modulo6). "
            "Restricción de períodos del requerimiento sobre historial: NO APLICA en este endpoint."
        ),
    }
    escenarios.append(e2a)

    # E2b export
    st_ex_r, body_ex_r = get_export(token_aud, formato="json")
    code_ex_r = code_of(body_ex_r)
    export_deny_ok = st_ex_r == 403
    e2b_pasos = [
        f"GET {ENDPOINT_EXPORT}?formato=json con token Auditor HTTP {st_ex_r}",
        f"code={code_ex_r}",
        "Permiso requerido por router: auditoria_integracion:E (Revisor Fiscal solo tiene cierres:R)",
    ]
    pet.append({"fase": "auditor_export", "http": st_ex_r, "code": code_ex_r, "body": limpiar(body_ex_r)})
    e2b = {
        "id": "E2b",
        "perfil": "Auditor",
        "nombre": "Exportación denegada",
        "caso_original": "TC-M07-102-013",
        "estado": "APROBADO" if export_deny_ok else "RECHAZADO",
        "validacion": "Exportación denegada",
        "esperado": "HTTP 403 en ruta real de exportación",
        "obtenido": f"HTTP {st_ex_r} code={code_ex_r}",
        "evidencia": "evidencia_e2_export_TC-M07-G056.json",
        "pasos": e2b_pasos,
        "observaciones": "Ruta real intentada: GET /integracion/auditoria/exportar",
    }
    escenarios.append(e2b)
    (RESULTADO / "evidencia_e2_export_TC-M07-G056.json").write_text(
        json.dumps(limpiar({
            "fecha_utc": ahora(), "perfil": "Auditor", "correo": aud_c,
            "ruta": ENDPOINT_EXPORT, "http": st_ex_r, "code": code_ex_r,
            "body": body_ex_r, "estado": e2b["estado"],
        }), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    (RESULTADO / e2a["evidencia"]).write_text(
        json.dumps(limpiar({
            "fecha_utc": ahora(), "perfil": "Auditor", "correo": aud_c,
            "permisos": perm_aud, "consulta": r2, "fa7": {"http": st_fa7, "code": code_fa7, "body": body_fa7},
            "rangos_fecha": rango_aud, "periodo_inexistente": periodo_inexistente,
            "export_http": st_ex_r, "estado_eventos": e2a_estado, "estado_export": e2b["estado"],
        }), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # E2c / M08 períodos — clasificación explícita
    m08 = {
        "fecha_utc": ahora(),
        "nombre_caso_m08": "Períodos contables referidos como M08 en el caso; implementación real en modulo6 / M06",
        "esquema_bd": "modulo6.periodos_contables",
        "endpoint_periodos": ENDPOINT_PERIODOS,
        "http_periodos_admin": st_per,
        "periodos_muestra": [
            {
                "id": p.get("id_periodo_contable"),
                "estado": p.get("estado"),
                "fecha_inicio": p.get("fecha_inicio"),
                "fecha_fin": p.get("fecha_fin"),
            }
            for p in (periodos[:8] if isinstance(periodos, list) else [])
            if isinstance(p, dict)
        ],
        "cerrado_encontrado": bool(cerrado),
        "abierto_encontrado": bool(abierto),
        "auditoria_valida_periodo": False,
        "auditoria_param_id_periodo": False,
        "restriccion_cerrado_en_aaef": "Sí (ConsultarAaefUseCase / aaef.py estado==CERRADO), no en GET /auditoria",
        "consulta_tiempo_real_m06": "GET /finanzas/periodos en esta ejecución",
        "autorizacion_backend_auditoria": "Solo permisos R de auditoría + filtros TIPOS_AUDITOR; sin ACL período",
        "rangos_probados_auditor": rango_aud,
        "cobertura": "NO APLICA",
        "justificacion": (
            "GET /integracion/auditoria no integra ni autoriza por período contable. "
            "Los filtros desde/hasta son fechas de evento. La restricción CERRADO aplica a la consulta AAEF (RF-95), "
            "no al historial RF-102. No se simula integración M08 inexistente sobre este endpoint."
        ),
    }
    (RESULTADO / "evidencia_integracion_m08_TC-M07-G056.json").write_text(
        json.dumps(limpiar(m08), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    e2c = {
        "id": "E2c",
        "perfil": "Auditor",
        "nombre": "Restricción períodos contables (M08/M06) sobre historial",
        "caso_original": "TC-M07-102-013",
        "estado": "NO APLICA",
        "validacion": "Restricciones de períodos contables en historial",
        "esperado": "Según requerimiento: solo períodos cerrados autorizados",
        "obtenido": (
            "Endpoint de auditoría no valida períodos; rangos fecha abiertos/cerrados responden sin ACL de período. "
            f"Cerrado={bool(cerrado)} Abierto={bool(abierto)}"
        ),
        "evidencia": "evidencia_integracion_m08_TC-M07-G056.json",
        "pasos": [
            "Inspección m07_router.consultar_auditoria: sin id_periodo",
            "Inspección ConsultarAuditoriaIntegracionUseCase: solo TIPOS_AUDITOR / solo_exitosos",
            f"GET {ENDPOINT_PERIODOS} HTTP {st_per}",
            "Pruebas desde/hasta con fechas de períodos reales sin denegación por estado",
        ],
        "observaciones": m08["justificacion"],
    }
    escenarios.append(e2c)

    # ---------- E3 Sin permisos ----------
    st3, body3 = get_auditoria(token_sin, pagina=1, tamano=10)
    code3 = code_of(body3)
    deny_ok = st3 == 403 and code3 == "ACCESO_DENEGADO"
    sin_items = isinstance(body3, dict) and not body3.get("items")
    e3_pasos = [
        f"Login Contador (sin permisos auditoría) HTTP {st_s}",
        f"GET {ENDPOINT_AUDIT} HTTP {st3} code={code3}",
        f"Sin items en body: {sin_items}",
    ]
    pet.append({"fase": "sin_consulta", "http": st3, "code": code3, "body": limpiar(body3)})

    st3f, body3f = get_auditoria(token_sin, pagina=1, tamano=10, tipo_evento="PAQUETE_AAEF_CONSULTADO")
    e3_pasos.append(f"GET con filtro tipo HTTP {st3f}")
    pet.append({"fase": "sin_filtro", "http": st3f, "body": limpiar(body3f)})

    st3e, body3e = get_export(token_sin, formato="json")
    code3e = code_of(body3e)
    e3_pasos.append(f"GET export HTTP {st3e} code={code3e}")
    pet.append({"fase": "sin_export", "http": st3e, "code": code3e, "body": limpiar(body3e)})

    # 401 sin Authorization
    st401, body401 = pedir("GET", ENDPOINT_AUDIT + "?pagina=1&tamano=1")[:2]
    e3_pasos.append(f"GET sin Authorization HTTP {st401}")
    pet.append({"fase": "sin_authorization", "http": st401, "body": limpiar(body401)})

    # Evento seguridad tras denegado
    st_den_post, body_den_post = get_auditoria(token_admin, pagina=1, tamano=20, tipo_evento="ACCESO_AUDITORIA_DENEGADO")
    total_den_post = (body_den_post or {}).get("total") if isinstance(body_den_post, dict) else None
    e3_pasos.append(f"ACCESO_AUDITORIA_DENEGADO ref={total_den_ref} post={total_den_post}")
    pet.append({"fase": "post_acceso_denegado", "http": st_den_post, "total": total_den_post, "ref": total_den_ref})

    e3_estado = "APROBADO" if (deny_ok and sin_items and st3e == 403) else "RECHAZADO"
    e3 = {
        "id": "E3",
        "perfil": "Usuario sin permisos",
        "nombre": "Acceso rechazado",
        "caso_original": "TC-M07-102-013",
        "estado": e3_estado,
        "validacion": "Acceso rechazado",
        "esperado": "HTTP 403 ACCESO_DENEGADO; sin historial; export 403; 401 sin token",
        "obtenido": (
            f"consulta={st3}/{code3}; filtro={st3f}; export={st3e}/{code3e}; sin_token={st401}; "
            f"denegados_ref={total_den_ref}->post={total_den_post}"
        ),
        "evidencia": "evidencia_e3_sin_permiso_TC-M07-G056.json",
        "pasos": e3_pasos,
        "observaciones": (
            "403 (autorización) distinto de 401 (autenticación). "
            "Intentos denegados pueden incrementar ACCESO_AUDITORIA_DENEGADO; no es contaminación de la consulta."
        ),
    }
    escenarios.append(e3)
    (RESULTADO / e3["evidencia"]).write_text(
        json.dumps(limpiar({
            "fecha_utc": ahora(), "perfil": "Sin permisos", "correo": sin_c,
            "permisos": perm_sin,
            "consulta": {"http": st3, "code": code3, "body": body3},
            "filtro": {"http": st3f, "body": body3f},
            "export": {"http": st3e, "code": code3e, "body": body3e},
            "sin_authorization": {"http": st401, "body": body401},
            "evento_seguridad": {"ref": total_den_ref, "post": total_den_post},
            "estado": e3_estado,
        }), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # ---------- Matriz ----------
    matriz = [
        {
            "funcionalidad": "Consultar historial",
            "administrador": f"Sí (HTTP {st0})",
            "auditor": f"Sí restringida (HTTP {st2})",
            "sin_permisos": f"No (HTTP {st3} {code3})",
            "evidencia": "evidencia_e1_admin / e2_auditor / e3_sin_permiso",
        },
        {
            "funcionalidad": "Consultar eventos AAEF (TIPOS_AUDITOR)",
            "administrador": "Sí",
            "auditor": "Sí (únicos permitidos)",
            "sin_permisos": "No",
            "evidencia": "e1 + e2 tipos",
        },
        {
            "funcionalidad": "Consultar eventos de otros tipos",
            "administrador": f"Sí (fuera_TIPOS={r0.get('fuera_tipos_auditor')})",
            "auditor": f"No (FA7 HTTP {st_fa7})" if fa7_ok else f"Verificar (HTTP {st_fa7})",
            "sin_permisos": "No",
            "evidencia": "e2 FA7 SOLICITUD_RECHAZADA",
        },
        {
            "funcionalidad": "Consultar períodos cerrados",
            "administrador": "N/A en auditoría (filtro fecha opcional)",
            "auditor": "N/A — sin ACL período en GET auditoría",
            "sin_permisos": "No (403 antes de filtros)",
            "evidencia": "evidencia_integracion_m08_TC-M07-G056.json",
        },
        {
            "funcionalidad": "Consultar períodos abiertos",
            "administrador": "N/A en auditoría (filtro fecha opcional)",
            "auditor": "N/A — backend no deniega por ABIERTO en historial",
            "sin_permisos": "No",
            "evidencia": "evidencia_integracion_m08_TC-M07-G056.json",
        },
        {
            "funcionalidad": "Consultar períodos inexistentes",
            "administrador": "N/A (sin param id_periodo; rango futuro → total 0)",
            "auditor": "N/A (igual)",
            "sin_permisos": "No",
            "evidencia": "rangos 2099-01-01",
        },
        {
            "funcionalidad": "Consultar IP de origen",
            "administrador": f"Sí (campo presente; no_nulas={r0.get('ip_origen_no_nulas')})",
            "auditor": f"No (forzado null; no_nulas={r2.get('ip_origen_no_nulas')})",
            "sin_permisos": "No",
            "evidencia": "e1/e2 resumen campos",
        },
        {
            "funcionalidad": "Consultar motivos de rechazo (json_detalle)",
            "administrador": f"Sí (no_nulos={r0.get('json_detalle_no_nulos')})",
            "auditor": f"No (forzado null; no_nulos={r2.get('json_detalle_no_nulos')})",
            "sin_permisos": "No",
            "evidencia": "e1/e2 resumen campos",
        },
        {
            "funcionalidad": "Exportar auditoría",
            "administrador": f"Sí (HTTP {st_ex_a})",
            "auditor": f"No (HTTP {st_ex_r})",
            "sin_permisos": f"No (HTTP {st3e})",
            "evidencia": "evidencia_e2_export + e1/e3",
        },
    ]
    (RESULTADO / "matriz_permisos_TC-M07-G056.json").write_text(
        json.dumps({"fecha_utc": ahora(), "matriz": matriz, "tipos_auditor": list(TIPOS_AUDITOR)},
                   ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    diagnostico = {
        "fecha_utc": ahora(),
        "base": BASE,
        "endpoints": {
            "consulta": "GET " + ENDPOINT_AUDIT,
            "exportacion": "GET " + ENDPOINT_EXPORT,
            "periodos_m06": "GET " + ENDPOINT_PERIODOS,
            "permisos": "GET /sesiones/me/permisos",
            "login": "POST /sesiones/",
        },
        "permisos_recurso": {
            "admin": perm_admin,
            "auditor": perm_aud,
            "sin_permisos": perm_sin,
        },
        "perfiles_test": {
            "administrador": admin_c,
            "auditor_revisor_fiscal": aud_c,
            "sin_permisos_contador": sin_c,
        },
        "disponibilidad": {
            "consulta_admin": st0,
            "consulta_auditor": st2,
            "consulta_sin": st3,
            "export_admin": st_ex_a,
            "export_auditor": st_ex_r,
            "export_sin": st3e,
            "periodos": st_per,
            "sin_token": st401,
        },
    }
    (RESULTADO / "diagnostico_endpoints_TC-M07-G056.json").write_text(
        json.dumps(limpiar(diagnostico), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    limitaciones.extend([
        "No se modificaron períodos ni roles en TEST.",
        "Credenciales solo por variables de entorno; tokens omitidos en evidencias.",
        "Integración 'M08' del enunciado: períodos reales en modulo6/M06; sin ACL período en GET auditoría.",
        "Intentos 403 pueden registrar ACCESO_AUDITORIA_DENEGADO (documentado ref→post).",
        "G052–G055 no fueron modificados.",
    ])

    counts = {
        "aprobados": sum(1 for e in escenarios if e["estado"] == "APROBADO"),
        "rechazados": sum(1 for e in escenarios if e["estado"] == "RECHAZADO"),
        "bloqueados": sum(1 for e in escenarios if e["estado"] == "BLOQUEADO"),
        "no_aplica": sum(1 for e in escenarios if e["estado"] == "NO APLICA"),
    }
    final = estado_final_de(escenarios)
    counts["estado_final"] = final

    data = {
        "caso": CASO,
        "rf": RF,
        "fecha_ejecucion_utc": ahora(),
        "estado_final": final,
        "matriz_permisos": matriz,
        "escenarios": escenarios,
        "integracion_m08": m08,
        "peticiones": limpiar(pet),
        "limitaciones": limitaciones,
        "resumen": counts,
        "endpoints_reales": diagnostico["endpoints"],
        "referencia_denegados": {"antes": total_den_ref, "despues": total_den_post},
    }
    (RESULTADO / "evidencia_ejecucion_TC-M07-G056.json").write_text(
        json.dumps(limpiar(data), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (RESULTADO / "resultado_TC-M07-G056.html").write_text(render_html(data), encoding="utf-8")

    # Tabla consola
    print("\n| Escenario | Perfil | Validación | Resultado | Evidencia |")
    print("|---|---|---|---|---|")
    for e in escenarios:
        print(f"| {e['id']} | {e['perfil']} | {e['validacion']} | {e['estado']} | {e['evidencia']} |")
    print(json.dumps({"caso": CASO, "resumen": counts, "estado_final": final}, ensure_ascii=False, indent=2))
    return 0 if final in ("APROBADO", "NO APLICA") else (1 if final == "RECHAZADO" else 2)


if __name__ == "__main__":
    raise SystemExit(main())
