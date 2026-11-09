"""Ejecución de TC-M06-G99 contra la API de TEST.

Autentica con POST /sesiones/ usando QA_CORREO y QA_CONTRASENA.
Solo consulta. No cierra períodos, no registra depreciación y no modifica asientos.

    python tests/Test_Testing/Test_Modulo6/RF-88/TC-M06-G99/ejecutar_tc_m06_g99.py
"""
from __future__ import annotations

import html
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

CARPETA = Path(__file__).resolve().parent
RESULTADOS = CARPETA / "resultados"
BASE_API = "https://api.inmero.co/api-sgpmp-test"
AMBIENTE = BASE_API
SECRETOS = {
    "token", "access_token", "contrasena", "password", "hash_integridad", "hash", "hash_cierre",
    "nombre_usuario", "correo_electronico", "numero_id_tributaria", "finca", "identificador",
    "infraestructura", "actor",
}
HECHO_DEPRECIACION = "DEPRECIACION_ACTIVO_COSTO"


def pedir(metodo: str, ruta: str, cuerpo: dict | None = None, token: str | None = None):
    datos = None if cuerpo is None else json.dumps(cuerpo).encode("utf-8")
    headers = {"Accept": "application/json"}
    if cuerpo is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(BASE_API + ruta, data=datos, headers=headers, method=metodo)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = {"message": raw[:240]}
        return exc.code, parsed
    except urllib.error.URLError as exc:
        return 0, {"message": str(exc.reason)[:240]}


def limpiar(valor, profundidad: int = 0):
    if profundidad > 5:
        return "..."
    if isinstance(valor, dict):
        return {
            clave: limpiar(item, profundidad + 1)
            for clave, item in valor.items()
            if clave not in SECRETOS
        }
    if isinstance(valor, list):
        return [limpiar(item, profundidad + 1) for item in valor[:30]]
    if isinstance(valor, str) and len(valor) > 240:
        return valor[:240]
    return valor


def error_de(payload) -> dict:
    if not isinstance(payload, dict):
        return {}
    return {
        "error_code": payload.get("error_code"),
        "message": str(payload.get("message") or "")[:180],
    }


def autenticar() -> tuple[int, str | None, dict]:
    correo = os.environ.get("QA_CORREO")
    contrasena = os.environ.get("QA_CONTRASENA")
    if not correo or not contrasena:
        raise SystemExit("Defina QA_CORREO y QA_CONTRASENA en el entorno del proceso. No las escriba en el archivo.")
    codigo, payload = pedir("POST", "/sesiones/", {"correo_electronico": correo, "contrasena": contrasena})
    token = payload.get("token") if isinstance(payload, dict) else None
    publico = limpiar(payload if isinstance(payload, dict) else {})
    if isinstance(publico, dict):
        publico["rol_autenticado"] = "Contador" if correo.startswith("contador@") else "cuenta de entorno"
    return codigo, token, publico if isinstance(publico, dict) else {}


def anotar(evidencias: list[dict], ruta: str, codigo: int, resumen: dict, validacion: str, resultado: str) -> None:
    evidencias.append({
        "caso": "TC-M06-G99",
        "subcaso": "TC-M06-12",
        "metodo": "GET",
        "ruta": ruta.split("?")[0],
        "consulta": ruta,
        "parametros": dict(urllib.parse.parse_qsl(ruta.split("?", 1)[1])) if "?" in ruta else {},
        "codigo": codigo,
        "respuesta": resumen,
        "lectura": True,
        "escritura": False,
        "validacion": validacion,
        "resultado_validacion": resultado,
    })


def consultar(token: str) -> tuple[list[dict], dict]:
    evidencias: list[dict] = []
    datos: dict = {"activos_costo": [], "periodos": [], "por_periodo": [], "auditoria": {}}

    codigo, activos = pedir("GET", "/finanzas/activos", token=token)
    lista = activos if isinstance(activos, list) else []
    costo = []
    fincas = set()
    for activo in lista:
        if not isinstance(activo, dict):
            continue
        if activo.get("id_finca") is not None:
            fincas.add(activo.get("id_finca"))
        if activo.get("valorado_por_costo"):
            costo.append({
                "id_activo_biologico": activo.get("id_activo_biologico"),
                "costo_base": activo.get("costo_base"),
                "depreciacion_acumulada": activo.get("depreciacion_acumulada"),
                "deterioro_acumulado": activo.get("deterioro_acumulado"),
                "valor_contable_por_costo": activo.get("valor_contable_por_costo"),
                "vida_util_meses": activo.get("vida_util_meses"),
            })
    datos["activos_reconocidos"] = len(lista)
    datos["fincas"] = len(fincas)
    datos["activos_costo"] = costo
    anotar(evidencias, "/finanzas/activos", codigo, {"registros": len(lista), "por_costo": len(costo)}, "Activos a costo", "LEIDO" if codigo == 200 else "NO_LEIDO")

    codigo, periodos = pedir("GET", "/finanzas/periodos", token=token)
    crudos = periodos if isinstance(periodos, list) else []
    nits = set()
    resumen_periodos = []
    for periodo in crudos:
        if not isinstance(periodo, dict):
            continue
        if periodo.get("numero_id_tributaria"):
            nits.add(periodo.get("numero_id_tributaria"))
        ultimo = periodo.get("ultimo_cierre") if isinstance(periodo.get("ultimo_cierre"), dict) else {}
        resumen_periodos.append({
            "id_periodo_contable": periodo.get("id_periodo_contable"),
            "estado": periodo.get("estado"),
            "fecha_inicio": periodo.get("fecha_inicio"),
            "fecha_fin": periodo.get("fecha_fin"),
            "ultimo_cierre_estado": ultimo.get("estado") or ultimo.get("estado_cierre"),
        })
    datos["periodos"] = resumen_periodos
    datos["nits"] = len(nits)
    anotar(evidencias, "/finanzas/periodos", codigo, {"registros": len(resumen_periodos), "nits": len(nits)}, "Períodos contables", "LEIDO" if codigo == 200 else "NO_LEIDO")

    for periodo in resumen_periodos:
        id_periodo = periodo.get("id_periodo_contable")
        if not isinstance(id_periodo, int):
            continue
        ficha = {"id_periodo_contable": id_periodo, "estado": periodo.get("estado")}
        if periodo.get("estado") == "ABIERTO":
            ruta = f"/finanzas/periodos/{id_periodo}/prevalidacion"
            codigo_p, cuerpo = pedir("GET", ruta, token=token)
            if codigo_p == 200 and isinstance(cuerpo, dict):
                ficha["prevalidacion"] = {
                    "puede_cerrar": cuerpo.get("puede_cerrar"),
                    "bloqueos": len(cuerpo.get("bloqueos") or []),
                    "activos_sin_precio": len(cuerpo.get("activos_sin_precio") or []),
                    "lineas_sin_trazabilidad": len(cuerpo.get("lineas_sin_trazabilidad") or []),
                }
            else:
                ficha["prevalidacion"] = {"http": codigo_p, **error_de(cuerpo)}
            anotar(evidencias, ruta, codigo_p, ficha["prevalidacion"], "Prevalidación de cierre", "LEIDO" if codigo_p == 200 else "NO_LEIDO")

        ruta = f"/finanzas/lineas?id_periodo_contable={id_periodo}"
        codigo_l, lineas = pedir("GET", ruta, token=token)
        depreciaciones = []
        if codigo_l == 200 and isinstance(lineas, list):
            for linea in lineas:
                if isinstance(linea, dict) and linea.get("tipo_hecho") == HECHO_DEPRECIACION:
                    depreciaciones.append({
                        "id_linea_asiento_nic41": linea.get("id_linea_asiento_nic41"),
                        "id_activo_biologico": linea.get("id_activo_biologico"),
                        "id_periodo_contable": linea.get("id_periodo_contable"),
                        "valor": linea.get("valor"),
                        "estado": linea.get("estado"),
                    })
            ficha["lineas"] = len(lineas)
        else:
            ficha["lineas_error"] = {"http": codigo_l, **error_de(lineas)}
        ficha["depreciaciones"] = depreciaciones
        anotar(
            evidencias, ruta, codigo_l,
            {"lineas": ficha.get("lineas"), "depreciacion_activo_costo": len(depreciaciones), **ficha.get("lineas_error", {})},
            "Asientos del período", "LEIDO" if codigo_l == 200 else "NO_LEIDO",
        )

        ruta = f"/finanzas/periodos/{id_periodo}/comprobantes"
        codigo_c, comprobantes = pedir("GET", ruta, token=token)
        ficha["comprobantes"] = len(comprobantes) if codigo_c == 200 and isinstance(comprobantes, list) else None
        if codigo_c != 200:
            ficha["comprobantes_error"] = {"http": codigo_c, **error_de(comprobantes)}
        anotar(evidencias, ruta, codigo_c, {"comprobantes": ficha["comprobantes"], **ficha.get("comprobantes_error", {})}, "Comprobantes NIC 41", "LEIDO" if codigo_c == 200 else "NO_LEIDO")

        ruta = f"/finanzas/periodos/{id_periodo}/estados-resultados"
        codigo_e, estados = pedir("GET", ruta, token=token)
        ficha["estados_resultados"] = len(estados) if codigo_e == 200 and isinstance(estados, list) else None
        if codigo_e != 200:
            ficha["estados_error"] = {"http": codigo_e, **error_de(estados)}
        anotar(evidencias, ruta, codigo_e, {"versiones": ficha["estados_resultados"], **ficha.get("estados_error", {})}, "Estado de resultados RF-93", "LEIDO" if codigo_e == 200 else "NO_LEIDO")
        datos["por_periodo"].append(ficha)

    for tipo in ("DEPRECIACION_REGISTRADA", "CIERRE_PERIODO_COMPLETADO", "CIERRE_PERIODO_FALLIDO"):
        ruta = f"/finanzas/auditoria?tipo_evento={tipo}&formato=TECNICO&tamano=100"
        codigo_a, cuerpo = pedir("GET", ruta, token=token)
        total = cuerpo.get("total_registros") if isinstance(cuerpo, dict) else None
        datos["auditoria"][tipo] = total
        resumen = {"total_registros": total} if codigo_a == 200 else {"http": codigo_a, **error_de(cuerpo)}
        anotar(evidencias, ruta, codigo_a, resumen, f"Auditoría {tipo}", "LEIDO" if codigo_a == 200 else "NO_LEIDO")
    return evidencias, datos


def aislado(datos: dict) -> bool:
    abiertos = [p for p in datos["periodos"] if p.get("estado") == "ABIERTO"]
    return (
        datos["activos_reconocidos"] == 1
        and datos["fincas"] <= 1
        and datos["nits"] <= 1
        and len(datos["periodos"]) <= 1
        and len(abiertos) == 1
        and len(datos["activos_costo"]) == 1
    )


def informes(login_codigo: int, login_publico: dict, evidencias: list[dict], datos: dict) -> dict:
    seguro = aislado(datos)
    abiertos = [p for p in datos["periodos"] if p.get("estado") == "ABIERTO"]
    cerrados = [p for p in datos["periodos"] if p.get("estado") == "CERRADO"]
    lineas_dep = sum(len(p.get("depreciaciones") or []) for p in datos["por_periodo"])
    motivo = (
        f"La cuenta leyó {datos['activos_reconocidos']} activos reconocidos, "
        f"{len(datos['activos_costo'])} a costo, {datos['fincas']} fincas, {datos['nits']} NIT, "
        f"{len(abiertos)} períodos abiertos y {len(cerrados)} cerrados. "
        f"Líneas DEPRECIACION_ACTIVO_COSTO ya visibles: {lineas_dep}. "
        "Ese conjunto es compartido. No se ejecutó POST /finanzas/periodos/{{id}}/cierre."
    )
    if not seguro:
        estado = "BLOQUEADO"
        obtenido = None
    else:
        estado = "BLOQUEADO"
        obtenido = None
        motivo += " Aunque el panorama estuviera aislado, esta corrida no cierra sin autorización explícita."
    subcasos = [
        {
            "id": "TC-M06-12",
            "validacion": "Registro del gasto por depreciación al cerrar el período",
            "esperado": "El cierre pasa el período a CERRADO y deja el asiento DEPRECIACION_ACTIVO_COSTO por el importe del período.",
            "obtenido": obtenido,
            "estado": estado,
            "motivo": motivo,
        },
        {
            "id": "TC-M06-12",
            "validacion": "Un segundo cierre del mismo período no duplica el asiento",
            "esperado": "Un período CERRADO rechaza otro cierre con 409 PERIODO_CERRADO y no vuelve a depreciar.",
            "obtenido": obtenido,
            "estado": estado,
            "motivo": motivo + " La regla está en el cierre, pero no se provocó un segundo intento.",
        },
    ]
    hallazgos = [{
        "id": "QUESTION-M06-G71-01",
        "titulo": "No hay un período abierto aislado para cerrar",
        "descripcion": motivo,
        "rf": "RF-87 / RF-88 / RF-93",
        "categoria": "Capacidad de prueba",
        "tipo": "QUESTION",
        "equipo": "QA, con un titular nuevo preparado por DBA si el NIT actual no puede segregarse",
        "severidad": "Medio",
        "tiempo_maximo": "2 días hábiles",
        "estado": "Abierto",
        "justificacion": "Impide ejecutar el cierre. No evidencia un asiento duplicado ni un cálculo incorrecto. Cerrar ahora procesaría todos los activos reconocidos del mismo NIT.",
        "correccion": "Disponer de un titular exclusivo, un solo activo a costo, un solo período abierto y autorización explícita para cerrarlo.",
    }]
    return {
        "caso": "TC-M06-G99",
        "subcaso": "TC-M06-12",
        "modulo": 6,
        "rf": "RF-87 / RF-88 / RF-93",
        "ambiente": AMBIENTE,
        "generado_en": datetime.now(timezone.utc).isoformat(),
        "login_http": login_codigo,
        "login": login_publico,
        "escrituras": False,
        "cierre_ejecutado": False,
        "segundo_cierre_ejecutado": False,
        "datos_prueba_creados": [],
        "contrato": {
            "cierre": "POST /finanzas/periodos/{id_periodo_contable}/cierre",
            "cuerpo": {"autorizar_exclusiones": False, "incluir_activos_sin_precio": False},
            "permiso_cierre": "cierre_periodo ejecutar",
            "depreciacion": "Dentro del cierre, hecho DEPRECIACION_ACTIVO_COSTO, por el delta del período",
            "estado_resultados": "GET y POST /finanzas/periodos/{id}/estados-resultados; el cierre también intenta generarlo",
            "segundo_cierre": "409 PERIODO_CERRADO; el período cerrado no se reabre ni se vuelve a depreciar",
            "alcance": "Todos los activos reconocidos del mismo NIT",
        },
        "panorama": {
            "activos_reconocidos": datos["activos_reconocidos"],
            "activos_costo": datos["activos_costo"],
            "fincas": datos["fincas"],
            "nits": datos["nits"],
            "periodos": datos["periodos"],
            "abiertos": len(abiertos),
            "cerrados": len(cerrados),
            "lineas_depreciacion": lineas_dep,
            "auditoria": datos["auditoria"],
            "aislado": seguro,
        },
        "por_periodo": datos["por_periodo"],
        "http": evidencias,
        "subcasos": subcasos,
        "hallazgos": hallazgos,
        "aprobados": 0,
        "rechazados": 0,
        "bloqueados": 2,
        "total": 2,
        "porcentaje_aprobacion": 0,
    }


def render(informe: dict) -> str:
    filas = "".join(
        "<tr><td>{id}</td><td>{validacion}</td><td>{esperado}</td><td>No ejecutado</td><td class=\"b\">{estado}</td><td>{motivo}</td></tr>".format(
            **{k: html.escape(str(v)) for k, v in sub.items()}
        )
        for sub in informe["subcasos"]
    )
    http = "".join(
        "<tr><td>GET {consulta}</td><td>{codigo}</td><td>{resultado}</td><td><code>{respuesta}</code></td></tr>".format(
            consulta=html.escape(item["consulta"]),
            codigo=item["codigo"],
            resultado=html.escape(item["resultado_validacion"]),
            respuesta=html.escape(json.dumps(item["respuesta"], ensure_ascii=False)),
        )
        for item in informe["http"]
    )
    hallazgos = "".join(
        "<li><strong>{id}</strong> {titulo}. {tipo}, {categoria}, {equipo}, {severidad}, {tiempo_maximo}. {justificacion}</li>".format(
            **{k: html.escape(str(v)) for k, v in h.items()}
        )
        for h in informe["hallazgos"]
    )
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <title>TC-M06-G99 — ejecución</title>
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
  <h1>Módulo 6 — RF-87 / RF-88 / RF-93 — TC-M06-G99</h1>
  <p>Fecha: {html.escape(informe['generado_en'])}. Ambiente: {html.escape(informe['ambiente'])}.</p>
  <p>Objetivo: comprobar el asiento de depreciación al cerrar un período y que un segundo cierre no lo duplique.</p>
  <p>Autenticación POST /sesiones/: HTTP {informe['login_http']}. Escrituras: ninguna. Cierre ejecutado: no.</p>
  <h2>Resumen</h2>
  <table>
    <tr><th>Total</th><td>{informe['total']}</td></tr>
    <tr><th>Aprobados</th><td>{informe['aprobados']}</td></tr>
    <tr><th>Rechazados</th><td>{informe['rechazados']}</td></tr>
    <tr><th>Bloqueados</th><td>{informe['bloqueados']}</td></tr>
    <tr><th>Porcentaje de aprobación</th><td>{informe['porcentaje_aprobacion']} %</td></tr>
  </table>
  <h2>Contrato identificado</h2>
  <pre>{html.escape(json.dumps(informe['contrato'], ensure_ascii=False, indent=2))}</pre>
  <h2>Validaciones</h2>
  <table>
    <thead><tr><th>Subcaso</th><th>Validación</th><th>Esperado</th><th>Obtenido</th><th>Estado</th><th>Detalle</th></tr></thead>
    <tbody>{filas}</tbody>
  </table>
  <h2>Panorama</h2>
  <pre>{html.escape(json.dumps(informe['panorama'], ensure_ascii=False, indent=2))}</pre>
  <h2>Períodos consultados</h2>
  <pre>{html.escape(json.dumps(informe['por_periodo'], ensure_ascii=False, indent=2))}</pre>
  <h2>Respuestas HTTP</h2>
  <table>
    <thead><tr><th>Solicitud</th><th>Código</th><th>Validación</th><th>Resumen sin secretos</th></tr></thead>
    <tbody>{http}</tbody>
  </table>
  <h2>Hallazgos</h2>
  <ul>{hallazgos}</ul>
</body>
</html>
"""


def main() -> int:
    RESULTADOS.mkdir(parents=True, exist_ok=True)
    codigo, token, login_publico = autenticar()
    if not token:
        informe = {
            "caso": "TC-M06-G99", "subcaso": "TC-M06-12", "modulo": 6, "rf": "RF-87 / RF-88 / RF-93",
            "ambiente": AMBIENTE, "generado_en": datetime.now(timezone.utc).isoformat(),
            "login_http": codigo, "login": login_publico, "escrituras": False, "cierre_ejecutado": False,
            "segundo_cierre_ejecutado": False, "datos_prueba_creados": [], "contrato": {}, "panorama": {},
            "por_periodo": [], "http": [],
            "subcasos": [
                {"id": "TC-M06-12", "validacion": "Registro del gasto por depreciación al cerrar el período", "esperado": "Cierre y asiento", "obtenido": None, "estado": "BLOQUEADO", "motivo": f"POST /sesiones/ respondió {codigo}."},
                {"id": "TC-M06-12", "validacion": "Un segundo cierre del mismo período no duplica el asiento", "esperado": "Sin duplicado", "obtenido": None, "estado": "BLOQUEADO", "motivo": f"POST /sesiones/ respondió {codigo}."},
            ],
            "hallazgos": [], "aprobados": 0, "rechazados": 0, "bloqueados": 2, "total": 2, "porcentaje_aprobacion": 0,
        }
    else:
        evidencias, datos = consultar(token)
        informe = informes(codigo, login_publico, evidencias, datos)
    (RESULTADOS / "resumen_ejecucion_TC-M06-G99.json").write_text(json.dumps(informe, ensure_ascii=False, indent=2), encoding="utf-8")
    (RESULTADOS / "evidencia_peticiones_TC-M06-G99.json").write_text(json.dumps({
        "caso": informe["caso"], "generado_en": informe["generado_en"], "ambiente": informe["ambiente"],
        "login_http": informe["login_http"], "login": informe["login"], "http": informe["http"],
        "subcasos": informe["subcasos"],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    (RESULTADOS / "resultado_ejecucion_TC-M06-G99.html").write_text(render(informe), encoding="utf-8")
    print(
        f"APROBADOS {informe['aprobados']} RECHAZADOS {informe['rechazados']} "
        f"BLOQUEADOS {informe['bloqueados']} PCT {informe['porcentaje_aprobacion']}"
    )
    return 0 if informe["aprobados"] == 2 else 2


if __name__ == "__main__":
    sys.exit(main())
