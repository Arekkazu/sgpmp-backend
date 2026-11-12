"""TC-M06-G108 contra TEST. Solo consultas.

La variación se compara con el umbral configurado antes de insertar. Confirmar
el caso de 6.000.000 guardaría un precio nuevo, así que no se envía ningún POST.

    python tests/Test_Testing/Test_Modulo6/RF-89/TC-M06-G108/ejecutar_tc_m06_g108.py
"""
from __future__ import annotations

import html
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

CARPETA = Path(__file__).resolve().parent
RESULTADOS = CARPETA / "resultados"
BASE_API = "https://api.inmero.co/api-sgpmp-test"
ZONA = "America/Bogota"
SECRETOS = {"token", "access_token", "contrasena", "password", "hash_integridad", "numero_id_tributaria", "evidencia", "hash_evidencia"}
ANTERIOR = Decimal("4000000")
CASOS = (
    {"subcaso": "TC-M06-32", "nuevo": Decimal("6500000"), "variacion": Decimal("62.5")},
    {"subcaso": "TC-M06-33", "nuevo": Decimal("6000000"), "variacion": Decimal("50")},
)


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
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode()
            payload = json.loads(raw) if raw else None
            codigo = resp.status
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"message": raw[:200]}
        codigo = exc.code
    return codigo, payload, round((time.perf_counter() - inicio) * 1000)


def limpiar(valor, profundidad: int = 0):
    if profundidad > 5:
        return "..."
    if isinstance(valor, dict):
        return {k: ({"omitido": True, "longitud": len(v) if isinstance(v, str) else None} if k in SECRETOS else limpiar(v, profundidad + 1)) for k, v in valor.items()}
    if isinstance(valor, list):
        return [limpiar(v, profundidad + 1) for v in valor[:30]]
    if isinstance(valor, str) and len(valor) > 220:
        return valor[:220]
    return valor


def evidencia(metodo, ruta, codigo, duracion, respuesta) -> dict:
    return {"metodo": metodo, "consulta": ruta, "codigo": codigo, "duracion_ms": duracion,
            "escritura": False, "en": datetime.now(timezone.utc).isoformat(), "respuesta": limpiar(respuesta)}


def ficha(precio: dict) -> dict:
    return {k: precio.get(k) for k in (
        "id_precio_mercado", "id_especie", "categoria", "fuente", "precio_unitario",
        "fecha_vigencia", "fecha_vencimiento", "estado", "es_aplicado")}


def render(informe: dict) -> str:
    filas = "".join(
        f"<tr><td>{html.escape(e['subcaso'])}</td><td>{html.escape(e['variacion'])} %</td>"
        f"<td>{html.escape(e['comparacion'])}</td><td class='b'>{html.escape(e['estado'])}</td>"
        f"<td>{html.escape(e['motivo'])}</td></tr>"
        for e in informe["escenarios"])
    return f"""<!DOCTYPE html><html lang="es"><head><meta charset="utf-8"><title>TC-M06-G108</title>
<style>body{{font-family:Segoe UI,sans-serif;margin:2rem;line-height:1.45}}table{{border-collapse:collapse;width:100%}}
th,td{{border:1px solid #ccc;padding:.45rem .6rem;text-align:left;vertical-align:top}}th{{background:#f3f3f3}}.b{{font-weight:700}}
pre{{white-space:pre-wrap;background:#fafafa;padding:.8rem}}</style></head><body>
<h1>Módulo 6 — RF-89 — TC-M06-G108</h1>
<p>Variaciones que requieren confirmación explícita. Generado: {html.escape(informe['generado_en'])}. Escrituras de precios: no.</p>
<table>
<tr><th>Porcentaje</th><td>{informe['porcentaje_aprobacion']} %</td></tr>
<tr><th>Umbral en TEST</th><td>{html.escape(str(informe['umbral']))} %</td></tr>
<tr><th>Precios</th><td>{informe['total_precios']}</td></tr>
<tr><th>Referencias de 4.000.000</th><td>{informe['referencias_4000000']}</td></tr>
</table>
<h2>Subcasos</h2>
<table><tr><th>Subcaso</th><th>Variación</th><th>Regla</th><th>Estado</th><th>Motivo</th></tr>{filas}</table>
<h2>Contrato</h2><pre>{html.escape(informe['contrato'])}</pre>
<h2>Precios vigentes aplicados</h2><pre>{html.escape(json.dumps(informe['aplicados'], ensure_ascii=False, indent=2))}</pre>
<h2>Auditoría</h2><pre>{html.escape(json.dumps(informe['auditoria'], ensure_ascii=False, indent=2))}</pre>
<h2>Hallazgos</h2><ul>{''.join(f'<li>{html.escape(h)}</li>' for h in informe['hallazgos'])}</ul>
</body></html>"""


def guardar(informe: dict) -> None:
    RESULTADOS.mkdir(parents=True, exist_ok=True)
    (RESULTADOS / "resultado_ejecucion_TC-M06-G108.html").write_text(render(informe), encoding="utf-8")
    (RESULTADOS / "resumen_ejecucion_TC-M06-G108.json").write_text(json.dumps(informe, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (RESULTADOS / "evidencia_peticiones_TC-M06-G108.json").write_text(json.dumps({
        "caso": "TC-M06-G108", "generado_en": informe["generado_en"], "peticiones": informe["peticiones"],
    }, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def main() -> int:
    inicio = time.perf_counter()
    peticiones = []
    contrato = (
        "POST /finanzas/precios. El Contador tiene precios_mercado crear. "
        "La variación es abs(nuevo - anterior) / anterior * 100. "
        "El anterior es el precio vigente de la misma especie, categoría, métrica y fuente. "
        "No se compara con otra fuente. Si no hay anterior, no hay variación y el registro sigue. "
        "La condición es desviacion > pct_umbral_desviacion_precio. El igual no pide confirmación. "
        "El umbral vive en la configuración contable; su valor inicial es 50 y debe ser mayor que 0. "
        "Sin confirmar_desviacion, una variación mayor responde 409 DESVIACION_PRECIO_REQUIERE_CONFIRMACION "
        "antes del INSERT, sin auditoría ni notificación. "
        "La confirmación es el mismo POST con confirmar_desviacion en true. Entonces inserta, "
        "audita PRECIO_REGISTRADO y, si corresponde, PRECIO_MARCADO_REEMPLAZADO. "
        "Un precio ACTIVO también avisa a los contadores."
    )
    informe = {
        "caso": "TC-M06-G108", "rf": ["RF-89"], "ambiente": BASE_API,
        "generado_en": datetime.now(timezone.utc).isoformat(), "contrato": contrato,
        "post_ejecutado": False, "umbral": None, "total_precios": None,
        "referencias_4000000": 0, "aplicados": [], "auditoria": {}, "escenarios": [],
        "peticiones": peticiones,
        "hallazgos": [
            "BLOQUEO DE PRUEBA: no existe un precio aislado de 4.000.000 ni autorización para registrar 6.500.000 o 6.000.000 en el catálogo compartido.",
        ],
        "aprobados": 0, "rechazados": 0, "bloqueados": 2, "porcentaje_aprobacion": 0,
    }
    correo, contrasena = os.environ.get("QA_CORREO"), os.environ.get("QA_CONTRASENA")
    if not correo or not contrasena:
        raise SystemExit("Defina QA_CORREO y QA_CONTRASENA.")
    codigo, login, duracion = pedir("POST", "/sesiones/", {"correo_electronico": correo, "contrasena": contrasena})
    token = login.get("token") if isinstance(login, dict) else None
    peticiones.append(evidencia("POST", "/sesiones/", codigo, duracion, limpiar(login if isinstance(login, dict) else {})))
    if codigo != 200 or not token:
        for caso in CASOS:
            informe["escenarios"].append({"subcaso": caso["subcaso"], "variacion": str(caso["variacion"]),
                                          "comparacion": "sin umbral leído", "estado": "BLOQUEADO",
                                          "motivo": "No fue posible autenticar al Contador.", "post_ejecutado": False})
        guardar(informe)
        print("BLOQUEADO")
        return 2

    codigo, config, duracion = pedir("GET", "/finanzas/configuracion", token=token)
    general = config.get("general") if isinstance(config, dict) else {}
    umbral = Decimal(str(general.get("pct_umbral_desviacion_precio"))) if isinstance(general, dict) and general.get("pct_umbral_desviacion_precio") is not None else None
    informe["umbral"] = str(umbral) if umbral is not None else None
    peticiones.append(evidencia("GET", "/finanzas/configuracion", codigo, duracion, {
        "pct_umbral_desviacion_precio": informe["umbral"],
        "dias_alerta_vencimiento_precio": general.get("dias_alerta_vencimiento_precio") if isinstance(general, dict) else None,
    }))
    codigo, precios, duracion = pedir("GET", "/finanzas/precios", token=token)
    lista = [ficha(p) for p in precios if isinstance(p, dict)] if isinstance(precios, list) else []
    informe["total_precios"] = len(lista)
    informe["aplicados"] = [p for p in lista if p.get("es_aplicado")]
    informe["referencias_4000000"] = sum(1 for p in lista if Decimal(str(p.get("precio_unitario"))) == ANTERIOR)
    peticiones.append(evidencia("GET", "/finanzas/precios", codigo, duracion, {
        "total": len(lista), "referencias_4000000": informe["referencias_4000000"], "aplicados": informe["aplicados"],
    }))
    for tipo in ("PRECIO_REGISTRADO", "PRECIO_MARCADO_REEMPLAZADO"):
        ruta = f"/finanzas/auditoria?tipo_evento={tipo}&formato=TECNICO&tamano=1"
        codigo_aud, auditoria, duracion = pedir("GET", ruta, token=token)
        total = auditoria.get("total_registros") if isinstance(auditoria, dict) else None
        informe["auditoria"][tipo] = {"http": codigo_aud, "total": total}
        peticiones.append(evidencia("GET", ruta, codigo_aud, duracion, {"total_registros": total}))

    for caso in CASOS:
        supera = None if umbral is None else caso["variacion"] > umbral
        comparacion = "sin umbral" if supera is None else f"{caso['variacion']} > {umbral} = {str(supera).lower()}"
        if caso["subcaso"] == "TC-M06-32":
            efecto = "Con el umbral leído, 62,5 % pediría confirmación y respondería 409 antes de insertar."
        else:
            efecto = "Con el umbral leído, 50 % no es mayor que el umbral, así que el POST insertaría el precio."
        informe["escenarios"].append({
            "subcaso": caso["subcaso"], "anterior": "4000000", "nuevo": str(caso["nuevo"]),
            "variacion": str(caso["variacion"]), "comparacion": comparacion, "supera_umbral": supera,
            "estado": "BLOQUEADO", "post_ejecutado": False,
            "motivo": (
                f"{efecto} No hay un precio de 4.000.000 aislado ni autorización para escribir en el catálogo compartido. "
                "No se envió el POST."
            ),
        })
    informe["duracion_ms"] = round((time.perf_counter() - inicio) * 1000)
    guardar(informe)
    print(f"TC-M06-32 BLOQUEADO TC-M06-33 BLOQUEADO umbral {informe['umbral']} referencias {informe['referencias_4000000']}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
