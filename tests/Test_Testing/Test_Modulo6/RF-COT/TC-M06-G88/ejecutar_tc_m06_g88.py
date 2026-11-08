"""TC-M06-G88 contra TEST.

Solo envía rechazos que ocurren antes de resolver el período. No envía una
cotización que el caso de uso podría guardar.

    python tests/Test_Testing/Test_Modulo6/RF-COT/TC-M06-G88/ejecutar_tc_m06_g88.py
"""
from __future__ import annotations

import html
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

CARPETA = Path(__file__).resolve().parent
RESULTADOS = CARPETA / "resultados"
BASE_API = "https://api.inmero.co/api-sgpmp-test"
ZONA = "America/Bogota"
ID_AUSENTE = 999999999
OMITIR = {"token", "access_token", "contrasena", "password", "hash_integridad", "numero_id_tributaria",
          "identificador", "finca", "razon_social", "infraestructura", "correo_electronico", "condiciones"}


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


def evidencia(metodo, ruta, codigo, duracion, respuesta, cuerpo=None) -> dict:
    return {"metodo": metodo, "consulta": ruta.split("?")[0], "codigo": codigo, "duracion_ms": duracion,
            "escritura": False, "en": datetime.now(timezone.utc).isoformat(), "cuerpo": cuerpo,
            "respuesta": limpiar(respuesta)}


def negocio(payload) -> str | None:
    return payload.get("error_code") or payload.get("code") if isinstance(payload, dict) else None


def mensaje(payload) -> str | None:
    if not isinstance(payload, dict):
        return None
    texto = payload.get("message") or payload.get("mensaje")
    if not isinstance(texto, str):
        return None
    return texto.replace("QA-M06-", "activo ")


def ficha_activo(activo: dict) -> dict:
    return {"id_activo_biologico": activo.get("id_activo_biologico"), "estado": activo.get("estado"),
            "especie": activo.get("especie"), "valorado_por_costo": activo.get("valorado_por_costo"),
            "valor_razonable_neto": None if activo.get("valor_razonable_neto") is None else str(activo.get("valor_razonable_neto"))}


def ids_cotizaciones(lista) -> list:
    return [c.get("id_cotizacion") for c in lista] if isinstance(lista, list) else []


def render(informe: dict) -> str:
    filas = "".join(
        "<tr>" + "".join(f"<td>{html.escape(str(e.get(k, '')))}</td>" for k in (
            "escenario", "subcaso", "http", "code", "esperado", "estado")) + "</tr>"
        for e in informe["escenarios"]
    )
    return f"""<!DOCTYPE html><html lang="es"><head><meta charset="utf-8"><title>TC-M06-G88</title>
<style>body{{font-family:Segoe UI,sans-serif;margin:2rem;line-height:1.45}}table{{border-collapse:collapse;width:100%}}
th,td{{border:1px solid #ccc;padding:.45rem .6rem;text-align:left;vertical-align:top}}th{{background:#f3f3f3}}
pre{{white-space:pre-wrap}}</style></head><body>
<h1>Módulo 6 — RF-COT — TC-M06-G88</h1>
<p>Generado: {html.escape(informe['generado_en'])}. Aprobación: {informe['porcentaje_aprobacion']} %.</p>
<table><tr><th>Escenario</th><th>Subcaso</th><th>HTTP</th><th>Código</th><th>Esperado</th><th>Estado</th></tr>{filas}</table>
<h2>Contrato</h2><pre>{html.escape(informe['contrato'])}</pre>
<h2>Conteos</h2><pre>{html.escape(json.dumps(informe['conteos'], ensure_ascii=False, indent=2))}</pre>
<h2>Hallazgos</h2><ul>{''.join(f'<li>{html.escape(h)}</li>' for h in informe['hallazgos'])}</ul>
</body></html>"""


def guardar(informe: dict) -> None:
    RESULTADOS.mkdir(parents=True, exist_ok=True)
    (RESULTADOS / "resultado_ejecucion_TC-M06-G88.html").write_text(render(informe), encoding="utf-8")
    (RESULTADOS / "resumen_ejecucion_TC-M06-G88.json").write_text(
        json.dumps({k: v for k, v in informe.items() if k != "analisis"}, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (RESULTADOS / "evidencia_peticiones_TC-M06-G88.json").write_text(json.dumps({
        "caso": "TC-M06-G88", "generado_en": informe["generado_en"], "peticiones": informe["peticiones"],
    }, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (RESULTADOS / "analisis_hallazgos_TC-M06-G88.md").write_text(informe["analisis"], encoding="utf-8")


def subir(escenarios: list[dict]) -> str:
    estados = [e["estado"] for e in escenarios]
    if estados and all(e == "APROBADO" for e in estados):
        return "APROBADO"
    if any(e == "RECHAZADO" for e in estados):
        return "RECHAZADO"
    if any(e == "REQUIERE ACLARACION" for e in estados):
        return "REQUIERE ACLARACION"
    return "BLOQUEADO"


def main() -> int:
    inicio = time.perf_counter()
    peticiones = []
    contrato = (
        "POST /finanzas/cotizaciones recibe activos_cotizados como enteros y valor_cotizacion_propuesto mayor que cero. "
        "No acepta un UUID ni un período. El orden es: activo inexistente responde 404 ACTIVO_NO_ENCONTRADO; "
        "estado distinto de ACTIVO o sin reconocimiento responde 422 ACTIVO_NO_DISPONIBLE; "
        "sin cálculo CALCULADO responde 422 VALOR_RAZONABLE_NO_DISPONIBLE. Esas tres ocurren antes de resolver el período. "
        "Un período cerrado no se rechaza: periodo_para usa el primer período abierto posterior o crea uno, y después inserta. "
        "Esa solicitud no se envía. El diseño pedía 422 también para el activo inexistente."
    )
    informe = {
        "caso": "TC-M06-G88", "ambiente": BASE_API, "generado_en": datetime.now(timezone.utc).isoformat(),
        "contrato": contrato, "activos": [], "periodos": [], "escenarios": [], "conteos": {},
        "peticiones": peticiones, "hallazgos": [], "newman_ejecutado": False,
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

    codigo, perfil, duracion = pedir("GET", "/usuarios/me", token=token)
    peticiones.append(evidencia("GET", "/usuarios/me", codigo, duracion, {
        "nombre_rol": perfil.get("nombre_rol") if isinstance(perfil, dict) else None,
        "estado_cuenta": perfil.get("estado_cuenta") if isinstance(perfil, dict) else None,
    }))
    codigo, activos, duracion = pedir("GET", "/finanzas/activos", token=token)
    informe["activos"] = [ficha_activo(a) for a in activos] if isinstance(activos, list) else []
    peticiones.append(evidencia("GET", "/finanzas/activos", codigo, duracion, {"total": len(informe["activos"]), "activos": informe["activos"]}))
    codigo, cotizaciones, duracion = pedir("GET", "/finanzas/cotizaciones", token=token)
    ids_antes = ids_cotizaciones(cotizaciones)
    peticiones.append(evidencia("GET", "/finanzas/cotizaciones", codigo, duracion, {"total": len(ids_antes), "ids": ids_antes}))
    codigo, periodos, duracion = pedir("GET", "/finanzas/periodos", token=token)
    informe["periodos"] = [{"id_periodo_contable": p.get("id_periodo_contable"), "estado": p.get("estado"),
                            "fecha_inicio": p.get("fecha_inicio"), "fecha_fin": p.get("fecha_fin")}
                           for p in periodos] if isinstance(periodos, list) else []
    peticiones.append(evidencia("GET", "/finanzas/periodos", codigo, duracion, {"total": len(informe["periodos"])}))
    ruta_aud = "/finanzas/auditoria?" + urllib.parse.urlencode([
        ("tipo_evento", "COTIZACION_REGISTRADA"), ("formato", "TECNICO"), ("tamano", "1")])
    codigo, auditoria, duracion = pedir("GET", ruta_aud, token=token)
    eventos_antes = auditoria.get("total_registros") if isinstance(auditoria, dict) else None
    peticiones.append(evidencia("GET", ruta_aud, codigo, duracion, {"total_registros": eventos_antes}))

    valores_antes = {a["id_activo_biologico"]: a["valor_razonable_neto"] for a in informe["activos"]}
    codigo, ausente, duracion = pedir("GET", f"/finanzas/activos/{ID_AUSENTE}", token=token)
    peticiones.append(evidencia("GET", f"/finanzas/activos/{ID_AUSENTE}", codigo, duracion, {"http": codigo, "code": negocio(ausente)}))
    if codigo == 404 and negocio(ausente) == "ACTIVO_NO_ENCONTRADO":
        cuerpo = {"activos_cotizados": [ID_AUSENTE], "valor_cotizacion_propuesto": "1000.0000"}
        codigo_r, respuesta, duracion = pedir("POST", "/finanzas/cotizaciones", cuerpo, token)
        peticiones.append(evidencia("POST", "/finanzas/cotizaciones", codigo_r, duracion, respuesta, cuerpo))
        informe["escenarios"].append({
            "escenario": "A activo inexistente", "subcaso": "TC-M06-46", "id_activo_biologico": ID_AUSENTE,
            "http": codigo_r, "code": negocio(respuesta), "mensaje": mensaje(respuesta), "esperado": "HTTP 422",
            "estado": "REQUIERE ACLARACION" if codigo_r == 404 and negocio(respuesta) == "ACTIVO_NO_ENCONTRADO" else "RECHAZADO",
            "motivo": "El activo no existe y el caso de uso responde 404 ACTIVO_NO_ENCONTRADO antes de guardar. El diseño pedía 422.",
        })
        if codigo_r == 201:
            informe["alta_inesperada"] = True
    else:
        informe["escenarios"].append({
            "escenario": "A activo inexistente", "subcaso": "TC-M06-46", "http": None, "code": None,
            "esperado": "HTTP 422", "estado": "BLOQUEADO",
            "motivo": "No se confirmó con una lectura que el identificador entero estuviera ausente.",
        })

    sin_valor = next((a for a in informe["activos"] if str(a.get("estado", "")).upper() == "ACTIVO" and a.get("valor_razonable_neto") is None), None)
    if sin_valor and not informe.get("alta_inesperada"):
        cuerpo = {"activos_cotizados": [sin_valor["id_activo_biologico"]], "valor_cotizacion_propuesto": "1000.0000"}
        codigo_r, respuesta, duracion = pedir("POST", "/finanzas/cotizaciones", cuerpo, token)
        peticiones.append(evidencia("POST", "/finanzas/cotizaciones", codigo_r, duracion, respuesta, cuerpo))
        correcto = codigo_r == 422 and negocio(respuesta) == "VALOR_RAZONABLE_NO_DISPONIBLE"
        informe["escenarios"].append({
            "escenario": "D sin valor razonable", "subcaso": "TC-M06-47", "id_activo_biologico": sin_valor["id_activo_biologico"],
            "estado_activo": sin_valor["estado"], "valorado_por_costo": sin_valor["valorado_por_costo"],
            "http": codigo_r, "code": negocio(respuesta), "mensaje": mensaje(respuesta), "esperado": "HTTP 422",
            "estado": "APROBADO" if correcto else ("RECHAZADO" if codigo_r == 201 else "REQUIERE ACLARACION"),
            "motivo": "El activo reconocido y ACTIVO no tiene cálculo de valor razonable.",
        })
        if codigo_r == 201:
            informe["alta_inesperada"] = True
    else:
        informe["escenarios"].append({
            "escenario": "D sin valor razonable", "subcaso": "TC-M06-47", "http": None, "code": None,
            "esperado": "HTTP 422", "estado": "BLOQUEADO",
            "motivo": "No hay un activo ACTIVO reconocido sin valor razonable, o el alta anterior persistió.",
        })

    informe["escenarios"].append({
        "escenario": "C período cerrado", "subcaso": "TC-M06-47", "http": None, "code": None, "esperado": "HTTP 422",
        "estado": "REQUIERE ACLARACION",
        "motivo": "La cotización no recibe un período. Si el de la fecha está cerrado, el caso de uso toma el abierto posterior e inserta. Enviar la solicitud crearía la cotización.",
    })

    no_activo = None
    admin_correo, admin_clave = os.environ.get("QA_ADMIN_CORREO"), os.environ.get("QA_ADMIN_CONTRASENA")
    if admin_correo and admin_clave and not informe.get("alta_inesperada"):
        codigo, login_admin, duracion = pedir("POST", "/sesiones/", {"correo_electronico": admin_correo, "contrasena": admin_clave})
        token_admin = login_admin.get("token") if isinstance(login_admin, dict) else None
        peticiones.append(evidencia("POST", "/sesiones/", codigo, duracion, limpiar(login_admin if isinstance(login_admin, dict) else {})))
        if token_admin:
            for pagina in range(1, 6):
                ruta = f"/activos-biologicos?pagina={pagina}&page_size=100"
                codigo, lista, duracion = pedir("GET", ruta, token=token_admin)
                registros = lista.get("registros", []) if isinstance(lista, dict) else []
                resumen = {"pagina": pagina, "total": lista.get("total_registros") if isinstance(lista, dict) else None,
                           "vistos": len(registros)}
                elegido = next((r for r in registros if str(r.get("nombre_estado", "")).upper() != "ACTIVO"), None)
                if elegido:
                    resumen["id_activo_biologico"] = elegido.get("id_activo_biologico")
                    resumen["nombre_estado"] = elegido.get("nombre_estado")
                peticiones.append(evidencia("GET", ruta, codigo, duracion, resumen))
                if elegido:
                    no_activo = {"id_activo_biologico": elegido.get("id_activo_biologico"), "estado": elegido.get("nombre_estado")}
                    break
                if not isinstance(lista, dict) or pagina >= (lista.get("total_paginas") or 1):
                    break
    if no_activo and not informe.get("alta_inesperada"):
        codigo, historia, duracion = pedir("GET", f"/finanzas/activos/{no_activo['id_activo_biologico']}", token=token)
        estado_contador = None
        if isinstance(historia, dict) and isinstance(historia.get("activo"), dict):
            estado_contador = historia["activo"].get("estado")
        peticiones.append(evidencia("GET", f"/finanzas/activos/{no_activo['id_activo_biologico']}", codigo, duracion, {
            "http": codigo, "code": negocio(historia), "estado": estado_contador,
        }))
        if codigo == 200 and str(estado_contador).upper() != "ACTIVO":
            cuerpo = {"activos_cotizados": [no_activo["id_activo_biologico"]], "valor_cotizacion_propuesto": "1000.0000"}
            codigo_r, respuesta, duracion = pedir("POST", "/finanzas/cotizaciones", cuerpo, token)
            peticiones.append(evidencia("POST", "/finanzas/cotizaciones", codigo_r, duracion, respuesta, cuerpo))
            correcto = codigo_r == 422 and negocio(respuesta) == "ACTIVO_NO_DISPONIBLE"
            informe["escenarios"].append({
                "escenario": "B estado distinto de ACTIVO", "subcaso": "TC-M06-46",
                "id_activo_biologico": no_activo["id_activo_biologico"], "estado_activo": estado_contador,
                "http": codigo_r, "code": negocio(respuesta), "mensaje": mensaje(respuesta), "esperado": "HTTP 422",
                "estado": "APROBADO" if correcto else ("RECHAZADO" if codigo_r == 201 else "REQUIERE ACLARACION"),
            })
        else:
            informe["escenarios"].append({
                "escenario": "B estado distinto de ACTIVO", "subcaso": "TC-M06-46", "http": None, "code": None,
                "esperado": "HTTP 422", "estado": "BLOQUEADO",
                "motivo": "El activo que no está ACTIVO no es visible para el Contador, así que el POST no aislaría la validación de estado.",
            })
    else:
        informe["escenarios"].append({
            "escenario": "B estado distinto de ACTIVO", "subcaso": "TC-M06-46", "http": None, "code": None,
            "esperado": "HTTP 422", "estado": "BLOQUEADO",
            "motivo": "No se encontró un activo en estado distinto de ACTIVO dentro de las páginas consultadas.",
        })

    codigo, cotizaciones, duracion = pedir("GET", "/finanzas/cotizaciones", token=token)
    ids_despues = ids_cotizaciones(cotizaciones)
    peticiones.append(evidencia("GET", "/finanzas/cotizaciones", codigo, duracion, {"total": len(ids_despues), "ids": ids_despues}))
    codigo, auditoria, duracion = pedir("GET", ruta_aud, token=token)
    eventos_despues = auditoria.get("total_registros") if isinstance(auditoria, dict) else None
    peticiones.append(evidencia("GET", ruta_aud, codigo, duracion, {"total_registros": eventos_despues}))
    codigo, activos, duracion = pedir("GET", "/finanzas/activos", token=token)
    despues = [ficha_activo(a) for a in activos] if isinstance(activos, list) else []
    valores_despues = {a["id_activo_biologico"]: a["valor_razonable_neto"] for a in despues}
    peticiones.append(evidencia("GET", "/finanzas/activos", codigo, duracion, {"total": len(despues)}))
    codigo, periodos, duracion = pedir("GET", "/finanzas/periodos", token=token)
    periodos_despues = [{"id_periodo_contable": p.get("id_periodo_contable"), "estado": p.get("estado")}
                        for p in periodos] if isinstance(periodos, list) else []
    peticiones.append(evidencia("GET", "/finanzas/periodos", codigo, duracion, {"total": len(periodos_despues)}))
    informe["conteos"] = {
        "cotizaciones_antes": ids_antes, "cotizaciones_despues": ids_despues,
        "eventos_antes": eventos_antes, "eventos_despues": eventos_despues,
        "sin_cotizacion_nueva": ids_antes == ids_despues, "sin_evento_nuevo": eventos_antes == eventos_despues,
        "valor_razonable_sin_cambio": valores_antes == valores_despues,
        "periodos_sin_cambio": [(p["id_periodo_contable"], p["estado"]) for p in informe["periodos"]] == [
            (p["id_periodo_contable"], p["estado"]) for p in periodos_despues],
    }
    intacto = all(informe["conteos"][k] for k in (
        "sin_cotizacion_nueva", "sin_evento_nuevo", "valor_razonable_sin_cambio", "periodos_sin_cambio"))
    if not intacto:
        for escenario in informe["escenarios"]:
            if escenario["estado"] == "APROBADO":
                escenario["estado"] = "RECHAZADO"
                escenario["motivo"] = "La respuesta de negocio coincidió, pero los conteos posteriores cambiaron."
    subcasos = []
    for codigo_sub in ("TC-M06-46", "TC-M06-47"):
        propios = [e for e in informe["escenarios"] if e["subcaso"] == codigo_sub]
        subcasos.append({"subcaso": codigo_sub, "estado": subir(propios), "escenarios": [e["escenario"] for e in propios]})
    informe["subcasos"] = subcasos
    aprobados = sum(s["estado"] == "APROBADO" for s in subcasos)
    informe["aprobados"] = aprobados
    informe["rechazados"] = sum(s["estado"] == "RECHAZADO" for s in subcasos)
    informe["bloqueados"] = sum(s["estado"] == "BLOQUEADO" for s in subcasos)
    informe["requiere_aclaracion"] = sum(s["estado"] == "REQUIERE ACLARACION" for s in subcasos)
    informe["porcentaje_aprobacion"] = round(aprobados / 2 * 100)
    informe["hallazgos"] = [
        "QUESTION-M06-G88-01: el activo inexistente responde 404 ACTIVO_NO_ENCONTRADO. El diseño esperaba 422. El DTO solo acepta enteros, no UUID.",
        "QUESTION-M06-G88-02: un período cerrado no impide la cotización. El caso de uso la lleva al período abierto posterior y la guarda. Esa solicitud no se envió.",
    ]
    if not intacto:
        informe["hallazgos"].insert(0, "Los conteos de cotizaciones, eventos, valores o períodos cambiaron durante la prueba.")
    informe["analisis"] = (
        "# TC-M06-G88\n\nNo se usó SQL local ni Newman. La evidencia salió del script de Python.\n\n"
        "El endpoint es POST /finanzas/cotizaciones. El período no es un campo del cuerpo.\n"
        f"Cotizaciones antes y después: {len(ids_antes)} y {len(ids_despues)}. "
        f"Eventos: {eventos_antes} y {eventos_despues}. Intactos: {intacto}.\n"
        + "\n".join(f"- {s['subcaso']}: {s['estado']}" for s in subcasos) + "\n"
    )
    informe["duracion_ms"] = round((time.perf_counter() - inicio) * 1000)
    guardar(informe)
    print(" ".join(f"{s['subcaso']} {s['estado']}" for s in subcasos), f"intacto {intacto}")
    for e in informe["escenarios"]:
        print(e["escenario"], e["estado"], e.get("http"), e.get("code"))
    return 0 if aprobados == 2 else 2


if __name__ == "__main__":
    raise SystemExit(main())
