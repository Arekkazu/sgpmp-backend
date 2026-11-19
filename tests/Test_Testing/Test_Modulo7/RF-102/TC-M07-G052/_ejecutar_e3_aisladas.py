# | Fecha      | Nombre      | Que se hizo |
# |------------|-------------|-------------|
# | 2026-11-17 | Laura López | Runner E3 aisladas + actualización de informe HTML sin borrar E1/E2/E4. |
"""Ejecuta pytest E3 aisladas, guarda evidencia y actualiza resultado_TC-M07-G52.html.

Conserva evidencia_ejecucion_TC-M07-G52.json (E1/E2/E4 API). No toca BD TEST.

    python tests/Test_Testing/Test_Modulo7/RF-102/TC-M07-G052/_ejecutar_e3_aisladas.py
"""
from __future__ import annotations

import html
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

CARPETA = Path(__file__).resolve().parent
RESULTADO = CARPETA / "Resultado"
EVIDENCIA_API = RESULTADO / "evidencia_ejecucion_TC-M07-G52.json"
EVIDENCIA_E3 = RESULTADO / "evidencia_e3_validaciones_aisladas_TC-M07-G52.json"
HTML_REPORTE = RESULTADO / "resultado_TC-M07-G52.html"
PYTEST_LOG = RESULTADO / "pytest_e3_aisladas.txt"
TEST_FILE = CARPETA / "test_tc_m07_g52_e3_validaciones_aisladas.py"
REPO = CARPETA.parents[4]


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


def badge(estado: str) -> str:
    colores = {
        "APROBADO": "#1b7a3d",
        "RECHAZADO": "#b00020",
        "BLOQUEADO": "#9a6b00",
        "NO APLICABLE": "#555555",
    }
    c = colores.get(estado, "#333")
    return (
        f'<span style="display:inline-block;padding:2px 10px;border-radius:4px;'
        f'background:{c};color:#fff;font-weight:600">{html.escape(estado)}</span>'
    )


def clasificar_e3(sub: dict) -> tuple[str, str]:
    """Estado del escenario E3 agrupado a partir de subescenarios."""
    e31, e32, e33 = sub["E3.1"]["estado"], sub["E3.2"]["estado"], sub["E3.3"]["estado"]
    detalle = f"E3.1={e31}; E3.2={e32}; E3.3={e33}"
    if e31 == "APROBADO" and e32 == "APROBADO" and e33 == "APROBADO":
        return "APROBADO", detalle
    if "RECHAZADO" in (e31, e32, e33):
        return "RECHAZADO", detalle
    # Incompleto sí; duplicado/no catalogado sin BD aislada → E3 sigue bloqueado
    return "BLOQUEADO", detalle + ". Persistencia PK/enum requiere PostgreSQL aislado (no TEST)."


def main() -> int:
    RESULTADO.mkdir(parents=True, exist_ok=True)
    if not EVIDENCIA_API.exists():
        print("Falta evidencia API previa:", EVIDENCIA_API, file=sys.stderr)
        return 1

    api = json.loads(EVIDENCIA_API.read_text(encoding="utf-8"))

    env = os.environ.copy()
    stub = str(REPO / "_win_fcntl_stub_borrar")
    env["PYTHONPATH"] = stub + os.pathsep + str(REPO) + (
        (os.pathsep + env["PYTHONPATH"]) if env.get("PYTHONPATH") else ""
    )
    env.setdefault("SECRET_KEY", "test-unitario-g52-e3")
    # Solo para importar módulos; las pruebas no abren conexión.
    env.setdefault("DATABASE_URL", "postgresql://g52:g52@127.0.0.1:5432/g52_aislada_no_usar")

    cmd = [
        sys.executable, "-m", "pytest", str(TEST_FILE),
        "-v", "--tb=short", "-q",
    ]
    proc = subprocess.run(cmd, cwd=str(REPO), env=env, capture_output=True, text=True)
    log = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
    PYTEST_LOG.write_text(log, encoding="utf-8")

    passed = proc.returncode == 0
    # Subescenarios según diseño real + resultado pytest
    sub = {
        "E3.1": {
            "nombre": "Evento incompleto (FA-8)",
            "funcion": "SqlAlchemyAuditoriaIntegracionRepository.registrar + EventoIntegracion.faltantes",
            "entrada": {
                "tipo_evento": "CONTRATO_ACTIVADO",
                "version_contrato": None,
                "id_evento_integracion": "00000000-0000-4000-8000-000000000052",
            },
            "esperado": "InfrastructureError AUDITORIA_INCOMPLETA; escribir() no invocado",
            "obtenido": (
                "pytest E3.1 PASSED: code=AUDITORIA_INCOMPLETA y mock escribir.assert_not_called"
                if passed else "pytest falló — ver pytest_e3_aisladas.txt"
            ),
            "excepcion": "InfrastructureError(code='AUDITORIA_INCOMPLETA')" if passed else None,
            "persistencia_invocada": False if passed else None,
            "nivel": "unidad (repositorio real + mock de escribir)",
            "estado": "APROBADO" if passed else "RECHAZADO",
        },
        "E3.2": {
            "nombre": "Evento duplicado (mismo UUID)",
            "funcion": "registrar() — inspección + doble llamada con mismo UUID",
            "entrada": {
                "id_evento_integracion": "11111111-1111-4111-8111-111111111152",
                "tipo_evento": "CONTRATO_ACTIVADO",
                "version_contrato": "3.0",
                "intentos": 2,
            },
            "esperado_ficha": "Segundo registro rechazado",
            "comportamiento_implementado": (
                "No hay validación de duplicados en Python. "
                "Rechazo solo vía PK eventos_integracion_pkey (migración 94b14a6931d6)."
            ),
            "obtenido": (
                "pytest demuestra: escribir() se invoca 2 veces con el mismo UUID en capa Python; "
                "PK documentada en migración; sin ejecución contra PostgreSQL aislado"
                if passed else "pytest falló"
            ),
            "excepcion": None,
            "persistencia_invocada": True,
            "nivel": "unidad (ausencia de lógica) — NO prueba el PK real",
            "estado": "BLOQUEADO",
            "justificacion": (
                "La detección de duplicados no está en el servicio/repositorio Python; "
                "está en la restricción PRIMARY KEY de BD. Probar el rechazo real exige "
                "PostgreSQL aislado (no la BD TEST compartida)."
            ),
        },
        "E3.3": {
            "nombre": "Tipo de evento no catalogado",
            "funcion": "registrar() + CAST enum en _INSERT",
            "entrada": {"tipo_evento": "TIPO_NO_CATALOGADO_QA_G52"},
            "esperado_ficha": "Rechazo antes de persistir",
            "comportamiento_implementado": (
                "faltantes() retorna [] si el tipo no está en _OBLIGATORIOS; "
                "registrar() invoca escribir(); el rechazo real sería CAST enum en PostgreSQL."
            ),
            "obtenido": (
                "pytest demuestra: escribir() SÍ se invoca para tipo no catalogado en capa Python; "
                "_INSERT contiene CAST a enum_evento_integracion_tipo_evento; "
                "sin ejecución del CAST contra PostgreSQL aislado"
                if passed else "pytest falló"
            ),
            "excepcion": None,
            "persistencia_invocada": True,
            "nivel": "unidad (ausencia de validación de catálogo en Python) — NO prueba el enum real",
            "estado": "BLOQUEADO",
            "justificacion": (
                "No existe validación de catálogo en registrar(). El rechazo depende del ENUM "
                "PostgreSQL. Sin BD aislada no se puede evidenciar el CAST fallido de forma segura."
            ),
        },
    }

    estado_e3, obtenido_e3 = clasificar_e3(sub)
    evidencia = {
        "caso": "TC-M07-G052",
        "escenario": "E3",
        "fecha_ejecucion_utc": ahora(),
        "herramienta": "pytest + unittest.mock",
        "pytest_returncode": proc.returncode,
        "pytest_passed": passed,
        "archivo_prueba": str(TEST_FILE.relative_to(REPO)).replace("\\", "/"),
        "log": str(PYTEST_LOG.relative_to(REPO)).replace("\\", "/"),
        "subescenarios": sub,
        "estado_e3": estado_e3,
        "obtenido_e3": obtenido_e3,
        "puede_aprobar_e3_completo": False,
        "motivo_no_aprobacion_completa": (
            "E3.1 sí; E3.2 y E3.3 dependen de restricciones PostgreSQL (PK y ENUM) "
            "no ejercitadas aquí para no tocar TEST."
        ),
        "bd_aislada_requerida_para": ["E3.2 PRIMARY KEY", "E3.3 CAST enum_evento_integracion_tipo_evento"],
        "evidencia_api_conservada": str(EVIDENCIA_API.name),
        "e1_e2_e4_desde_api": {
            e["id"]: e["estado"] for e in api.get("escenarios", []) if e.get("id") in ("E1", "E2", "E4")
        },
    }
    EVIDENCIA_E3.write_text(json.dumps(evidencia, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # Escenarios para HTML: E1/E2/E4 intactos desde API; E3 actualizado
    escenarios_html = []
    for e in api.get("escenarios", []):
        if e.get("id") == "E3":
            escenarios_html.append({
                "id": "E3",
                "nombre": e.get("nombre"),
                "estado": estado_e3,
                "esperado": e.get("esperado"),
                "obtenido": obtenido_e3 + " | " + (sub["E3.1"]["obtenido"] or ""),
            })
        else:
            escenarios_html.append(e)

    estados = [e["estado"] for e in escenarios_html]
    if "RECHAZADO" in estados:
        estado_final = "RECHAZADO"
    elif all(s == "APROBADO" for s in estados):
        estado_final = "APROBADO"
    else:
        estado_final = "BLOQUEADO"

    filas = []
    for escn in escenarios_html:
        filas.append(
            "<tr>"
            f"<td>{html.escape(escn['id'])}</td>"
            f"<td>{html.escape(escn['nombre'])}</td>"
            f"<td>{badge(escn['estado'])}</td>"
            f"<td>{html.escape(str(escn.get('esperado','')))}</td>"
            f"<td>{html.escape(str(escn.get('obtenido','')))}</td>"
            "</tr>"
        )

    sub_rows = []
    for sid, s in sub.items():
        sub_rows.append(
            "<tr>"
            f"<td>{html.escape(sid)}</td>"
            f"<td>{html.escape(s['nombre'])}</td>"
            f"<td>{badge(s['estado'])}</td>"
            f"<td><code>{html.escape(s['funcion'])}</code></td>"
            f"<td>{html.escape(json.dumps(s.get('entrada'), ensure_ascii=False))}</td>"
            f"<td>{html.escape(str(s.get('esperado') or s.get('esperado_ficha') or ''))}</td>"
            f"<td>{html.escape(str(s.get('obtenido','')))}</td>"
            f"<td>{html.escape(str(s.get('excepcion')))}</td>"
            f"<td>{html.escape(str(s.get('persistencia_invocada')))}</td>"
            f"<td>{html.escape(str(s.get('nivel','')))}</td>"
            "</tr>"
        )

    pet_rows = []
    for p in api.get("peticiones", []):
        pet_rows.append(
            "<tr>"
            f"<td>{html.escape(str(p.get('fase')))}</td>"
            f"<td>{html.escape(str(p.get('metodo')))}</td>"
            f"<td>{html.escape(str(p.get('ruta')))}</td>"
            f"<td>{html.escape(str(p.get('http')))}</td>"
            f"<td><code>{html.escape(json.dumps(p.get('respuesta_resumen'), ensure_ascii=False)[:400])}</code></td>"
            "</tr>"
        )

    uuids = api.get("uuids_verificados") or []
    doc = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8"/>
<title>TC-M07-G052 — RF-102</title>
<style>
body{{font-family:Segoe UI,Arial,sans-serif;margin:24px;color:#1a1a1a;background:#f7f7f5}}
h1,h2,h3{{color:#102a43}}
.card{{background:#fff;border:1px solid #ddd;border-radius:8px;padding:16px 20px;margin:16px 0}}
table{{border-collapse:collapse;width:100%;font-size:13px}}
th,td{{border:1px solid #ddd;padding:8px;vertical-align:top;text-align:left}}
th{{background:#e8eef5}}
code{{font-size:11px;word-break:break-word}}
.meta span{{display:inline-block;margin-right:16px}}
.note{{background:#fff8e6;border-left:4px solid #9a6b00;padding:10px 14px;margin:12px 0}}
</style>
</head>
<body>
<h1>TC-M07-G052 — Verificar registro y validación de eventos de integración</h1>
<div class="card meta">
  <span><strong>Requisito:</strong> RF-102 · CU07</span>
  <span><strong>Entorno API:</strong> TEST (E1/E2/E4)</span>
  <span><strong>E3:</strong> pytest aislado (sin BD TEST)</span>
  <span><strong>Actualización E3 UTC:</strong> {html.escape(ahora())}</span>
  <span><strong>Estado final:</strong> {badge(estado_final)}</span>
</div>
<div class="note">
  E1, E2 y E4 conservan la evidencia API de <code>{html.escape(EVIDENCIA_API.name)}</code>.
  E3 se reevaluó con <code>{html.escape(EVIDENCIA_E3.name)}</code> y
  <code>{html.escape(PYTEST_LOG.name)}</code>. No se insertó nada en TEST para E3.
</div>
<div class="card">
  <h2>Escenarios del caso agrupado</h2>
  <table>
    <thead><tr><th>ID</th><th>Escenario</th><th>Estado</th><th>Esperado</th><th>Obtenido</th></tr></thead>
    <tbody>{''.join(filas)}</tbody>
  </table>
</div>
<div class="card">
  <h2>Detalle E3 — validaciones aisladas</h2>
  <table>
    <thead><tr>
      <th>ID</th><th>Escenario</th><th>Estado</th><th>Función</th><th>Entrada</th>
      <th>Esperado</th><th>Obtenido</th><th>Excepción</th><th>Persistencia</th><th>Nivel</th>
    </tr></thead>
    <tbody>{''.join(sub_rows)}</tbody>
  </table>
  <p><strong>Estado E3:</strong> {badge(estado_e3)} — {html.escape(obtenido_e3)}</p>
</div>
<div class="card">
  <h2>Evidencias HTTP E1/E2/E4 (sin credenciales) — conservadas</h2>
  <table>
    <thead><tr><th>Fase</th><th>Método</th><th>Ruta</th><th>HTTP</th><th>Resumen</th></tr></thead>
    <tbody>{''.join(pet_rows)}</tbody>
  </table>
</div>
<div class="card">
  <h2>UUID verificados (API)</h2>
  <ul>{''.join(f'<li><code>{html.escape(u)}</code></li>' for u in uuids) if uuids else '<li>N/A</li>'}</ul>
</div>
<div class="card">
  <h2>Dependencias pendientes</h2>
  <ul>
    <li>PostgreSQL aislado (no TEST) para ejercitar PK de duplicados y CAST de enum no catalogado.</li>
    <li>Cinco UUID de muestra del DBA (opcional, para contraste documental).</li>
  </ul>
</div>
<p style="color:#666;font-size:12px">Generado por _ejecutar_e3_aisladas.py — sin secretos.</p>
</body>
</html>
"""
    HTML_REPORTE.write_text(doc, encoding="utf-8")

    print(json.dumps({
        "pytest_passed": passed,
        "estado_e3": estado_e3,
        "sub": {k: v["estado"] for k, v in sub.items()},
        "estado_final_caso": estado_final,
        "html": str(HTML_REPORTE),
        "evidencia_e3": str(EVIDENCIA_E3),
        "evidencia_api_intacta": EVIDENCIA_API.exists(),
    }, ensure_ascii=False, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
