"""TC-M06-G112 contra TEST.

No se registra una inversión válida: capitalizar o llevarla a gasto cambia
datos compartidos. Solo se envían montos no positivos y justificaciones
insuficientes, porque se rechazan antes de insertar.

    python tests/Test_Testing/Test_Modulo6/RF-90/TC-M06-G112/ejecutar_tc_m06_g112.py
"""
from __future__ import annotations

import html
import json
import os
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

CARPETA = Path(__file__).resolve().parent
RESULTADOS = CARPETA / "resultados"
BASE_API = "https://api.inmero.co/api-sgpmp-test"
ZONA = "America/Bogota"
ACTIVO = 951
SECRETOS = {"token", "access_token", "contrasena", "password", "hash_integridad", "numero_id_tributaria",
            "identificador", "finca", "infraestructura", "razon_sin_mercado", "tercero_nit", "tercero_razon_social"}


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
        with urllib.request.urlopen(req, timeout=90) as resp:
            raw = resp.read().decode()
            payload = json.loads(raw) if raw else None
            codigo = resp.status
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"message": raw[:240]}
        codigo = exc.code
    return codigo, payload, round((time.perf_counter() - inicio) * 1000)


def limpiar(valor, profundidad: int = 0):
    if profundidad > 4:
        return "..."
    if isinstance(valor, dict):
        return {k: ({"omitido": True} if k in SECRETOS else limpiar(v, profundidad + 1)) for k, v in valor.items()}
    if isinstance(valor, list):
        return [limpiar(v, profundidad + 1) for v in valor[:20]]
    if isinstance(valor, str) and len(valor) > 240:
        return valor[:240]
    return valor


def evidencia(metodo, ruta, codigo, duracion, respuesta, cuerpo=None) -> dict:
    return {"metodo": metodo, "consulta": ruta, "codigo": codigo, "duracion_ms": duracion, "escritura": False,
            "en": datetime.now(timezone.utc).isoformat(), "cuerpo": cuerpo, "respuesta": limpiar(respuesta)}


def negocio(payload) -> str | None:
    if isinstance(payload, dict):
        return payload.get("error_code") or payload.get("code")
    return None


def ficha_activo(a: dict) -> dict:
    return {k: a.get(k) for k in (
        "id_activo_biologico", "especie", "estado", "indicador_reconocimiento", "valorado_por_costo",
        "costo_base", "valor_contable_por_costo", "depreciacion_acumulada", "deterioro_acumulado",
        "valor_razonable_neto", "fecha_calculo")}


def resumir_costos(lista) -> dict:
    if not isinstance(lista, list):
        return {"total": None}
    return {"total": len(lista),
            "subtipos": dict(Counter(c.get("subtipo_costo") for c in lista if isinstance(c, dict))),
            "politicas": dict(Counter(c.get("politica_capitalizacion") for c in lista if isinstance(c, dict)))}


def matriz_relevante(config) -> list[dict]:
    filas = config.get("matriz") if isinstance(config, dict) else []
    salida = []
    for fila in filas or []:
        if not isinstance(fila, dict):
            continue
        texto = " ".join(str(fila.get(k) or "") for k in ("tipo_hecho", "sentido", "subtipo_costo"))
        if any(clave in texto for clave in ("CAPITALIZACION", "INVERSION", "MANO_OBRA")):
            salida.append({k: fila.get(k) for k in (
                "tipo_hecho", "sentido", "id_especie", "subtipo_costo", "cuenta_debito", "cuenta_credito")})
    return salida


def render(informe: dict) -> str:
    filas = "".join(
        f"<tr><td>{html.escape(e['subcaso'])}</td><td>{html.escape(e['estado'])}</td><td>{html.escape(e['motivo'])}</td></tr>"
        for e in informe["escenarios"])
    return f"""<!DOCTYPE html><html lang="es"><head><meta charset="utf-8"><title>TC-M06-G112</title>
<style>body{{font-family:Segoe UI,sans-serif;margin:2rem;line-height:1.45}}table{{border-collapse:collapse;width:100%}}
th,td{{border:1px solid #ccc;padding:.45rem .6rem;text-align:left;vertical-align:top}}th{{background:#f3f3f3}}
pre{{white-space:pre-wrap}}</style></head><body>
<h1>Módulo 6 — RF-90 / RF-109 / RF-93 — TC-M06-G112</h1>
<p>Generado: {html.escape(informe['generado_en'])}. Inversión válida: no registrada.</p>
<table><tr><th>Porcentaje</th><td>{informe['porcentaje_aprobacion']} %</td></tr>
<tr><th>Aprobados / rechazados / bloqueados</th><td>{informe['aprobados']} / {informe['rechazados']} / {informe['bloqueados']}</td></tr></table>
<h2>Subcasos</h2><table><tr><th>Subcaso</th><th>Estado</th><th>Motivo</th></tr>{filas}</table>
<h2>Contrato</h2><pre>{html.escape(informe['contrato'])}</pre>
<h2>Complementos rechazados</h2><pre>{html.escape(json.dumps(informe['complementos'], ensure_ascii=False, indent=2))}</pre>
<h2>Activo 951</h2><pre>{html.escape(json.dumps(informe['activo_951'], ensure_ascii=False, indent=2))}</pre>
<h2>Hallazgos</h2><ul>{''.join(f'<li>{html.escape(h)}</li>' for h in informe['hallazgos'])}</ul>
</body></html>"""


def guardar(informe: dict) -> None:
    RESULTADOS.mkdir(parents=True, exist_ok=True)
    (RESULTADOS / "resultado_ejecucion_TC-M06-G112.html").write_text(render(informe), encoding="utf-8")
    (RESULTADOS / "resumen_ejecucion_TC-M06-G112.json").write_text(json.dumps(informe, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (RESULTADOS / "evidencia_peticiones_TC-M06-G112.json").write_text(json.dumps({
        "caso": "TC-M06-G112", "generado_en": informe["generado_en"], "peticiones": informe["peticiones"],
    }, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (RESULTADOS / "analisis_hallazgos_TC-M06-G112.md").write_text(informe["analisis"], encoding="utf-8")


def main() -> int:
    inicio = time.perf_counter()
    peticiones = []
    contrato = (
        "La inversión directa es el subtipo INVERSION_DIRECTA y su naturaleza es INVERSION. "
        "No hay una política global CAPITALIZAR o GASTO. La política sale de la solicitud: "
        "confirmar_capitalizacion en true capitaliza solo si el activo tiene valoración por costo activa; "
        "en un activo a valor razonable responde CAPITALIZACION_NO_PERMITIDA. Sin esa confirmación, la política es GASTO. "
        "Capitalizar suma el monto a costos_adquisicion y valor_contable_por_costo. No modifica el valor razonable. "
        "El asiento, cuando el origen es mano de obra propia, usa el hecho MANO_OBRA_PROPIA y el sentido CAPITALIZACION o UNICO. "
        "Una compra a proveedor no genera línea: viaja como factura. "
        "La justificación de una inversión debe tener al menos 10 caracteres y se exige antes de consultar el período. "
        "El monto debe ser mayor que cero en el DTO. "
        "RF-109 es la matriz de cuentas en la configuración contable. "
        "RF-93, al armar el estado de resultados, trata como gasto la inversión con política GASTO y excluye la capitalizada. "
        "El estado de resultados se genera sobre períodos cerrados."
    )
    informe = {
        "caso": "TC-M06-G112", "rf": ["RF-90", "RF-109", "RF-93"], "ambiente": BASE_API,
        "generado_en": datetime.now(timezone.utc).isoformat(), "contrato": contrato,
        "activos": [], "inversiones": {}, "matriz": [], "complementos": [], "activo_951": {},
        "escenarios": [], "peticiones": peticiones,
        "hallazgos": ["BLOQUEO DE PRUEBA: no hay un activo ni un período aislados para registrar una inversión. Capitalizar cambia el costo del activo 951 y el gasto crea un asiento en el período compartido."],
        "aprobados": 0, "rechazados": 0, "bloqueados": 2, "porcentaje_aprobacion": 0,
    }
    correo, contrasena = os.environ.get("QA_CORREO"), os.environ.get("QA_CONTRASENA")
    if not correo or not contrasena:
        raise SystemExit("Defina QA_CORREO y QA_CONTRASENA.")
    codigo, login, duracion = pedir("POST", "/sesiones/", {"correo_electronico": correo, "contrasena": contrasena})
    token = login.get("token") if isinstance(login, dict) else None
    peticiones.append(evidencia("POST", "/sesiones/", codigo, duracion, limpiar(login if isinstance(login, dict) else {})))
    if codigo != 200 or not token:
        guardar(informe)
        print("SIN SESION")
        return 2

    codigo, openapi, duracion = pedir("GET", "/openapi.json")
    caminos = (openapi or {}).get("paths") or {} if codigo == 200 and isinstance(openapi, dict) else {}
    informe["rutas"] = {
        "/finanzas/costos": sorted(k for k in (caminos.get("/finanzas/costos") or {}) if k in {"get", "post"}),
        "/finanzas/configuracion/matriz": sorted(k for k in (caminos.get("/finanzas/configuracion/matriz") or {}) if k in {"get", "post"}),
        "/finanzas/periodos/{id_periodo_contable}/estados-resultados": sorted(
            k for k in (caminos.get("/finanzas/periodos/{id_periodo_contable}/estados-resultados") or {}) if k in {"get", "post"}),
    }
    peticiones.append(evidencia("GET", "/openapi.json", codigo, duracion, informe["rutas"]))
    codigo, config, duracion = pedir("GET", "/finanzas/configuracion", token=token)
    informe["matriz"] = matriz_relevante(config if isinstance(config, dict) else {})
    peticiones.append(evidencia("GET", "/finanzas/configuracion", codigo, duracion, {"matriz_relevante": len(informe["matriz"])}))
    codigo, activos, duracion = pedir("GET", "/finanzas/activos", token=token)
    fichas = [ficha_activo(a) for a in activos if isinstance(a, dict)] if isinstance(activos, list) else []
    informe["activos"] = fichas
    informe["activo_951"]["antes"] = next((a for a in fichas if a.get("id_activo_biologico") == ACTIVO), None)
    peticiones.append(evidencia("GET", "/finanzas/activos", codigo, duracion, {
        "total": len(fichas), "a_costo": sum(1 for a in fichas if a.get("valorado_por_costo")),
        "activo_951": informe["activo_951"]["antes"]}))
    codigo, costos, duracion = pedir("GET", "/finanzas/costos?subtipo_costo=INVERSION_DIRECTA", token=token)
    informe["inversiones"] = resumir_costos(costos)
    peticiones.append(evidencia("GET", "/finanzas/costos?subtipo_costo=INVERSION_DIRECTA", codigo, duracion, informe["inversiones"]))
    codigo, todos, duracion = pedir("GET", "/finanzas/costos", token=token)
    antes = resumir_costos(todos)
    peticiones.append(evidencia("GET", "/finanzas/costos", codigo, duracion, antes))
    ruta_aud = "/finanzas/auditoria?tipo_evento=COSTO_REGISTRADO&formato=TECNICO&tamano=1"
    codigo, auditoria, duracion = pedir("GET", ruta_aud, token=token)
    auditoria_antes = auditoria.get("total_registros") if isinstance(auditoria, dict) else None
    peticiones.append(evidencia("GET", ruta_aud, codigo, duracion, {"total_registros": auditoria_antes}))

    base = {"subtipo_costo": "INVERSION_DIRECTA", "origen_costo": "MANO_OBRA_PROPIA", "monto_costo": 100,
            "fecha_costo": "2026-11-08", "id_activo_biologico": ACTIVO, "confirmar_capitalizacion": True}
    complementos = [
        ("monto_cero", {**base, "monto_costo": 0, "justificacion": "Justificacion de prueba suficiente."}),
        ("monto_negativo", {**base, "monto_costo": -100, "justificacion": "Justificacion de prueba suficiente."}),
        ("sin_justificacion", {k: v for k, v in base.items()}),
        ("justificacion_vacia", {**base, "justificacion": ""}),
        ("justificacion_corta", {**base, "justificacion": "corta"}),
    ]
    for nombre, cuerpo in complementos:
        codigo_r, respuesta, duracion = pedir("POST", "/finanzas/costos", cuerpo, token)
        informe["complementos"].append({"nombre": nombre, "http": codigo_r, "code": negocio(respuesta)})
        peticiones.append(evidencia("POST", "/finanzas/costos", codigo_r, duracion, respuesta, cuerpo))
        if codigo_r in (200, 201):
            break
    codigo, todos, duracion = pedir("GET", "/finanzas/costos", token=token)
    despues = resumir_costos(todos)
    peticiones.append(evidencia("GET", "/finanzas/costos", codigo, duracion, despues))
    codigo, auditoria, duracion = pedir("GET", ruta_aud, token=token)
    auditoria_despues = auditoria.get("total_registros") if isinstance(auditoria, dict) else None
    peticiones.append(evidencia("GET", ruta_aud, codigo, duracion, {"total_registros": auditoria_despues}))
    codigo, historial, duracion = pedir("GET", f"/finanzas/activos/{ACTIVO}", token=token)
    valoracion = (historial or {}).get("valoracion_costo") if isinstance(historial, dict) else None
    informe["activo_951"]["despues"] = {k: valoracion.get(k) for k in (
        "costos_adquisicion", "valor_contable_por_costo", "depreciacion_acumulada", "deterioro_acumulado")} if isinstance(valoracion, dict) else None
    peticiones.append(evidencia("GET", f"/finanzas/activos/{ACTIVO}", codigo, duracion, informe["activo_951"]["despues"]))
    informe["sin_persistencia"] = antes.get("total") == despues.get("total") and auditoria_antes == auditoria_despues
    motivo = (
        "Registrar la inversión con justificación válida y confirmación sumaría el monto al costo del activo compartido 951. "
        "Sin confirmación la dejaría como gasto y crearía el asiento en el período compartido. "
        "No hay un activo aislado. El período que contiene hoy está cerrado y el abierto siguiente empieza en diciembre."
    )
    for subcaso in ("TC-M06-39", "TC-M06-40"):
        informe["escenarios"].append({"subcaso": subcaso, "estado": "BLOQUEADO", "post_valido": False, "motivo": motivo})
    informe["analisis"] = (
        "# TC-M06-G112\n\nNo se usó SQL local. No se registró una inversión válida.\n\n"
        "- TC-M06-39 CAPITALIZAR: BLOQUEADO.\n- TC-M06-40 GASTO: BLOQUEADO.\n\n"
        "Los complementos de monto y justificación se rechazaron antes de insertar.\n"
        + "\n".join(f"- {c['nombre']}: {c['http']} {c['code']}" for c in informe["complementos"])
        + f"\n\nPersistencia intacta: {informe['sin_persistencia']}.\n"
    )
    informe["duracion_ms"] = round((time.perf_counter() - inicio) * 1000)
    guardar(informe)
    print("TC-M06-39 BLOQUEADO TC-M06-40 BLOQUEADO",
          " ".join(f"{c['nombre']} {c['http']}" for c in informe["complementos"]),
          f"intacto {informe['sin_persistencia']}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
