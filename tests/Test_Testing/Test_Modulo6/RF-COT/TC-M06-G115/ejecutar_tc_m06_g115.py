"""TC-M06-G115 contra TEST.

No registra cotizaciones. Consulta permisos de Contador, Administrador y
Productor, y envía el POST del Productor porque el permiso se niega antes
de crear la cotización.

    python tests/Test_Testing/Test_Modulo6/RF-COT/TC-M06-G115/ejecutar_tc_m06_g115.py
"""
from __future__ import annotations

import html
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

CARPETA = Path(__file__).resolve().parent
RESULTADOS = CARPETA / "resultados"
BASE_API = "https://api.inmero.co/api-sgpmp-test"
ZONA = "America/Bogota"
OMITIR = {"token", "access_token", "contrasena", "password", "hash_integridad", "numero_id_tributaria",
          "identificador", "finca", "infraestructura", "razon_sin_mercado", "correo_electronico",
          "numero_identificacion", "telefono", "direccion", "nombre", "apellidos", "condiciones"}
ACCIONES = {1: "crear", 2: "leer", 3: "actualizar", 4: "desactivar", 5: "ejecutar"}
ROLES = {1: "Administrador", 2: "Productor", 5: "Contador"}


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
    if profundidad > 5:
        return "..."
    if isinstance(valor, dict):
        return {k: ({"omitido": True} if k in OMITIR else limpiar(v, profundidad + 1)) for k, v in valor.items()}
    if isinstance(valor, list):
        return [limpiar(v, profundidad + 1) for v in valor[:30]]
    if isinstance(valor, str) and len(valor) > 240:
        return valor[:240]
    return valor


def evidencia(metodo, ruta, codigo, duracion, respuesta, cuerpo=None) -> dict:
    return {"metodo": metodo, "consulta": ruta.split("?")[0], "codigo": codigo, "duracion_ms": duracion,
            "escritura": False, "en": datetime.now(timezone.utc).isoformat(), "cuerpo": cuerpo,
            "respuesta": limpiar(respuesta)}


def negocio(payload) -> str | None:
    return payload.get("error_code") or payload.get("code") if isinstance(payload, dict) else None


def sesion(correo: str, contrasena: str, peticiones: list) -> tuple[str | None, bool]:
    codigo, login, duracion = pedir("POST", "/sesiones/", {"correo_electronico": correo, "contrasena": contrasena})
    token = login.get("token") if isinstance(login, dict) else None
    cerrada = isinstance(login, dict) and "cerrado automáticamente" in str(login.get("message", ""))
    peticiones.append(evidencia("POST", "/sesiones/", codigo, duracion, limpiar(login if isinstance(login, dict) else {})))
    return token if codigo == 200 else None, cerrada


def perfil(token: str, peticiones: list) -> dict:
    codigo, datos, duracion = pedir("GET", "/usuarios/me", token=token)
    ficha = {"http": codigo, "id_usuario": datos.get("id_usuario") if isinstance(datos, dict) else None,
             "nombre_rol": datos.get("nombre_rol") if isinstance(datos, dict) else None,
             "estado_cuenta": datos.get("estado_cuenta") if isinstance(datos, dict) else None}
    peticiones.append(evidencia("GET", "/usuarios/me", codigo, duracion, ficha))
    return ficha


def permiso_cotizaciones(token: str, peticiones: list) -> dict:
    codigo, datos, duracion = pedir("GET", "/sesiones/me/permisos", token=token)
    lista = datos.get("permisos", []) if isinstance(datos, dict) else []
    acciones = sorted(p.get("id_accion") for p in lista if isinstance(p, dict) and p.get("nombre_recurso") == "cotizaciones")
    ficha = {"http": codigo, "total_permisos": len(lista), "cotizaciones": [ACCIONES.get(a, a) for a in acciones],
             "puede_crear": 1 in acciones}
    peticiones.append(evidencia("GET", "/sesiones/me/permisos", codigo, duracion, ficha))
    return ficha


def ficha_activo(activo: dict) -> dict:
    return {"id_activo_biologico": activo.get("id_activo_biologico"), "estado": activo.get("estado"),
            "especie": activo.get("especie"), "valorado_por_costo": activo.get("valorado_por_costo"),
            "valor_razonable_neto": None if activo.get("valor_razonable_neto") is None else str(activo.get("valor_razonable_neto")),
            "valor_contable_por_costo": None if activo.get("valor_contable_por_costo") is None else str(activo.get("valor_contable_por_costo"))}


def ficha_cotizacion(item: dict) -> dict:
    return {"id_cotizacion": item.get("id_cotizacion"), "estado": item.get("estado"),
            "id_periodo_contable": item.get("id_periodo_contable"), "activos_cotizados": item.get("activos_cotizados"),
            "valor_razonable_referencia": None if item.get("valor_razonable_referencia") is None else str(item.get("valor_razonable_referencia")),
            "valor_cotizacion_propuesto": None if item.get("valor_cotizacion_propuesto") is None else str(item.get("valor_cotizacion_propuesto")),
            "id_usuario": item.get("id_usuario"), "fecha_emision": item.get("fecha_emision")}


def periodos_publicos(lista) -> list[dict]:
    if not isinstance(lista, list):
        return []
    return [{"id_periodo_contable": p.get("id_periodo_contable"), "estado": p.get("estado"),
             "fecha_inicio": p.get("fecha_inicio"), "fecha_fin": p.get("fecha_fin")}
            for p in lista if isinstance(p, dict)]


def render(informe: dict) -> str:
    filas = "".join(
        f"<tr><td>{html.escape(r['rol'])}</td><td>{html.escape(str(r.get('nombre_rol')))}</td>"
        f"<td>{html.escape(', '.join(r['cotizaciones'].get('cotizaciones', [])))}</td>"
        f"<td>{html.escape(str(r['cotizaciones'].get('puede_crear')))}</td></tr>"
        for r in informe["roles"]
    )
    escenarios = "".join(
        f"<tr><td>{html.escape(e['subcaso'])}</td><td>{html.escape(e['estado'])}</td><td>{html.escape(e['motivo'])}</td></tr>"
        for e in informe["escenarios"]
    )
    return f"""<!DOCTYPE html><html lang="es"><head><meta charset="utf-8"><title>TC-M06-G115</title>
<style>body{{font-family:Segoe UI,sans-serif;margin:2rem;line-height:1.45}}table{{border-collapse:collapse;width:100%}}
th,td{{border:1px solid #ccc;padding:.45rem .6rem;text-align:left;vertical-align:top}}th{{background:#f3f3f3}}
pre{{white-space:pre-wrap}}</style></head><body>
<h1>Módulo 6 — RF-COT — TC-M06-G115</h1>
<p>Generado: {html.escape(informe['generado_en'])}. No se registró una cotización válida.</p>
<p>Aprobación: {informe['porcentaje_aprobacion']} %.</p>
<h2>Permisos de cotizaciones</h2>
<table><tr><th>Rol</th><th>Nombre en el perfil</th><th>Acciones</th><th>Puede crear</th></tr>{filas}</table>
<h2>Subcasos</h2><table><tr><th>Subcaso</th><th>Estado</th><th>Motivo</th></tr>{escenarios}</table>
<h2>Contrato</h2><pre>{html.escape(informe['contrato'])}</pre>
<h2>Hallazgos</h2><ul>{''.join(f'<li>{html.escape(h)}</li>' for h in informe['hallazgos'])}</ul>
</body></html>"""


def guardar(informe: dict) -> None:
    RESULTADOS.mkdir(parents=True, exist_ok=True)
    (RESULTADOS / "resultado_ejecucion_TC-M06-G115.html").write_text(render(informe), encoding="utf-8")
    (RESULTADOS / "resumen_ejecucion_TC-M06-G115.json").write_text(
        json.dumps({k: v for k, v in informe.items() if k != "analisis"}, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (RESULTADOS / "evidencia_peticiones_TC-M06-G115.json").write_text(json.dumps({
        "caso": "TC-M06-G115", "generado_en": informe["generado_en"], "peticiones": informe["peticiones"],
    }, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (RESULTADOS / "analisis_hallazgos_TC-M06-G115.md").write_text(informe["analisis"], encoding="utf-8")


def main() -> int:
    inicio = time.perf_counter()
    peticiones = []
    contrato = (
        "POST /finanzas/cotizaciones responde 201. El cuerpo exige activos_cotizados y "
        "valor_cotizacion_propuesto mayor que cero. La referencia no se envía: es la suma del último "
        "valor razonable neto de los activos. El estado guardado es COTIZADO. No cambia el valor del activo "
        "ni crea asientos. Sí inserta la cotización y el evento COTIZACION_REGISTRADA, y resuelve el período "
        "abierto de la fecha de emisión. Hoy cae en un período cerrado, así que el caso de uso usaría el "
        "primer período abierto posterior. El recurso es cotizaciones. Crear es la acción 1. "
        "Contador: crear, leer, actualizar y desactivar. Administrador: crear, leer y desactivar. "
        "Productor: solo leer. La negación es HTTP 403 ACCESO_DENEGADO y ocurre antes del caso de uso."
    )
    informe = {
        "caso": "TC-M06-G115", "rf": ["RF-COT"], "ambiente": BASE_API,
        "generado_en": datetime.now(timezone.utc).isoformat(), "contrato": contrato,
        "roles": [], "activos": [], "periodos": [], "cotizaciones_iniciales": {}, "conteos": {},
        "productor_post": None, "peticiones": peticiones, "hallazgos": [], "escenarios": [],
        "sesiones_previas_cerradas": [],
    }
    cuentas = {
        "Contador": (os.environ.get("QA_CORREO"), os.environ.get("QA_CONTRASENA")),
        "Administrador": (os.environ.get("QA_ADMIN_CORREO"), os.environ.get("QA_ADMIN_CONTRASENA")),
        "Productor": (os.environ.get("QA_PRODUCTOR_CORREO"), os.environ.get("QA_PRODUCTOR_CONTRASENA")),
    }
    if any(not correo or not clave for correo, clave in cuentas.values()):
        raise SystemExit("Defina las credenciales de Contador, Administrador y Productor en el entorno.")

    token_contador, cerrada = sesion(*cuentas["Contador"], peticiones)
    informe["sesiones_previas_cerradas"].append({"rol": "Contador", "cerro_otra_sesion": cerrada})
    if not token_contador:
        guardar(informe)
        print("SIN SESION CONTADOR")
        return 2
    contador = {"rol": "Contador", **perfil(token_contador, peticiones), "cotizaciones": permiso_cotizaciones(token_contador, peticiones)}
    informe["roles"].append(contador)

    codigo, cotizaciones, duracion = pedir("GET", "/finanzas/cotizaciones", token=token_contador)
    fichas = [ficha_cotizacion(c) for c in cotizaciones] if isinstance(cotizaciones, list) else []
    informe["cotizaciones_iniciales"] = {"http": codigo, "total": len(fichas),
                                         "estados": dict(Counter(c["estado"] for c in fichas)), "muestra": fichas[:20]}
    peticiones.append(evidencia("GET", "/finanzas/cotizaciones", codigo, duracion, informe["cotizaciones_iniciales"]))

    codigo, activos, duracion = pedir("GET", "/finanzas/activos", token=token_contador)
    informe["activos"] = [ficha_activo(a) for a in activos] if isinstance(activos, list) else []
    peticiones.append(evidencia("GET", "/finanzas/activos", codigo, duracion, {"total": len(informe["activos"]), "activos": informe["activos"]}))

    codigo, periodos, duracion = pedir("GET", "/finanzas/periodos", token=token_contador)
    informe["periodos"] = periodos_publicos(periodos)
    peticiones.append(evidencia("GET", "/finanzas/periodos", codigo, duracion, {"total": len(informe["periodos"])}))

    ruta_aud = "/finanzas/auditoria?" + urllib.parse.urlencode([
        ("tipo_evento", "COTIZACION_REGISTRADA"), ("formato", "TECNICO"), ("tamano", "1"), ("pagina", "1"),
    ])
    codigo, auditoria, duracion = pedir("GET", ruta_aud, token=token_contador)
    eventos_antes = auditoria.get("total_registros") if isinstance(auditoria, dict) else None
    peticiones.append(evidencia("GET", ruta_aud, codigo, duracion, {"total_registros": eventos_antes}))

    candidato = next((a for a in informe["activos"] if str(a.get("estado", "")).upper() == "ACTIVO" and a.get("valor_razonable_neto")), None)
    informe["candidato_no_usado"] = candidato

    for rol in ("Administrador", "Productor"):
        token, cerrada = sesion(*cuentas[rol], peticiones)
        informe["sesiones_previas_cerradas"].append({"rol": rol, "cerro_otra_sesion": cerrada})
        if not token:
            informe["roles"].append({"rol": rol, "autenticado": False, "cotizaciones": {}})
            continue
        informe["roles"].append({"rol": rol, "autenticado": True, **perfil(token, peticiones),
                                  "cotizaciones": permiso_cotizaciones(token, peticiones)})
        if rol == "Administrador" and candidato:
            codigo, detalle, duracion = pedir("GET", f"/activos-biologicos/{candidato['id_activo_biologico']}", token=token)
            estado = detalle.get("nombre_estado") or detalle.get("estado_actual") if isinstance(detalle, dict) else None
            peticiones.append(evidencia("GET", f"/activos-biologicos/{candidato['id_activo_biologico']}", codigo, duracion,
                                        {"http": codigo, "id_activo_biologico": candidato["id_activo_biologico"], "estado": estado}))
            informe["detalle_biologico"] = {"http": codigo, "id_activo_biologico": candidato["id_activo_biologico"], "estado": estado}
        if rol == "Productor" and token:
            cuerpo = {"activos_cotizados": [candidato["id_activo_biologico"] if candidato else informe["activos"][0]["id_activo_biologico"]],
                      "valor_cotizacion_propuesto": "1000.0000"} if informe["activos"] else None
            if cuerpo and not informe["roles"][-1]["cotizaciones"].get("puede_crear"):
                codigo, respuesta, duracion = pedir("POST", "/finanzas/cotizaciones", cuerpo, token)
                informe["productor_post"] = {"http": codigo, "code": negocio(respuesta), "cuerpo_valido": True}
                peticiones.append(evidencia("POST", "/finanzas/cotizaciones", codigo, duracion, respuesta, cuerpo))

    token_contador, cerrada = sesion(*cuentas["Contador"], peticiones)
    informe["sesiones_previas_cerradas"].append({"rol": "Contador", "cerro_otra_sesion": cerrada})
    codigo, cotizaciones, duracion = pedir("GET", "/finanzas/cotizaciones", token=token_contador)
    total_despues = len(cotizaciones) if isinstance(cotizaciones, list) else None
    peticiones.append(evidencia("GET", "/finanzas/cotizaciones", codigo, duracion, {"total": total_despues}))
    codigo, auditoria, duracion = pedir("GET", ruta_aud, token=token_contador)
    eventos_despues = auditoria.get("total_registros") if isinstance(auditoria, dict) else None
    peticiones.append(evidencia("GET", ruta_aud, codigo, duracion, {"total_registros": eventos_despues}))
    codigo, activos, duracion = pedir("GET", "/finanzas/activos", token=token_contador)
    despues = [ficha_activo(a) for a in activos] if isinstance(activos, list) else []
    peticiones.append(evidencia("GET", "/finanzas/activos", codigo, duracion, {"total": len(despues)}))
    antes_valores = {a["id_activo_biologico"]: a["valor_razonable_neto"] for a in informe["activos"]}
    despues_valores = {a["id_activo_biologico"]: a["valor_razonable_neto"] for a in despues}
    informe["conteos"] = {
        "cotizaciones_inicial": informe["cotizaciones_iniciales"].get("total"), "cotizaciones_final": total_despues,
        "eventos_inicial": eventos_antes, "eventos_final": eventos_despues,
        "valor_razonable_sin_cambio": antes_valores == despues_valores,
    }
    productor = next(r for r in informe["roles"] if r["rol"] == "Productor")
    denegado = (informe["productor_post"] or {}).get("http") == 403 and (informe["productor_post"] or {}).get("code") == "ACCESO_DENEGADO"
    intacto = informe["conteos"]["cotizaciones_inicial"] == total_despues and eventos_antes == eventos_despues and informe["conteos"]["valor_razonable_sin_cambio"]
    nombre = str(productor.get("nombre_rol", "")).strip().lower()
    cuenta = str(productor.get("estado_cuenta", "")).strip().lower()
    es_productor = productor.get("autenticado") and nombre == "productor" and cuenta == "activo"
    estado_45 = "APROBADO" if es_productor and denegado and intacto else "BLOQUEADO"
    motivo_45 = ("El Productor autenticado recibió 403 ACCESO_DENEGADO. No aumentaron las cotizaciones ni los eventos, "
                 "y el valor razonable leído no cambió.") if estado_45 == "APROBADO" else (
        "No se demostró la negación: la sesión, el rol o la respuesta no coinciden con un 403 sin persistencia.")
    informe["escenarios"] = [
        {"subcaso": "TC-M06-44", "estado": "BLOQUEADO",
         "motivo": "No se registró la cotización. El alta inserta la fila, el evento COTIZACION_REGISTRADA y la asocia al período abierto compartido."},
        {"subcaso": "TC-M06-45", "estado": estado_45, "motivo": motivo_45},
    ]
    aprobados = sum(e["estado"] == "APROBADO" for e in informe["escenarios"])
    informe["aprobados"] = aprobados
    informe["rechazados"] = sum(e["estado"] == "RECHAZADO" for e in informe["escenarios"])
    informe["bloqueados"] = sum(e["estado"] == "BLOQUEADO" for e in informe["escenarios"])
    informe["requiere_aclaracion"] = 0
    informe["porcentaje_aprobacion"] = round(aprobados / 2 * 100)
    informe["hallazgos"] = [
        "BLOQUEO DE PRUEBA: no hay un activo aislado y autorizado para registrar una cotización de Contador o Administrador.",
    ]
    if fichas and all(c["valor_razonable_referencia"] is None for c in fichas):
        informe["hallazgos"].append(
            "Las cotizaciones ya existentes no traen valor de referencia y no hay eventos COTIZACION_REGISTRADA. "
            "Sus fechas son anteriores a la implementación actual. Esta prueba no las creó."
        )
    if estado_45 == "APROBADO":
        informe["hallazgos"].append("TC-M06-45 se comprobó con el POST del Productor. La dependencia de permiso responde antes del caso de uso.")
    informe["analisis"] = (
        "# TC-M06-G115\n\n"
        "No se usó SQL local ni se registró una cotización válida.\n\n"
        "El endpoint es POST /finanzas/cotizaciones. El estado persistido es COTIZADO y la referencia es el valor razonable neto.\n"
        f"Cotizaciones antes y después: {informe['conteos']['cotizaciones_inicial']} y {total_despues}. "
        f"Eventos COTIZACION_REGISTRADA: {eventos_antes} y {eventos_despues}.\n"
        f"TC-M06-44: BLOQUEADO. TC-M06-45: {estado_45}.\n"
    )
    informe["duracion_ms"] = round((time.perf_counter() - inicio) * 1000)
    guardar(informe)
    print("TC-M06-44 BLOQUEADO", f"TC-M06-45 {estado_45}", f"post {informe['productor_post']}", f"intacto {intacto}")
    return 0 if aprobados == 2 else 2


if __name__ == "__main__":
    raise SystemExit(main())
