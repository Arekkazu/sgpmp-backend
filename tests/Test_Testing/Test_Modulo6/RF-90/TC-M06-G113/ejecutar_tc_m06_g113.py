"""TC-M06-G113 contra TEST.

No se registra el costo de 900.000. Solo se envían rechazos que ocurren
antes de crear períodos o costos: monto no positivo y activos repetidos.

    python tests/Test_Testing/Test_Modulo6/RF-90/TC-M06-G113/ejecutar_tc_m06_g113.py
"""
from __future__ import annotations

import html
import json
import os
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, ROUND_DOWN
from pathlib import Path

CARPETA = Path(__file__).resolve().parent
RESULTADOS = CARPETA / "resultados"
BASE_API = "https://api.inmero.co/api-sgpmp-test"
ZONA = "America/Bogota"
SECRETOS = {"token", "access_token", "contrasena", "password", "hash_integridad", "numero_id_tributaria",
            "identificador", "finca", "tercero_nit", "tercero_razon_social"}


def truncar2(valor: Decimal) -> Decimal:
    return Decimal(valor).quantize(Decimal("0.01"), rounding=ROUND_DOWN)


def repartir(monto: Decimal, participaciones: dict[int, Decimal]) -> dict[int, Decimal]:
    """Misma regla que nic41.repartir: trunca y el residuo va al mayor (empate: menor id)."""
    total = sum(participaciones.values(), Decimal(0))
    partes = {k: truncar2(monto * v / total) for k, v in participaciones.items()}
    mayor = min(participaciones, key=lambda k: (-participaciones[k], k))
    partes[mayor] += monto - sum(partes.values(), Decimal(0))
    return partes


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
        return {k: ({"omitido": True} if k in SECRETOS else limpiar(v, profundidad + 1)) for k, v in valor.items()}
    if isinstance(valor, list):
        return [limpiar(v, profundidad + 1) for v in valor[:20]]
    if isinstance(valor, str) and len(valor) > 240:
        return valor[:240]
    return valor


def evidencia(metodo, ruta, codigo, duracion, respuesta, cuerpo=None) -> dict:
    return {"metodo": metodo, "consulta": ruta, "codigo": codigo, "duracion_ms": duracion, "escritura": False,
            "en": datetime.now(timezone.utc).isoformat(), "cuerpo": cuerpo, "respuesta": limpiar(respuesta)}


def negocio(payload) -> str | None:
    return payload.get("error_code") or payload.get("code") if isinstance(payload, dict) else None


def resumir(lista) -> dict:
    if not isinstance(lista, list):
        return {"total": None}
    grupos = [c.get("id_grupo_reparto") for c in lista if isinstance(c, dict) and c.get("id_grupo_reparto")]
    return {"total": len(lista), "con_grupo": len(grupos), "grupos": len(set(grupos)),
            "metodos": dict(Counter(c.get("metodo_reparto") for c in lista if isinstance(c, dict) and c.get("metodo_reparto")))}


def escenario_codigo(nombre: str, monto: Decimal, pesos: dict[int, Decimal]) -> dict:
    partes = repartir(monto, pesos)
    return {"nombre": nombre, "origen": "inspeccion de codigo, no ejecutado en TEST",
            "monto": str(monto), "participaciones": {str(k): str(v) for k, v in pesos.items()},
            "importes": {str(k): str(v) for k, v in partes.items()},
            "suma": str(sum(partes.values(), Decimal(0))), "cuadra": sum(partes.values(), Decimal(0)) == monto}


def render(informe: dict) -> str:
    return f"""<!DOCTYPE html><html lang="es"><head><meta charset="utf-8"><title>TC-M06-G113</title>
<style>body{{font-family:Segoe UI,sans-serif;margin:2rem;line-height:1.45}}table{{border-collapse:collapse;width:100%}}
th,td{{border:1px solid #ccc;padding:.45rem .6rem;text-align:left;vertical-align:top}}th{{background:#f3f3f3}}
pre{{white-space:pre-wrap}}</style></head><body>
<h1>Módulo 6 — RF-90 — TC-M06-G113</h1>
<p>Generado: {html.escape(informe['generado_en'])}. Costo compartido de 900.000: no registrado.</p>
<table><tr><th>Subcaso</th><td>TC-M06-42</td></tr>
<tr><th>Estado</th><td>{html.escape(informe['escenarios'][0]['estado'])}</td></tr>
<tr><th>Porcentaje</th><td>{informe['porcentaje_aprobacion']} %</td></tr></table>
<h2>Motivo</h2><p>{html.escape(informe['escenarios'][0]['motivo'])}</p>
<h2>Regla</h2><pre>{html.escape(informe['contrato'])}</pre>
<h2>Cálculo de la regla, sin escritura</h2><pre>{html.escape(json.dumps(informe['calculos'], ensure_ascii=False, indent=2))}</pre>
<h2>Rechazos enviados</h2><pre>{html.escape(json.dumps(informe['rechazos'], ensure_ascii=False, indent=2))}</pre>
<h2>Hallazgos</h2><ul>{''.join(f'<li>{html.escape(h)}</li>' for h in informe['hallazgos'])}</ul>
</body></html>"""


def guardar(informe: dict) -> None:
    RESULTADOS.mkdir(parents=True, exist_ok=True)
    (RESULTADOS / "resultado_ejecucion_TC-M06-G113.html").write_text(render(informe), encoding="utf-8")
    (RESULTADOS / "resumen_ejecucion_TC-M06-G113.json").write_text(json.dumps(informe, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (RESULTADOS / "evidencia_peticiones_TC-M06-G113.json").write_text(json.dumps({
        "caso": "TC-M06-G113", "generado_en": informe["generado_en"], "peticiones": informe["peticiones"],
    }, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (RESULTADOS / "analisis_hallazgos_TC-M06-G113.md").write_text(informe["analisis"], encoding="utf-8")


def main() -> int:
    inicio = time.perf_counter()
    peticiones = []
    contrato = (
        "POST /finanzas/costos reparte cuando activos_reparto trae más de un activo. "
        "El método POR_BIOMASA usa peso_kg por cabezas solo si todos los activos tienen peso. "
        "Si falta el peso de alguno, el reparto usa la cantidad de cabezas. "
        "El peso es el último pesaje o, si no hay, el peso promedio actual. No es un corte a la fecha del costo. "
        "repartir trunca cada parte a 2 decimales con ROUND_DOWN. El residuo se suma al de mayor participación; "
        "si empatan, al de menor id. La suma queda igual al monto. "
        "Los activos repetidos responden 422 REPARTO_INVALIDO antes de consultar el período. "
        "Un monto 0 o negativo responde 400 VAL_ENTRADA en el DTO. "
        "Una participación total no positiva levanta ValueError dentro del caso de uso, después de resolver el período. "
        "Ese camino no se ejecutó."
    )
    calculos = [
        escenario_codigo("900000 entre 100, 200 y 300", Decimal("900000"), {1: Decimal(100), 2: Decimal(200), 3: Decimal(300)}),
        escenario_codigo("100 entre tres partes iguales", Decimal("100"), {3: Decimal(1), 4: Decimal(1), 5: Decimal(1)}),
        escenario_codigo("100000 entre tres partes iguales", Decimal("100000"), {3: Decimal(1), 4: Decimal(1), 5: Decimal(1)}),
    ]
    informe = {
        "caso": "TC-M06-G113", "subcaso": "TC-M06-42", "rf": ["RF-90"], "ambiente": BASE_API,
        "generado_en": datetime.now(timezone.utc).isoformat(), "contrato": contrato, "calculos": calculos,
        "costos": {}, "rechazos": [], "peticiones": peticiones,
        "hallazgos": ["BLOQUEO DE PRUEBA: no hay tres activos aislados con biomasa de 100, 200 y 300 kg ni autorización para registrar 900.000 en el catálogo compartido."],
        "escenarios": [], "aprobados": 0, "rechazados": 0, "bloqueados": 1, "requiere_aclaracion": 0, "porcentaje_aprobacion": 0,
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
    informe["costos"] = resumir(costos)
    peticiones.append(evidencia("GET", "/finanzas/costos", codigo, duracion, informe["costos"]))
    ruta_aud = "/finanzas/auditoria?tipo_evento=COSTO_REGISTRADO&formato=TECNICO&tamano=1"
    codigo, auditoria, duracion = pedir("GET", ruta_aud, token=token)
    antes = auditoria.get("total_registros") if isinstance(auditoria, dict) else None
    peticiones.append(evidencia("GET", ruta_aud, codigo, duracion, {"total_registros": antes}))
    base = {"subtipo_costo": "ALIMENTO", "origen_costo": "MANO_OBRA_PROPIA", "fecha_costo": "2026-11-08", "metodo_reparto": "POR_BIOMASA"}
    for nombre, cuerpo in (
        ("monto_cero", {**base, "monto_costo": 0, "activos_reparto": [951, 943]}),
        ("monto_negativo", {**base, "monto_costo": -100, "activos_reparto": [951, 943]}),
        ("activos_repetidos", {**base, "monto_costo": 100, "activos_reparto": [951, 951]}),
    ):
        codigo_r, respuesta, duracion = pedir("POST", "/finanzas/costos", cuerpo, token)
        informe["rechazos"].append({"nombre": nombre, "http": codigo_r, "code": negocio(respuesta)})
        peticiones.append(evidencia("POST", "/finanzas/costos", codigo_r, duracion, respuesta, cuerpo))
    codigo, costos, duracion = pedir("GET", "/finanzas/costos", token=token)
    despues = resumir(costos)
    peticiones.append(evidencia("GET", "/finanzas/costos", codigo, duracion, despues))
    codigo, auditoria, duracion = pedir("GET", ruta_aud, token=token)
    audit_despues = auditoria.get("total_registros") if isinstance(auditoria, dict) else None
    peticiones.append(evidencia("GET", ruta_aud, codigo, duracion, {"total_registros": audit_despues}))
    informe["sin_persistencia"] = informe["costos"].get("total") == despues.get("total") and antes == audit_despues
    informe["escenarios"].append({
        "subcaso": "TC-M06-42", "estado": "BLOQUEADO", "registro_ejecutado": False,
        "motivo": "No se registró el costo de 900.000. Crear el reparto insertaría un costo en cada activo compartido y podría generar asientos. No hay tres activos aislados con esas biomasas.",
    })
    informe["analisis"] = (
        "# TC-M06-G113\n\nNo se usó SQL local. El reparto de 900.000 no se ejecutó en TEST.\n\n"
        "La regla del código trunca a 2 decimales y asigna el residuo al de mayor participación, con empate por el menor id.\n"
        "Aplicada a 100, 200 y 300 sobre 900.000 da 150.000, 300.000 y 450.000, y la suma cuadra.\n"
        "Aplicada a 100 entre tres partes iguales da 33.34 al id menor y 33.33 a los otros.\n"
        f"Persistencia intacta tras los rechazos: {informe['sin_persistencia']}.\n"
    )
    informe["duracion_ms"] = round((time.perf_counter() - inicio) * 1000)
    guardar(informe)
    print("TC-M06-42 BLOQUEADO", " ".join(f"{r['nombre']} {r['http']} {r['code']}" for r in informe["rechazos"]),
          f"intacto {informe['sin_persistencia']}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
