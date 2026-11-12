"""TC-M06-G103, RF-89, incidencia INC-M06-291-G75, issue #978.

La primera evaluación del 8 de noviembre permanece en resultados/primera_evaluacion.
TC-M06-22 y TC-M06-24 ya quedaron APROBADOS y este script no los vuelve a enviar.
TC-M06-23 sigue BLOQUEADO. Esta corrida solo consulta TEST y prepara la revisión.

Reglas confirmadas en RegistrarPrecioUseCase._validar:
- Se rechaza la vigencia solo cuando (hoy_usuario - fecha_vigencia).days > 365.
  Exactamente 365 días continúa. El código es FECHA_VIGENCIA_FUERA_DE_RANGO, HTTP 400.
- Si fecha_vencimiento viene informada, debe ser estrictamente posterior a fecha_vigencia.
  Igual o anterior responde FECHA_VENCIMIENTO_INVALIDA, HTTP 400.
- hoy_usuario es el día calendario de X-Zona-Horaria. Sin esa cabecera, el día es UTC.

Una vigencia de exactamente 365 días es anterior a hoy. El caso de uso no puede
guardarla como PROGRAMADO: ese estado exige fecha_vigencia posterior a hoy.
Este script no inventa otra solicitud para sortear esa condición.

    python tests/Test_Testing/Test_Modulo6/RF-89/TC-M06-G103/ejecutar_tc_m06_g103.py
"""
from __future__ import annotations

import html
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

CARPETA = Path(__file__).resolve().parent
RESULTADOS = CARPETA / "resultados"
PRIMERA = RESULTADOS / "primera_evaluacion"
SOPORTE = RESULTADOS / "soporte_preparacion"
BASE_API = "https://api.inmero.co/api-sgpmp-test"
ZONA = "America/Bogota"
ESPECIE = 424
PRECIOS_INFORMADOS = {436, 437}
SECRETOS = {"token", "access_token", "contrasena", "password", "hash_integridad", "numero_id_tributaria"}


def hoy_negocio() -> datetime.date:
    """Mismo día calendario que hoy_usuario cuando la petición envía America/Bogota."""
    return datetime.now(ZoneInfo(ZONA)).date()


def vigencia_de_365(hoy) -> tuple:
    vigencia = hoy - timedelta(days=365)
    return vigencia, (hoy - vigencia).days


def pedir(metodo: str, ruta: str, cuerpo: dict | None = None, token: str | None = None):
    if metodo == "POST" and ruta.startswith("/finanzas/precios"):
        raise RuntimeError("POST /finanzas/precios está bloqueado en esta preparación.")
    datos = None if cuerpo is None else json.dumps(cuerpo).encode("utf-8")
    headers = {"Accept": "application/json", "X-Zona-Horaria": ZONA}
    if cuerpo is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(BASE_API + ruta, data=datos, headers=headers, method=metodo)
    inicio = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
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
    return codigo, payload, round((time.perf_counter() - inicio) * 1000)


def limpiar(valor, profundidad: int = 0):
    if profundidad > 5:
        return "..."
    if isinstance(valor, dict):
        return {
            clave: ({"omitido": True, "longitud": len(item)} if isinstance(item, str) else {"omitido": True})
            if clave in SECRETOS else limpiar(item, profundidad + 1)
            for clave, item in valor.items()
        }
    if isinstance(valor, list):
        return [limpiar(v, profundidad + 1) for v in valor[:40]]
    if isinstance(valor, str) and len(valor) > 240:
        return valor[:240]
    return valor


def evidencia(metodo: str, ruta: str, codigo: int, duracion: int, cuerpo, respuesta) -> dict:
    return {
        "metodo": metodo, "consulta": ruta, "codigo": codigo, "duracion_ms": duracion,
        "escritura": metodo == "POST", "en": datetime.now(ZoneInfo(ZONA)).isoformat(),
        "cuerpo": limpiar(cuerpo), "respuesta": limpiar(respuesta),
    }


def resumir_precio(precio: dict) -> dict:
    return {
        "id": precio.get("id_precio_mercado"),
        "id_especie": precio.get("id_especie"),
        "categoria": precio.get("categoria"),
        "fuente": precio.get("fuente"),
        "precio_unitario": precio.get("precio_unitario"),
        "fecha_vigencia": precio.get("fecha_vigencia"),
        "fecha_vencimiento": precio.get("fecha_vencimiento"),
        "estado": precio.get("estado"),
        "es_aplicado": precio.get("es_aplicado"),
        "unidad_medida": precio.get("unidad_medida"),
    }


def guardar(informe: dict, peticiones: list) -> None:
    if SOPORTE.resolve() == PRIMERA.resolve() or PRIMERA in SOPORTE.parents:
        raise RuntimeError("La preparación no puede escribir sobre la primera evaluación.")
    SOPORTE.mkdir(parents=True, exist_ok=True)
    (SOPORTE / "resultado_preparacion_TC-M06-G103.html").write_text(render(informe), encoding="utf-8")
    (SOPORTE / "resumen_preparacion_TC-M06-G103.json").write_text(
        json.dumps(informe, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (SOPORTE / "evidencias_preparacion_TC-M06-G103.json").write_text(json.dumps({
        "caso": "TC-M06-G103", "tipo": "preparacion", "post_precio_ejecutado": False,
        "generado_en": informe["generado_en"], "peticiones": peticiones,
    }, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def render(informe: dict) -> str:
    precios = "".join(
        "<tr>"
        f"<td>{html.escape(str(p['id']))}</td><td>{html.escape(str(p['fuente']))}</td>"
        f"<td>{html.escape(str(p['precio_unitario']))}</td><td>{html.escape(str(p['fecha_vigencia']))}</td>"
        f"<td>{html.escape(str(p['estado']))}</td><td>{html.escape(str(p['es_aplicado']))}</td></tr>"
        for p in informe["precios_424"]
    )
    diferencias = "".join(f"<li>{html.escape(d)}</li>" for d in informe["diferencias"])
    return f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8"><title>Preparación TC-M06-G103</title>
<style>
 body {{ font-family: Segoe UI, sans-serif; margin: 2rem; line-height: 1.45; }}
 table {{ border-collapse: collapse; width: 100%; }}
 th, td {{ border: 1px solid #ccc; padding: .45rem .6rem; text-align: left; vertical-align: top; }}
 th {{ background: #f3f3f3; }}
</style></head><body>
<h1>Preparación TC-M06-G103 — TC-M06-23</h1>
<p>Issue #978. Esta página es soporte de preparación, no una ejecución del subcaso. POST de precio: no enviado.</p>
<p>Fecha de negocio: {html.escape(informe['fecha_negocio'])} ({html.escape(ZONA)}).
Vigencia que cumpliría 365 días: {html.escape(informe['fecha_vigencia_365'])}.
Antigüedad comprobada: {informe['antiguedad_dias']} días.</p>
<p>{html.escape(informe['decision'])}</p>
<h2>Precios leídos de la especie 424</h2>
<table><tr><th>Id</th><th>Fuente</th><th>Precio</th><th>Vigencia</th><th>Estado</th><th>Aplicado</th></tr>{precios}</table>
<h2>Diferencias frente al dato informado</h2>
<ul>{diferencias}</ul>
</body></html>"""


def main() -> int:
    hoy = hoy_negocio()
    vigencia, antiguedad = vigencia_de_365(hoy)
    if antiguedad != 365:
        raise SystemExit(f"El cálculo no dio 365 días: {antiguedad}.")
    if os.environ.get("TC_M06_23_AUTORIZAR_POST") == "AUTORIZADO":
        print("La variable de autorización está presente. Esta preparación igual no envía POST /finanzas/precios.")

    correo = os.environ.get("QA_CORREO")
    contrasena = os.environ.get("QA_CONTRASENA")
    if not correo or not contrasena:
        raise SystemExit("Defina QA_CORREO y QA_CONTRASENA en el entorno.")

    peticiones = []
    codigo, login, duracion = pedir("POST", "/sesiones/", {"correo_electronico": correo, "contrasena": contrasena})
    token = login.get("token") if isinstance(login, dict) else None
    peticiones.append(evidencia("POST", "/sesiones/", codigo, duracion, {"correo_electronico": "omitido"}, limpiar(login)))
    if codigo != 200 or not token:
        raise SystemExit("No fue posible autenticar. No se consultó el catálogo.")

    codigo, precios, duracion = pedir("GET", f"/finanzas/precios?id_especie={ESPECIE}", token=token)
    lista = [resumir_precio(p) for p in precios if isinstance(p, dict)] if isinstance(precios, list) else []
    peticiones.append(evidencia("GET", f"/finanzas/precios?id_especie={ESPECIE}", codigo, duracion, None, lista))

    codigo, periodos, duracion = pedir("GET", "/finanzas/periodos?numero_id_tributaria=900000003", token=token)
    periodo = next((p for p in periodos if isinstance(p, dict) and p.get("id_periodo_contable") == 220), None) if isinstance(periodos, list) else None
    periodo_publico = None if periodo is None else {
        "id_periodo_contable": periodo.get("id_periodo_contable"),
        "estado": periodo.get("estado"),
        "fecha_inicio": periodo.get("fecha_inicio"),
        "fecha_fin": periodo.get("fecha_fin"),
    }
    peticiones.append(evidencia("GET", "/finanzas/periodos?numero_id_tributaria=900000003", codigo, duracion, None, periodo_publico))

    codigo, catalogo, duracion = pedir("GET", "/configuracion/especies", token=token)
    especie = None
    if isinstance(catalogo, dict):
        especie = next((e for e in catalogo.get("items") or [] if isinstance(e, dict) and e.get("id_especie") == ESPECIE), None)
    especie_publica = None if especie is None else {
        "id_especie": especie.get("id_especie"),
        "nombre": especie.get("nombre") or especie.get("especie"),
        "es_activo": especie.get("es_activo"),
    }
    peticiones.append(evidencia("GET", "/configuracion/especies", codigo, duracion, None, especie_publica))

    codigo, config, duracion = pedir("GET", "/finanzas/configuracion", token=token)
    umbral = None
    parametro = None
    if isinstance(config, dict):
        umbral = (config.get("general") or {}).get("pct_umbral_desviacion_precio")
        parametro = next((e for e in config.get("especies") or [] if isinstance(e, dict) and e.get("id_especie") == ESPECIE), None)
    peticiones.append(evidencia("GET", "/finanzas/configuracion", codigo, duracion, None, {
        "pct_umbral_desviacion_precio": umbral, "especie_424": parametro,
    }))

    codigo, activos, duracion = pedir("GET", "/activos-biologicos?id_especie=424&page_size=5", token=token)
    total_activos = activos.get("total_registros") if isinstance(activos, dict) else None
    peticiones.append(evidencia("GET", "/activos-biologicos?id_especie=424&page_size=5", codigo, duracion, None, {
        "http": codigo, "total_registros": total_activos,
    }))

    ids = {p["id"] for p in lista}
    diferencias = []
    if ids - PRECIOS_INFORMADOS:
        diferencias.append(
            "La especie 424 tiene precios que el informe del 8 de noviembre no incluía: "
            + ", ".join(str(i) for i in sorted(ids - PRECIOS_INFORMADOS)) + "."
        )
    for precio in lista:
        if precio["id"] == 436 and (precio["estado"] != "ACTIVO" or precio["es_aplicado"] is not True):
            diferencias.append(
                f"El precio 436 existe con vigencia {precio['fecha_vigencia']} y valor {precio['precio_unitario']}, "
                f"pero hoy está {precio['estado']} y es_aplicado={precio['es_aplicado']}."
            )
        if precio["id"] == 437 and precio["estado"] != "PROGRAMADO":
            diferencias.append(
                f"El precio 437 existe con vigencia {precio['fecha_vigencia']} y valor {precio['precio_unitario']}, "
                f"pero hoy está {precio['estado']}, no programado."
            )
    if codigo != 200:
        diferencias.append(f"GET /activos-biologicos?id_especie=424 respondió HTTP {codigo}. No se confirmó que la especie no tenga activos.")
    if periodo_publico is None or periodo_publico.get("estado") != "ABIERTO":
        diferencias.append("El período 220 no se leyó como ABIERTO.")

    decision = (
        "Preparación detenida. No se construyó ni se envió POST /finanzas/precios. "
        "El catálogo vigente no coincide con el dato informado y una vigencia de exactamente 365 días "
        "no puede ser, a la vez, una vigencia futura: el caso de uso la almacenaría como ACTIVO."
    )
    informe = {
        "caso": "TC-M06-G103",
        "rf": "RF-89",
        "incidencia": "INC-M06-291-G75",
        "issue": 978,
        "tipo": "preparacion",
        "ejecucion_funcional": False,
        "post_precio_ejecutado": False,
        "caso_completo_reclasificado": False,
        "subcasos": {
            "TC-M06-22": "APROBADO en la primera evaluación; no se repitió.",
            "TC-M06-23": "BLOQUEADO. Preparado para revisión, sin solicitud enviada.",
            "TC-M06-24": "APROBADO en la primera evaluación; no se repitió.",
        },
        "generado_en": datetime.now(ZoneInfo(ZONA)).isoformat(),
        "fecha_negocio": hoy.isoformat(),
        "zona": ZONA,
        "fecha_vigencia_365": vigencia.isoformat(),
        "antiguedad_dias": antiguedad,
        "solicitud": {
            "enviada": False,
            "completa": False,
            "endpoint": "POST /finanzas/precios",
            "fecha_vigencia_calculada": vigencia.isoformat(),
            "puede_ser_programado": False,
            "motivo": decision,
        },
        "precios_424": lista,
        "periodo_220": periodo_publico,
        "especie": especie_publica,
        "umbral_desviacion": umbral,
        "parametro_especie": parametro,
        "activos_http": peticiones[-1]["codigo"],
        "diferencias": diferencias,
        "decision": decision,
        "reglas": [
            "Exactamente 365 días de antigüedad se acepta, porque la comparación es estrictamente mayor que 365.",
            "366 días se rechaza con HTTP 400 y FECHA_VIGENCIA_FUERA_DE_RANGO.",
            "Vencimiento posterior a la vigencia es válido.",
            "Vencimiento igual a la vigencia se rechaza con HTTP 400 y FECHA_VENCIMIENTO_INVALIDA.",
            "Vencimiento anterior a la vigencia se rechaza con el mismo código. TC-M06-24 ya cubrió ese rechazo.",
        ],
    }
    guardar(informe, peticiones)
    print(decision)
    print(f"fecha_negocio={hoy.isoformat()} fecha_vigencia_365={vigencia.isoformat()} antiguedad={antiguedad}")
    print("POST /finanzas/precios no enviado. Solicitud completa: no construida.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
