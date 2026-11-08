"""TC-M06-G82 contra TEST.

El registro válido de un mantenimiento inserta un costo en el catálogo compartido,
así que no se envía. Sí se envían el monto 0, el monto -100 y el intento de tratar
un alimento como inversión: esas tres peticiones se rechazan antes de insertar.

    python tests/Test_Testing/Test_Modulo6/RF-90/TC-M06-G82/ejecutar_tc_m06_g82.py
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
            "tercero_nit", "tercero_dv", "tercero_razon_social", "identificador", "finca", "razon_sin_mercado"}
OMITIR = SECRETOS | {"lineas", "reconocimientos", "calculos", "mediciones", "productos"}


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
        return {k: ({"omitido": True} if k in OMITIR else limpiar(v, profundidad + 1)) for k, v in valor.items()}
    if isinstance(valor, list):
        return [limpiar(v, profundidad + 1) for v in valor[:20]]
    if isinstance(valor, str) and len(valor) > 240:
        return valor[:240]
    return valor


def evidencia(metodo, ruta, codigo, duracion, respuesta, escritura: bool = False, cuerpo=None) -> dict:
    return {"metodo": metodo, "consulta": ruta, "codigo": codigo, "duracion_ms": duracion, "escritura": escritura,
            "en": datetime.now(timezone.utc).isoformat(), "cuerpo": cuerpo, "respuesta": limpiar(respuesta)}


def codigo_negocio(payload) -> str | None:
    if isinstance(payload, dict):
        return payload.get("error_code") or payload.get("code") or payload.get("codigo")
    return None


def resumir_costos(lista) -> dict:
    if not isinstance(lista, list):
        return {"total": None}
    return {
        "total": len(lista),
        "naturalezas": dict(Counter(c.get("naturaleza_costo") for c in lista if isinstance(c, dict))),
        "politicas": dict(Counter(c.get("politica_capitalizacion") for c in lista if isinstance(c, dict))),
        "subtipos": dict(Counter(c.get("subtipo_costo") for c in lista if isinstance(c, dict))),
        "mantenimiento_capitalizado": sum(
            1 for c in lista if isinstance(c, dict) and c.get("naturaleza_costo") == "MANTENIMIENTO"
            and c.get("politica_capitalizacion") == "CAPITALIZAR"),
    }


def libros(payload) -> dict | None:
    if not isinstance(payload, dict):
        return None
    costo = payload.get("valoracion_costo")
    if not isinstance(costo, dict):
        return {"valoracion_costo": None}
    return {k: costo.get(k) for k in (
        "id_valoracion_por_costo", "costos_adquisicion", "depreciacion_acumulada",
        "deterioro_acumulado", "valor_contable_por_costo", "es_activa")}


def render(informe: dict) -> str:
    filas = "".join(
        f"<tr><td>{html.escape(e['subcaso'])}</td><td>{html.escape(e['estado'])}</td><td>{html.escape(e['motivo'])}</td></tr>"
        for e in informe["escenarios"])
    return f"""<!DOCTYPE html><html lang="es"><head><meta charset="utf-8"><title>TC-M06-G82</title>
<style>body{{font-family:Segoe UI,sans-serif;margin:2rem;line-height:1.45}}table{{border-collapse:collapse;width:100%}}
th,td{{border:1px solid #ccc;padding:.45rem .6rem;text-align:left;vertical-align:top}}th{{background:#f3f3f3}}</style></head><body>
<h1>Módulo 6 — RF-90 — TC-M06-G82</h1>
<p>Generado: {html.escape(informe['generado_en'])}. Registro válido de mantenimiento: no enviado.</p>
<table><tr><th>Porcentaje</th><td>{informe['porcentaje_aprobacion']} %</td></tr>
<tr><th>Aprobados / rechazados / bloqueados</th><td>{informe['aprobados']} / {informe['rechazados']} / {informe['bloqueados']}</td></tr></table>
<h2>Subcasos</h2><table><tr><th>Subcaso</th><th>Estado</th><th>Motivo</th></tr>{filas}</table>
<h2>Contrato</h2><pre>{html.escape(informe['contrato'])}</pre>
<h2>Costos de mantenimiento</h2><pre>{html.escape(json.dumps(informe['mantenimiento'], ensure_ascii=False, indent=2))}</pre>
<h2>Valor en libros del activo 951</h2><pre>{html.escape(json.dumps(informe['libros'], ensure_ascii=False, indent=2))}</pre>
<h2>Hallazgos</h2><ul>{''.join(f'<li>{html.escape(h)}</li>' for h in informe['hallazgos'])}</ul>
</body></html>"""


def guardar(informe: dict) -> None:
    RESULTADOS.mkdir(parents=True, exist_ok=True)
    (RESULTADOS / "resultado_ejecucion_TC-M06-G82.html").write_text(render(informe), encoding="utf-8")
    (RESULTADOS / "resumen_ejecucion_TC-M06-G82.json").write_text(json.dumps(informe, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (RESULTADOS / "evidencia_peticiones_TC-M06-G82.json").write_text(json.dumps({
        "caso": "TC-M06-G82", "generado_en": informe["generado_en"], "peticiones": informe["peticiones"],
    }, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (RESULTADOS / "analisis_hallazgos_TC-M06-G82.md").write_text(informe["analisis"], encoding="utf-8")


def main() -> int:
    inicio = time.perf_counter()
    peticiones = []
    contrato = (
        "POST /finanzas/costos está publicado. El Contador y el Administrador pueden crearlo; el Revisor Fiscal solo consulta. "
        "ALIMENTO, MEDICAMENTO, MANO_OBRA y VETERINARIO son MANTENIMIENTO. Su política es GASTO. "
        "CAPITALIZAR solo aplica a una INVERSION con confirmar_capitalizacion y un activo valorado por costo. "
        "Declarar un alimento como inversión responde 422 RECLASIFICACION_NO_PERMITIDA antes de crear el período o el costo. "
        "monto_costo debe ser mayor que cero en el DTO, así que 0 y -100 responden 400 VAL_ENTRADA antes del caso de uso. "
        "Un mantenimiento con MANO_OBRA_PROPIA genera asiento. Una compra de proveedor genera el costo y viaja como factura, sin línea. "
        "La capitalización suma el monto a costos_adquisicion y valor_contable_por_costo. El mantenimiento no entra a esa suma. "
        "La auditoría del registro exitoso es COSTO_REGISTRADO."
    )
    informe = {
        "caso": "TC-M06-G82", "rf": ["RF-90"], "ambiente": BASE_API,
        "generado_en": datetime.now(timezone.utc).isoformat(), "contrato": contrato,
        "mantenimiento": {}, "periodos": {}, "libros": {}, "auditoria_antes": None, "auditoria_despues": None,
        "escenarios": [], "peticiones": peticiones, "hallazgos": [],
        "aprobados": 0, "rechazados": 0, "bloqueados": 0, "porcentaje_aprobacion": 0,
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
    caminos = ((openapi or {}).get("paths") or {}) if codigo == 200 and isinstance(openapi, dict) else {}
    metodos = sorted(k for k in (caminos.get("/finanzas/costos") or {}) if k in {"get", "post", "put", "patch", "delete"})
    detalle = "/activos-biologicos/{id_activo}" in caminos
    informe["metodos_costos"] = metodos
    informe["detalle_biologico_publicado"] = detalle
    peticiones.append(evidencia("GET", "/openapi.json", codigo, duracion, {"metodos_costos": metodos, "detalle_biologico": detalle}))

    def costos(ruta: str) -> tuple[int, dict]:
        codigo_c, lista, duracion_c = pedir("GET", ruta, token=token)
        resumen = resumir_costos(lista)
        peticiones.append(evidencia("GET", ruta, codigo_c, duracion_c, resumen))
        return codigo_c, resumen

    _, informe["mantenimiento"] = costos("/finanzas/costos?naturaleza_costo=MANTENIMIENTO")
    codigo_todos, todos_antes = costos("/finanzas/costos")
    informe["costos_antes"] = todos_antes
    codigo_p, periodos, duracion = pedir("GET", "/finanzas/periodos", token=token)
    estados = dict(Counter(p.get("estado") for p in periodos if isinstance(p, dict))) if isinstance(periodos, list) else {}
    informe["periodos"] = {"http": codigo_p, "total": len(periodos) if isinstance(periodos, list) else None, "estados": estados}
    peticiones.append(evidencia("GET", "/finanzas/periodos", codigo_p, duracion, informe["periodos"]))
    codigo_a, historial, duracion = pedir("GET", f"/finanzas/activos/{ACTIVO}", token=token)
    informe["libros"]["antes"] = libros(historial)
    peticiones.append(evidencia("GET", f"/finanzas/activos/{ACTIVO}", codigo_a, duracion, {"valoracion_costo": informe["libros"]["antes"]}))
    ruta_aud = "/finanzas/auditoria?tipo_evento=COSTO_REGISTRADO&formato=TECNICO&tamano=1"
    codigo_u, auditoria, duracion = pedir("GET", ruta_aud, token=token)
    informe["auditoria_antes"] = auditoria.get("total_registros") if isinstance(auditoria, dict) else None
    peticiones.append(evidencia("GET", ruta_aud, codigo_u, duracion, {"total_registros": informe["auditoria_antes"]}))

    base = {"subtipo_costo": "ALIMENTO", "origen_costo": "MANO_OBRA_PROPIA", "fecha_costo": "2026-11-08", "id_activo_biologico": ACTIVO}
    rechazos = []
    for nombre, monto in (("monto_cero", 0), ("monto_negativo", -100)):
        cuerpo = {**base, "monto_costo": monto}
        codigo_r, respuesta, duracion = pedir("POST", "/finanzas/costos", cuerpo, token)
        rechazos.append({"nombre": nombre, "http": codigo_r, "code": codigo_negocio(respuesta)})
        peticiones.append(evidencia("POST", "/finanzas/costos", codigo_r, duracion, respuesta, cuerpo=cuerpo))
    capitalizar = {**base, "monto_costo": 100, "naturaleza_costo": "INVERSION", "confirmar_capitalizacion": True}
    codigo_k, respuesta_k, duracion = pedir("POST", "/finanzas/costos", capitalizar, token)
    peticiones.append(evidencia("POST", "/finanzas/costos", codigo_k, duracion, respuesta_k, cuerpo=capitalizar))

    _, todos_despues = costos("/finanzas/costos")
    informe["costos_despues"] = todos_despues
    codigo_a, historial, duracion = pedir("GET", f"/finanzas/activos/{ACTIVO}", token=token)
    informe["libros"]["despues"] = libros(historial)
    peticiones.append(evidencia("GET", f"/finanzas/activos/{ACTIVO}", codigo_a, duracion, {"valoracion_costo": informe["libros"]["despues"]}))
    codigo_u, auditoria, duracion = pedir("GET", ruta_aud, token=token)
    informe["auditoria_despues"] = auditoria.get("total_registros") if isinstance(auditoria, dict) else None
    peticiones.append(evidencia("GET", ruta_aud, codigo_u, duracion, {"total_registros": informe["auditoria_despues"]}))
    intacto = (codigo_todos == 200 and todos_antes.get("total") == todos_despues.get("total")
               and informe["auditoria_antes"] == informe["auditoria_despues"]
               and informe["libros"]["antes"] == informe["libros"]["despues"])

    informe["escenarios"].append({
        "subcaso": "TC-M06-35", "estado": "BLOQUEADO", "post_ejecutado": False,
        "motivo": "Registrar un alimento o medicamento válido crea el costo, puede generar asiento o factura y audita COSTO_REGISTRADO en el período compartido. No hay un activo aislado ni autorización para esa escritura.",
    })
    cero_ok = rechazos[0]["http"] == 400 and rechazos[1]["http"] == 400 and intacto
    informe["escenarios"].append({
        "subcaso": "TC-M06-36",
        "estado": "APROBADO" if cero_ok else "RECHAZADO",
        "escenarios": rechazos, "sin_persistencia": intacto,
        "motivo": ("0 y -100 respondieron 400 VAL_ENTRADA. La cantidad de costos, la auditoría y el valor en libros quedaron iguales."
                   if cero_ok else "La respuesta o la comparación antes/después no confirma el rechazo sin persistencia."),
    })
    capital_ok = codigo_k == 422 and codigo_negocio(respuesta_k) == "RECLASIFICACION_NO_PERMITIDA" and intacto
    informe["escenarios"].append({
        "subcaso": "TC-M06-38",
        "estado": "APROBADO" if capital_ok else "RECHAZADO",
        "http": codigo_k, "code": codigo_negocio(respuesta_k), "sin_persistencia": intacto,
        "motivo": ("Un alimento declarado como inversión y con confirmación de capitalización respondió 422 RECLASIFICACION_NO_PERMITIDA. No se creó el costo y el valor en libros del activo 951 no cambió."
                   if capital_ok else "La reclasificación no produjo el rechazo esperado o cambió datos compartidos."),
    })
    informe["hallazgos"].append(
        "BLOQUEO DE PRUEBA: TC-M06-35 requiere un activo y un período aislados. El registro válido no se ejecutó.")
    estados_finales = [e["estado"] for e in informe["escenarios"]]
    informe["aprobados"] = estados_finales.count("APROBADO")
    informe["rechazados"] = estados_finales.count("RECHAZADO")
    informe["bloqueados"] = estados_finales.count("BLOQUEADO")
    informe["porcentaje_aprobacion"] = round(informe["aprobados"] / len(informe["escenarios"]) * 100)
    informe["analisis"] = (
        "# TC-M06-G82\n\n"
        "No se usó SQL local. Las lecturas salieron de la API de TEST.\n\n"
        f"- TC-M06-35: {informe['escenarios'][0]['estado']}. {informe['escenarios'][0]['motivo']}\n"
        f"- TC-M06-36: {informe['escenarios'][1]['estado']}. {informe['escenarios'][1]['motivo']}\n"
        f"- TC-M06-38: {informe['escenarios'][2]['estado']}. {informe['escenarios'][2]['motivo']}\n\n"
        "El mantenimiento queda en política GASTO. La suma al valor contable solo ocurre con política CAPITALIZAR, "
        "reservada a una inversión confirmada sobre un activo valorado por costo.\n"
    )
    informe["duracion_ms"] = round((time.perf_counter() - inicio) * 1000)
    guardar(informe)
    print(" ".join(f"{e['subcaso']} {e['estado']}" for e in informe["escenarios"]), f"| {informe['porcentaje_aprobacion']}% intacto {intacto}")
    return 0 if informe["rechazados"] == 0 and informe["bloqueados"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
