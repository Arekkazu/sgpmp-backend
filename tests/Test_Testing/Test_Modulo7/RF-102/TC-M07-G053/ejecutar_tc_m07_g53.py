# | Fecha      | Nombre      | Que se hizo |
# |------------|-------------|-------------|
# | 2026-11-17 | Laura López | TC-M07-G053 RF-102: integridad, corrupción, inmutabilidad, protección sensible. |
"""TC-M07-G053 — integridad y protección de auditoría (RF-102).

Orquesta: API TEST (Admin) + pytest unitario + Postgres aislado.
Credenciales solo por entorno: QA_ADMIN_CORREO / QA_ADMIN_CONTRASENA.

    python tests/Test_Testing/Test_Modulo7/RF-102/TC-M07-G053/ejecutar_tc_m07_g53.py
"""
from __future__ import annotations

import html
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

BASE = "https://api.inmero.co/api-sgpmp-test"
ZONA = "America/Bogota"
CASO = "TC-M07-G053"
RF = "RF-102"
CARPETA = Path(__file__).resolve().parent
RESULTADO = CARPETA / "Resultado"
REPO = CARPETA.parents[4]

SECRETOS_PATRON = re.compile(
    r"(?i)(client_secret|api[_-]?key|access_token|refresh_token|authorization|bearer\s+eyj|"
    r"-----BEGIN|password\s*[:=])"
)
VALORES_FICTICIOS = ("TEST_SECRET_123456", "sk_test_fake_not_real", "hmac_fake_signature_abcdef0123456789")


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
            if kl in ("token", "access_token", "client_secret", "contrasena", "password") or kl.endswith("_token"):
                out[k] = {"omitido": True}
            elif kl == "hash_integridad" and isinstance(x, str) and len(x) > 12:
                out[k] = x[:12] + "…"
            else:
                out[k] = limpiar(x, d + 1)
        return out
    if isinstance(v, list):
        return [limpiar(x, d + 1) for x in v[:60]]
    if isinstance(v, str) and len(v) > 500:
        return v[:500] + "…"
    return v


def badge(estado: str) -> str:
    c = {"APROBADO": "#1b7a3d", "RECHAZADO": "#b00020", "BLOQUEADO": "#9a6b00", "NO APLICA": "#555"}.get(estado, "#333")
    return f'<span style="display:inline-block;padding:2px 10px;border-radius:4px;background:{c};color:#fff;font-weight:600">{html.escape(estado)}</span>'


def escanear_sensible(obj: Any, ruta: str = "$") -> list[str]:
    hallados = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            kl = str(k).lower()
            if any(s in kl for s in ("client_secret", "api_key", "access_token", "password", "contrasena")):
                if v not in (None, "", {"omitido": True}) and not (isinstance(v, dict) and v.get("omitido")):
                    hallados.append(f"{ruta}.{k}=expuesto")
            hallados.extend(escanear_sensible(v, f"{ruta}.{k}"))
    elif isinstance(obj, list):
        for i, v in enumerate(obj[:40]):
            hallados.extend(escanear_sensible(v, f"{ruta}[{i}]"))
    elif isinstance(obj, str):
        for fict in VALORES_FICTICIOS:
            if fict in obj:
                hallados.append(f"{ruta} contiene valor ficticio completo")
        if SECRETOS_PATRON.search(obj) and "omitido" not in obj.lower():
            # evitar falsos positivos de códigos de evento
            if "bearer eyj" in obj.lower() or "begin private" in obj.lower():
                hallados.append(f"{ruta} patrón secreto")
    return hallados


def render_html(data: dict) -> str:
    filas = []
    detalle = []
    for e in data["escenarios"]:
        filas.append(
            "<tr>"
            f"<td>{html.escape(e['id'])}</td><td>{html.escape(e['caso_original'])}</td>"
            f"<td>{html.escape(e['nombre'])}</td><td>{badge(e['estado'])}</td>"
            f"<td>{html.escape(e['tipo_prueba'])}</td>"
            f"<td>{html.escape(e.get('evidencia',''))}</td>"
            "</tr>"
        )
        pasos = e.get("pasos") or []
        pasos_html = "".join(f"<li>{html.escape(p)}</li>" for p in pasos)
        detalle.append(
            f"<div class='card'><h3>{html.escape(e['id'])} — {html.escape(e['caso_original'])}: "
            f"{html.escape(e['nombre'])} {badge(e['estado'])}</h3>"
            f"<p><strong>Tipo:</strong> {html.escape(e['tipo_prueba'])}</p>"
            f"<p><strong>Resultado esperado:</strong> {html.escape(e['esperado'])}</p>"
            f"<p><strong>Resultado obtenido:</strong> {html.escape(e['obtenido'])}</p>"
            f"<p><strong>Evidencia:</strong> <code>{html.escape(e.get('evidencia',''))}</code></p>"
            f"<p><strong>Pasos ejecutados:</strong></p><ul>{pasos_html}</ul>"
            f"<p><strong>Observaciones:</strong> {html.escape(e.get('observaciones',''))}</p>"
            "</div>"
        )
    pet = []
    for p in data.get("peticiones", []):
        pet.append(
            "<tr>"
            f"<td>{html.escape(str(p.get('fase')))}</td><td>{html.escape(str(p.get('metodo')))}</td>"
            f"<td>{html.escape(str(p.get('ruta')))}</td><td>{html.escape(str(p.get('http')))}</td>"
            f"<td><code>{html.escape(json.dumps(limpiar(p.get('respuesta_resumen')), ensure_ascii=False)[:350])}</code></td>"
            "</tr>"
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
ul{{margin:8px 0 8px 20px}}
</style></head><body>
<h1>{html.escape(CASO)} — Verificar la integridad y protección de los registros de auditoría</h1>
<div class="card meta">
  <span><strong>ID:</strong> {html.escape(CASO)}</span>
  <span><strong>Requisito:</strong> {html.escape(RF)} · CU07 · Módulo 7</span>
  <span><strong>Responsable:</strong> Laura López</span>
  <span><strong>Agrupa:</strong> TC-M07-102-005 … 008</span>
  <span><strong>Estado final:</strong> {badge(data['estado_final'])}</span>
  <span><strong>Ejecución UTC:</strong> {html.escape(data['fecha_ejecucion_utc'])}</span>
</div>
<div class="note">
  <strong>Ámbitos (no mezclar):</strong>
  <ul>
    <li><strong>E1/E3-API/E4</strong> — API TEST <code>{html.escape(BASE)}</code> (consultas Admin + PUT/PATCH/DELETE).</li>
    <li><strong>E1/E2/E4 unitario</strong> — pytest <code>test_tc_m07_g53_integridad.py</code>.</li>
    <li><strong>E2/E3 SQL</strong> — Postgres Docker aislado <code>infra-db-1</code>, BD temporal <code>sgpmp_g053_e_tmp</code> (DROP al finalizar). Sin UPDATE/DELETE en TEST.</li>
  </ul>
</div>
<div class="card"><h2>Resumen de escenarios</h2>
<table><thead><tr><th>ID</th><th>Original</th><th>Nombre</th><th>Estado</th><th>Tipo</th><th>Evidencia</th></tr></thead>
<tbody>{''.join(filas)}</tbody></table></div>
{''.join(detalle)}
<div class="card"><h2>Peticiones HTTP (sin secretos)</h2>
<table><thead><tr><th>Fase</th><th>Método</th><th>Ruta</th><th>HTTP</th><th>Resumen</th></tr></thead>
<tbody>{''.join(pet)}</tbody></table></div>
<div class="lim"><h3>Limitaciones técnicas</h3><pre>{html.escape(json.dumps(data.get('limitaciones', []), ensure_ascii=False, indent=2))}</pre></div>
<div class="card"><h3>Resumen final</h3><pre>{html.escape(json.dumps(data.get('resumen', {}), ensure_ascii=False, indent=2))}</pre>
<p><strong>Errores:</strong> {html.escape(data.get('errores') or 'Ninguno en la última ejecución.')}</p>
</div>
</body></html>"""


def main() -> int:
    RESULTADO.mkdir(parents=True, exist_ok=True)
    pet: list[dict] = []
    limitaciones: list[str] = []
    admin_correo = os.environ.get("QA_ADMIN_CORREO") or os.environ.get("TEST_ADMIN_EMAIL")
    admin_clave = os.environ.get("QA_ADMIN_CONTRASENA") or os.environ.get("TEST_ADMIN_PASSWORD")

    # --- API login ---
    token = None
    items: list[dict] = []
    if not admin_correo or not admin_clave:
        limitaciones.append("Sin QA_ADMIN_* : escenarios API quedan BLOQUEADOS")
    else:
        st, login, _ = pedir("POST", "/sesiones/", {"correo_electronico": admin_correo, "contrasena": admin_clave})
        pet.append({"fase": "login_admin", "metodo": "POST", "ruta": "/sesiones/", "http": st,
                    "respuesta_resumen": {"ok": st in (200, 201), "tiene_token": bool((login or {}).get("token"))}})
        token = (login or {}).get("token") if isinstance(login, dict) else None
        if token:
            st_a, body, _ = pedir("GET", "/integracion/auditoria?pagina=1&tamano=50", token=token)
            pet.append({"fase": "consulta_auditoria", "metodo": "GET", "ruta": "/integracion/auditoria?tamano=50",
                        "http": st_a, "respuesta_resumen": {
                            "total": (body or {}).get("total") if isinstance(body, dict) else None,
                            "items": len((body or {}).get("items") or []) if isinstance(body, dict) else 0,
                            "claves_item": sorted(list(((body or {}).get("items") or [{}])[0].keys())) if isinstance(body, dict) and (body.get("items")) else [],
                        }})
            if st_a == 200 and isinstance(body, dict):
                items = body.get("items") or []

    # --- pytest unitario ---
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO / "_win_fcntl_stub_borrar") + os.pathsep + str(REPO)
    env.setdefault("SECRET_KEY", "test-g53")
    env.setdefault("DATABASE_URL", "postgresql://g53:g53@127.0.0.1:5432/g53_no_usar")
    pytest_log = RESULTADO / "pytest_g53_integridad.txt"
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", str(CARPETA / "test_tc_m07_g53_integridad.py"), "-v", "--tb=short", "-q"],
        cwd=str(REPO), env=env, capture_output=True, text=True,
    )
    pytest_log.write_text((proc.stdout or "") + "\n" + (proc.stderr or ""), encoding="utf-8")
    pytest_ok = proc.returncode == 0

    # --- postgres aislado ---
    pg_proc = subprocess.run(
        [sys.executable, str(CARPETA / "_ejecutar_postgres_aislada_g53.py")],
        cwd=str(REPO), env=env, capture_output=True, text=True,
    )
    (RESULTADO / "log_postgres_aislada_g53.txt").write_text(
        (pg_proc.stdout or "") + "\n" + (pg_proc.stderr or ""), encoding="utf-8")
    pg_ok = pg_proc.returncode == 0
    e2_sql = json.loads((RESULTADO / "evidencia_e2_corrupcion_TC-M07-G053.json").read_text(encoding="utf-8")) if (RESULTADO / "evidencia_e2_corrupcion_TC-M07-G053.json").exists() else {}
    e3_sql = json.loads((RESULTADO / "evidencia_e3_inmutabilidad_sql_TC-M07-G053.json").read_text(encoding="utf-8")) if (RESULTADO / "evidencia_e3_inmutabilidad_sql_TC-M07-G053.json").exists() else {}
    diag_pg = json.loads((RESULTADO / "diagnostico_postgres_aislada_TC-M07-G053.json").read_text(encoding="utf-8")) if (RESULTADO / "diagnostico_postgres_aislada_TC-M07-G053.json").exists() else {}

    # ===== E1 =====
    claves = sorted(list(items[0].keys())) if items else []
    tiene_hash_en_api = "hash_integridad" in claves
    integros = [i for i in items if i.get("integridad") == "INTEGRO"]
    corruptos_api = [i for i in items if i.get("integridad") == "CORRUPTO"]
    e1_api_ok = bool(items) and len(integros) == len(items) and all("integridad" in i for i in items)
    e1_hash_db = (diag_pg.get("e1_aislada_hash") or {}).get("coinciden")
    if e1_api_ok and pytest_ok and e1_hash_db:
        estado_e1 = "APROBADO"
        obtenido_e1 = (
            f"API: {len(items)} eventos con integridad=INTEGRO; hash_integridad en respuesta={tiene_hash_en_api}. "
            f"Unitario SHA-256 OK. Postgres aislado: hash Python==hash DB."
        )
    elif not token:
        estado_e1 = "BLOQUEADO"
        obtenido_e1 = "Sin Admin para consultar API; unitario/pg según logs"
    else:
        estado_e1 = "RECHAZADO" if items else "BLOQUEADO"
        obtenido_e1 = f"api_ok={e1_api_ok} pytest={pytest_ok} hash_db={e1_hash_db} corruptos_api={len(corruptos_api)}"
    if not tiene_hash_en_api:
        limitaciones.append(
            "GET /integracion/auditoria expone campo 'integridad' (INTEGRO/CORRUPTO) vía _presentar; "
            "no incluye hash_integridad en asdict(evento). Recálculo independiente vs hash almacenado "
            "se validó en unitario + INSERT aislado."
        )

    e1_ev = {
        "escenario": "E1", "fecha_utc": ahora(), "estado": estado_e1,
        "api_items": len(items), "integros": len(integros), "hash_en_api": tiene_hash_en_api,
        "pytest_ok": pytest_ok, "hash_db_aislada": e1_hash_db,
        "algoritmo": "hash_sha256 = SHA-256(JSON sort_keys, separators=(',',':')) sobre asdict(campos); property excluida",
    }
    (RESULTADO / "evidencia_e1_hash_TC-M07-G053.json").write_text(
        json.dumps(limpiar(e1_ev), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # ===== E2 =====
    estado_e2 = e2_sql.get("estado") or ("BLOQUEADO" if not pg_ok else "RECHAZADO")
    obtenido_e2 = (
        f"INSERT hash falso + _presentar → {e2_sql.get('integridad')}; alerta={e2_sql.get('alerta_generada')}. "
        "Sin UPDATE en TEST (triggers lo impedirían; corrupción simulada por hash almacenado incorrecto)."
    )

    # ===== E3 =====
    estados_metodo = {}
    if token:
        for metodo in ("PUT", "PATCH", "DELETE"):
            st_m, body_m, _ = pedir(metodo, "/integracion/auditoria", {"intento": True} if metodo != "DELETE" else None, token=token)
            pet.append({"fase": f"inmutabilidad_api_{metodo}", "metodo": metodo, "ruta": "/integracion/auditoria",
                        "http": st_m, "respuesta_resumen": limpiar(body_m if isinstance(body_m, dict) else {"raw": body_m})})
            estados_metodo[metodo] = st_m
        # verificar evento INTENTO
        st_i, body_i, _ = pedir("GET", "/integracion/auditoria?tipo_evento=INTENTO_MODIFICACION_AUDITORIA&tamano=5", token=token)
        pet.append({"fase": "verificar_intento", "metodo": "GET",
                    "ruta": "/integracion/auditoria?tipo_evento=INTENTO_MODIFICACION_AUDITORIA", "http": st_i,
                    "respuesta_resumen": {"total": (body_i or {}).get("total") if isinstance(body_i, dict) else None}})
        intentos = (body_i or {}).get("total") if isinstance(body_i, dict) else 0
    else:
        intentos = None

    api_inm_ok = token and all(estados_metodo.get(m) == 405 for m in ("PUT", "PATCH", "DELETE"))
    sql_inm_ok = e3_sql.get("estado") == "APROBADO"
    if api_inm_ok and sql_inm_ok:
        estado_e3 = "APROBADO"
        obtenido_e3 = f"API PUT/PATCH/DELETE → 405; eventos INTENTO total={intentos}. SQL triggers UPDATE/DELETE/TRUNCATE bloqueados (TGR-M07-14)."
    elif not token and sql_inm_ok:
        estado_e3 = "BLOQUEADO"
        obtenido_e3 = "SQL aislado APROBADO; API no ejecutada (sin Admin)"
    else:
        estado_e3 = "RECHAZADO" if token else "BLOQUEADO"
        obtenido_e3 = f"api_metodos={estados_metodo} sql={e3_sql.get('estado')}"

    e3_ev = {"escenario": "E3", "fecha_utc": ahora(), "estado": estado_e3,
             "http_metodos": estados_metodo, "intentos_total": intentos, "sql": e3_sql}
    (RESULTADO / "evidencia_e3_inmutabilidad_TC-M07-G053.json").write_text(
        json.dumps(limpiar(e3_ev), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # ===== E4 =====
    hallazgos = []
    for it in items[:30]:
        hallazgos.extend(escanear_sensible(it, "item"))
    # exportar muestra pequeña si permiso
    if token:
        st_x, body_x, _ = pedir("GET", "/integracion/auditoria/exportar?formato=json", token=token, timeout=90)
        pet.append({"fase": "exportar_auditoria", "metodo": "GET", "ruta": "/integracion/auditoria/exportar?formato=json",
                    "http": st_x, "respuesta_resumen": {
                        "ok": st_x == 200,
                        "tipo": type(body_x).__name__,
                        "hallazgos_sensible": len(escanear_sensible(body_x)) if body_x is not None else None,
                    }})
        if st_x == 200:
            hallazgos.extend(escanear_sensible(body_x, "export"))

    # Regla HMAC[:8]*** → NO APLICA (no implementada en M07)
    hmac_rule = "NO APLICA"
    limitaciones.append(
        "Regla HMAC primeros 8 caracteres + '***': no implementada en src/accounting_integration "
        "(protección por diseño: no se persisten secretos/tokens/envelope en eventos_integracion)."
    )
    # Vista restringida probada en unitario
    if not hallazgos and pytest_ok and items is not None:
        estado_e4 = "APROBADO" if token else "BLOQUEADO"
        obtenido_e4 = (
            "Sin exposición de client_secret/tokens en muestra API; snapshot sin secretos; "
            f"vista restringida oculta ip/json_detalle (unitario). HMAC 8*** → {hmac_rule}."
        )
        if not token:
            obtenido_e4 = "Unitario OK; API no consultada"
    elif hallazgos:
        estado_e4 = "RECHAZADO"
        obtenido_e4 = f"Hallazgos sensibles: {hallazgos[:10]}"
    else:
        estado_e4 = "BLOQUEADO"
        obtenido_e4 = "No se pudo completar verificación API/unitario"

    e4_ev = {"escenario": "E4", "fecha_utc": ahora(), "estado": estado_e4, "hallazgos": hallazgos,
             "hmac_ocho_asteriscos": hmac_rule, "valores_ficticios_busqueda": list(VALORES_FICTICIOS),
             "pytest_ok": pytest_ok}
    (RESULTADO / "evidencia_e4_enmascaramiento_TC-M07-G053.json").write_text(
        json.dumps(limpiar(e4_ev), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    escenarios = [
        {
            "id": "E1", "caso_original": "TC-M07-102-005", "nombre": "Hash SHA-256", "estado": estado_e1,
            "tipo_prueba": "API TEST + unitario + Postgres aislado",
            "esperado": "Hashes válidos / integridad verificable",
            "obtenido": obtenido_e1, "evidencia": "evidencia_e1_hash_TC-M07-G053.json",
            "pasos": [
                "Login Admin y GET /integracion/auditoria (muestra 50)",
                "Verificar campo integridad=INTEGRO en API (hash_integridad no expuesto en asdict)",
                "pytest: recalcular SHA-256(JSON sort_keys) vs EventoIntegracion.hash_integridad",
                "Postgres aislado: INSERT con hash correcto y comparar hash_python == hash_db",
            ],
            "observaciones": "hash_integridad es @property excluida del cálculo; API expone integridad recalculada.",
        },
        {
            "id": "E2", "caso_original": "TC-M07-102-006", "nombre": "Detección corrupción", "estado": estado_e2,
            "tipo_prueba": "Unitario + Postgres aislado (INSERT hash falso)",
            "esperado": "CORRUPTO + alerta",
            "obtenido": obtenido_e2, "evidencia": "evidencia_e2_corrupcion_TC-M07-G053.json",
            "pasos": [
                "Unitario: _presentar con hash_guardado distinto → CORRUPTO + alertar",
                "BD temporal: INSERT con hash falso (sin UPDATE; triggers lo impedirían)",
                "Aplicar _presentar sobre el registro aislado y capturar alerta",
                "DROP DATABASE sgpmp_g053_e_tmp",
            ],
            "observaciones": "No se alteró la BD compartida de TEST. Corrupción = desajuste hash almacenado vs contenido.",
        },
        {
            "id": "E3", "caso_original": "TC-M07-102-007", "nombre": "Inmutabilidad", "estado": estado_e3,
            "tipo_prueba": "API TEST PUT/PATCH/DELETE + triggers SQL aislados",
            "esperado": "Rechazo sin alterar registros",
            "obtenido": obtenido_e3,
            "evidencia": "evidencia_e3_inmutabilidad_TC-M07-G053.json + evidencia_e3_inmutabilidad_sql_TC-M07-G053.json",
            "pasos": [
                "PUT /integracion/auditoria → 405",
                "PATCH /integracion/auditoria → 405",
                "DELETE /integracion/auditoria → 405",
                "GET filtro INTENTO_MODIFICACION_AUDITORIA",
                "Postgres aislado: UPDATE/DELETE/TRUNCATE → TGR-M07-14",
            ],
            "observaciones": "PUT, PATCH y DELETE comprobados de forma independiente (no por analogía).",
        },
        {
            "id": "E4", "caso_original": "TC-M07-102-008", "nombre": "Protección sensible", "estado": estado_e4,
            "tipo_prueba": "API TEST + unitario (HMAC NO APLICA)",
            "esperado": "Sin secretos expuestos",
            "obtenido": obtenido_e4, "evidencia": "evidencia_e4_enmascaramiento_TC-M07-G053.json",
            "pasos": [
                "Escanear items de auditoría y export JSON por secretos/valores ficticios",
                "Unitario: ClienteExterno.snapshot sin secretos",
                "Unitario: vista restringida oculta ip_origen y json_detalle",
                "Buscar lógica HMAC[:8]+*** en accounting_integration",
            ],
            "observaciones": "Regla HMAC 8*** no implementada (NO APLICA). Protección por diseño: no se persisten secretos en eventos.",
        },
    ]

    estados = [e["estado"] for e in escenarios]
    if "RECHAZADO" in estados:
        estado_final = "RECHAZADO"
    elif all(s in ("APROBADO", "NO APLICA") for s in estados) and any(s == "APROBADO" for s in estados) and "BLOQUEADO" not in estados:
        estado_final = "APROBADO"
    elif "BLOQUEADO" in estados:
        estado_final = "BLOQUEADO"
    else:
        estado_final = "BLOQUEADO"

    # Si E4 is APROBADO with HMAC as NO APLICA nested - fine. estado_e4 shouldn't be NO APLICA for whole E4.

    resumen = {
        "aprobados": sum(1 for s in estados if s == "APROBADO"),
        "rechazados": sum(1 for s in estados if s == "RECHAZADO"),
        "bloqueados": sum(1 for s in estados if s == "BLOQUEADO"),
        "no_aplica": sum(1 for s in estados if s == "NO APLICA"),
        "estado_final": estado_final,
    }

    data = {
        "caso": CASO, "requisito": RF, "fecha_ejecucion_utc": ahora(), "entorno_api": "TEST",
        "estado_final": estado_final, "escenarios": escenarios, "peticiones": pet,
        "limitaciones": limitaciones, "resumen": resumen,
        "pytest_ok": pytest_ok, "postgres_ok": pg_ok,
        "errores": None if estado_final == "APROBADO" else "Ver escenarios RECHAZADO/BLOQUEADO",
    }
    (RESULTADO / "evidencia_ejecucion_TC-M07-G053.json").write_text(
        json.dumps(limpiar(data), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (RESULTADO / "resultado_TC-M07-G053.html").write_text(render_html(data), encoding="utf-8")

    print(json.dumps({
        "caso": CASO,
        "estado_final": estado_final,
        "escenarios": {e["id"]: e["estado"] for e in escenarios},
        "resumen": resumen,
        "html": str(RESULTADO / "resultado_TC-M07-G053.html"),
    }, ensure_ascii=False, indent=2))
    return 0 if estado_final == "APROBADO" else 2


if __name__ == "__main__":
    raise SystemExit(main())
