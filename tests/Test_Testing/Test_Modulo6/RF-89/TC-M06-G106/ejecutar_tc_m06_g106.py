"""TC-M06-G106 contra TEST. Solo consultas.

La corrección es un INSERT nuevo. En el catálogo compartido cambiaría el
precio aplicado, así que no se envía.

    python tests/Test_Testing/Test_Modulo6/RF-89/TC-M06-G106/ejecutar_tc_m06_g106.py
"""
from __future__ import annotations

import html
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

CARPETA = Path(__file__).resolve().parent
RESULTADOS = CARPETA / "resultados"
BASE_API = "https://api.inmero.co/api-sgpmp-test"
ZONA = "America/Bogota"
SECRETOS = {"token", "access_token", "contrasena", "password", "hash_integridad", "numero_id_tributaria", "evidencia", "hash_evidencia"}


def pedir(metodo: str, ruta: str, cuerpo: dict | None = None, token: str | None = None):
    datos = None if cuerpo is None else json.dumps(cuerpo).encode()
    headers = {"Accept": "application/json", "X-Zona-Horaria": ZONA}
    if cuerpo is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(BASE_API + ruta, data=datos, headers=headers, method=metodo)
    inicio = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode()
            payload = json.loads(raw) if raw else None
            codigo = resp.status
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"message": raw[:200]}
        codigo = exc.code
    return codigo, payload, round((time.perf_counter() - inicio) * 1000)


def limpiar(valor, profundidad: int = 0):
    if profundidad > 5:
        return "..."
    if isinstance(valor, dict):
        return {k: ({"omitido": True, "longitud": len(v) if isinstance(v, str) else None} if k in SECRETOS else limpiar(v, profundidad + 1)) for k, v in valor.items()}
    if isinstance(valor, list):
        return [limpiar(v, profundidad + 1) for v in valor[:40]]
    if isinstance(valor, str) and len(valor) > 220:
        return valor[:220]
    return valor


def evidencia(metodo, ruta, codigo, duracion, respuesta) -> dict:
    return {"metodo": metodo, "consulta": ruta, "codigo": codigo, "duracion_ms": duracion,
            "escritura": False, "en": datetime.now(timezone.utc).isoformat(), "respuesta": limpiar(respuesta)}


def ficha(precio: dict) -> dict:
    return {
        "id": precio.get("id_precio_mercado"),
        "id_especie": precio.get("id_especie"),
        "categoria": precio.get("categoria"),
        "fuente": precio.get("fuente"),
        "precio_unitario": precio.get("precio_unitario"),
        "fecha_vigencia": precio.get("fecha_vigencia"),
        "fecha_vencimiento": precio.get("fecha_vencimiento"),
        "estado": precio.get("estado"),
        "es_aplicado": precio.get("es_aplicado"),
        "id_precio_corregido": precio.get("id_precio_corregido"),
        "evidencia_presente": bool(str(precio.get("evidencia") or "").strip()),
    }


def render(informe: dict) -> str:
    esc = informe["escenarios"][0]
    return f"""<!DOCTYPE html><html lang="es"><head><meta charset="utf-8"><title>TC-M06-G106</title>
<style>body{{font-family:Segoe UI,sans-serif;margin:2rem;line-height:1.45}}table{{border-collapse:collapse;width:100%}}
th,td{{border:1px solid #ccc;padding:.45rem .6rem;text-align:left;vertical-align:top}}th{{background:#f3f3f3}}.b{{font-weight:700}}
pre{{white-space:pre-wrap;background:#fafafa;padding:.8rem}}</style></head><body>
<h1>Módulo 6 — RF-89 / RF-94 — TC-M06-G106</h1>
<p>Corrección de precios e integridad del historial. Generado: {html.escape(informe['generado_en'])}. Escrituras de precios: no.</p>
<table>
<tr><th>Subcaso</th><td>TC-M06-30</td></tr>
<tr><th>Estado</th><td class="b">{html.escape(esc['estado'])}</td></tr>
<tr><th>Porcentaje</th><td>{informe['porcentaje_aprobacion']} %</td></tr>
<tr><th>Precios</th><td>{informe['total']}</td></tr>
<tr><th>POST de corrección</th><td>no enviado</td></tr>
</table>
<h2>Motivo</h2><p>{html.escape(esc['motivo'])}</p>
<h2>Contrato observado en el código</h2><pre>{html.escape(informe['contrato'])}</pre>
<h2>Precios</h2><pre>{html.escape(json.dumps(informe['precios'], ensure_ascii=False, indent=2))}</pre>
<h2>Auditoría</h2><pre>{html.escape(json.dumps(informe['auditoria'], ensure_ascii=False, indent=2))}</pre>
<h2>Hallazgos</h2><ul>{''.join(f'<li>{html.escape(h)}</li>' for h in informe['hallazgos'])}</ul>
</body></html>"""


def guardar(informe: dict) -> None:
    RESULTADOS.mkdir(parents=True, exist_ok=True)
    (RESULTADOS / "resultado_ejecucion_TC-M06-G106.html").write_text(render(informe), encoding="utf-8")
    (RESULTADOS / "resumen_ejecucion_TC-M06-G106.json").write_text(json.dumps(informe, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (RESULTADOS / "evidencia_peticiones_TC-M06-G106.json").write_text(json.dumps({
        "caso": "TC-M06-G106", "generado_en": informe["generado_en"], "peticiones": informe["peticiones"],
    }, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def main() -> int:
    inicio = time.perf_counter()
    peticiones = []
    contrato = (
        "POST /finanzas/precios inserta una fila nueva y responde 201. No hay PUT, PATCH ni DELETE de precios. "
        "El repositorio solo tiene INSERT. El trigger tgr_m06_07_inmutabilidad_precios rechaza UPDATE y DELETE. "
        "La corrección se expresa con id_precio_corregido, que apunta al registro original sin modificarlo. "
        "Si el nuevo precio queda vigente, la consulta lo marca aplicado y el anterior de la misma fuente puede quedar SUPERADO. "
        "También se registran PRECIO_REGISTRADO y, cuando corresponde, PRECIO_MARCADO_REEMPLAZADO. "
        "Un precio ACTIVO nuevo avisa a los contadores en otra transacción."
    )
    motivo = (
        "No se envió el POST. Corregir un precio crea otro registro en el catálogo compartido. "
        "Si su vigencia lo deja aplicable, cambia el precio usado por las simulaciones y puede generar auditoría y una notificación. "
        "No hay un catálogo aislado ni autorización para hacer esa escritura. "
        "Por eso no se pudo comparar el original antes y después de una corrección ejecutada en esta prueba."
    )
    hallazgos = [
        "BLOQUEO DE PRUEBA: el catálogo de precios de TEST es compartido y la corrección no puede ejecutarse sin aislamiento o autorización.",
        "QUESTION-M06-G78-01: el mensaje del trigger todavía nombra la columna id_precio_coregido. El contrato actual del DTO usa id_precio_corregido.",
    ]
    informe = {
        "caso": "TC-M06-G106", "subcaso": "TC-M06-30", "rf": ["RF-89", "RF-94"], "ambiente": BASE_API,
        "generado_en": datetime.now(timezone.utc).isoformat(), "contrato": contrato,
        "post_ejecutado": False, "total": None, "precios": [], "correcciones_previas": [], "auditoria": {},
        "escenarios": [{"subcaso": "TC-M06-30", "estado": "BLOQUEADO", "motivo": motivo, "post_ejecutado": False}],
        "peticiones": peticiones, "hallazgos": hallazgos,
        "aprobados": 0, "rechazados": 0, "bloqueados": 1, "porcentaje_aprobacion": 0,
    }
    correo, contrasena = os.environ.get("QA_CORREO"), os.environ.get("QA_CONTRASENA")
    if not correo or not contrasena:
        raise SystemExit("Defina QA_CORREO y QA_CONTRASENA.")
    codigo, login, duracion = pedir("POST", "/sesiones/", {"correo_electronico": correo, "contrasena": contrasena})
    token = login.get("token") if isinstance(login, dict) else None
    peticiones.append(evidencia("POST", "/sesiones/", codigo, duracion, limpiar(login if isinstance(login, dict) else {})))
    codigo_api, openapi, duracion = pedir("GET", "/openapi.json")
    caminos = ((openapi or {}).get("paths") or {}).get("/finanzas/precios") if codigo_api == 200 and isinstance(openapi, dict) else {}
    metodos = sorted(caminos.keys()) if isinstance(caminos, dict) else []
    informe["metodos_publicados"] = metodos
    peticiones.append(evidencia("GET", "/openapi.json", codigo_api, duracion, {"metodos_precios": metodos}))
    if codigo != 200 or not token:
        informe["escenarios"][0]["motivo"] = "No fue posible autenticar al Contador."
        guardar(informe)
        print("BLOQUEADO")
        return 2

    codigo, precios, duracion = pedir("GET", "/finanzas/precios", token=token)
    fichas = [ficha(p) for p in precios if isinstance(p, dict)] if isinstance(precios, list) else []
    informe["total"] = len(fichas)
    informe["precios"] = fichas
    informe["correcciones_previas"] = [p for p in fichas if p.get("id_precio_corregido")]
    informe["aplicados"] = [p for p in fichas if p.get("es_aplicado")]
    peticiones.append(evidencia("GET", "/finanzas/precios", codigo, duracion, {"total": len(fichas), "correcciones_previas": len(informe["correcciones_previas"]), "aplicados": informe["aplicados"]}))
    for tipo in ("PRECIO_REGISTRADO", "PRECIO_MARCADO_REEMPLAZADO"):
        ruta = f"/finanzas/auditoria?tipo_evento={tipo}&formato=TECNICO&tamano=1"
        codigo_aud, auditoria, duracion = pedir("GET", ruta, token=token)
        total = auditoria.get("total_registros") if isinstance(auditoria, dict) else None
        informe["auditoria"][tipo] = {"http": codigo_aud, "total": total}
        peticiones.append(evidencia("GET", ruta, codigo_aud, duracion, {"total_registros": total}))
    informe["duracion_ms"] = round((time.perf_counter() - inicio) * 1000)
    guardar(informe)
    print(f"TC-M06-30 BLOQUEADO total {informe['total']} correcciones_previas {len(informe['correcciones_previas'])} metodos {metodos}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
