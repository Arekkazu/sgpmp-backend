"""Ejecución de TC-M06-G98 contra la API de TEST.

Autentica con POST /sesiones/ usando QA_CORREO y QA_CONTRASENA del entorno.
Solo consulta. No registra eventos sanitarios, no registra deterioros y no cierra períodos.
Si el titular visible no está aislado, un escenario que exigiría escritura queda BLOQUEADO.

    python tests/Test_Testing/Test_Modulo6/RF-88/TC-M06-G98/ejecutar_tc_m06_g98.py
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
from decimal import Decimal, InvalidOperation
from pathlib import Path

CARPETA = Path(__file__).resolve().parent
RESULTADOS = CARPETA / "resultados"
BASE_API = "https://api.inmero.co/api-sgpmp-test"
AMBIENTE = BASE_API
TOLERANCIA = Decimal("0.01")
SECRETOS = {
    "token", "access_token", "contrasena", "password", "hash_integridad",
    "nombre_usuario", "correo_electronico", "numero_id_tributaria",
}
CLINICOS = {"diagnostico", "medicamento", "dosis", "unidad_dosis", "frecuencia", "duracion", "observaciones"}


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
            if not raw:
                return resp.status, None
            return resp.status, json.loads(raw)
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
    if profundidad > 6:
        return "..."
    if isinstance(valor, dict):
        salida = {}
        for clave, item in valor.items():
            if clave in SECRETOS or clave in CLINICOS:
                continue
            if clave in ("finca", "identificador", "infraestructura", "actor"):
                continue
            salida[clave] = limpiar(item, profundidad + 1)
        return salida
    if isinstance(valor, list):
        return [limpiar(item, profundidad + 1) for item in valor[:40]]
    if isinstance(valor, str) and len(valor) > 240:
        return valor[:240]
    return valor


def dec(valor) -> Decimal | None:
    if valor is None or isinstance(valor, bool):
        return None
    try:
        return Decimal(str(valor))
    except (InvalidOperation, ValueError):
        return None


def autenticar() -> tuple[int, str | None, dict]:
    correo = os.environ.get("QA_CORREO")
    contrasena = os.environ.get("QA_CONTRASENA")
    if not correo or not contrasena:
        raise SystemExit("Defina QA_CORREO y QA_CONTRASENA en el entorno del proceso. No las escriba en el archivo.")
    codigo, payload = pedir("POST", "/sesiones/", {"correo_electronico": correo, "contrasena": contrasena})
    token = payload.get("token") if isinstance(payload, dict) else None
    publico = limpiar(payload if isinstance(payload, dict) else {})
    return codigo, token, publico if isinstance(publico, dict) else {}


def rutas_openapi() -> tuple[int, list[str]]:
    codigo, payload = pedir("GET", "/openapi.json")
    if codigo != 200 or not isinstance(payload, dict):
        return codigo, []
    interes = ("sanitari", "deterior", "evento", "activos", "auditoria")
    encontradas = []
    for ruta, metodos in (payload.get("paths") or {}).items():
        texto = ruta.lower()
        if any(clave in texto for clave in interes) and isinstance(metodos, dict):
            verbos = ",".join(sorted(k.upper() for k in metodos if k in ("get", "post", "put", "patch", "delete")))
            encontradas.append(f"{verbos} {ruta}")
    return codigo, sorted(encontradas)


def eventos_de(payload) -> list[dict]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for clave in ("eventos", "items", "data"):
            if isinstance(payload.get(clave), list):
                return [item for item in payload[clave] if isinstance(item, dict)]
    return []


def id_evento(evento: dict) -> int | None:
    for clave in ("id_evento", "id_eventos", "id_evento_sanitario"):
        valor = evento.get(clave)
        if isinstance(valor, int):
            return valor
        if isinstance(valor, str) and valor.isdigit():
            return int(valor)
    return None


def payload_deterioro(evento: dict) -> dict:
    for clave in ("payload_evento", "resumen_payload", "datos_nuevos"):
        valor = evento.get(clave)
        if isinstance(valor, dict):
            return valor
        if isinstance(valor, str):
            try:
                parsed = json.loads(valor)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed
    return {}


def consultar(token: str) -> tuple[list[dict], dict]:
    evidencias: list[dict] = []
    datos: dict = {"activos": [], "periodos": [], "deterioros": [], "por_activo": []}

    def anotar(metodo: str, ruta: str, codigo: int, resumen: dict) -> None:
        evidencias.append({"metodo": metodo, "ruta": ruta.split("?")[0], "consulta": ruta, "codigo": codigo, "resumen": resumen})

    codigo_openapi, rutas = rutas_openapi()
    anotar("GET", "/openapi.json", codigo_openapi, {"rutas_relevantes": len(rutas)})
    datos["openapi_codigo"] = codigo_openapi
    datos["rutas"] = rutas

    for ruta, destino in (
        ("/finanzas/activos", "activos"),
        ("/finanzas/periodos", "periodos"),
        ("/finanzas/auditoria?tipo_evento=DETERIORO_REGISTRADO&formato=TECNICO&tamano=100", "deterioros"),
    ):
        codigo, payload = pedir("GET", ruta, token=token)
        if destino == "deterioros" and codigo == 200 and isinstance(payload, dict):
            datos["deterioros"] = eventos_de(payload)
            anotar("GET", ruta, codigo, {"total_registros": payload.get("total_registros"), "devueltos": len(datos["deterioros"])})
        elif codigo == 200 and isinstance(payload, list):
            datos[destino] = payload
            anotar("GET", ruta, codigo, {"registros": len(payload)})
        else:
            anotar("GET", ruta, codigo, limpiar(payload) if isinstance(payload, dict) else {"tipo": type(payload).__name__})

    activos = [a for a in datos["activos"] if isinstance(a, dict) and isinstance(a.get("id_activo_biologico"), int)]
    for activo in activos[:40]:
        id_activo = activo["id_activo_biologico"]
        ficha: dict = {"id_activo_biologico": id_activo, "valorado_por_costo": bool(activo.get("valorado_por_costo"))}
        for nombre, ruta in (
            ("sanitarios_m06", f"/finanzas/activos/{id_activo}/eventos-sanitarios"),
            ("eventos_m02", f"/activos-biologicos/{id_activo}/eventos"),
            ("historial", f"/finanzas/activos/{id_activo}"),
        ):
            codigo, payload = pedir("GET", ruta, token=token)
            ficha[nombre + "_http"] = codigo
            if nombre == "historial" and codigo == 200 and isinstance(payload, dict):
                valoracion = payload.get("valoracion_costo") if isinstance(payload.get("valoracion_costo"), dict) else {}
                lineas = payload.get("lineas") if isinstance(payload.get("lineas"), list) else []
                ficha["valoracion_costo"] = limpiar(valoracion)
                ficha["lineas_deterioro"] = sum(
                    1 for linea in lineas
                    if isinstance(linea, dict) and str(linea.get("tipo_hecho") or "") == "DETERIORO_ACTIVO_COSTO"
                )
                anotar("GET", ruta, codigo, {
                    "valorado": bool(valoracion),
                    "deterioro_acumulado": valoracion.get("deterioro_acumulado"),
                    "valor_contable_por_costo": valoracion.get("valor_contable_por_costo"),
                    "lineas_deterioro": ficha["lineas_deterioro"],
                })
            elif codigo == 200:
                eventos = eventos_de(payload)
                clinicos = []
                for evento in eventos:
                    sanitario = evento.get("sanitario") if isinstance(evento.get("sanitario"), dict) else None
                    if nombre == "sanitarios_m06" or sanitario is not None or str(evento.get("tipo") or "").upper() in {
                        "VACUNACION", "TRATAMIENTO", "DIAGNOSTICO", "CONTROL_PREVENTIVO", "SANITARIO",
                    }:
                        clinicos.append({
                            "id_evento": id_evento(evento),
                            "tipo": (sanitario or evento).get("tipo") or evento.get("tipo"),
                            "tiene_monto": any(k in evento for k in ("impacto_economico", "impacto_economico_cop", "valor_economico")),
                        })
                ficha[nombre] = clinicos
                anotar("GET", ruta, codigo, {"eventos": len(eventos), "sanitarios_o_clinicos": len(clinicos)})
            else:
                ficha[nombre] = []
                anotar("GET", ruta, codigo, limpiar(payload) if isinstance(payload, dict) else {"vacio": True})
        datos["por_activo"].append(ficha)
    return evidencias, datos


def medir(datos: dict) -> dict:
    activos = datos["activos"]
    periodos = datos["periodos"]
    fincas = {a.get("id_finca") for a in activos if isinstance(a, dict) and a.get("id_finca") is not None}
    nits = {p.get("numero_id_tributaria") for p in periodos if isinstance(p, dict) and p.get("numero_id_tributaria")}
    por_costo = sum(1 for a in activos if isinstance(a, dict) and a.get("valorado_por_costo"))
    return {
        "activos": len(activos),
        "fincas": len(fincas),
        "nits_en_periodos": len(nits),
        "periodos": len(periodos),
        "valorados_por_costo": por_costo,
        "aislado": len(activos) == 1 and len(fincas) <= 1 and len(nits) <= 1 and len(periodos) <= 1,
        "deterioros_auditados": len(datos["deterioros"]),
        "openapi_http": datos.get("openapi_codigo"),
    }


def deterioros_limpios(datos: dict) -> list[dict]:
    salida = []
    for evento in datos["deterioros"]:
        cuerpo = payload_deterioro(evento)
        salida.append({
            "id_activo_biologico": evento.get("id_activo_biologico"),
            "id_evento_sanitario": cuerpo.get("id_evento_sanitario"),
            "impacto": cuerpo.get("impacto") if cuerpo.get("impacto") is not None else evento.get("monto_afectado"),
            "valor_contable_auditado": cuerpo.get("valor_contable"),
            "monto_afectado": evento.get("monto_afectado"),
        })
    return salida


def formula_cuadra(valoracion: dict) -> tuple[bool, str]:
    costo = dec(valoracion.get("costos_adquisicion"))
    dep = dec(valoracion.get("depreciacion_acumulada"))
    det = dec(valoracion.get("deterioro_acumulado"))
    libros = dec(valoracion.get("valor_contable_por_costo"))
    if None in (costo, dep, det, libros):
        return False, "La valoración por costo no trae costo, depreciación, deterioro y valor en libros."
    esperado = max(Decimal("0"), costo - dep - det)
    if abs(esperado - libros) <= TOLERANCIA:
        return True, f"valor_en_libros {libros} = max(0, {costo} - {dep} - {det})"
    return False, f"valor_en_libros {libros}; la fórmula da {esperado}"


def clasificar(datos: dict, panorama: dict) -> tuple[list[dict], list[dict]]:
    registros = deterioros_limpios(datos)
    eventos_por_activo: dict[int, set[int]] = {}
    eventos_sin_monto: list[dict] = []
    for ficha in datos["por_activo"]:
        ids = set()
        for origen in ("sanitarios_m06", "eventos_m02"):
            for evento in ficha.get(origen) or []:
                if isinstance(evento, dict) and isinstance(evento.get("id_evento"), int):
                    ids.add(evento["id_evento"])
                    if not evento.get("tiene_monto"):
                        eventos_sin_monto.append({
                            "id_activo_biologico": ficha["id_activo_biologico"],
                            "id_evento": evento["id_evento"],
                            "tipo": evento.get("tipo"),
                            "valorado_por_costo": ficha.get("valorado_por_costo"),
                            "valoracion_costo": ficha.get("valoracion_costo") or {},
                        })
        eventos_por_activo[ficha["id_activo_biologico"]] = ids

    vinculados = []
    for registro in registros:
        activo_id = registro.get("id_activo_biologico")
        evento_id = registro.get("id_evento_sanitario")
        impacto = dec(registro.get("impacto"))
        if isinstance(activo_id, int) and isinstance(evento_id, int) and impacto is not None and impacto > 0:
            if evento_id in eventos_por_activo.get(activo_id, set()):
                ficha = next(f for f in datos["por_activo"] if f["id_activo_biologico"] == activo_id)
                vinculados.append((registro, ficha, impacto))

    ids_con_deterioro = {
        (r.get("id_activo_biologico"), r.get("id_evento_sanitario"))
        for r in registros
        if r.get("id_evento_sanitario") is not None
    }
    compartido = (
        f"Hay {panorama['activos']} activos, {panorama['fincas']} fincas, "
        f"{panorama['nits_en_periodos']} NIT y {panorama['periodos']} períodos. "
        "No se creó un evento ni se registró un deterioro."
    )

    if vinculados:
        registro, ficha, impacto = vinculados[0]
        valoracion = ficha.get("valoracion_costo") or {}
        cuadra, detalle = formula_cuadra(valoracion)
        det = dec(valoracion.get("deterioro_acumulado"))
        incorporado = det is not None and det + TOLERANCIA >= impacto
        estado = "APROBADO" if cuadra and incorporado else "RECHAZADO"
        motivo = (
            f"Activo {ficha['id_activo_biologico']}, evento {registro['id_evento_sanitario']}, "
            f"impacto {impacto}. {detalle}. "
            f"Líneas DETERIORO_ACTIVO_COSTO: {ficha.get('lineas_deterioro', 0)}."
        )
        if not incorporado:
            motivo += " El deterioro acumulado no cubre el impacto auditado."
        sub_10 = {
            "id": "TC-M06-10",
            "esperado": "El impacto económico del evento sanitario queda dentro del deterioro y del valor en libros.",
            "obtenido": detalle,
            "estado": estado,
            "motivo": motivo,
        }
    else:
        sub_10 = {
            "id": "TC-M06-10",
            "esperado": "Evento sanitario del activo, impacto económico verificable e incorporación al valor en libros.",
            "obtenido": None,
            "estado": "BLOQUEADO",
            "motivo": (
                f"Eventos clínicos sin monto en el cuerpo: {len(eventos_sin_monto)}. "
                f"Deterioros auditados con evento del mismo activo: {len(vinculados)}. {compartido} "
                "Registrar el deterioro escribiría la valoración compartida."
            ),
        }

    candidato_11 = None
    for evento in eventos_sin_monto:
        if (evento["id_activo_biologico"], evento["id_evento"]) in ids_con_deterioro:
            continue
        valoracion = evento["valoracion_costo"]
        det = dec(valoracion.get("deterioro_acumulado")) if valoracion else None
        if evento["valorado_por_costo"] and det is not None and det == 0:
            cuadra, detalle = formula_cuadra(valoracion)
            if cuadra:
                candidato_11 = (evento, detalle)
                break
    if candidato_11:
        evento, detalle = candidato_11
        sub_11 = {
            "id": "TC-M06-11",
            "esperado": "Un evento clínico sin monto no genera deterioro ni reduce el valor en libros.",
            "obtenido": detalle,
            "estado": "APROBADO",
            "motivo": (
                f"Activo {evento['id_activo_biologico']}, evento {evento['id_evento']}, tipo {evento.get('tipo')}. "
                "El evento no trae impacto económico y no aparece en DETERIORO_REGISTRADO. "
                f"El deterioro acumulado es 0. {detalle}."
            ),
        }
    else:
        sub_11 = {
            "id": "TC-M06-11",
            "esperado": "Evento clínico asociado, sin afectación económica, y valor en libros sin deterioro por ese evento.",
            "obtenido": None,
            "estado": "BLOQUEADO",
            "motivo": (
                f"No hay un activo a costo con evento clínico, deterioro acumulado 0 y sin DETERIORO_REGISTRADO "
                f"para ese evento. Eventos clínicos leídos: {len(eventos_sin_monto)}. {compartido}"
            ),
        }

    hallazgos = []
    if sub_10["estado"] == "BLOQUEADO" or sub_11["estado"] == "BLOQUEADO":
        hallazgos.append({
            "id": "QUESTION-M06-G98-01",
            "titulo": "No hay un par aislado de evento sanitario con y sin impacto económico",
            "descripcion": compartido + " El monto no viaja en el evento de RF-41; se informa al registrar el deterioro de RF-88.",
            "rf": "RF-88 / RF-41",
            "categoria": "Capacidad de prueba",
            "tipo": "QUESTION",
            "equipo": "QA, con datos aislados preparados por DBA si el NIT actual no puede segregarse",
            "severidad": "Medio",
            "tiempo_maximo": "2 días hábiles",
            "estado": "Abierto",
            "justificacion": "Impide ejecutar el caso. No evidencia un cálculo incorrecto ni un endpoint ausente. Forzar el alta modificaría activos y valoraciones compartidos.",
            "correccion": "Disponer de un titular exclusivo, un activo valorado por costo, un evento sanitario ya asociado y, para el escenario positivo, un impacto que pueda registrarse solo sobre ese activo.",
        })
    if sub_10["estado"] == "RECHAZADO":
        hallazgos.append({
            "id": "BUG-M06-G98-01",
            "titulo": "El deterioro auditado no queda reflejado en el valor en libros",
            "descripcion": sub_10["motivo"],
            "rf": "RF-88",
            "categoria": "Funcional",
            "tipo": "BUG",
            "equipo": "Desarrollo Backend",
            "severidad": "Severo",
            "tiempo_maximo": "1 día hábil",
            "estado": "Abierto",
            "justificacion": "La valoración persistida no cumple la fórmula costo menos depreciación menos deterioro con el impacto ya auditado.",
            "correccion": "Revisar el alta de deterioro y el valor en libros del activo señalado en la evidencia.",
        })
    return [sub_10, sub_11], hallazgos


def informes(login_codigo: int, login_publico: dict, evidencias: list[dict], datos: dict) -> dict:
    panorama = medir(datos)
    subcasos, hallazgos = clasificar(datos, panorama)
    conteo = {"APROBADO": 0, "RECHAZADO": 0, "BLOQUEADO": 0}
    for sub in subcasos:
        conteo[sub["estado"]] += 1
    return {
        "caso": "TC-M06-G98",
        "modulo": 6,
        "rf": "RF-88 / RF-41",
        "ambiente": AMBIENTE,
        "generado_en": datetime.now(timezone.utc).isoformat(),
        "login_http": login_codigo,
        "login": login_publico,
        "escrituras": False,
        "datos_prueba_creados": [],
        "integracion": {
            "evento_sanitario": "POST /activos-biologicos/{id_activo}/eventos/sanitario",
            "consulta_eventos": "GET /activos-biologicos/{id_activo}/eventos",
            "eventos_para_deterioro": "GET /finanzas/activos/{id_activo_biologico}/eventos-sanitarios",
            "deterioro": "POST /finanzas/activos/{id_activo_biologico}/deterioros",
            "valor_en_libros": "GET /finanzas/activos y GET /finanzas/activos/{id_activo_biologico}",
            "auditoria": "GET /finanzas/auditoria?tipo_evento=DETERIORO_REGISTRADO",
            "monto_en_evento_rf41": False,
            "monto_en_deterioro_rf88": True,
        },
        "rutas_openapi": datos.get("rutas") or [],
        "panorama": panorama,
        "deterioros": deterioros_limpios(datos),
        "http": evidencias,
        "subcasos": subcasos,
        "hallazgos": hallazgos,
        "aprobados": conteo["APROBADO"],
        "rechazados": conteo["RECHAZADO"],
        "bloqueados": conteo["BLOQUEADO"],
        "total": 2,
        "porcentaje_aprobacion": round(conteo["APROBADO"] * 100 / 2, 2),
    }


def render(informe: dict) -> str:
    filas = "".join(
        "<tr><td>{id}</td><td>{esperado}</td><td>{obtenido}</td><td class=\"b\">{estado}</td><td>{motivo}</td></tr>".format(
            **{k: html.escape(str(v)) for k, v in sub.items()}
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
        "<li><strong>{id}</strong> {titulo}. {tipo}, {categoria}, {equipo}, {severidad}, {tiempo_maximo}. {justificacion}</li>".format(
            **{k: html.escape(str(v)) for k, v in h.items()}
        )
        for h in informe["hallazgos"]
    ) or "<li>Sin hallazgos abiertos.</li>"
    rutas = "".join(f"<li><code>{html.escape(r)}</code></li>" for r in informe["rutas_openapi"][:40])
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <title>TC-M06-G98 — ejecución</title>
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
  <h1>Módulo 6 — RF-88 / RF-41 — TC-M06-G98</h1>
  <p>Fecha: {html.escape(informe['generado_en'])}. Ambiente: {html.escape(informe['ambiente'])}.</p>
  <p>Autenticación POST /sesiones/: HTTP {informe['login_http']}. Escrituras: ninguna. Datos de prueba creados: ninguno.</p>
  <h2>Resumen</h2>
  <table>
    <tr><th>Total</th><td>{informe['total']}</td></tr>
    <tr><th>Aprobados</th><td>{informe['aprobados']}</td></tr>
    <tr><th>Rechazados</th><td>{informe['rechazados']}</td></tr>
    <tr><th>Bloqueados</th><td>{informe['bloqueados']}</td></tr>
    <tr><th>Porcentaje de aprobación</th><td>{informe['porcentaje_aprobacion']} %</td></tr>
  </table>
  <h2>Subcasos</h2>
  <table>
    <thead><tr><th>Subcaso</th><th>Esperado</th><th>Obtenido</th><th>Estado</th><th>Validación</th></tr></thead>
    <tbody>{filas}</tbody>
  </table>
  <h2>Integración identificada</h2>
  <pre>{html.escape(json.dumps(informe['integracion'], ensure_ascii=False, indent=2))}</pre>
  <h2>Rutas relevantes en OpenAPI</h2>
  <ul>{rutas}</ul>
  <h2>Panorama</h2>
  <pre>{html.escape(json.dumps(informe['panorama'], ensure_ascii=False, indent=2))}</pre>
  <h2>Respuestas HTTP</h2>
  <table>
    <thead><tr><th>Solicitud</th><th>Código</th><th>Resumen sin secretos</th></tr></thead>
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
            "caso": "TC-M06-G98", "modulo": 6, "rf": "RF-88 / RF-41", "ambiente": AMBIENTE,
            "generado_en": datetime.now(timezone.utc).isoformat(), "login_http": codigo,
            "login": login_publico, "escrituras": False, "datos_prueba_creados": [],
            "integracion": {}, "rutas_openapi": [], "panorama": {}, "deterioros": [], "http": [],
            "subcasos": [
                {"id": "TC-M06-10", "esperado": "Deterioro incorporado al valor en libros", "obtenido": None, "estado": "BLOQUEADO", "motivo": f"POST /sesiones/ respondió {codigo}."},
                {"id": "TC-M06-11", "esperado": "Evento clínico sin deterioro monetario", "obtenido": None, "estado": "BLOQUEADO", "motivo": f"POST /sesiones/ respondió {codigo}."},
            ],
            "hallazgos": [{
                "id": "QUESTION-M06-G98-02", "titulo": "La autenticación no entregó token",
                "descripcion": f"HTTP {codigo}.", "rf": "RF-88 / RF-41", "categoria": "Seguridad",
                "tipo": "QUESTION", "equipo": "QA / Implementación", "severidad": "Severo",
                "tiempo_maximo": "1 día hábil", "estado": "Abierto",
                "justificacion": "Sin token no se puede leer el módulo ni ejecutar los subcasos.",
                "correccion": "Confirmar la cuenta del ambiente TEST y que no esté bloqueada.",
            }],
            "aprobados": 0, "rechazados": 0, "bloqueados": 2, "total": 2, "porcentaje_aprobacion": 0,
        }
    else:
        evidencias, datos = consultar(token)
        informe = informes(codigo, login_publico, evidencias, datos)
    (RESULTADOS / "resumen_ejecucion_TC-M06-G98.json").write_text(
        json.dumps(informe, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    (RESULTADOS / "evidencia_peticiones_TC-M06-G98.json").write_text(
        json.dumps({
            "login_http": informe["login_http"], "login": informe["login"],
            "http": informe["http"], "panorama": informe["panorama"],
            "deterioros": informe["deterioros"], "subcasos": informe["subcasos"],
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (RESULTADOS / "resultado_ejecucion_TC-M06-G98.html").write_text(render(informe), encoding="utf-8")
    print(
        f"APROBADOS {informe['aprobados']} RECHAZADOS {informe['rechazados']} "
        f"BLOQUEADOS {informe['bloqueados']} PCT {informe['porcentaje_aprobacion']}"
    )
    return 0 if informe["aprobados"] == 2 and informe["rechazados"] == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
