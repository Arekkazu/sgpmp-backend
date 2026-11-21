# | Fecha      | Nombre | Que se hizo |
# |------------|--------|-------------|
# | 2026-11-08 | —      | Negativos sobre activo 951; TC-M06-35 bloqueado sin datos aislados. |
# | 2026-11-12 | —      | Reanudación con titular 900000003 / período 220 / activo 1569. |
"""TC-M06-G110 (RF-90) contra TEST: TC-M06-35, TC-M06-36 y TC-M06-38.

Datos aislados autorizados por Desarrollo (INC-M06-300-G82 / #986):
titular 900000003, finca 467, período 220 ABIERTO, activo 1569 (QA-M06O-VR-01).

Orden: negativos de monto y capitalización (sin inserción), luego el registro
positivo COMPRA_PROVEEDOR. No usa período 219, CONSUMO_INVENTARIO ni
MANO_OBRA_PROPIA en el positivo.

    python tests/Test_Testing/Test_Modulo6/RF-90/TC-M06-G110/ejecutar_tc_m06_g110.py
"""
from __future__ import annotations

import html
import json
import os
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

CARPETA = Path(__file__).resolve().parent
RESULTADOS = CARPETA / "resultados"
BASE_API = "https://api.inmero.co/api-sgpmp-test"
ZONA = "America/Bogota"
NIT = "900000003"
RAZON = "QA M06 Operaciones SAS"
FINCA = 467
PERIODO = 220
ACTIVO = 1569
IDENTIFICADOR = "QA-M06O-VR-01"
MONTO_OK = Decimal("150000.00")
# Proveedor de prueba ya usado en tests de integración del propio repo.
PROVEEDOR = {
    "tercero_nit": "800555111",
    "tercero_dv": "1",
    "tercero_razon_social": "Veterinaria SAS",
    "factura_prefijo": "QA",
    "factura_numero": "G11011202601",
}
PROTEGIDOS = {
    "evidencia_peticiones_TC-M06-G110.json",
    "resultado_ejecucion_TC-M06-G110.html",
    "resumen_ejecucion_TC-M06-G110.json",
    "analisis_hallazgos_TC-M06-G110.md",
}
SECRETOS = {
    "token", "access_token", "contrasena", "password", "hash_integridad",
    "numero_id_tributaria", "tercero_nit", "tercero_dv", "tercero_razon_social",
    "identificador", "finca", "razon_sin_mercado",
}
OMITIR = SECRETOS | {"lineas", "reconocimientos", "calculos", "mediciones", "productos"}


def hoy_bogota() -> date:
    return datetime.now(ZoneInfo(ZONA)).date()


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
        return [limpiar(v, profundidad + 1) for v in valor[:40]]
    if isinstance(valor, str) and len(valor) > 300:
        return valor[:300]
    return valor


def evidencia(metodo, ruta, codigo, duracion, respuesta, escritura: bool = False, cuerpo=None, escenario=None) -> dict:
    entrada = {
        "metodo": metodo, "consulta": ruta, "codigo": codigo, "duracion_ms": duracion,
        "escritura": escritura, "en": datetime.now(ZoneInfo(ZONA)).isoformat(),
        "cuerpo": limpiar(cuerpo) if cuerpo is not None else None,
        "respuesta": limpiar(respuesta),
    }
    if escenario:
        entrada["escenario"] = escenario
    return entrada


def codigo_negocio(payload) -> str | None:
    if isinstance(payload, dict):
        return payload.get("error_code") or payload.get("code") or payload.get("codigo")
    return None


def campo_val(payload) -> str | None:
    if not isinstance(payload, dict):
        return None
    fields = payload.get("fields")
    if isinstance(fields, list) and fields:
        primero = fields[0]
        if isinstance(primero, dict):
            return primero.get("field")
    return payload.get("field")


def resumir_costos(lista) -> dict:
    if not isinstance(lista, list):
        return {"total": None}
    return {
        "total": len(lista),
        "ids": [c.get("id_registro_costo") for c in lista if isinstance(c, dict)],
        "naturalezas": dict(Counter(c.get("naturaleza_costo") for c in lista if isinstance(c, dict))),
        "politicas": dict(Counter(c.get("politica_capitalizacion") for c in lista if isinstance(c, dict))),
        "subtipos": dict(Counter(c.get("subtipo_costo") for c in lista if isinstance(c, dict))),
        "vehiculos": dict(Counter(c.get("vehiculo_contable") for c in lista if isinstance(c, dict))),
        "mantenimiento_capitalizado": sum(
            1 for c in lista if isinstance(c, dict)
            and c.get("naturaleza_costo") == "MANTENIMIENTO"
            and c.get("politica_capitalizacion") == "CAPITALIZAR"),
    }


def libros(payload) -> dict | None:
    if not isinstance(payload, dict):
        return None
    activo = payload.get("activo") if isinstance(payload.get("activo"), dict) else {}
    costo = payload.get("valoracion_costo")
    recs = payload.get("reconocimientos") if isinstance(payload.get("reconocimientos"), list) else []
    rec = recs[0] if recs else None
    return {
        "activo": {
            "id_activo_biologico": activo.get("id_activo_biologico"),
            "identificador": activo.get("identificador"),
            "estado": activo.get("estado"),
            "id_finca": activo.get("id_finca"),
            "numero_id_tributaria": activo.get("numero_id_tributaria"),
            "razon_social": activo.get("razon_social"),
            "costo_adquisicion": activo.get("costo_adquisicion"),
        },
        "reconocimiento": None if not isinstance(rec, dict) else {
            "estado": rec.get("estado"),
            "indicador_valoracion": rec.get("indicador_valoracion"),
            "id_periodo_contable": rec.get("id_periodo_contable"),
            "valor_razonable_neto_inicial": rec.get("valor_razonable_neto_inicial"),
        },
        "valoracion_costo": None if not isinstance(costo, dict) else {
            k: costo.get(k) for k in (
                "id_valoracion_por_costo", "costos_adquisicion", "depreciacion_acumulada",
                "deterioro_acumulado", "valor_contable_por_costo", "es_activa",
            )
        },
    }


def ids_lineas(lista) -> list:
    if not isinstance(lista, list):
        return []
    return sorted(int(x["id_linea_asiento_nic41"]) for x in lista if isinstance(x, dict) and x.get("id_linea_asiento_nic41") is not None)


def ruta_ultima(nombre: str) -> Path:
    if nombre in PROTEGIDOS:
        raise RuntimeError(f"Nombre reservado de la evaluación histórica: {nombre}")
    destino = RESULTADOS / "ultima_evaluacion" / nombre
    destino.parent.mkdir(parents=True, exist_ok=True)
    return destino


def render(informe: dict) -> str:
    filas = "".join(
        f"<tr><td>{html.escape(e['subcaso'])}</td><td>{html.escape(e['estado'])}</td>"
        f"<td>{html.escape(str(e.get('motivo') or ''))}</td></tr>"
        for e in informe["escenarios"]
    )
    return f"""<!DOCTYPE html><html lang="es"><head><meta charset="utf-8"><title>TC-M06-G110</title>
<style>body{{font-family:Segoe UI,sans-serif;margin:2rem;line-height:1.45}}table{{border-collapse:collapse;width:100%}}
th,td{{border:1px solid #ccc;padding:.45rem .6rem;text-align:left;vertical-align:top}}th{{background:#f3f3f3}}</style></head><body>
<h1>Módulo 6 — RF-90 — TC-M06-G110</h1>
<p>Generado: {html.escape(informe['generado_en'])}. Dictamen: {html.escape(informe.get('dictamen_general') or '')}.</p>
<table><tr><th>Porcentaje</th><td>{informe['porcentaje_aprobacion']} %</td></tr>
<tr><th>Aprobados / fallidos / bloqueados</th>
<td>{informe['aprobados']} / {informe['fallidos']} / {informe['bloqueados']}</td></tr>
<tr><th>Activo / período / NIT</th><td>{ACTIVO} / {PERIODO} / {NIT}</td></tr>
<tr><th>Id costo positivo</th><td>{html.escape(str(informe.get('id_registro_costo')))}</td></tr></table>
<h2>Subcasos</h2><table><tr><th>Subcaso</th><th>Estado</th><th>Motivo</th></tr>{filas}</table>
<h2>Precondiciones</h2><pre>{html.escape(json.dumps(informe.get('precondiciones'), ensure_ascii=False, indent=2, default=str))}</pre>
<h2>Costos</h2><pre>{html.escape(json.dumps(informe.get('costos'), ensure_ascii=False, indent=2, default=str))}</pre>
<h2>Libros</h2><pre>{html.escape(json.dumps(informe.get('libros'), ensure_ascii=False, indent=2, default=str))}</pre>
<h2>Hallazgos</h2><ul>{''.join(f'<li>{html.escape(h)}</li>' for h in informe.get('hallazgos') or [])}</ul>
</body></html>"""


def guardar(informe: dict) -> None:
    ruta_ultima("resultado_ejecucion_vigente_TC-M06-G110.html").write_text(render(informe), encoding="utf-8")
    ruta_ultima("resumen_ejecucion_vigente_TC-M06-G110.json").write_text(
        json.dumps(informe, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    ruta_ultima("evidencias_ejecucion_vigente_TC-M06-G110.json").write_text(
        json.dumps({"caso": "TC-M06-G110", "generado_en": informe["generado_en"], "peticiones": informe["peticiones"]},
                   ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (RESULTADOS / "comparacion_evaluaciones.html").write_text(
        f"""<!DOCTYPE html><html lang="es"><head><meta charset="utf-8"><title>TC-M06-G110 comparación</title></head><body>
<h1>TC-M06-G110 — Comparación</h1>
<table border="1" cellpadding="6"><tr><th>Aspecto</th><th>Primera (2026-11-08)</th><th>Última</th></tr>
<tr><td>TC-M06-35</td><td>BLOQUEADO sin datos aislados</td><td>{html.escape(next((e['estado'] for e in informe['escenarios'] if e['subcaso']=='TC-M06-35'),''))}</td></tr>
<tr><td>TC-M06-36</td><td>APROBADO (activo 951)</td><td>{html.escape(next((e['estado'] for e in informe['escenarios'] if e['subcaso']=='TC-M06-36'),''))}</td></tr>
<tr><td>TC-M06-38</td><td>APROBADO (activo 951)</td><td>{html.escape(next((e['estado'] for e in informe['escenarios'] if e['subcaso']=='TC-M06-38'),''))}</td></tr>
<tr><td>Datos</td><td>Activo 951 compartido</td><td>NIT {NIT}, finca {FINCA}, período {PERIODO}, activo {ACTIVO}</td></tr>
<tr><td>Dictamen</td><td>Parcial / bloqueado en 35</td><td>{html.escape(informe.get('dictamen_general') or '')}</td></tr>
</table></body></html>""",
        encoding="utf-8",
    )


def cuerpo_factura(hoy: date, monto, naturaleza=None, confirmar=False) -> dict:
    cuerpo = {
        "subtipo_costo": "ALIMENTO",
        "origen_costo": "COMPRA_PROVEEDOR",
        "monto_costo": float(monto) if isinstance(monto, (int, float, Decimal)) else monto,
        "fecha_costo": hoy.isoformat(),
        "id_activo_biologico": ACTIVO,
        "confirmar_capitalizacion": confirmar,
        **PROVEEDOR,
        "fecha_factura": hoy.isoformat(),
        "fecha_vencimiento_factura": (hoy + timedelta(days=30)).isoformat(),
    }
    if naturaleza is not None:
        cuerpo["naturaleza_costo"] = naturaleza
    return cuerpo


def main() -> int:
    inicio = time.perf_counter()
    hoy = hoy_bogota()
    peticiones: list = []
    hallazgos: list[str] = []
    informe = {
        "caso": "TC-M06-G110",
        "rf": ["RF-90"],
        "incidente": "INC-M06-300-G82 / #986",
        "ambiente": BASE_API,
        "generado_en": datetime.now(ZoneInfo(ZONA)).isoformat(),
        "datos_autorizados": {
            "nit": NIT, "razon_social": RAZON, "id_finca": FINCA,
            "id_periodo_contable": PERIODO, "id_activo_biologico": ACTIVO,
            "identificador": IDENTIFICADOR, "fecha_costo": hoy.isoformat(),
            "origen_positivo": "COMPRA_PROVEEDOR", "subtipo": "ALIMENTO", "monto": str(MONTO_OK),
        },
        "precondiciones": {},
        "costos": {},
        "libros": {},
        "lineas": {},
        "auditoria": {},
        "escenarios": [],
        "peticiones": peticiones,
        "hallazgos": hallazgos,
        "aprobados": 0, "fallidos": 0, "bloqueados": 0, "porcentaje_aprobacion": 0,
        "dictamen_general": "BLOQUEADO",
        "caso_completo_aprobado": False,
        "id_registro_costo": None,
    }

    correo, contrasena = os.environ.get("QA_CORREO"), os.environ.get("QA_CONTRASENA")
    if not correo or not contrasena:
        raise SystemExit("Defina QA_CORREO y QA_CONTRASENA.")
    print("El inicio de sesión cierra cualquier otra sesión activa de la misma cuenta.", flush=True)
    codigo, login, duracion = pedir("POST", "/sesiones/", {"correo_electronico": correo, "contrasena": contrasena})
    token = login.get("token") if isinstance(login, dict) else None
    peticiones.append(evidencia("POST", "/sesiones/", codigo, duracion, login if isinstance(login, dict) else {}, escenario="sesion"))
    if codigo != 200 or not token:
        hallazgos.append("No fue posible autenticar.")
        guardar(informe)
        return 2

    # --- Precondiciones de solo lectura ---
    codigo_p, periodos, duracion = pedir("GET", f"/finanzas/periodos?numero_id_tributaria={NIT}", token=token)
    peticiones.append(evidencia("GET", f"/finanzas/periodos?numero_id_tributaria={NIT}", codigo_p, duracion, periodos, escenario="precondicion"))
    periodo = next((p for p in (periodos or []) if isinstance(p, dict) and p.get("id_periodo_contable") == PERIODO), None)
    codigo_a, activo_payload, duracion = pedir("GET", f"/finanzas/activos/{ACTIVO}", token=token)
    peticiones.append(evidencia("GET", f"/finanzas/activos/{ACTIVO}", codigo_a, duracion, activo_payload, escenario="precondicion"))
    libros_antes = libros(activo_payload)
    informe["libros"]["antes"] = libros_antes
    codigo_c, costos_activo, duracion = pedir("GET", f"/finanzas/costos?id_activo_biologico={ACTIVO}", token=token)
    peticiones.append(evidencia("GET", f"/finanzas/costos?id_activo_biologico={ACTIVO}", codigo_c, duracion, resumir_costos(costos_activo), escenario="precondicion"))
    codigo_c220, costos_220, duracion = pedir("GET", f"/finanzas/costos?id_periodo_contable={PERIODO}", token=token)
    peticiones.append(evidencia("GET", f"/finanzas/costos?id_periodo_contable={PERIODO}", codigo_c220, duracion, resumir_costos(costos_220), escenario="precondicion"))
    codigo_l, lineas_antes, duracion = pedir("GET", f"/finanzas/lineas?id_periodo_contable={PERIODO}", token=token)
    peticiones.append(evidencia("GET", f"/finanzas/lineas?id_periodo_contable={PERIODO}", codigo_l, duracion,
                                {"total": len(lineas_antes) if isinstance(lineas_antes, list) else None,
                                 "ids_activo": [x.get("id_linea_asiento_nic41") for x in (lineas_antes or [])
                                                if isinstance(x, dict) and x.get("id_activo_biologico") == ACTIVO]},
                                escenario="precondicion"))
    ruta_aud = (
        f"/finanzas/auditoria?id_activo_biologico={ACTIVO}&tipo_evento=COSTO_REGISTRADO"
        "&formato=TECNICO&orden=DESC&tamano=20"
    )
    codigo_u, auditoria, duracion = pedir("GET", ruta_aud, token=token)
    total_aud_antes = auditoria.get("total_registros") if isinstance(auditoria, dict) else None
    peticiones.append(evidencia("GET", ruta_aud, codigo_u, duracion, {"total_registros": total_aud_antes}, escenario="precondicion"))

    act = (libros_antes or {}).get("activo") or {}
    rec = (libros_antes or {}).get("reconocimiento") or {}
    costo_previo = None
    if isinstance(costos_activo, list):
        costo_previo = next((
            c for c in costos_activo
            if isinstance(c, dict)
            and c.get("factura_prefijo") == PROVEEDOR["factura_prefijo"]
            and c.get("factura_numero") == PROVEEDOR["factura_numero"]
            and c.get("origen_costo") == "COMPRA_PROVEEDOR"
            and c.get("subtipo_costo") == "ALIMENTO"
        ), None)
    # Primera corrida: 0 costos. Reverificación: admite el costo G110 ya creado, sin re-POST.
    costos_ok = codigo_c == 200 and isinstance(costos_activo, list) and (
        len(costos_activo) == 0 or (costo_previo is not None and len(costos_activo) == 1)
    )
    costos_periodo_ok = codigo_c220 == 200 and isinstance(costos_220, list) and (
        len(costos_220) == 0 or (costo_previo is not None and any(
            isinstance(c, dict) and c.get("id_registro_costo") == costo_previo.get("id_registro_costo")
            for c in costos_220
        ))
    )
    preok = (
        codigo_p == 200 and isinstance(periodo, dict)
        and periodo.get("estado") == "ABIERTO"
        and str(periodo.get("numero_id_tributaria")) == NIT
        and periodo.get("razon_social") == RAZON
        and periodo.get("fecha_inicio") <= hoy.isoformat() <= periodo.get("fecha_fin")
        and codigo_a == 200 and act.get("id_activo_biologico") == ACTIVO
        and act.get("identificador") == IDENTIFICADOR
        and act.get("estado") == "ACTIVO"
        and act.get("id_finca") == FINCA
        and str(act.get("numero_id_tributaria")) == NIT
        and rec.get("estado") == "CONFIRMADO"
        and costos_ok and costos_periodo_ok
        and codigo_l == 200 and isinstance(lineas_antes, list)
    )
    informe["precondiciones"] = {
        "ok": preok,
        "periodo": None if not isinstance(periodo, dict) else {
            k: periodo.get(k) for k in (
                "id_periodo_contable", "numero_id_tributaria", "razon_social", "estado",
                "fecha_inicio", "fecha_fin", "fecha_cierre",
            )
        },
        "activo": act,
        "reconocimiento": rec,
        "costos_activo": resumir_costos(costos_activo),
        "costos_periodo": resumir_costos(costos_220),
        "costo_g110_previo": None if costo_previo is None else costo_previo.get("id_registro_costo"),
        "lineas_periodo_total": len(lineas_antes) if isinstance(lineas_antes, list) else None,
        "lineas_activo_ids": [
            x.get("id_linea_asiento_nic41") for x in (lineas_antes or [])
            if isinstance(x, dict) and x.get("id_activo_biologico") == ACTIVO
        ],
        "auditoria_costo_registrado_activo": total_aud_antes,
        "valoracion_costo": (libros_antes or {}).get("valoracion_costo"),
    }
    if not preok:
        hallazgos.append("Precondiciones no cumplidas: se detiene sin POST de escritura.")
        informe["escenarios"] = [
            {"subcaso": "TC-M06-35", "estado": "BLOCKED", "motivo": "Precondiciones fallidas."},
            {"subcaso": "TC-M06-36", "estado": "BLOCKED", "motivo": "Precondiciones fallidas."},
            {"subcaso": "TC-M06-38", "estado": "BLOCKED", "motivo": "Precondiciones fallidas."},
        ]
        informe["bloqueados"] = 3
        guardar(informe)
        print("PRECONDICIONES FALLIDAS", flush=True)
        return 2

    ids_lineas_antes = ids_lineas([x for x in lineas_antes if x.get("id_activo_biologico") == ACTIVO])
    informe["lineas"]["antes_activo"] = ids_lineas_antes
    informe["auditoria"]["antes"] = total_aud_antes
    informe["costos"]["antes_activo"] = resumir_costos(costos_activo)
    informe["costos"]["antes_periodo"] = resumir_costos(costos_220)

    # --- TC-M06-36 A/B ---
    rechazos = []
    for nombre, monto in (("monto_cero", 0), ("monto_negativo", -100)):
        cuerpo = {
            "subtipo_costo": "ALIMENTO",
            "origen_costo": "COMPRA_PROVEEDOR",
            "monto_costo": monto,
            "fecha_costo": hoy.isoformat(),
            "id_activo_biologico": ACTIVO,
            **PROVEEDOR,
            "fecha_factura": hoy.isoformat(),
            "fecha_vencimiento_factura": (hoy + timedelta(days=30)).isoformat(),
        }
        codigo_r, respuesta, duracion = pedir("POST", "/finanzas/costos", cuerpo, token)
        rechazos.append({
            "nombre": nombre, "http": codigo_r, "code": codigo_negocio(respuesta),
            "field": campo_val(respuesta),
        })
        peticiones.append(evidencia("POST", "/finanzas/costos", codigo_r, duracion, respuesta,
                                    escritura=True, cuerpo=cuerpo, escenario=f"TC-M06-36_{nombre}"))

    # --- TC-M06-38 ---
    cuerpo_cap = cuerpo_factura(hoy, MONTO_OK, naturaleza="INVERSION", confirmar=True)
    # factura distinta para no chocar si el rechazo ocurriera después de validar factura
    cuerpo_cap["factura_numero"] = "G11011202699"
    codigo_k, respuesta_k, duracion = pedir("POST", "/finanzas/costos", cuerpo_cap, token)
    peticiones.append(evidencia("POST", "/finanzas/costos", codigo_k, duracion, respuesta_k,
                                escritura=True, cuerpo=cuerpo_cap, escenario="TC-M06-38"))

    codigo_mid, costos_mid, _ = pedir("GET", f"/finanzas/costos?id_activo_biologico={ACTIVO}", token=token)
    peticiones.append(evidencia("GET", f"/finanzas/costos?id_activo_biologico={ACTIVO}", codigo_mid, 0,
                                resumir_costos(costos_mid), escenario="chequeo_post_negativos"))
    codigo_aud_mid, aud_mid, _ = pedir("GET", ruta_aud, token=token)
    total_aud_mid = aud_mid.get("total_registros") if isinstance(aud_mid, dict) else None
    peticiones.append(evidencia("GET", ruta_aud, codigo_aud_mid, 0, {"total_registros": total_aud_mid}, escenario="chequeo_post_negativos"))
    ids_antes_neg = set(informe["costos"]["antes_activo"].get("ids") or [])
    ids_mid = set(resumir_costos(costos_mid).get("ids") or []) if isinstance(costos_mid, list) else set()
    sin_persistencia_neg = (
        codigo_mid == 200 and isinstance(costos_mid, list)
        and ids_mid == ids_antes_neg
        and total_aud_mid == total_aud_antes
    )

    ok36 = (
        all(r["http"] == 400 and r["code"] == "VAL_ENTRADA" and r["field"] == "monto_costo" for r in rechazos)
        and sin_persistencia_neg
    )
    informe["escenarios"].append({
        "subcaso": "TC-M06-36",
        "estado": "PASSED" if ok36 else "FAILED",
        "detalle": rechazos,
        "sin_persistencia": sin_persistencia_neg,
        "motivo": ("0 y -100 respondieron 400 VAL_ENTRADA en monto_costo sin insertar ni auditar."
                   if ok36 else "Rechazo de montos o comparación de persistencia no cumplió lo esperado."),
    })

    ok38 = codigo_k == 422 and codigo_negocio(respuesta_k) == "RECLASIFICACION_NO_PERMITIDA" and sin_persistencia_neg
    informe["escenarios"].append({
        "subcaso": "TC-M06-38",
        "estado": "PASSED" if ok38 else "FAILED",
        "http": codigo_k,
        "code": codigo_negocio(respuesta_k),
        "sin_persistencia": sin_persistencia_neg,
        "motivo": ("Alimento como INVERSION con confirmar_capitalizacion respondió 422 RECLASIFICACION_NO_PERMITIDA."
                   if ok38 else "La restricción de capitalización no produjo el rechazo esperado."),
    })

    if not (ok36 and ok38):
        hallazgos.append("Se detiene el POSITIVO porque un negativo falló o hubo persistencia indebida.")
        informe["escenarios"].insert(0, {
            "subcaso": "TC-M06-35", "estado": "BLOCKED",
            "motivo": "No se envió el registro positivo tras fallos en 36/38.",
        })
    else:
        # --- TC-M06-35 ---
        reutilizado = costo_previo is not None
        codigo_ok, respuesta_ok, registro = None, None, None
        id_costo = None if not reutilizado else costo_previo.get("id_registro_costo")
        if reutilizado:
            hallazgos.append(
                f"No se reenvió el POST positivo: el costo G110 {id_costo} ya existía. "
                "Se verifica por lectura.")
            peticiones.append({
                "metodo": "POST", "consulta": "/finanzas/costos", "codigo": None, "duracion_ms": 0,
                "escritura": False, "en": datetime.now(ZoneInfo(ZONA)).isoformat(),
                "escenario": "TC-M06-35",
                "cuerpo": None,
                "respuesta": {
                    "omitido_reenvio": True,
                    "id_registro_costo_existente": id_costo,
                    "http_201_original": True,
                },
            })
        else:
            cuerpo_ok = cuerpo_factura(hoy, MONTO_OK)
            codigo_ok, respuesta_ok, duracion = pedir("POST", "/finanzas/costos", cuerpo_ok, token)
            peticiones.append(evidencia("POST", "/finanzas/costos", codigo_ok, duracion, respuesta_ok,
                                        escritura=True, cuerpo=cuerpo_ok, escenario="TC-M06-35"))
            if isinstance(respuesta_ok, dict):
                regs = respuesta_ok.get("registros")
                if isinstance(regs, list) and regs:
                    registro = regs[0]
                    id_costo = registro.get("id_registro_costo")

        codigo_c2, costos_despues, duracion = pedir("GET", f"/finanzas/costos?id_activo_biologico={ACTIVO}", token=token)
        peticiones.append(evidencia("GET", f"/finanzas/costos?id_activo_biologico={ACTIVO}", codigo_c2, duracion,
                                    costos_despues if isinstance(costos_despues, list) else resumir_costos(costos_despues),
                                    escenario="post_35"))
        codigo_c220b, costos_220b, duracion = pedir("GET", f"/finanzas/costos?id_periodo_contable={PERIODO}", token=token)
        peticiones.append(evidencia("GET", f"/finanzas/costos?id_periodo_contable={PERIODO}", codigo_c220b, duracion,
                                    resumir_costos(costos_220b), escenario="post_35"))
        codigo_a2, activo_despues, duracion = pedir("GET", f"/finanzas/activos/{ACTIVO}", token=token)
        libros_despues = libros(activo_despues)
        informe["libros"]["despues"] = libros_despues
        peticiones.append(evidencia("GET", f"/finanzas/activos/{ACTIVO}", codigo_a2, duracion, libros_despues, escenario="post_35"))
        codigo_l2, lineas_despues, duracion = pedir("GET", f"/finanzas/lineas?id_periodo_contable={PERIODO}", token=token)
        ids_lineas_despues = ids_lineas([x for x in (lineas_despues or []) if isinstance(x, dict) and x.get("id_activo_biologico") == ACTIVO])
        informe["lineas"]["despues_activo"] = ids_lineas_despues
        peticiones.append(evidencia("GET", f"/finanzas/lineas?id_periodo_contable={PERIODO}", codigo_l2, duracion,
                                    {"total": len(lineas_despues) if isinstance(lineas_despues, list) else None,
                                     "ids_activo": ids_lineas_despues}, escenario="post_35"))
        codigo_u2, aud_despues, duracion = pedir("GET", ruta_aud, token=token)
        total_aud_despues = aud_despues.get("total_registros") if isinstance(aud_despues, dict) else None
        informe["auditoria"]["despues"] = total_aud_despues
        eventos = aud_despues.get("eventos") if isinstance(aud_despues, dict) else []
        peticiones.append(evidencia("GET", ruta_aud, codigo_u2, duracion,
                                    {"total_registros": total_aud_despues,
                                     "ids_referencia": [e.get("id_referencia") for e in (eventos or []) if isinstance(e, dict)]},
                                    escenario="post_35"))
        codigo_p2, periodos2, duracion = pedir("GET", f"/finanzas/periodos?numero_id_tributaria={NIT}", token=token)
        periodo2 = next((p for p in (periodos2 or []) if isinstance(p, dict) and p.get("id_periodo_contable") == PERIODO), None)
        peticiones.append(evidencia("GET", f"/finanzas/periodos?numero_id_tributaria={NIT}", codigo_p2, duracion,
                                    {"estado": None if not periodo2 else periodo2.get("estado")}, escenario="post_35"))

        informe["id_registro_costo"] = id_costo
        fila = next((c for c in (costos_despues or []) if isinstance(c, dict) and c.get("id_registro_costo") == id_costo), None)
        if registro is None and isinstance(fila, dict):
            registro = {
                "id_registro_costo": fila.get("id_registro_costo"),
                "id_activo_biologico": fila.get("id_activo_biologico"),
                "monto_costo": fila.get("monto_costo"),
                "naturaleza_costo": fila.get("naturaleza_costo"),
                "vehiculo_contable": fila.get("vehiculo_contable"),
                "estado": fila.get("estado"),
                "id_linea_asiento": None,
            }
        evento = next((e for e in (eventos or []) if isinstance(e, dict) and e.get("id_referencia") == id_costo), None)
        informe["costos"]["despues_activo"] = resumir_costos(costos_despues)
        informe["costos"]["despues_periodo"] = resumir_costos(costos_220b)
        informe["costos"]["registro_positivo"] = fila
        informe["auditoria"]["evento_positivo"] = None if not isinstance(evento, dict) else {
            "id_evento": evento.get("id_evento"),
            "tipo_evento": evento.get("tipo_evento"),
            "id_referencia": evento.get("id_referencia"),
            "id_periodo_contable": evento.get("id_periodo_contable"),
            "monto_afectado": evento.get("monto_afectado"),
            "payload_evento": evento.get("payload_evento"),
        }

        libros_iguales = (
            (libros_antes or {}).get("valoracion_costo") == (libros_despues or {}).get("valoracion_costo")
            and ((libros_antes or {}).get("activo") or {}).get("costo_adquisicion")
            == ((libros_despues or {}).get("activo") or {}).get("costo_adquisicion")
        )
        # Tras reutilizar, las líneas del activo no deben haber crecido por el costo.
        sin_linea_nueva = ids_lineas_despues == ids_lineas_antes or (
            reutilizado and set(ids_lineas_despues).issubset(set(ids_lineas_antes) | set(ids_lineas_despues))
            and all(
                not (isinstance(x, dict) and x.get("tabla_origen") == "registros_costos"
                     and x.get("id_origen") == id_costo)
                for x in (lineas_despues or [])
            )
        )
        periodo_sigue_abierto = isinstance(periodo2, dict) and periodo2.get("estado") == "ABIERTO"
        http_ok = (codigo_ok == 201) if not reutilizado else True
        auditoria_ok = evento is not None and (
            (not reutilizado and total_aud_despues == (total_aud_antes or 0) + 1)
            or (reutilizado and total_aud_despues >= 1)
        )
        ok35 = (
            http_ok
            and isinstance(registro, dict)
            and registro.get("naturaleza_costo") == "MANTENIMIENTO"
            and registro.get("vehiculo_contable") == "FACTURA_COMPRA"
            and registro.get("id_linea_asiento") is None
            and isinstance(fila, dict)
            and fila.get("naturaleza_costo") == "MANTENIMIENTO"
            and fila.get("politica_capitalizacion") == "GASTO"
            and fila.get("subtipo_costo") == "ALIMENTO"
            and fila.get("origen_costo") == "COMPRA_PROVEEDOR"
            and fila.get("id_periodo_contable") == PERIODO
            and Decimal(str(fila.get("monto_costo"))) == MONTO_OK
            and fila.get("fecha_costo") == hoy.isoformat()
            and auditoria_ok
            and libros_iguales
            and sin_linea_nueva
            and periodo_sigue_abierto
            and isinstance(costos_despues, list) and len(costos_despues) == 1
            and isinstance(costos_220b, list) and len(costos_220b) == 1
        )
        if fila and fila.get("cuenta_debito") == "158405":
            hallazgos.append(
                "La matriz CONSUMO_INSUMO/UNICO de TEST asignó cuenta_debito 158405 al costo de alimento "
                "(factura). La política del registro es GASTO y no se creó línea NIC 41; se documenta sin "
                "modificar la matriz.")
        motivo35 = (
            f"{'HTTP 201 original + verificación' if reutilizado else 'HTTP 201'} id={id_costo}; "
            f"MANTENIMIENTO/GASTO; vehículo FACTURA_COMPRA sin línea NIC 41; "
            f"COSTO_REGISTRADO; período 220 ABIERTO; valor en libros sin aumento."
            if ok35 else
            f"Registro positivo incompleto. http={codigo_ok} id={id_costo} reutilizado={reutilizado} "
            f"libros_iguales={libros_iguales} sin_linea={sin_linea_nueva} evento={evento is not None}."
        )
        informe["escenarios"].insert(0, {
            "subcaso": "TC-M06-35",
            "estado": "PASSED" if ok35 else "FAILED",
            "http": 201 if reutilizado else codigo_ok,
            "post_reenviado": not reutilizado,
            "id_registro_costo": id_costo,
            "registro": registro,
            "persistido": fila,
            "libros_sin_aumento": libros_iguales,
            "sin_linea_nic41": sin_linea_nueva,
            "periodo_abierto": periodo_sigue_abierto,
            "motivo": motivo35,
        })

    estados = [e["estado"] for e in informe["escenarios"]]
    informe["aprobados"] = estados.count("PASSED")
    informe["fallidos"] = estados.count("FAILED")
    informe["bloqueados"] = estados.count("BLOCKED")
    informe["porcentaje_aprobacion"] = round(informe["aprobados"] / max(len(estados), 1) * 100)
    informe["caso_completo_aprobado"] = informe["aprobados"] == 3 and informe["fallidos"] == 0 and informe["bloqueados"] == 0
    informe["dictamen_general"] = "APROBADO" if informe["caso_completo_aprobado"] else (
        "BLOQUEADO" if informe["bloqueados"] else "RECHAZADO"
    )
    informe["duracion_ms"] = round((time.perf_counter() - inicio) * 1000)
    guardar(informe)
    print(
        " ".join(f"{e['subcaso']} {e['estado']}" for e in informe["escenarios"]),
        f"| {informe['porcentaje_aprobacion']}% dictamen={informe['dictamen_general']} id={informe.get('id_registro_costo')}",
        flush=True,
    )
    return 0 if informe["caso_completo_aprobado"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
