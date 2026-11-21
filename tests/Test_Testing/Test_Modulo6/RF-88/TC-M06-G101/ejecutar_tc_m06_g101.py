"""TC-M06-G101 contra TEST.

TC-M06-14 no se envía: el cambio a valor razonable confirma valoración, asiento
y auditoría sobre el titular compartido.

TC-M06-15 solo se envía si el activo está a costo, no tiene precio vigente y el
período que usaría el caso de uso ya existe. En ese camino la valoración no
escribe y el 422 revierte la sesión.

    python tests/Test_Testing/Test_Modulo6/RF-88/TC-M06-G101/ejecutar_tc_m06_g101.py
"""
from __future__ import annotations

import html
import json
import os
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

CARPETA = Path(__file__).resolve().parent
RESULTADOS = CARPETA / "resultados"
BASE_API = "https://api.inmero.co/api-sgpmp-test"
ZONA = "America/Bogota"
SECRETOS = {
    "token", "access_token", "contrasena", "password", "hash_integridad",
    "numero_id_tributaria", "finca", "identificador", "razon_social", "correo_electronico",
}
VALORABLES = {"ACTIVO", "EN_TRATAMIENTO"}


def hoy_bogota() -> date:
    return datetime.now(timezone(timedelta(hours=-5))).date()


def pedir(metodo: str, ruta: str, cuerpo: dict | None = None, token: str | None = None):
    datos = None if cuerpo is None else json.dumps(cuerpo).encode("utf-8")
    headers = {"Accept": "application/json", "X-Zona-Horaria": ZONA}
    if cuerpo is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(BASE_API + ruta, data=datos, headers=headers, method=metodo)
    inicio = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8")
            payload = json.loads(raw) if raw else None
            codigo = resp.status
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"message": raw[:240]}
        codigo = exc.code
    duracion = round((time.perf_counter() - inicio) * 1000)
    return codigo, payload, duracion


def limpiar(valor, profundidad: int = 0):
    if profundidad > 6:
        return "..."
    if isinstance(valor, dict):
        return {k: limpiar(v, profundidad + 1) for k, v in valor.items() if k not in SECRETOS}
    if isinstance(valor, list):
        return [limpiar(v, profundidad + 1) for v in valor[:30]]
    if isinstance(valor, str) and len(valor) > 300:
        return valor[:300]
    return valor


def autenticar() -> tuple[int, str | None, dict]:
    correo = os.environ.get("QA_CORREO")
    contrasena = os.environ.get("QA_CONTRASENA")
    if not correo or not contrasena:
        raise SystemExit("Defina QA_CORREO y QA_CONTRASENA en el entorno. No las escriba en el archivo.")
    codigo, payload, duracion = pedir("POST", "/sesiones/", {"correo_electronico": correo, "contrasena": contrasena})
    token = payload.get("token") if isinstance(payload, dict) else None
    publico = limpiar(payload if isinstance(payload, dict) else {})
    if isinstance(publico, dict):
        publico["duracion_ms"] = duracion
    return codigo, token, publico if isinstance(publico, dict) else {}


def fecha(valor) -> date | None:
    if not isinstance(valor, str) or len(valor) < 10:
        return None
    try:
        return date.fromisoformat(valor[:10])
    except ValueError:
        return None


def decision_periodo(periodos: list[dict], dia: date) -> dict:
    limpios = []
    for periodo in periodos:
        inicio = fecha(periodo.get("fecha_inicio"))
        fin = fecha(periodo.get("fecha_fin"))
        if inicio is None or fin is None:
            continue
        limpios.append({
            "id": periodo.get("id_periodo_contable"),
            "estado": periodo.get("estado"),
            "inicio": inicio,
            "fin": fin,
        })
    contiene = [p for p in limpios if p["inicio"] <= dia <= p["fin"]]
    resumen = [{"id": p["id"], "estado": p["estado"], "inicio": p["inicio"].isoformat(), "fin": p["fin"].isoformat()} for p in limpios]
    if any(p["estado"] == "ABIERTO" for p in contiene):
        return {"crea_periodo": False, "en_cierre": False, "motivo": "Hay un período ABIERTO que contiene hoy. El caso de uso lo reutiliza.", "periodos": resumen}
    if any(p["estado"] == "EN_CIERRE" for p in contiene):
        return {"crea_periodo": False, "en_cierre": True, "motivo": "El período de hoy está EN_CIERRE. El POST no evaluaría el precio.", "periodos": resumen}
    if not contiene:
        if not any(p["inicio"] > dia for p in limpios):
            return {"crea_periodo": True, "en_cierre": False, "motivo": "No hay período para hoy ni posteriores. El caso de uso insertaría uno antes de valorar.", "periodos": resumen}
        if any(p["estado"] == "ABIERTO" and p["fin"] >= dia for p in limpios):
            return {"crea_periodo": False, "en_cierre": False, "motivo": "Hoy no cae en un período, pero ya existe uno abierto posterior.", "periodos": resumen}
        return {"crea_periodo": True, "en_cierre": False, "motivo": "No hay período abierto reutilizable.", "periodos": resumen}
    desde = max(p["fin"] for p in contiene)
    if any(p["estado"] == "ABIERTO" and p["fin"] >= desde for p in limpios):
        return {"crea_periodo": False, "en_cierre": False, "motivo": "El período de hoy está cerrado y ya existe uno abierto posterior. No se inserta otro.", "periodos": resumen}
    return {"crea_periodo": True, "en_cierre": False, "motivo": "El período de hoy está cerrado y no hay uno abierto posterior. El caso de uso insertaría el siguiente.", "periodos": resumen}


def permiso_actualizar(permisos: dict) -> bool:
    pares = permisos.get("permisos") if isinstance(permisos, dict) else None
    if not isinstance(pares, list):
        return False
    return any(
        isinstance(p, dict) and p.get("nombre_recurso") == "valoracion_por_costo" and p.get("id_accion") == 3
        for p in pares
    )


def evidencia(metodo: str, ruta: str, codigo: int, duracion: int, respuesta, escritura: bool = False) -> dict:
    return {
        "metodo": metodo,
        "consulta": ruta,
        "codigo": codigo,
        "duracion_ms": duracion,
        "lectura": not escritura,
        "escritura": escritura,
        "en": datetime.now(timezone.utc).isoformat(),
        "respuesta": limpiar(respuesta),
    }


def resumir_precio(payload) -> dict:
    if not isinstance(payload, list):
        return {"http_util": False, "total": None}
    vigentes = [p for p in payload if isinstance(p, dict) and str(p.get("estado") or "").upper() in {"VIGENTE", "ACTIVO", "APLICADO"}]
    elegido = vigentes[0] if vigentes else None
    return {
        "total": len(payload),
        "vigentes_o_aplicados": len(vigentes),
        "fuente": None if elegido is None else elegido.get("fuente"),
        "estado_precio": None if elegido is None else elegido.get("estado"),
        "precio_unitario": None if elegido is None else elegido.get("precio_unitario"),
    }


def foto(token: str, id_activo: int, id_especie: int | None) -> tuple[list[dict], dict]:
    llamadas = [
        ("financiero", "GET", f"/finanzas/activos/{id_activo}", False),
        ("simulacion", "GET", f"/finanzas/activos/{id_activo}/simulacion", False),
        ("auditoria", "GET", f"/finanzas/auditoria?id_activo_biologico={id_activo}&formato=TECNICO&tamano=100", False),
        ("metodo", "GET", f"/finanzas/auditoria?id_activo_biologico={id_activo}&tipo_evento=METODO_VALORACION_CAMBIADO&formato=TECNICO&tamano=100", False),
    ]
    if id_especie:
        llamadas.append(("precios", "GET", f"/finanzas/precios?id_especie={id_especie}", False))
    evidencias = []
    crudo = {}
    for nombre, metodo, ruta, escritura in llamadas:
        codigo, payload, duracion = pedir(metodo, ruta, token=token)
        crudo[nombre] = payload if codigo == 200 else {"http": codigo}
        evidencias.append(evidencia(metodo, ruta, codigo, duracion, resumir_respuesta(nombre, codigo, payload), escritura))
        crudo[nombre + "_http"] = codigo
    return evidencias, armar_foto(id_activo, crudo)


def resumir_respuesta(nombre: str, codigo: int, payload) -> dict:
    if codigo != 200:
        return limpiar(payload) if isinstance(payload, dict) else {"codigo": codigo}
    if nombre == "simulacion" and isinstance(payload, dict):
        precio = payload.get("precio") if isinstance(payload.get("precio"), dict) else {}
        calculo = payload.get("calculo") if isinstance(payload.get("calculo"), dict) else {}
        return {
            "es_valido": payload.get("es_valido"),
            "motivo": payload.get("motivo"),
            "mensaje": payload.get("mensaje"),
            "fuente": precio.get("fuente"),
            "precio_unitario": precio.get("precio_unitario"),
            "valor_neto": calculo.get("valor_neto"),
            "estado_calculo": calculo.get("estado"),
        }
    if nombre == "financiero" and isinstance(payload, dict):
        return {
            "estado": (payload.get("activo") or {}).get("estado") if isinstance(payload.get("activo"), dict) else None,
            "valoracion_costo": bool(payload.get("valoracion_costo")),
            "lineas": len(payload.get("lineas") or []),
            "calculos": len(payload.get("calculos") or []),
        }
    if nombre in {"auditoria", "metodo"} and isinstance(payload, dict):
        return {"total_registros": payload.get("total_registros")}
    if nombre == "precios":
        return resumir_precio(payload)
    return {"tipo": type(payload).__name__}


def armar_foto(id_activo: int, crudo: dict) -> dict:
    fin = crudo.get("financiero") if isinstance(crudo.get("financiero"), dict) else {}
    activo = fin.get("activo") if isinstance(fin.get("activo"), dict) else {}
    costo = fin.get("valoracion_costo") if isinstance(fin.get("valoracion_costo"), dict) else {}
    lineas = fin.get("lineas") if isinstance(fin.get("lineas"), list) else []
    calculos = fin.get("calculos") if isinstance(fin.get("calculos"), list) else []
    sim = crudo.get("simulacion") if isinstance(crudo.get("simulacion"), dict) else {}
    precio = sim.get("precio") if isinstance(sim.get("precio"), dict) else {}
    calculo = sim.get("calculo") if isinstance(sim.get("calculo"), dict) else {}
    aud = crudo.get("auditoria") if isinstance(crudo.get("auditoria"), dict) else {}
    metodo = crudo.get("metodo") if isinstance(crudo.get("metodo"), dict) else {}
    tipos = {}
    for linea in lineas:
        if isinstance(linea, dict):
            clave = str(linea.get("tipo_hecho") or "SIN_TIPO")
            tipos[clave] = tipos.get(clave, 0) + 1
    return {
        "id_activo_biologico": id_activo,
        "financiero_http": crudo.get("financiero_http"),
        "simulacion_http": crudo.get("simulacion_http"),
        "tiene_titular": bool(activo.get("numero_id_tributaria")),
        "estado": activo.get("estado"),
        "id_especie": activo.get("id_especie"),
        "especie": activo.get("especie"),
        "metodo": "COSTO" if costo.get("es_activa") else ("SIN_COSTO_ACTIVO" if crudo.get("financiero_http") == 200 else None),
        "es_activa": costo.get("es_activa"),
        "id_valoracion_por_costo": costo.get("id_valoracion_por_costo"),
        "costos_adquisicion": costo.get("costos_adquisicion"),
        "depreciacion_acumulada": costo.get("depreciacion_acumulada"),
        "deterioro_acumulado": costo.get("deterioro_acumulado"),
        "valor_contable_por_costo": costo.get("valor_contable_por_costo"),
        "vida_util_meses": costo.get("vida_util_meses"),
        "reconocimientos": len(fin.get("reconocimientos") or []) if isinstance(fin.get("reconocimientos"), list) else None,
        "lineas_total": len(lineas),
        "lineas_por_tipo": tipos,
        "variacion_vr_pm": tipos.get("VARIACION_VR_PM", 0),
        "calculos": len(calculos),
        "es_valido": sim.get("es_valido"),
        "motivo": sim.get("motivo"),
        "mensaje_simulacion": sim.get("mensaje"),
        "fuente_precio": precio.get("fuente"),
        "precio_unitario": precio.get("precio_unitario"),
        "costos_venta_simulados": {
            "transporte": calculo.get("costo_transporte"),
            "comisiones": calculo.get("costo_comisiones"),
            "impuestos": calculo.get("costo_impuestos_transaccion"),
            "otros": calculo.get("otros_costos_disposicion"),
        } if calculo else None,
        "valor_neto_simulado": calculo.get("valor_neto"),
        "estado_calculo": calculo.get("estado"),
        "auditoria_total": aud.get("total_registros"),
        "auditoria_metodo": metodo.get("total_registros"),
        "precios": resumir_precio(crudo.get("precios")) if crudo.get("precios_http") == 200 else {"http": crudo.get("precios_http")},
    }


def comparar(antes: dict, despues: dict) -> dict:
    claves = [
        "estado", "metodo", "es_activa", "id_valoracion_por_costo", "costos_adquisicion",
        "depreciacion_acumulada", "deterioro_acumulado", "valor_contable_por_costo",
        "lineas_total", "variacion_vr_pm", "calculos", "auditoria_total", "auditoria_metodo",
    ]
    diferencias = {clave: {"antes": antes.get(clave), "despues": despues.get(clave)} for clave in claves if antes.get(clave) != despues.get(clave)}
    return {"sin_cambios": not diferencias, "diferencias": diferencias}


def escenario_base(subcaso: str, objetivo: str) -> dict:
    return {
        "subcaso": subcaso,
        "objetivo": objetivo,
        "endpoint": "POST /finanzas/activos/{id_activo_biologico}/valor-razonable",
        "cuerpo": None,
        "post_ejecutado": False,
        "activo": None,
        "antes": None,
        "despues": None,
        "comparacion": None,
        "http_obtenido": None,
        "codigo_negocio": None,
        "mensaje": None,
        "duracion_ms": None,
        "estado": "BLOQUEADO",
        "motivo": "",
    }


def render(informe: dict) -> str:
    filas = []
    for esc in informe["escenarios"]:
        filas.append(
            "<tr>"
            f"<td>{html.escape(esc['subcaso'])}</td>"
            f"<td>{html.escape(str(esc.get('activo')))}</td>"
            f"<td>{'sí' if esc['post_ejecutado'] else 'no'}</td>"
            f"<td>{html.escape(str(esc.get('http_obtenido')))}</td>"
            f"<td>{html.escape(str(esc.get('codigo_negocio') or ''))}</td>"
            f"<td class='b'>{html.escape(esc['estado'])}</td>"
            f"<td>{html.escape(esc['motivo'])}</td>"
            "</tr>"
        )
    bloques = []
    for esc in informe["escenarios"]:
        bloques.append(
            f"<h2>{html.escape(esc['subcaso'])}</h2>"
            f"<p>{html.escape(esc['objetivo'])}</p>"
            f"<p>Activo: {html.escape(str(esc.get('activo')))}. POST ejecutado: {esc['post_ejecutado']}.</p>"
            "<h3>Antes</h3><pre>"
            + html.escape(json.dumps(esc.get("antes") or {}, ensure_ascii=False, indent=2))
            + "</pre><h3>Respuesta</h3><pre>"
            + html.escape(json.dumps({"http": esc.get("http_obtenido"), "codigo": esc.get("codigo_negocio"), "mensaje": esc.get("mensaje")}, ensure_ascii=False, indent=2))
            + "</pre><h3>Después</h3><pre>"
            + html.escape(json.dumps(esc.get("despues") or {}, ensure_ascii=False, indent=2))
            + "</pre><h3>Comparación</h3><pre>"
            + html.escape(json.dumps(esc.get("comparacion") or {}, ensure_ascii=False, indent=2))
            + "</pre>"
        )
    hallazgos = "".join(f"<li>{html.escape(h)}</li>" for h in informe["hallazgos"])
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <title>TC-M06-G101</title>
  <style>
    body {{ font-family: Segoe UI, sans-serif; margin: 2rem; line-height: 1.45; }}
    table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; }}
    th, td {{ border: 1px solid #ccc; padding: .45rem .6rem; vertical-align: top; text-align: left; }}
    th {{ background: #f3f3f3; }}
    .b {{ font-weight: 700; }}
    pre {{ white-space: pre-wrap; background: #fafafa; padding: .8rem; }}
  </style>
</head>
<body>
  <h1>Módulo 6 — RF-88 — TC-M06-G101</h1>
  <p>Retorno del modelo de costo a valor razonable y rechazo cuando no hay precio vigente. Relacionado con RF-83, RF-88, RF-89 y RF-94.</p>
  <p>Fecha: {html.escape(informe['generado_en'])}. Ambiente: {html.escape(informe['ambiente'])}. Duración del script: {informe['duracion_ms']} ms.</p>
  <p>Este informe registra las respuestas reales. Una simulación GET no equivale a la transición de método.</p>
  <h2>Resumen</h2>
  <table>
    <tr><th>Aprobados</th><td>{informe['aprobados']}</td></tr>
    <tr><th>Rechazados</th><td>{informe['rechazados']}</td></tr>
    <tr><th>Bloqueados</th><td>{informe['bloqueados']}</td></tr>
    <tr><th>Porcentaje</th><td class="b">{informe['porcentaje_aprobacion']} %</td></tr>
    <tr><th>Titulares distintos en períodos</th><td>{informe['titulares']}</td></tr>
    <tr><th>Aislado para QA</th><td>{informe['aislado']}</td></tr>
  </table>
  <h2>Endpoints</h2>
  <ul>
    <li>GET /finanzas/activos</li>
    <li>GET /finanzas/activos/{{id}}</li>
    <li>GET /finanzas/activos/{{id}}/simulacion</li>
    <li>GET /finanzas/precios?id_especie={{id}}</li>
    <li>GET /finanzas/periodos</li>
    <li>GET /finanzas/auditoria</li>
    <li>POST /finanzas/activos/{{id}}/valor-razonable, solo si el rechazo no escribe</li>
  </ul>
  <h2>Subcasos</h2>
  <table>
    <tr><th>Subcaso</th><th>Activo</th><th>POST</th><th>HTTP</th><th>Código</th><th>Estado</th><th>Motivo</th></tr>
    {''.join(filas)}
  </table>
  {''.join(bloques)}
  <h2>Períodos leídos</h2>
  <pre>{html.escape(json.dumps(informe['periodos'], ensure_ascii=False, indent=2))}</pre>
  <h2>Candidatos a costo</h2>
  <pre>{html.escape(json.dumps(informe['candidatos'], ensure_ascii=False, indent=2))}</pre>
  <h2>Hallazgos y limitaciones</h2>
  <ul>{hallazgos}</ul>
</body>
</html>
"""


def guardar(informe: dict) -> None:
    RESULTADOS.mkdir(parents=True, exist_ok=True)
    (RESULTADOS / "resultado_ejecucion_TC-M06-G101.html").write_text(render(informe), encoding="utf-8")
    (RESULTADOS / "resumen_ejecucion_TC-M06-G101.json").write_text(
        json.dumps(informe, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (RESULTADOS / "evidencia_peticiones_TC-M06-G101.json").write_text(json.dumps({
        "caso": informe["caso"],
        "generado_en": informe["generado_en"],
        "peticiones": informe["peticiones"],
    }, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def main() -> int:
    inicio = time.perf_counter()
    generado = datetime.now(timezone.utc).isoformat()
    peticiones: list[dict] = []
    hallazgos: list[str] = []
    positivo = escenario_base(
        "TC-M06-14",
        "Retorno exitoso de COSTO a VALOR_RAZONABLE cuando hay precio, costos de venta, magnitud y período abierto.",
    )
    negativo = escenario_base(
        "TC-M06-15",
        "Rechazo 422 SIN_PRECIO_PARA_VALOR_RAZONABLE sin cambios financieros cuando no hay precio vigente.",
    )
    informe = {
        "caso": "TC-M06-G101",
        "rf": ["RF-88", "RF-83", "RF-89", "RF-94"],
        "ambiente": BASE_API,
        "generado_en": generado,
        "login_http": None,
        "login": None,
        "puede_actualizar_costo": False,
        "titulares": None,
        "aislado": False,
        "periodos": {},
        "candidatos": [],
        "escenarios": [positivo, negativo],
        "peticiones": peticiones,
        "hallazgos": hallazgos,
        "aprobados": 0,
        "rechazados": 0,
        "bloqueados": 2,
        "porcentaje_aprobacion": 0,
        "duracion_ms": 0,
    }

    codigo, token, publico = autenticar()
    informe["login_http"] = codigo
    informe["login"] = publico
    peticiones.append(evidencia("POST", "/sesiones/", codigo, publico.get("duracion_ms", 0), publico, True))
    if codigo != 200 or not token:
        motivo = "No fue posible autenticar al Contador."
        positivo["motivo"] = motivo
        negativo["motivo"] = motivo
        hallazgos.append(motivo)
        informe["duracion_ms"] = round((time.perf_counter() - inicio) * 1000)
        guardar(informe)
        print("BLOQUEADO 0")
        return 2

    codigo, permisos, duracion = pedir("GET", "/sesiones/me/permisos", token=token)
    informe["puede_actualizar_costo"] = codigo == 200 and permiso_actualizar(permisos if isinstance(permisos, dict) else {})
    peticiones.append(evidencia("GET", "/sesiones/me/permisos", codigo, duracion, {
        "puede_actualizar_valoracion_por_costo": informe["puede_actualizar_costo"],
        "total": len(permisos.get("permisos") or []) if isinstance(permisos, dict) else None,
    }))

    codigo, periodos, duracion = pedir("GET", "/finanzas/periodos", token=token)
    lista_periodos = periodos if isinstance(periodos, list) else []
    titulares = {p.get("numero_id_tributaria") for p in lista_periodos if isinstance(p, dict) and p.get("numero_id_tributaria")}
    informe["titulares"] = len(titulares)
    informe["aislado"] = False
    decision = decision_periodo(lista_periodos, hoy_bogota())
    informe["periodos"] = {"http": codigo, "total": len(lista_periodos), **{k: v for k, v in decision.items() if k != "periodos"}, "detalle": decision["periodos"]}
    peticiones.append(evidencia("GET", "/finanzas/periodos", codigo, duracion, {"total": len(lista_periodos), "titulares": len(titulares), "decision": informe["periodos"]}))
    if len(titulares) != 1:
        hallazgos.append("No se pudo confirmar un único titular contable o hay más de uno. El positivo permanece bloqueado.")
    else:
        hallazgos.append("Los períodos pertenecen a un único titular compartido. No hay un período aislado para QA ni autorización para modificarlo.")

    codigo, activos, duracion = pedir("GET", "/finanzas/activos", token=token)
    lista = activos if isinstance(activos, list) else []
    costo = [a for a in lista if isinstance(a, dict) and a.get("valorado_por_costo")]
    peticiones.append(evidencia("GET", "/finanzas/activos", codigo, duracion, {
        "http": codigo,
        "reconocidos": len(lista),
        "a_costo": [a.get("id_activo_biologico") for a in costo],
    }))
    if codigo != 200:
        motivo = "No se pudo listar los activos reconocidos."
        positivo["motivo"] = motivo
        negativo["motivo"] = motivo
        hallazgos.append(motivo)
        informe["duracion_ms"] = round((time.perf_counter() - inicio) * 1000)
        guardar(informe)
        print("BLOQUEADO 0")
        return 2

    candidatos = []
    for activo in costo:
        id_activo = activo.get("id_activo_biologico")
        evidencias, snap = foto(token, id_activo, activo.get("id_especie"))
        peticiones.extend(evidencias)
        candidatos.append(snap)
    informe["candidatos"] = candidatos

    apto_positivo = [
        c for c in candidatos
        if c.get("es_activa") and c.get("estado") in VALORABLES and c.get("es_valido") is True
        and c.get("estado_calculo") != "REVISION_REQUERIDA" and c.get("fuente_precio") and c.get("costos_venta_simulados")
    ]
    apto_negativo = [
        c for c in candidatos
        if c.get("es_activa") and c.get("estado") in VALORABLES and c.get("motivo") == "SIN_PRECIO"
        and c.get("es_valido") is False and c.get("tiene_titular") and c.get("financiero_http") == 200
    ]
    if not candidatos:
        hallazgos.append("El Contador no tiene activos reconocidos con valoración por costo activa.")
    else:
        hallazgos.append(
            "Activos a costo visibles: " + ", ".join(str(c["id_activo_biologico"]) for c in candidatos) + "."
        )

    positivo["motivo"] = (
        "No se envió el POST. El retorno exitoso desactiva la valoración por costo, registra el cálculo "
        "y, si hay diferencia, el asiento VARIACION_VR_PM y la auditoría METODO_VALORACION_CAMBIADO. "
        "Esa escritura queda en el titular compartido y no hay autorización para modificarlo."
    )
    if apto_positivo:
        positivo["activo"] = apto_positivo[0]["id_activo_biologico"]
        positivo["antes"] = apto_positivo[0]
        hallazgos.append(
            f"El activo {apto_positivo[0]['id_activo_biologico']} cumple la simulación de valor razonable, "
            "pero la simulación no ejecuta la transición y el POST no se envió."
        )
    else:
        motivos = {str(c["id_activo_biologico"]): c.get("motivo") or ("VALIDO" if c.get("es_valido") else c.get("estado")) for c in candidatos}
        hallazgos.append("Ningún activo a costo tiene simulación válida con precio y costos de venta. Detalle: " + json.dumps(motivos, ensure_ascii=False) + ".")

    if not informe["puede_actualizar_costo"]:
        negativo["motivo"] = "La cuenta autenticada no tiene permiso de actualización sobre valoracion_por_costo. No se envió el POST."
    elif decision["crea_periodo"]:
        negativo["motivo"] = decision["motivo"] + " No se envió el POST: un insert de período, aunque luego revierta, no se considera un rechazo sin efectos."
        if apto_negativo:
            negativo["activo"] = apto_negativo[0]["id_activo_biologico"]
            negativo["antes"] = apto_negativo[0]
    elif decision["en_cierre"]:
        negativo["motivo"] = decision["motivo"] + " No se envió el POST."
    elif not apto_negativo:
        negativo["motivo"] = (
            "No hay un activo a costo, en estado valorable y sin precio vigente. "
            "Un rechazo por costos de venta usa el mismo código HTTP, pero no demuestra la ausencia de precio. No se envió el POST."
        )
    else:
        elegido = next((c for c in apto_negativo if c["id_activo_biologico"] == 951), apto_negativo[0])
        negativo["activo"] = elegido["id_activo_biologico"]
        negativo["antes"] = elegido
        ruta = f"/finanzas/activos/{elegido['id_activo_biologico']}/valor-razonable"
        codigo_post, respuesta, duracion = pedir("POST", ruta, token=token)
        negativo["post_ejecutado"] = True
        negativo["http_obtenido"] = codigo_post
        negativo["duracion_ms"] = duracion
        negativo["codigo_negocio"] = respuesta.get("error_code") if isinstance(respuesta, dict) else None
        negativo["mensaje"] = respuesta.get("message") if isinstance(respuesta, dict) else None
        peticiones.append(evidencia("POST", ruta, codigo_post, duracion, respuesta, True))
        evidencias, despues = foto(token, elegido["id_activo_biologico"], elegido.get("id_especie"))
        peticiones.extend(evidencias)
        codigo_per, periodos_despues, duracion_per = pedir("GET", "/finanzas/periodos", token=token)
        peticiones.append(evidencia("GET", "/finanzas/periodos", codigo_per, duracion_per, {"total": len(periodos_despues) if isinstance(periodos_despues, list) else None}))
        despues["periodos_total"] = len(periodos_despues) if isinstance(periodos_despues, list) else None
        elegido["periodos_total"] = len(lista_periodos)
        comparacion = comparar(elegido, despues)
        ids_antes = [p.get("id") for p in decision["periodos"]]
        ids_despues = [p.get("id_periodo_contable") for p in periodos_despues] if isinstance(periodos_despues, list) else []
        if sorted(ids_antes, key=lambda v: (v is None, v)) != sorted(ids_despues, key=lambda v: (v is None, v)):
            comparacion["sin_cambios"] = False
            comparacion["diferencias"]["periodos"] = {"antes": ids_antes, "despues": ids_despues}
        negativo["despues"] = despues
        negativo["comparacion"] = comparacion
        mensaje = (negativo["mensaje"] or "").lower()
        http_ok = codigo_post == 422 and negativo["codigo_negocio"] == "SIN_PRECIO_PARA_VALOR_RAZONABLE" and "precio" in mensaje
        if http_ok and comparacion["sin_cambios"] and despues.get("periodos_total") == len(lista_periodos):
            negativo["estado"] = "APROBADO"
            negativo["motivo"] = (
                "El POST respondió 422 SIN_PRECIO_PARA_VALOR_RAZONABLE. "
                "La valoración por costo, las líneas, los cálculos, la auditoría y los períodos quedaron iguales."
            )
        else:
            negativo["estado"] = "RECHAZADO"
            negativo["motivo"] = "El POST se ejecutó y el resultado no cumplió el rechazo sin efectos persistentes."
            hallazgos.append(negativo["motivo"] + " HTTP " + str(codigo_post) + " " + str(negativo["codigo_negocio"]) + ".")

    if negativo["estado"] == "BLOQUEADO" and negativo["antes"] is None and apto_negativo:
        negativo["activo"] = apto_negativo[0]["id_activo_biologico"]
        negativo["antes"] = apto_negativo[0]

    informe["aprobados"] = sum(1 for e in informe["escenarios"] if e["estado"] == "APROBADO")
    informe["rechazados"] = sum(1 for e in informe["escenarios"] if e["estado"] == "RECHAZADO")
    informe["bloqueados"] = sum(1 for e in informe["escenarios"] if e["estado"] == "BLOQUEADO")
    informe["porcentaje_aprobacion"] = round(informe["aprobados"] / len(informe["escenarios"]) * 100)
    informe["duracion_ms"] = round((time.perf_counter() - inicio) * 1000)
    guardar(informe)
    print(
        f"TC-M06-14 {positivo['estado']} POST {positivo['post_ejecutado']} | "
        f"TC-M06-15 {negativo['estado']} POST {negativo['post_ejecutado']} "
        f"HTTP {negativo['http_obtenido']} {negativo['codigo_negocio']} | "
        f"APROBADOS {informe['aprobados']} RECHAZADOS {informe['rechazados']} "
        f"BLOQUEADOS {informe['bloqueados']} PCT {informe['porcentaje_aprobacion']}"
    )
    return 0 if informe["aprobados"] == len(informe["escenarios"]) else 2


if __name__ == "__main__":
    raise SystemExit(main())
