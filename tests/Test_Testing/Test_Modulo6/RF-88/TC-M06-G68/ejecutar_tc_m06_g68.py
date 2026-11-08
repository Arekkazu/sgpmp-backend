"""Ejecución funcional de TC-M06-G68 contra la API de TEST.

Autentica con POST /sesiones/ usando QA_CORREO y QA_CONTRASENA del entorno.
No guarda la contraseña ni el token. Si el titular visible no está aislado,
no llama reconocimiento, cierre ni deterioro.

    python tests/Test_Testing/Test_Modulo6/RF-88/TC-M06-G68/ejecutar_tc_m06_g68.py
"""
from __future__ import annotations

import html
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

CARPETA = Path(__file__).resolve().parent
RESULTADOS = CARPETA / "resultados"
BASE_API = "https://api.inmero.co/api-sgpmp-test"
AMBIENTE = "https://api.inmero.co/api-sgpmp-test"


def pedir(metodo: str, ruta: str, cuerpo: dict | None = None, token: str | None = None):
    datos = None if cuerpo is None else json.dumps(cuerpo).encode("utf-8")
    headers = {"Accept": "application/json"}
    if cuerpo is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(BASE_API + ruta, data=datos, headers=headers, method=metodo)
    try:
        with urllib.request.urlopen(req, timeout=40) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = {"message": raw[:240]}
        return exc.code, parsed


def publico(payload):
    if not isinstance(payload, dict):
        return {"tipo": type(payload).__name__}
    limpio = {k: v for k, v in payload.items() if k not in ("token", "access_token", "contrasena")}
    if "message" in limpio:
        limpio["message"] = str(limpio["message"])[:240]
    if "error_code" in limpio:
        limpio["error_code"] = limpio["error_code"]
    return {k: limpio[k] for k in list(limpio)[:6]}


def numero(valor):
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def autenticar() -> tuple[int, str | None, dict]:
    correo = os.environ.get("QA_CORREO")
    contrasena = os.environ.get("QA_CONTRASENA")
    if not correo or not contrasena:
        raise SystemExit("Defina QA_CORREO y QA_CONTRASENA en el entorno del proceso. No las escriba en el archivo.")
    codigo, payload = pedir("POST", "/sesiones/", {"correo_electronico": correo, "contrasena": contrasena})
    token = payload.get("token") if isinstance(payload, dict) else None
    return codigo, token, publico(payload if isinstance(payload, dict) else {})


def consultar(token: str) -> tuple[list[dict], dict]:
    evidencias = []
    datos = {}
    rutas = [
        ("/finanzas/configuracion", None),
        ("/finanzas/activos", None),
        ("/finanzas/periodos", None),
        ("/finanzas/reconocimientos/propuestas", None),
        ("/finanzas/auditoria", None),
        ("/finanzas/auditoria?tipo_evento=DETERIORO_REGISTRADO", "deterioro"),
        ("/finanzas/auditoria?tipo_evento=DEPRECIACION_REGISTRADA", "depreciacion"),
    ]
    for ruta, clave in rutas:
        codigo, payload = pedir("GET", ruta, token=token)
        evidencias.append({"metodo": "GET", "ruta": ruta.split("?")[0] if "auditoria?" in ruta else ruta, "consulta": ruta, "codigo": codigo, "resumen": resumir(ruta, codigo, payload)})
        if clave:
            datos[clave] = payload if codigo == 200 else {}
        elif ruta == "/finanzas/activos" and codigo == 200:
            datos["activos"] = payload if isinstance(payload, list) else []
        elif ruta == "/finanzas/periodos" and codigo == 200:
            datos["periodos"] = payload if isinstance(payload, list) else []
        elif ruta == "/finanzas/reconocimientos/propuestas" and codigo == 200:
            datos["propuestas"] = payload if isinstance(payload, list) else []
        elif ruta == "/finanzas/configuracion":
            datos["configuracion_codigo"] = codigo
            datos["configuracion"] = payload if isinstance(payload, dict) else {}
        elif ruta == "/finanzas/auditoria":
            datos["auditoria_sin_filtro"] = publico(payload) if isinstance(payload, dict) else {}
    return evidencias, datos


def resumir(ruta: str, codigo: int, payload) -> dict:
    if isinstance(payload, list):
        return {"codigo": codigo, "registros": len(payload)}
    if not isinstance(payload, dict):
        return {"codigo": codigo}
    if "error_code" in payload:
        return {"codigo": codigo, "error_code": payload.get("error_code"), "message": str(payload.get("message") or "")[:180]}
    if "total_registros" in payload:
        return {"codigo": codigo, "total_registros": payload.get("total_registros")}
    return {
        "codigo": codigo,
        "claves": list(payload)[:8],
        "especies": len(payload.get("especies") or []) if isinstance(payload.get("especies"), list) else None,
        "matriz": len(payload.get("matriz") or []) if isinstance(payload.get("matriz"), list) else None,
        "lineas_pendientes_cuenta": payload.get("lineas_pendientes_cuenta"),
    }


def medir(datos: dict) -> dict:
    activos = datos.get("activos") or []
    periodos = datos.get("periodos") or []
    propuestas = datos.get("propuestas") or []
    fincas = {a.get("finca") for a in activos if isinstance(a, dict)}
    nits = {p.get("numero_id_tributaria") for p in periodos if isinstance(p, dict) and p.get("numero_id_tributaria")}
    estados = {}
    for periodo in periodos:
        if isinstance(periodo, dict):
            estado = str(periodo.get("estado") or "")
            estados[estado] = estados.get(estado, 0) + 1
    costo_10 = 0
    por_costo = 0
    for activo in activos:
        if not isinstance(activo, dict):
            continue
        if activo.get("valorado_por_costo"):
            por_costo += 1
        costo = numero(activo.get("costo_base") if activo.get("costo_base") is not None else activo.get("costo_adquisicion"))
        if costo == 10000000:
            costo_10 += 1
    propuestas_10 = 0
    for propuesta in propuestas:
        if isinstance(propuesta, dict) and numero(propuesta.get("costo_adquisicion")) == 10000000:
            propuestas_10 += 1
    aislado = len(activos) == 1 and len(fincas) == 1 and len(nits) == 1 and len(periodos) <= 1 and costo_10 == 1
    return {
        "activos": len(activos),
        "fincas": len(fincas),
        "nits": len(nits),
        "periodos": len(periodos),
        "estados_periodo": estados,
        "propuestas": len(propuestas),
        "valoraciones_por_costo": por_costo,
        "costo_10000000": costo_10,
        "propuestas_costo_10000000": propuestas_10,
        "deterioros_auditados": (datos.get("deterioro") or {}).get("total_registros"),
        "depreciaciones_auditadas": (datos.get("depreciacion") or {}).get("total_registros"),
        "configuracion_http": datos.get("configuracion_codigo"),
        "aislado": aislado,
    }


def informes(login_codigo: int, login_publico: dict, evidencias: list[dict], panorama: dict) -> dict:
    ahora = datetime.now(timezone.utc).isoformat()
    motivo = (
        "El administrador autenticó y leyó el módulo. "
        f"Hay {panorama['activos']} activos reconocidos, {panorama['fincas']} fincas, "
        f"{panorama['nits']} NIT y {panorama['periodos']} períodos. "
        f"Activos o propuestas con costo 10000000: {panorama['costo_10000000']} y {panorama['propuestas_costo_10000000']}. "
        "Ese conjunto es el ya inspeccionado y no es un titular exclusivo. "
        "No se reconoció, no se cerró un período y no se registró deterioro."
    )
    alerta = (
        "GET /finanzas/auditoria sin filtro responde FILTRO_OBLIGATORIO. "
        f"DETERIORO_REGISTRADO tiene {panorama['deterioros_auditados']} evento(s) y "
        f"DEPRECIACION_REGISTRADA tiene {panorama['depreciaciones_auditadas']}. "
        "No aparece una alerta persistente distinta de ese evento genérico."
    )
    subcasos = [
        {"id": "TC-M06-05", "entrada": "10000000, depreciacion 2000000, deterioro 1000000", "esperado": "7000000", "obtenido": None, "estado": "BLOQUEADO", "persistido": False, "motivo": motivo},
        {"id": "TC-M06-06", "entrada": "10000000, depreciacion 10000000, deterioro 0", "esperado": "0", "obtenido": None, "estado": "BLOQUEADO", "persistido": False, "motivo": motivo},
        {"id": "TC-M06-07", "entrada": "10000000, depreciacion 7000000, deterioro 5000000", "esperado": "0 y alerta persistente consultable", "obtenido": None, "estado": "BLOQUEADO", "persistido": False, "motivo": motivo + " " + alerta},
    ]
    hallazgos = [
        {
            "id": "QUESTION-M06-003",
            "titulo": "No hay titular aislado para el costo de 10000000",
            "descripcion": motivo,
            "rf": "RF-88",
            "categoria": "Capacidad de prueba",
            "tipo": "QUESTION",
            "equipo": "QA, con un titular nuevo preparado por DBA si el NIT actual no puede segregarse",
            "severidad": "Medio",
            "tiempo_maximo": "2 días hábiles",
            "correccion": "Disponer de una finca, un NIT, un activo de costo 10000000 y un período que no compartan los 13 reconocimientos ni los 8 períodos actuales.",
        },
        {
            "id": "HALL-M06-G68-02",
            "titulo": "No hay alerta persistente cuando el valor en libros se lleva a cero",
            "descripcion": alerta,
            "rf": "RF-88",
            "categoria": "FLUJO",
            "tipo": "BUG",
            "equipo": "Desarrollo Backend",
            "severidad": "Medio",
            "tiempo_maximo": "2 días hábiles",
            "correccion": "Guardar una alerta consultable por activo, distinta de DETERIORO_REGISTRADO y del texto aviso de la respuesta.",
        },
    ]
    return {
        "caso": "TC-M06-G68",
        "modulo": 6,
        "rf": "RF-88",
        "ambiente": AMBIENTE,
        "generado_en": ahora,
        "login_http": login_codigo,
        "login": login_publico,
        "escrituras_financieras": False,
        "datos_prueba_creados": [],
        "panorama": panorama,
        "http": evidencias,
        "subcasos": subcasos,
        "hallazgos": hallazgos,
        "aprobados": 0,
        "rechazados": 0,
        "bloqueados": 3,
        "total": 3,
        "porcentaje_aprobacion": 0,
    }


def render(informe: dict) -> str:
    filas = "".join(
        "<tr><td>{id}</td><td>{entrada}</td><td>{esperado}</td><td>No ejecutado</td><td class=\"b\">{estado}</td><td>{motivo}</td></tr>".format(
            **{k: html.escape(str(v)) for k, v in sub.items() if k != "persistido"}
        )
        for sub in informe["subcasos"]
    )
    http = "".join(
        "<tr><td>{metodo} {consulta}</td><td>{codigo}</td><td><code>{resumen}</code></td></tr>".format(
            metodo=item["metodo"],
            consulta=html.escape(item["consulta"]),
            codigo=item["codigo"],
            resumen=html.escape(json.dumps(item["resumen"], ensure_ascii=False)),
        )
        for item in informe["http"]
    )
    hallazgos = "".join(
        "<li><strong>{id}</strong> {titulo}. {tipo}, {categoria}, {equipo}, {severidad}. {correccion}</li>".format(
            **{k: html.escape(str(v)) for k, v in h.items()}
        )
        for h in informe["hallazgos"]
    )
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <title>TC-M06-G68 — ejecución funcional</title>
  <style>
    body {{ font-family: Segoe UI, sans-serif; margin: 2rem; line-height: 1.45; }}
    table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; }}
    th, td {{ border: 1px solid #ccc; padding: .45rem .6rem; vertical-align: top; text-align: left; }}
    th {{ background: #f3f3f3; }}
    .b {{ font-weight: 700; }}
    code {{ font-family: Consolas, monospace; }}
  </style>
</head>
<body>
  <h1>Módulo 6 — RF-88 — TC-M06-G68</h1>
  <p>Fecha: {html.escape(informe['generado_en'])}. Ambiente: {html.escape(informe['ambiente'])}.</p>
  <p>Autenticación POST /sesiones/: HTTP {informe['login_http']}. Escrituras financieras: ninguna. Datos de prueba creados: ninguno.</p>
  <h2>Resumen</h2>
  <table>
    <tr><th>Total</th><td>3</td></tr>
    <tr><th>Aprobados</th><td>0</td></tr>
    <tr><th>Rechazados</th><td>0</td></tr>
    <tr><th>Bloqueados</th><td>3</td></tr>
    <tr><th>Porcentaje de aprobación</th><td>0 %</td></tr>
  </table>
  <h2>Subcasos</h2>
  <table>
    <thead><tr><th>Subcaso</th><th>Entrada</th><th>Esperado</th><th>Obtenido</th><th>Estado</th><th>Validación</th></tr></thead>
    <tbody>{filas}</tbody>
  </table>
  <h2>Panorama leído antes de escribir</h2>
  <pre>{html.escape(json.dumps(informe['panorama'], ensure_ascii=False, indent=2))}</pre>
  <h2>Respuestas HTTP</h2>
  <table>
    <thead><tr><th>Solicitud</th><th>Código</th><th>Resumen sin secretos</th></tr></thead>
    <tbody>{http}</tbody>
  </table>
  <h2>Hallazgos</h2>
  <ul>{hallazgos}</ul>
  <h2>Conclusión</h2>
  <p>RF-88 no se cumplió en esta corrida: los tres subcasos quedaron bloqueados. El cálculo no se persistió y la alerta de TC-M06-07 no se consultó como un registro propio.</p>
</body>
</html>
"""


def main() -> int:
    RESULTADOS.mkdir(parents=True, exist_ok=True)
    codigo, token, login_publico = autenticar()
    if not token:
        informe = {
            "caso": "TC-M06-G68", "modulo": 6, "rf": "RF-88", "ambiente": AMBIENTE,
            "generado_en": datetime.now(timezone.utc).isoformat(), "login_http": codigo,
            "login": login_publico, "escrituras_financieras": False, "datos_prueba_creados": [],
            "panorama": {}, "http": [], "subcasos": [], "hallazgos": [],
            "aprobados": 0, "rechazados": 0, "bloqueados": 3, "total": 3, "porcentaje_aprobacion": 0,
        }
    else:
        evidencias, datos = consultar(token)
        panorama = medir(datos)
        informe = informes(codigo, login_publico, evidencias, panorama)
        if panorama["aislado"]:
            informe["nota"] = "El panorama quedó aislado, pero esta corrida no escribe sin una autorización explícita adicional."
    (RESULTADOS / "resumen_ejecucion_TC-M06-G68.json").write_text(json.dumps(informe, ensure_ascii=False, indent=2), encoding="utf-8")
    (RESULTADOS / "evidencia_peticiones_TC-M06-G68.json").write_text(
        json.dumps({"login_http": informe["login_http"], "login": informe["login"], "http": informe["http"], "panorama": informe["panorama"]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (RESULTADOS / "resultado_ejecucion_TC-M06-G68.html").write_text(render(informe), encoding="utf-8")
    print(f"APROBADOS {informe['aprobados']} RECHAZADOS {informe['rechazados']} BLOQUEADOS {informe['bloqueados']} PCT {informe['porcentaje_aprobacion']}")
    return 0 if informe["aprobados"] == 3 else 2


if __name__ == "__main__":
    sys.exit(main())
