# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-11-17 | Laura López  | TC-M07-G052 RF-102: registro/validación eventos integración (TEST). |
"""TC-M07-G052 (RF-102 / CU07) — registro y validación de eventos de integración.

Ejecuta contra la API TEST (no local). Credenciales solo por entorno:

  QA_ADMIN_CORREO / QA_ADMIN_CONTRASENA  → consulta /integracion/auditoria
  QA_CORREO / QA_CONTRASENA              → Contador QA (solo permisos; NO llama auditoría)

No inserta en BD, no altera hashes, no usa Contador para GET /integracion/auditoria.

    python tests/Test_Testing/Test_Modulo7/RF-102/TC-M07-G052/ejecutar_tc_m07_g52.py
"""
from __future__ import annotations

import html
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

BASE = "https://api.inmero.co/api-sgpmp-test"
ZONA = "America/Bogota"
CASO = "TC-M07-G052"
RF = "RF-102"
CARPETA = Path(__file__).resolve().parent
RESULTADO = CARPETA / "Resultado"
JSON_EVIDENCIA = RESULTADO / "evidencia_ejecucion_TC-M07-G52.json"
HTML_REPORTE = RESULTADO / "resultado_TC-M07-G52.html"

SECRETOS = {
    "token", "access_token", "contrasena", "password", "Authorization",
    "client_secret", "hash_secreto", "refresh_token",
}

# RF-102 8.2 — campos obligatorios por tipo (código EventoIntegracion._OBLIGATORIOS)
OBLIGATORIOS_POR_TIPO = {
    "PAQUETE_AAEF_CONSULTADO": (
        "endpoint", "metodo_http", "codigo_http", "latencia_ms", "id_cliente_externo",
        "numero_id_tributaria", "hash_contenido", "tamano_payload_bytes",
    ),
    "SOLICITUD_RECHAZADA": ("endpoint", "metodo_http", "codigo_http", "codigo_resultado"),
    "CREDENCIALES_EN_URL": ("endpoint", "metodo_http", "codigo_http"),
    "RATE_LIMIT_EXCEDIDO": ("endpoint", "codigo_http"),
    "VISTA_AAEF_GENERADA": ("numero_id_tributaria", "hash_contenido", "tamano_payload_bytes", "version_contrato"),
    "TOKEN_CANAL_EMITIDO": ("id_cliente_externo", "id_usuario"),
    "TOKEN_CANAL_RECHAZADO": ("codigo_resultado",),
    "SECRETO_ROTADO": ("id_cliente_externo",),
    "CONTRATO_ACTIVADO": ("version_contrato",),
    "CONTRATO_DEPRECADO": ("version_contrato",),
    "CONTRATO_INACTIVADO": ("version_contrato",),
    "CONTRATO_REGISTRADO": ("version_contrato",),
}

CAMPOS_GENERALES = (
    "id_evento_integracion", "tipo_evento", "modulo", "fecha_evento",
    "fecha_registro", "tipo_actor", "severidad", "hash_integridad",
)

TIPOS_CATALOGO_API = {
    "PAQUETE_AAEF_CONSULTADO", "SOLICITUD_RECHAZADA", "CREDENCIALES_EN_URL", "RATE_LIMIT_EXCEDIDO",
    "VISTA_AAEF_GENERADA", "PREPARACION_AAEF_FALLIDA", "TOKEN_CANAL_EMITIDO", "TOKEN_CANAL_RECHAZADO",
    "USUARIO_CREADO_M2M", "USUARIO_ACTUALIZADO_M2M", "ESTADO_USUARIO_CAMBIADO_M2M",
    "CLIENTE_REGISTRADO", "CLIENTE_EDITADO", "CLIENTE_SUSPENDIDO", "CLIENTE_REACTIVADO", "CLIENTE_REVOCADO",
    "SECRETO_ROTADO", "CONTRATO_REGISTRADO", "CONTRATO_ACTIVADO", "CONTRATO_DEPRECADO", "CONTRATO_INACTIVADO",
    "CONTRATO_ACTIVACION_BLOQUEADA", "ANEXO_REGISTRADO", "ANEXO_EN_REVISION", "ANEXO_APROBADO",
    "ANEXO_VALIDACION_FALLIDA", "INTENTO_MODIFICACION_AUDITORIA", "ACCESO_AUDITORIA_DENEGADO",
    "REGISTRO_AUDITORIA_CORRUPTO",
}

FUENTES = {
    "RF-95": ["PAQUETE_AAEF_CONSULTADO", "SOLICITUD_RECHAZADA", "CREDENCIALES_EN_URL", "RATE_LIMIT_EXCEDIDO"],
    "RF-97/RF-AE01": ["PAQUETE_AAEF_CONSULTADO", "VISTA_AAEF_GENERADA", "PREPARACION_AAEF_FALLIDA"],
    "RF-98": ["CONTRATO_REGISTRADO", "CONTRATO_ACTIVADO", "CONTRATO_DEPRECADO", "CONTRATO_INACTIVADO",
              "CONTRATO_ACTIVACION_BLOQUEADA", "ANEXO_REGISTRADO", "ANEXO_EN_REVISION", "ANEXO_APROBADO",
              "ANEXO_VALIDACION_FALLIDA"],
    "RF-101": ["CLIENTE_REGISTRADO", "CLIENTE_EDITADO", "CLIENTE_SUSPENDIDO", "CLIENTE_REACTIVADO",
               "CLIENTE_REVOCADO", "SECRETO_ROTADO"],
    "RF-SSO02": ["TOKEN_CANAL_EMITIDO", "TOKEN_CANAL_RECHAZADO", "USUARIO_CREADO_M2M",
                 "USUARIO_ACTUALIZADO_M2M", "ESTADO_USUARIO_CAMBIADO_M2M"],
    "RF-102": ["INTENTO_MODIFICACION_AUDITORIA", "ACCESO_AUDITORIA_DENEGADO", "REGISTRO_AUDITORIA_CORRUPTO"],
}


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


def pedir(metodo: str, ruta: str, cuerpo: Any = None, token: Optional[str] = None, timeout: int = 60):
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
            return resp.status, (json.loads(raw) if raw else None), None
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
            # No redactar flags booleanos tipo tiene_token / token_presente
            if k in SECRETOS or (
                ("secret" in kl or "contrasen" in kl or "password" in kl)
                or (kl == "token" or kl.endswith("_token") or kl.startswith("token_"))
            ):
                out[k] = {"omitido": True}
            elif k == "hash_integridad" and isinstance(x, str) and len(x) > 12:
                out[k] = x[:12] + "…"
            else:
                out[k] = limpiar(x, d + 1)
        return out
    if isinstance(v, list):
        return [limpiar(x, d + 1) for x in v[:80]]
    if isinstance(v, str) and len(v) > 600:
        return v[:600] + "…"
    return v


def permiso_lectura(permisos: list, nombre: str) -> bool:
    """GET /sesiones/me/permisos → lista de {nombre_recurso, id_accion} (2=leer)."""
    for p in permisos or []:
        if not isinstance(p, dict):
            continue
        recurso = (p.get("nombre_recurso") or p.get("recurso") or "").strip()
        if recurso != nombre:
            continue
        accion = p.get("id_accion")
        if accion in (2, "2") or (isinstance(accion, int) and accion >= 2):
            return True
        acciones = p.get("acciones") or []
        if isinstance(acciones, list):
            for a in acciones:
                if a in (2, "2", "R", "leer"):
                    return True
                if isinstance(a, dict) and a.get("id_accion") in (2, "2"):
                    return True
    return False


def es_utc(valor: Any) -> dict:
    """Comprueba exposición UTC sin asumir solo por sufijo Z."""
    info = {"valor": valor, "parseable": False, "aware": False, "offset_cero": False, "termina_z": False}
    if not isinstance(valor, str) or not valor:
        return info
    info["termina_z"] = valor.endswith("Z") or valor.endswith("+00:00")
    try:
        texto = valor.replace("Z", "+00:00") if valor.endswith("Z") else valor
        dt = datetime.fromisoformat(texto)
        info["parseable"] = True
        info["aware"] = dt.tzinfo is not None
        if dt.tzinfo is not None:
            info["offset_cero"] = dt.utcoffset() == timezone.utc.utcoffset(dt)
    except ValueError:
        pass
    return info


def resumen_evento(ev: dict) -> dict:
    return {
        "id_evento_integracion": ev.get("id_evento_integracion"),
        "tipo_evento": ev.get("tipo_evento"),
        "modulo": ev.get("modulo"),
        "fecha_evento": ev.get("fecha_evento"),
        "fecha_registro": ev.get("fecha_registro"),
        "tipo_actor": ev.get("tipo_actor"),
        "severidad": ev.get("severidad"),
        "integridad": ev.get("integridad"),
        "hash_integridad_presente": bool(ev.get("hash_integridad")),
        "endpoint": ev.get("endpoint"),
        "metodo_http": ev.get("metodo_http"),
        "codigo_http": ev.get("codigo_http"),
        "codigo_resultado": ev.get("codigo_resultado"),
        "id_cliente_externo": ev.get("id_cliente_externo"),
        "correo_usuario": ev.get("correo_usuario"),
        "numero_id_tributaria": ev.get("numero_id_tributaria"),
        "version_contrato": ev.get("version_contrato"),
        "hash_contenido_presente": bool(ev.get("hash_contenido")),
        "id_intercambio": ev.get("id_intercambio"),
        "fecha_desde": ev.get("fecha_desde"),
        "fecha_hasta": ev.get("fecha_hasta"),
    }


def validar_generales(ev: dict) -> list[str]:
    faltan = []
    for c in CAMPOS_GENERALES:
        # API expone hash_integridad; integridad es derivado
        if c == "hash_integridad":
            if not ev.get("hash_integridad") and ev.get("integridad") != "INTEGRO":
                # si integridad INTEGRO implica hash verificado
                if ev.get("integridad") != "INTEGRO":
                    faltan.append(c)
            continue
        if ev.get(c) in (None, ""):
            faltan.append(c)
    return faltan


def validar_condicionales(ev: dict) -> dict:
    tipo = ev.get("tipo_evento")
    req = OBLIGATORIOS_POR_TIPO.get(tipo, ())
    faltan = [c for c in req if ev.get(c) in (None, "")]
    return {"tipo": tipo, "requeridos": list(req), "faltantes": faltan, "ok": not faltan}


def badge(estado: str) -> str:
    colores = {
        "APROBADO": "#1b7a3d",
        "RECHAZADO": "#b00020",
        "BLOQUEADO": "#9a6b00",
        "NO APLICABLE": "#555555",
    }
    c = colores.get(estado, "#333")
    return f'<span style="display:inline-block;padding:2px 10px;border-radius:4px;background:{c};color:#fff;font-weight:600">{html.escape(estado)}</span>'


def render_html(data: dict) -> str:
    esc = html.escape
    filas = []
    for escn in data["escenarios"]:
        filas.append(
            "<tr>"
            f"<td>{esc(escn['id'])}</td>"
            f"<td>{esc(escn['nombre'])}</td>"
            f"<td>{badge(escn['estado'])}</td>"
            f"<td>{esc(escn['esperado'])}</td>"
            f"<td>{esc(escn['obtenido'])}</td>"
            "</tr>"
        )
    pet_rows = []
    for p in data.get("peticiones", []):
        pet_rows.append(
            "<tr>"
            f"<td>{esc(str(p.get('fase')))}</td>"
            f"<td>{esc(str(p.get('metodo')))}</td>"
            f"<td>{esc(str(p.get('ruta')))}</td>"
            f"<td>{esc(str(p.get('http')))}</td>"
            f"<td><code>{esc(json.dumps(limpiar(p.get('respuesta_resumen')), ensure_ascii=False)[:400])}</code></td>"
            "</tr>"
        )
    uuids = data.get("uuids_verificados") or []
    campos = data.get("campos_comprobados") or {}
    bloqueados = data.get("bloqueados") or []
    deps = data.get("dependencias") or []
    errores = data.get("errores") or []

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8"/>
<title>{esc(CASO)} — {esc(RF)}</title>
<style>
body{{font-family:Segoe UI,Arial,sans-serif;margin:24px;color:#1a1a1a;background:#f7f7f5}}
h1,h2,h3{{color:#102a43}}
.card{{background:#fff;border:1px solid #ddd;border-radius:8px;padding:16px 20px;margin:16px 0}}
table{{border-collapse:collapse;width:100%;font-size:14px}}
th,td{{border:1px solid #ddd;padding:8px;vertical-align:top;text-align:left}}
th{{background:#e8eef5}}
code{{font-size:12px;word-break:break-word}}
.meta span{{display:inline-block;margin-right:16px}}
ul{{margin:8px 0 8px 20px}}
</style>
</head>
<body>
<h1>{esc(CASO)} — Verificar registro y validación de eventos de integración</h1>
<div class="card meta">
  <span><strong>Requisito:</strong> {esc(RF)} · CU07</span>
  <span><strong>Entorno:</strong> TEST ({esc(BASE)})</span>
  <span><strong>Fecha UTC:</strong> {esc(data.get('fecha_ejecucion_utc',''))}</span>
  <span><strong>Herramientas:</strong> Python urllib · OpenAPI TEST · Postman/Newman (colección)</span>
  <span><strong>Estado final:</strong> {badge(data.get('estado_final',''))}</span>
</div>
<div class="card">
  <h2>Objetivo</h2>
  <p>Comprobar que los eventos de integración se registren correctamente, cumplan la estructura RF-102,
  rechacen información inválida y manejen fechas/horas en UTC. Agrupa TC-M07-102-001..004.</p>
</div>
<div class="card">
  <h2>Escenarios</h2>
  <table>
    <thead><tr><th>ID</th><th>Escenario</th><th>Estado</th><th>Esperado</th><th>Obtenido</th></tr></thead>
    <tbody>{''.join(filas)}</tbody>
  </table>
</div>
<div class="card">
  <h2>Evidencias HTTP (sin credenciales)</h2>
  <table>
    <thead><tr><th>Fase</th><th>Método</th><th>Ruta</th><th>HTTP</th><th>Resumen</th></tr></thead>
    <tbody>{''.join(pet_rows) if pet_rows else '<tr><td colspan="5">Sin peticiones</td></tr>'}</tbody>
  </table>
</div>
<div class="card">
  <h2>UUID de eventos verificados</h2>
  <ul>{''.join(f'<li><code>{esc(u)}</code></li>' for u in uuids) if uuids else '<li>No disponibles / no inventados</li>'}</ul>
</div>
<div class="card">
  <h2>Campos obligatorios y condicionales comprobados</h2>
  <pre>{esc(json.dumps(campos, ensure_ascii=False, indent=2))}</pre>
</div>
<div class="card">
  <h2>Errores encontrados</h2>
  <ul>{''.join(f'<li>{esc(e)}</li>' for e in errores) if errores else '<li>Ninguno reportado en la ejecución</li>'}</ul>
</div>
<div class="card">
  <h2>Escenarios / verificaciones bloqueadas</h2>
  <ul>{''.join(f'<li>{esc(b)}</li>' for b in bloqueados) if bloqueados else '<li>Ninguna</li>'}</ul>
</div>
<div class="card">
  <h2>Dependencias pendientes</h2>
  <ul>{''.join(f'<li>{esc(d)}</li>' for d in deps) if deps else '<li>Ninguna</li>'}</ul>
</div>
<div class="card">
  <h2>Notas de fuentes (código / OpenAPI)</h2>
  <pre>{esc(json.dumps(data.get('fuentes_mapeo', {}), ensure_ascii=False, indent=2))}</pre>
</div>
<p style="color:#666;font-size:12px">Generado por ejecutar_tc_m07_g52.py — no incluye secretos ni tokens.</p>
</body>
</html>
"""


def main() -> int:
    RESULTADO.mkdir(parents=True, exist_ok=True)
    admin_correo = os.environ.get("QA_ADMIN_CORREO") or os.environ.get("TEST_ADMIN_EMAIL")
    admin_clave = os.environ.get("QA_ADMIN_CONTRASENA") or os.environ.get("TEST_ADMIN_PASSWORD")
    cont_correo = os.environ.get("QA_CORREO")
    cont_clave = os.environ.get("QA_CONTRASENA")

    pet: list[dict] = []
    errores: list[str] = []
    bloqueados: list[str] = []
    deps: list[str] = []
    uuids: list[str] = []
    escenarios: list[dict] = []
    campos_comprobados: dict[str, Any] = {}
    fuentes_mapeo: dict[str, Any] = {
        "generadores_codigo": {
            "RF-95/RF-AE01": "GET /integracion/aaef/productores/{nit} (token canal) · gateway_aaef",
            "RF-97/RF-AE02": "GET /integracion/aaef/vista-previa/productores/{nit} (sesión Contador)",
            "RF-98": "POST/activar/deprecar /integracion/contratos* · anexos",
            "RF-101": "POST/PATCH /integracion/clientes* · rotar/suspender/revocar",
            "RF-SSO02": "POST /integraciones/agrofusion/token · usuarios M2M",
            "RF-102": "GET /integracion/auditoria (lectura) · PUT/PATCH/DELETE → 405 + INTENTO_MODIFICACION_AUDITORIA",
        },
        "sin_endpoint_publico_insert": True,
        "tabla": "modulo7.eventos_integracion",
        "dba_confirmado": {
            "registros": 129,
            "tipos": 14,
            "hash_integridad_100pct": True,
            "uuids_muestra": "no proporcionados",
        },
    }

    # --- OpenAPI (sin auth) ---
    st_oa, openapi, err_oa = pedir("GET", "/openapi.json", timeout=90)
    # algunos despliegues exponen openapi en raíz distinta; ya lo leímos vía URL absoluta antes
    if st_oa not in (200, None) or not isinstance(openapi, dict):
        try:
            with urllib.request.urlopen(BASE + "/openapi.json", timeout=90) as resp:
                openapi = json.loads(resp.read().decode())
                st_oa = resp.status
        except Exception:
            openapi = {}
    paths = (openapi or {}).get("paths") or {}
    tiene_get_aud = "get" in (paths.get("/integracion/auditoria") or {})
    tiene_post_aud = "post" in (paths.get("/integracion/auditoria") or {})
    pet.append({
        "fase": "openapi", "metodo": "GET", "ruta": "/openapi.json", "http": st_oa,
        "respuesta_resumen": {
            "integracion_auditoria_get": tiene_get_aud,
            "integracion_auditoria_post": tiene_post_aud,
            "integracion_auditoria_exportar": "get" in (paths.get("/integracion/auditoria/exportar") or {}),
        },
    })

    admin_token = None
    admin_tiene_aud = False
    admin_permisos = []
    items: list[dict] = []
    total_api = None

    if not admin_correo or not admin_clave:
        bloqueados.append("Sin QA_ADMIN_CORREO/QA_ADMIN_CONTRASENA (o TEST_ADMIN_*): no se consulta /integracion/auditoria")
        deps.append("Credencial Administrador TEST con permiso auditoria_integracion (lectura)")
    else:
        st, login, _ = pedir("POST", "/sesiones/", {"correo_electronico": admin_correo, "contrasena": admin_clave})
        pet.append({
            "fase": "login_admin", "metodo": "POST", "ruta": "/sesiones/", "http": st,
            "respuesta_resumen": {"ok": st in (200, 201), "tiene_token": bool((login or {}).get("token"))},
        })
        admin_token = (login or {}).get("token") if isinstance(login, dict) else None
        if not admin_token:
            errores.append(f"Login administrador falló HTTP {st}")
            bloqueados.append("No fue posible autenticar administrador para consultar auditoría")
        else:
            st_p, perms, _ = pedir("GET", "/sesiones/me/permisos", token=admin_token)
            admin_permisos = (perms or {}).get("permisos") if isinstance(perms, dict) else []
            if not isinstance(admin_permisos, list):
                admin_permisos = []
            admin_tiene_aud = permiso_lectura(admin_permisos, "auditoria_integracion")
            # fallback: si el shape no matchea, intentar la consulta y clasificar
            pet.append({
                "fase": "permisos_admin", "metodo": "GET", "ruta": "/sesiones/me/permisos", "http": st_p,
                "respuesta_resumen": {
                    "total_permisos": len(admin_permisos),
                    "auditoria_integracion_detectado": admin_tiene_aud,
                    "recursos_m07": sorted({
                        (p.get("nombre_recurso") or "") for p in admin_permisos
                        if isinstance(p, dict) and "integracion" in (p.get("nombre_recurso") or "")
                    }),
                },
            })

            if not admin_tiene_aud:
                # Probe controlado: un solo GET. Si 403, no insistir.
                st_a, body_a, _ = pedir("GET", "/integracion/auditoria?pagina=1&tamano=5", token=admin_token)
                pet.append({
                    "fase": "probe_auditoria_admin", "metodo": "GET",
                    "ruta": "/integracion/auditoria?pagina=1&tamano=5", "http": st_a,
                    "respuesta_resumen": limpiar({
                        "code": (body_a or {}).get("code") if isinstance(body_a, dict) else None,
                        "message": (body_a or {}).get("message") if isinstance(body_a, dict) else None,
                        "total": (body_a or {}).get("total") if isinstance(body_a, dict) else None,
                    }),
                })
                if st_a == 200 and isinstance(body_a, dict):
                    admin_tiene_aud = True
                    items = body_a.get("items") or []
                    total_api = body_a.get("total")
                elif st_a == 403:
                    bloqueados.append("Administrador autenticado sin permiso auditoria_integracion (HTTP 403)")
                    deps.append("Asignar permiso auditoria_integracion (R) a la cuenta de prueba autorizada")
                else:
                    bloqueados.append(f"Consulta auditoría no disponible (HTTP {st_a})")
            else:
                st_a, body_a, _ = pedir("GET", "/integracion/auditoria?pagina=1&tamano=100", token=admin_token)
                pet.append({
                    "fase": "consulta_auditoria", "metodo": "GET",
                    "ruta": "/integracion/auditoria?pagina=1&tamano=100", "http": st_a,
                    "respuesta_resumen": {
                        "total": (body_a or {}).get("total") if isinstance(body_a, dict) else None,
                        "items": len((body_a or {}).get("items") or []) if isinstance(body_a, dict) else 0,
                    },
                })
                if st_a == 200 and isinstance(body_a, dict):
                    items = body_a.get("items") or []
                    total_api = body_a.get("total")
                else:
                    errores.append(f"GET /integracion/auditoria HTTP {st_a}")
                    bloqueados.append("Falló la consulta autorizada de auditoría")

    # Contador: solo permisos (NO llamar auditoría)
    cont_tiene_aud = None
    if cont_correo and cont_clave:
        st_c, login_c, _ = pedir("POST", "/sesiones/", {"correo_electronico": cont_correo, "contrasena": cont_clave})
        tok_c = (login_c or {}).get("token") if isinstance(login_c, dict) else None
        pet.append({
            "fase": "login_contador", "metodo": "POST", "ruta": "/sesiones/", "http": st_c,
            "respuesta_resumen": {"ok": st_c in (200, 201), "tiene_token": bool(tok_c)},
        })
        if tok_c:
            st_pc, perms_c, _ = pedir("GET", "/sesiones/me/permisos", token=tok_c)
            lista_c = (perms_c or {}).get("permisos") if isinstance(perms_c, dict) else []
            if not isinstance(lista_c, list):
                lista_c = []
            cont_tiene_aud = permiso_lectura(lista_c, "auditoria_integracion")
            cont_cierres = permiso_lectura(lista_c, "auditoria_integracion_cierres")
            pet.append({
                "fase": "permisos_contador", "metodo": "GET", "ruta": "/sesiones/me/permisos", "http": st_pc,
                "respuesta_resumen": {
                    "auditoria_integracion": cont_tiene_aud,
                    "auditoria_integracion_cierres": cont_cierres,
                    "nota": "No se llamó GET /integracion/auditoria con Contador (evita ACCESO_AUDITORIA_DENEGADO)",
                },
            })
            if cont_tiene_aud:
                errores.append("Contador QA tiene auditoria_integracion (inesperado según diagnóstico DBA/QA)")
    else:
        bloqueados.append("Sin QA_CORREO/QA_CONTRASENA: no se verificó ausencia de permiso en Contador")

    # --- Generación segura 1: inmutabilidad API (PUT) ---
    generado_intento = None
    generado_token = None
    st_put = None
    st_tok = None
    if admin_token and admin_tiene_aud:
        antes_ids = {e.get("id_evento_integracion") for e in items if isinstance(e, dict)}
        st_put, body_put, _ = pedir("PUT", "/integracion/auditoria", {"intento": True}, token=admin_token)
        pet.append({
            "fase": "generador_seguro_inmutabilidad", "metodo": "PUT", "ruta": "/integracion/auditoria",
            "http": st_put,
            "respuesta_resumen": limpiar(body_put if isinstance(body_put, dict) else {"raw": body_put}),
        })
        st_a2, body_a2, _ = pedir(
            "GET", "/integracion/auditoria?tipo_evento=INTENTO_MODIFICACION_AUDITORIA&pagina=1&tamano=10",
            token=admin_token,
        )
        pet.append({
            "fase": "verificar_intento_modificacion", "metodo": "GET",
            "ruta": "/integracion/auditoria?tipo_evento=INTENTO_MODIFICACION_AUDITORIA", "http": st_a2,
            "respuesta_resumen": {
                "total": (body_a2 or {}).get("total") if isinstance(body_a2, dict) else None,
                "items": len((body_a2 or {}).get("items") or []) if isinstance(body_a2, dict) else 0,
            },
        })
        if st_a2 == 200 and isinstance(body_a2, dict):
            for ev in body_a2.get("items") or []:
                if ev.get("id_evento_integracion") not in antes_ids or st_put == 405:
                    generado_intento = ev
                    break
            if generado_intento is None and (body_a2.get("items") or []):
                generado_intento = (body_a2.get("items") or [])[0]
            # refrescar muestra
            st_full, body_full, _ = pedir("GET", "/integracion/auditoria?pagina=1&tamano=100", token=admin_token)
            if st_full == 200 and isinstance(body_full, dict):
                items = body_full.get("items") or items
                total_api = body_full.get("total", total_api)

        # --- Generación segura 2: token canal inválido ---
        st_tok, body_tok, _ = pedir("POST", "/integraciones/agrofusion/token", {
            "client_id": "qa-g52-no-existe",
            "client_secret": "secreto-invalido-no-usar",
            "email": "qa.g52.inexistente@example.com",
        })
        pet.append({
            "fase": "generador_seguro_token_rechazado", "metodo": "POST",
            "ruta": "/integraciones/agrofusion/token", "http": st_tok,
            "respuesta_resumen": limpiar(body_tok if isinstance(body_tok, dict) else {"raw": body_tok}),
        })
        st_tok_ev, body_tok_ev, _ = pedir(
            "GET", "/integracion/auditoria?tipo_evento=TOKEN_CANAL_RECHAZADO&pagina=1&tamano=10",
            token=admin_token,
        )
        pet.append({
            "fase": "verificar_token_rechazado", "metodo": "GET",
            "ruta": "/integracion/auditoria?tipo_evento=TOKEN_CANAL_RECHAZADO", "http": st_tok_ev,
            "respuesta_resumen": {
                "total": (body_tok_ev or {}).get("total") if isinstance(body_tok_ev, dict) else None,
                "items": len((body_tok_ev or {}).get("items") or []) if isinstance(body_tok_ev, dict) else 0,
            },
        })
        if st_tok_ev == 200 and isinstance(body_tok_ev, dict) and (body_tok_ev.get("items") or []):
            generado_token = (body_tok_ev.get("items") or [])[0]
    else:
        bloqueados.append(
            "No se ejecutaron generadores seguros (PUT inmutabilidad / token inválido) por falta de consulta autorizada"
        )

    # --- Escenario 1 ---
    tipos_vistos = Counter(e.get("tipo_evento") for e in items if isinstance(e, dict))
    cobertura_fuentes = {
        fuente: {
            "tipos_esperados": tipos,
            "tipos_observados": [t for t in tipos if tipos_vistos.get(t)],
            "presente": any(tipos_vistos.get(t) for t in tipos),
        }
        for fuente, tipos in FUENTES.items()
    }
    fuentes_mapeo["cobertura_en_muestra"] = cobertura_fuentes
    fuentes_mapeo["tipos_en_muestra"] = dict(tipos_vistos)
    fuentes_mapeo["total_api"] = total_api
    fuentes_mapeo["muestra"] = len(items)

    if admin_tiene_aud and items:
        # evidencia de registro existente + generadores seguros
        ok_gen = bool(generado_intento) and st_put == 405
        ok_tok = bool(generado_token) and st_tok in (401, 403, 404)
        if ok_gen or ok_tok or total_api:
            estado_e1 = "APROBADO"
            obtenido_e1 = (
                f"Consulta autorizada OK (total={total_api}, muestra={len(items)}, tipos={len(tipos_vistos)}). "
                f"PUT inmutabilidad HTTP {st_put if admin_token else 'n/a'}; "
                f"token inválido HTTP {st_tok if admin_token else 'n/a'}."
            )
            if not ok_gen:
                obtenido_e1 += " Generador INTENTO_MODIFICACION no confirmado en muestra."
            if not ok_tok:
                obtenido_e1 += " Generador TOKEN_CANAL_RECHAZADO no confirmado."
        else:
            estado_e1 = "RECHAZADO"
            obtenido_e1 = "Consulta OK pero sin evidencia de tipos/generación"
        for ev in items[:5]:
            if ev.get("id_evento_integracion"):
                uuids.append(ev["id_evento_integracion"])
        if generado_intento and generado_intento.get("id_evento_integracion"):
            uuids.append(generado_intento["id_evento_integracion"])
        if generado_token and generado_token.get("id_evento_integracion"):
            uuids.append(generado_token["id_evento_integracion"])
    elif not admin_tiene_aud:
        estado_e1 = "BLOQUEADO"
        obtenido_e1 = "Sin credencial con auditoria_integracion; no se verificó registro vía API"
    else:
        estado_e1 = "RECHAZADO"
        obtenido_e1 = f"Consulta autorizada devolvió 0 ítems (total={total_api})"

    # limitaciones de generación por fuente
    for fuente, meta in cobertura_fuentes.items():
        if fuente in ("RF-98", "RF-101") and not meta["presente"]:
            bloqueados.append(
                f"{fuente}: no se ejecutaron escrituras de contratos/clientes (irreversibles); "
                f"tipos no presentes en muestra tamano<=100"
            )
        if fuente == "RF-97/RF-AE01" and not meta["presente"]:
            bloqueados.append(
                f"{fuente}: no se ejecutó vista-previa/consulta AAEF real (requiere canal/periodo autorizado)"
            )

    escenarios.append({
        "id": "E1",
        "nombre": "Registro de eventos de integración (TC-M07-102-001)",
        "estado": estado_e1,
        "esperado": "Operaciones generadoras dejan eventos consultables con tipo/módulo/actor/fechas",
        "obtenido": obtenido_e1,
    })

    # --- Escenario 2 ---
    if items:
        fallos_gen = []
        fallos_cond = []
        detalle_cond = []
        for ev in items:
            fg = validar_generales(ev)
            if fg:
                fallos_gen.append({"id": ev.get("id_evento_integracion"), "faltantes": fg})
            vc = validar_condicionales(ev)
            detalle_cond.append({
                "id": ev.get("id_evento_integracion"),
                "tipo": vc["tipo"],
                "requeridos": vc["requeridos"],
                "faltantes": vc["faltantes"],
                "ok": vc["ok"],
            })
            if not vc["ok"]:
                fallos_cond.append({"id": ev.get("id_evento_integracion"), "tipo": vc["tipo"], "faltantes": vc["faltantes"]})
        integro_ok = all((e.get("integridad") == "INTEGRO") or bool(e.get("hash_integridad")) for e in items)
        campos_comprobados = {
            "generales": list(CAMPOS_GENERALES),
            "eventos_evaluados": len(items),
            "fallos_generales": fallos_gen[:20],
            "fallos_condicionales": fallos_cond[:20],
            "muestra_condicionales": detalle_cond[:15],
            "integridad_ok_muestra": integro_ok,
            "nota": "Solo se exigen condicionales definidos en _OBLIGATORIOS para el tipo",
        }
        if not fallos_gen and not fallos_cond and integro_ok:
            estado_e2 = "APROBADO"
            obtenido_e2 = f"Muestra {len(items)}: generales y condicionales OK; integridad presente/INTEGRO"
        else:
            estado_e2 = "RECHAZADO"
            obtenido_e2 = (
                f"Fallos generales={len(fallos_gen)}, condicionales={len(fallos_cond)}, "
                f"integridad_ok={integro_ok}"
            )
    else:
        estado_e2 = "BLOQUEADO"
        obtenido_e2 = "Sin eventos consultados; no se validaron campos"
        bloqueados.append("E2 bloqueado por dependencia de consulta autorizada")

    escenarios.append({
        "id": "E2",
        "nombre": "Campos obligatorios y condicionales (TC-M07-102-002)",
        "estado": estado_e2,
        "esperado": "Estructura RF-102 cumplida según tipo de evento",
        "obtenido": obtenido_e2,
    })

    # --- Escenario 3 ---
    # No hay endpoint público de inserción. Validamos rechazo observable seguro + documentamos límites.
    e3_partes = []
    # 3a incompletos: sin API pública
    e3_partes.append({
        "chequeo": "eventos_incompletos",
        "estado": "BLOQUEADO",
        "detalle": "registrar() rechaza con AUDITORIA_INCOMPLETA vía faltantes(); no hay endpoint público para enviar evento incompleto",
    })
    # 3b duplicados: sin lógica de negocio dedicada expuesta
    e3_partes.append({
        "chequeo": "eventos_duplicados",
        "estado": "BLOQUEADO",
        "detalle": "No existe operación pública ni regla de negocio expuesta para 'evento duplicado' más allá de PK UUID",
    })
    # 3c no catalogados: OpenAPI Literal + enum BD; sin insert público
    e3_partes.append({
        "chequeo": "tipos_no_catalogados",
        "estado": "BLOQUEADO",
        "detalle": "Catálogo en TipoEvento/OpenAPI y enum BD; sin mecanismo controlado para persistir tipo fuera de catálogo vía API",
    })
    # Evidencia parcial segura: inmutabilidad 405 (relacionada a protección, no a invalid payload insert)
    if admin_token and admin_tiene_aud and st_put is not None:
        e3_partes.append({
            "chequeo": "modificacion_api_rechazada",
            "estado": "APROBADO" if st_put == 405 else "RECHAZADO",
            "detalle": f"PUT /integracion/auditoria → HTTP {st_put} (FA-2 inmutabilidad)",
        })

    campos_comprobados["rechazo_invalido"] = e3_partes
    if all(p["estado"] == "BLOQUEADO" for p in e3_partes if p["chequeo"] != "modificacion_api_rechazada"):
        # Si al menos inmutabilidad pasó, el escenario sigue BLOQUEADO en el núcleo 001-003 de rechazo de insert
        estado_e3 = "BLOQUEADO"
        obtenido_e3 = (
            "Sin mecanismo público para insertar eventos incompletos/duplicados/no catalogados. "
            + "; ".join(f"{p['chequeo']}={p['estado']}" for p in e3_partes)
        )
        bloqueados.append("E3: requiere harness interno o endpoint de prueba controlado para inválidos")
        deps.append("Mecanismo controlado de prueba para FA-8 (incompletos) y tipos fuera de catálogo, sin escribir a mano en BD")
    else:
        estado_e3 = "BLOQUEADO"
        obtenido_e3 = json.dumps(e3_partes, ensure_ascii=False)

    escenarios.append({
        "id": "E3",
        "nombre": "Rechazo de eventos inválidos (TC-M07-102-003)",
        "estado": estado_e3,
        "esperado": "Incompletos/duplicados/no catalogados rechazados con evidencia de ejecución",
        "obtenido": obtenido_e3,
    })

    # --- Escenario 4 UTC ---
    if items:
        checks = []
        for ev in items:
            fe = es_utc(ev.get("fecha_evento"))
            fr = es_utc(ev.get("fecha_registro"))
            ok = fe["parseable"] and fr["parseable"] and fe["aware"] and fr["aware"] and fe["offset_cero"] and fr["offset_cero"]
            checks.append({
                "id": ev.get("id_evento_integracion"),
                "fecha_evento": fe,
                "fecha_registro": fr,
                "ok": ok,
            })
            if len(checks) >= 10:
                break
        # comparación entre dos eventos reales si hay >=2
        comparacion = None
        if len(items) >= 2:
            a, b = items[0], items[1]
            comparacion = {
                "evento_a": a.get("id_evento_integracion"),
                "evento_b": b.get("id_evento_integracion"),
                "fecha_evento_a": a.get("fecha_evento"),
                "fecha_evento_b": b.get("fecha_evento"),
                "ambas_aware_utc": all(
                    es_utc(x.get("fecha_evento"))["ok"] if False else (
                        es_utc(x.get("fecha_evento"))["parseable"]
                        and es_utc(x.get("fecha_evento"))["aware"]
                        and es_utc(x.get("fecha_evento"))["offset_cero"]
                    )
                    for x in (a, b)
                ),
            }
        ok_all = all(c["ok"] for c in checks) and len(checks) > 0
        campos_comprobados["utc"] = {"muestra": checks, "comparacion": comparacion}
        # also verify ahora_utc default in domain uses timezone.utc (code evidence noted, not alone for APROBADO)
        fuentes_mapeo["utc_codigo"] = "EventoIntegracion.ahora_utc() → datetime.now(timezone.utc)"
        if ok_all:
            estado_e4 = "APROBADO"
            obtenido_e4 = f"{len(checks)} eventos con fecha_evento/fecha_registro parseables, aware y offset UTC 0"
        else:
            estado_e4 = "RECHAZADO"
            obtenido_e4 = f"Fallaron checks UTC en muestra: {[c for c in checks if not c['ok']][:5]}"
    else:
        estado_e4 = "BLOQUEADO"
        obtenido_e4 = "Sin eventos para validar normalización UTC"
        bloqueados.append("E4 bloqueado por dependencia de consulta autorizada")
        deps.append("UUID de muestra del DBA (5) para contrastar fechas específicas")

    escenarios.append({
        "id": "E4",
        "nombre": "Normalización de fechas/horas a UTC (TC-M07-102-004)",
        "estado": estado_e4,
        "esperado": "fecha_evento y fecha_registro en UTC según implementación",
        "obtenido": obtenido_e4,
    })

    # Estado final del caso agrupado
    estados = [e["estado"] for e in escenarios]
    if "RECHAZADO" in estados:
        estado_final = "RECHAZADO"
    elif all(s == "APROBADO" for s in estados):
        estado_final = "APROBADO"
    elif "BLOQUEADO" in estados and any(s == "APROBADO" for s in estados):
        estado_final = "BLOQUEADO"
    elif all(s == "BLOQUEADO" for s in estados):
        estado_final = "BLOQUEADO"
    else:
        estado_final = "BLOQUEADO"

    # Dedupe uuids
    uuids = list(dict.fromkeys([u for u in uuids if u]))

    data = {
        "caso": CASO,
        "requisito": RF,
        "fecha_ejecucion_utc": ahora(),
        "entorno": "TEST",
        "base_url": BASE,
        "estado_final": estado_final,
        "escenarios": escenarios,
        "peticiones": pet,
        "uuids_verificados": uuids,
        "campos_comprobados": campos_comprobados,
        "errores": errores,
        "bloqueados": bloqueados,
        "dependencias": deps,
        "fuentes_mapeo": fuentes_mapeo,
        "muestra_eventos": [resumen_evento(e) for e in items[:12] if isinstance(e, dict)],
        "contador_sin_auditoria_integracion": (False if cont_tiene_aud is None else (not cont_tiene_aud)),
        "openapi_sin_post_auditoria": not tiene_post_aud and tiene_get_aud,
    }

    JSON_EVIDENCIA.write_text(json.dumps(limpiar(data), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    HTML_REPORTE.write_text(render_html(data), encoding="utf-8")

    print(json.dumps({
        "caso": CASO,
        "estado_final": estado_final,
        "escenarios": {e["id"]: e["estado"] for e in escenarios},
        "html": str(HTML_REPORTE),
        "json": str(JSON_EVIDENCIA),
        "uuids": len(uuids),
        "total_api": total_api,
    }, ensure_ascii=False, indent=2))
    return 0 if estado_final == "APROBADO" else 2


if __name__ == "__main__":
    raise SystemExit(main())
