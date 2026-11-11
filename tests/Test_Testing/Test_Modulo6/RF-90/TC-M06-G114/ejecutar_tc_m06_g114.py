"""TC-M06-G114 contra TEST.

No registra un costo válido. Compara los costos ya existentes con la auditoría
financiera de M06 y envía un rechazo que no puede persistir.

    python tests/Test_Testing/Test_Modulo6/RF-90/TC-M06-G114/ejecutar_tc_m06_g114.py
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
from decimal import Decimal
from pathlib import Path

CARPETA = Path(__file__).resolve().parent
RESULTADOS = CARPETA / "resultados"
BASE_API = "https://api.inmero.co/api-sgpmp-test"
ZONA = "America/Bogota"
OMITIR = {"token", "access_token", "contrasena", "password", "hash_integridad", "numero_id_tributaria",
          "identificador", "identificador_activo", "activo", "finca", "tercero_nit", "tercero_razon_social",
          "tercero_dv", "nombre_usuario", "factura_numero", "factura_prefijo", "justificacion"}


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


def consulta(ruta: str, params: list[tuple[str, str]]) -> str:
    return ruta + "?" + urllib.parse.urlencode(params)


def numero(valor) -> Decimal | None:
    if valor is None:
        return None
    return Decimal(str(valor))


def ficha_costo(costo: dict) -> dict:
    return {
        "id_registro_costo": costo.get("id_registro_costo"),
        "id_activo_biologico": costo.get("id_activo_biologico"),
        "id_periodo_contable": costo.get("id_periodo_contable"),
        "monto_costo": str(costo.get("monto_costo")),
        "origen_costo": costo.get("origen_costo"),
        "naturaleza_costo": costo.get("naturaleza_costo"),
        "subtipo_costo": costo.get("subtipo_costo"),
        "estado": costo.get("estado"),
        "politica_capitalizacion": costo.get("politica_capitalizacion"),
        "vehiculo_contable": costo.get("vehiculo_contable"),
        "id_usuario": costo.get("id_usuario"),
        "id_grupo_reparto": costo.get("id_grupo_reparto"),
        "fecha_costo": costo.get("fecha_costo"),
        "fecha_registro": costo.get("fecha_registro"),
    }


def ficha_evento(evento: dict) -> dict:
    payload = evento.get("payload_evento") if isinstance(evento.get("payload_evento"), dict) else {}
    claves = ("naturaleza", "subtipo", "origen", "vehiculo", "politica", "id_grupo_reparto",
              "origen_costo", "subtipo_costo", "vehiculo_contable", "tipo_suministro")
    return {
        "id_evento": evento.get("id_evento"),
        "tipo_evento": evento.get("tipo_evento"),
        "modulo": evento.get("modulo"),
        "id_referencia": evento.get("id_referencia"),
        "id_activo_biologico": evento.get("id_activo_biologico"),
        "id_periodo_contable": evento.get("id_periodo_contable"),
        "monto_afectado": None if evento.get("monto_afectado") is None else str(evento.get("monto_afectado")),
        "id_usuario": evento.get("id_usuario"),
        "tipo_actor": evento.get("tipo_actor"),
        "id_sistema": evento.get("id_sistema"),
        "timestamp_evento": evento.get("timestamp_evento"),
        "severidad": evento.get("severidad_evento"),
        "origen_registro": evento.get("origen_registro"),
        "payload": {k: payload.get(k) for k in claves if k in payload},
    }


def cruzar(costos: list[dict], eventos: list[dict]) -> list[dict]:
    por_referencia: dict[int, list[dict]] = {}
    for evento in eventos:
        por_referencia.setdefault(evento.get("id_referencia"), []).append(evento)
    relaciones = []
    for costo in costos:
        coinciden = por_referencia.get(costo["id_registro_costo"], [])
        evento = coinciden[0] if coinciden else None
        payload = (evento or {}).get("payload") or {}
        relaciones.append({
            "id_registro_costo": costo["id_registro_costo"],
            "eventos": len(coinciden),
            "id_evento": None if evento is None else evento["id_evento"],
            "modulo_m06": bool(evento and evento["modulo"] == "M06"),
            "activo": bool(evento and evento["id_activo_biologico"] == costo["id_activo_biologico"]),
            "periodo": bool(evento and evento["id_periodo_contable"] == costo["id_periodo_contable"]),
            "importe": bool(evento and numero(evento["monto_afectado"]) == numero(costo["monto_costo"])),
            "usuario": bool(evento and evento["id_usuario"] == costo["id_usuario"]),
            "origen": bool(evento and (payload.get("origen") or payload.get("origen_costo")) == costo["origen_costo"]),
            "subtipo": bool(evento and (payload.get("subtipo") or payload.get("subtipo_costo")) == costo["subtipo_costo"]),
            "clasificacion": bool(evento and payload.get("naturaleza") == costo["naturaleza_costo"]),
        })
    return relaciones


def periodos_publicos(lista) -> list[dict]:
    if not isinstance(lista, list):
        return []
    return [{"id_periodo_contable": p.get("id_periodo_contable"), "estado": p.get("estado"),
             "fecha_inicio": p.get("fecha_inicio"), "fecha_fin": p.get("fecha_fin")}
            for p in lista if isinstance(p, dict)]


def render(informe: dict) -> str:
    filas = "".join(
        "<tr>" + "".join(f"<td>{html.escape(str(v))}</td>" for v in (
            r["id_registro_costo"], r["id_evento"], r["eventos"], r["modulo_m06"], r["activo"],
            r["periodo"], r["importe"], r["usuario"], r["origen"], r["subtipo"], r["clasificacion"])) + "</tr>"
        for r in informe["relaciones_lectura"]
    )
    return f"""<!DOCTYPE html><html lang="es"><head><meta charset="utf-8"><title>TC-M06-G114</title>
<style>body{{font-family:Segoe UI,sans-serif;margin:2rem;line-height:1.45}}table{{border-collapse:collapse;width:100%}}
th,td{{border:1px solid #ccc;padding:.45rem .6rem;text-align:left;vertical-align:top}}th{{background:#f3f3f3}}
pre{{white-space:pre-wrap}}</style></head><body>
<h1>Módulo 6 — RF-90 / RF-94 — TC-M06-G114</h1>
<p>Generado: {html.escape(informe['generado_en'])}. No se registró un costo nuevo. No se consultó la auditoría de M02.</p>
<table><tr><th>Subcaso</th><td>TC-M06-43</td></tr>
<tr><th>Estado</th><td>{html.escape(informe['escenarios'][0]['estado'])}</td></tr>
<tr><th>Porcentaje</th><td>{informe['porcentaje_aprobacion']} %</td></tr>
<tr><th>RF-90</th><td>POST /finanzas/costos</td></tr>
<tr><th>RF-94</th><td>GET /finanzas/auditoria</td></tr></table>
<h2>Contrato</h2><pre>{html.escape(informe['contrato'])}</pre>
<h2>Lectura de costos ya existentes</h2>
<table><tr><th>Costo</th><th>Evento</th><th>Cantidad</th><th>M06</th><th>Activo</th><th>Período</th>
<th>Importe</th><th>Usuario</th><th>Origen</th><th>Subtipo</th><th>Clasificación</th></tr>{filas}</table>
<h2>Conteos</h2><pre>{html.escape(json.dumps(informe['conteos'], ensure_ascii=False, indent=2))}</pre>
<h2>Hallazgos</h2><ul>{''.join(f'<li>{html.escape(h)}</li>' for h in informe['hallazgos'])}</ul>
</body></html>"""


def guardar(informe: dict) -> None:
    RESULTADOS.mkdir(parents=True, exist_ok=True)
    (RESULTADOS / "resultado_ejecucion_TC-M06-G114.html").write_text(render(informe), encoding="utf-8")
    (RESULTADOS / "resumen_ejecucion_TC-M06-G114.json").write_text(
        json.dumps(informe, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (RESULTADOS / "evidencia_peticiones_TC-M06-G114.json").write_text(json.dumps({
        "caso": "TC-M06-G114", "generado_en": informe["generado_en"], "peticiones": informe["peticiones"],
        "auditoria_m02_consultada": False,
    }, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (RESULTADOS / "analisis_hallazgos_TC-M06-G114.md").write_text(informe["analisis"], encoding="utf-8")


def main() -> int:
    inicio = time.perf_counter()
    peticiones = []
    contrato = (
        "RF-90 registra con POST /finanzas/costos y responde 201. El Contador crea, consulta y clasifica. "
        "El Administrador crea y consulta. El Revisor Fiscal solo consulta. "
        "Dentro de la misma transacción, después de insertar el costo, se escribe COSTO_REGISTRADO en "
        "modulo6.auditorias_financieras. id_referencia es el id del costo. El payload guarda naturaleza, "
        "subtipo, origen, vehículo, política y grupo de reparto. El monto, el activo, el período y el usuario "
        "van en columnas propias. modulo_origen queda en M06. "
        "RF-94 consulta con GET /finanzas/auditoria. Exige tipo de evento, período o activo. "
        "formato TECNICO devuelve id_referencia e id_usuario. El formato LEGIBLE, que es el predeterminado, "
        "no los devuelve. La ruta no filtra por id de costo ni por usuario, aunque el repositorio acepta id_usuario. "
        "Un rechazo de validación no entra al caso de uso y no escribe COSTO_REGISTRADO. "
        "La bitácora de rechazos de M02 no aplica a /finanzas. "
        "GET /activos-biologicos/auditoria no se usa."
    )
    informe = {
        "caso": "TC-M06-G114", "subcaso": "TC-M06-43", "rf": ["RF-90", "RF-94"], "ambiente": BASE_API,
        "generado_en": datetime.now(timezone.utc).isoformat(), "contrato": contrato,
        "auditoria_m02_consultada": False, "registro_nuevo": False, "conteos": {}, "costos_lectura": [],
        "eventos_lectura": [], "relaciones_lectura": [], "periodos": [], "comprobaciones": [],
        "peticiones": peticiones, "hallazgos": [], "escenarios": [],
        "aprobados": 0, "rechazados": 0, "bloqueados": 1, "requiere_aclaracion": 0, "porcentaje_aprobacion": 0,
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

    codigo, costos, duracion = pedir("GET", "/finanzas/costos", token=token)
    costos_ficha = [ficha_costo(c) for c in costos] if isinstance(costos, list) else []
    informe["costos_lectura"] = costos_ficha
    peticiones.append(evidencia("GET", "/finanzas/costos", codigo, duracion, {"total": len(costos_ficha), "costos": costos_ficha}))

    ruta_eventos = consulta("/finanzas/auditoria", [
        ("tipo_evento", "COSTO_REGISTRADO"), ("formato", "TECNICO"), ("tamano", "50"), ("orden", "ASC"), ("pagina", "1"),
    ])
    codigo, auditoria, duracion = pedir("GET", ruta_eventos, token=token)
    eventos = [ficha_evento(e) for e in (auditoria.get("eventos") or [])] if isinstance(auditoria, dict) else []
    total_eventos = auditoria.get("total_registros") if isinstance(auditoria, dict) else None
    informe["eventos_lectura"] = eventos
    peticiones.append(evidencia("GET", ruta_eventos, codigo, duracion, {
        "total_registros": total_eventos, "resumen_severidad": auditoria.get("resumen_severidad") if isinstance(auditoria, dict) else None,
        "eventos": eventos,
    }))

    ruta_clasificados = consulta("/finanzas/auditoria", [
        ("tipo_evento", "COSTO_CLASIFICADO"), ("formato", "TECNICO"), ("tamano", "20"), ("pagina", "1"),
    ])
    codigo, clasificados, duracion = pedir("GET", ruta_clasificados, token=token)
    total_clasificados = clasificados.get("total_registros") if isinstance(clasificados, dict) else None
    peticiones.append(evidencia("GET", ruta_clasificados, codigo, duracion, {"total_registros": total_clasificados}))

    codigo, periodos, duracion = pedir("GET", "/finanzas/periodos", token=token)
    informe["periodos"] = periodos_publicos(periodos)
    peticiones.append(evidencia("GET", "/finanzas/periodos", codigo, duracion, {"total": len(informe["periodos"]), "periodos": informe["periodos"]}))

    codigo, sin_filtro, duracion = pedir("GET", "/finanzas/auditoria?formato=TECNICO&tamano=1", token=token)
    informe["comprobaciones"].append({"nombre": "filtro_obligatorio", "http": codigo, "code": negocio(sin_filtro)})
    peticiones.append(evidencia("GET", "/finanzas/auditoria", codigo, duracion, sin_filtro))

    codigo, tipo_ajeno, duracion = pedir("GET", "/finanzas/auditoria?tipo_evento=AUDITORIA_M02&formato=TECNICO&tamano=1", token=token)
    informe["comprobaciones"].append({"nombre": "tipo_ajeno", "http": codigo, "code": negocio(tipo_ajeno)})
    peticiones.append(evidencia("GET", "/finanzas/auditoria", codigo, duracion, tipo_ajeno))

    cuerpo = {"subtipo_costo": "ALIMENTO", "origen_costo": "MANO_OBRA_PROPIA", "monto_costo": 0,
              "fecha_costo": "2026-11-08", "id_activo_biologico": 951}
    codigo, rechazo, duracion = pedir("POST", "/finanzas/costos", cuerpo, token)
    informe["comprobaciones"].append({"nombre": "monto_cero", "http": codigo, "code": negocio(rechazo), "escritura": False})
    peticiones.append(evidencia("POST", "/finanzas/costos", codigo, duracion, rechazo, cuerpo))

    codigo, costos_despues, duracion = pedir("GET", "/finanzas/costos", token=token)
    total_despues = len(costos_despues) if isinstance(costos_despues, list) else None
    peticiones.append(evidencia("GET", "/finanzas/costos", codigo, duracion, {"total": total_despues}))
    codigo, auditoria_despues, duracion = pedir("GET", ruta_eventos, token=token)
    eventos_despues = auditoria_despues.get("total_registros") if isinstance(auditoria_despues, dict) else None
    peticiones.append(evidencia("GET", ruta_eventos, codigo, duracion, {"total_registros": eventos_despues}))

    relaciones = cruzar(costos_ficha, eventos)
    informe["relaciones_lectura"] = relaciones
    ids_periodos = {p["id_periodo_contable"] for p in informe["periodos"]}
    periodos_existentes = all(c["id_periodo_contable"] in ids_periodos for c in costos_ficha) if ids_periodos else None
    informe["conteos"] = {
        "costos_inicial": len(costos_ficha), "costos_final": total_despues,
        "costo_registrado_inicial": total_eventos, "costo_registrado_final": eventos_despues,
        "costo_clasificado": total_clasificados, "eventos_devueltos": len(eventos),
        "periodos_de_los_costos_existen": periodos_existentes,
        "sin_costo_nuevo": len(costos_ficha) == total_despues and total_eventos == eventos_despues,
    }
    referencias = [e["id_referencia"] for e in eventos]
    duplicados = sorted({r for r in referencias if referencias.count(r) > 1})
    informe["duplicados_en_lectura"] = duplicados
    huerfanos = [e["id_evento"] for e in eventos if e["id_referencia"] not in {c["id_registro_costo"] for c in costos_ficha}]
    informe["eventos_sin_costo_en_listado"] = huerfanos
    sin_evento = [r["id_registro_costo"] for r in relaciones if r["eventos"] == 0]
    informe["hallazgos"] = [
        "BLOQUEO DE PRUEBA: no hay un activo ni un período aislados y autorizados para registrar un costo nuevo.",
        "QUESTION-M06-G114-01: GET /finanzas/auditoria no filtra por el id del costo ni por el usuario. "
        "La relación está en id_referencia y solo la devuelve formato=TECNICO. El formato predeterminado LEGIBLE la omite.",
    ]
    por_periodo = {p["id_periodo_contable"]: p for p in informe["periodos"]}
    fuera = []
    for costo in costos_ficha:
        periodo = por_periodo.get(costo["id_periodo_contable"])
        fecha = str(costo["fecha_costo"])[:10]
        if periodo and not (periodo["fecha_inicio"] <= fecha <= periodo["fecha_fin"]):
            fuera.append(costo["id_registro_costo"])
    informe["costos_con_fecha_fuera_del_periodo"] = fuera
    if costos_ficha and all(c["origen_costo"] == "CONSUMO_INVENTARIO" for c in costos_ficha):
        informe["hallazgos"].append(
            "QUESTION-M06-G114-02: los costos existentes son de CONSUMO_INVENTARIO. El costo guarda el usuario de servicio "
            "y el evento queda con id_usuario nulo y actor de sistema. El payload usa origen_costo y subtipo_costo, "
            "y no trae la naturaleza. El registro manual usa otras claves. Esta prueba no ejecutó ese registro."
        )
    if fuera:
        informe["hallazgos"].append(
            "QUESTION-M06-G114-03: los costos " + ", ".join(str(i) for i in fuera)
            + " tienen una fecha que no cae dentro del período guardado. El evento de auditoría repite ese período. "
            "El alta manual rechaza esa situación; el proceso de provisiones no hace esa comprobación. Estos registros ya existían."
        )
    if sin_evento:
        informe["hallazgos"].append(
            "Los costos " + ", ".join(str(i) for i in sin_evento) + " no tienen COSTO_REGISTRADO en la página consultada."
        )
    if duplicados:
        informe["hallazgos"].append(
            "Hay más de un COSTO_REGISTRADO para las referencias " + ", ".join(str(i) for i in duplicados) + "."
        )
    informe["escenarios"].append({
        "subcaso": "TC-M06-43", "estado": "BLOQUEADO", "registro_ejecutado": False,
        "motivo": "No se registró un costo válido. La lectura de los dos costos existentes no sustituye esa operación.",
    })
    informe["analisis"] = (
        "# TC-M06-G114\n\n"
        "No se consultó `GET /activos-biologicos/auditoria`. No se usó SQL local.\n\n"
        "RF-90 es `POST /finanzas/costos`. RF-94 es `GET /finanzas/auditoria`, tabla `modulo6.auditorias_financieras`.\n"
        "El evento de un registro exitoso es `COSTO_REGISTRADO`. `id_referencia` guarda el id del costo.\n\n"
        f"Costos leídos: {len(costos_ficha)}. Eventos COSTO_REGISTRADO: {total_eventos}. "
        f"COSTO_CLASIFICADO: {total_clasificados}.\n"
        "La comparación de la tabla es una lectura de datos ya existentes. No aprueba TC-M06-43.\n"
        f"Después del rechazo de monto 0, costos {total_despues} y eventos {eventos_despues}.\n"
        f"Duplicados por referencia: {duplicados or 'ninguno'}. Costos sin evento: {sin_evento or 'ninguno'}.\n"
        f"Costos cuya fecha no cae en el período guardado: {fuera or 'ninguno'}.\n"
    )
    informe["duracion_ms"] = round((time.perf_counter() - inicio) * 1000)
    guardar(informe)
    print("TC-M06-43 BLOQUEADO", f"costos {len(costos_ficha)} eventos {total_eventos}",
          f"sin_evento {sin_evento or '-'} duplicados {duplicados or '-'}",
          f"intacto {informe['conteos']['sin_costo_nuevo']}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
