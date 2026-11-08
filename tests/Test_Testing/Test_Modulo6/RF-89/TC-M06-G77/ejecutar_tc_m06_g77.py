"""TC-M06-G77 contra TEST. Solo consultas.

Compara el precio que devuelve la simulación con la prioridad
MERCADO_ACTIVO > UPRA > ESTIMADA y, dentro de cada fuente, con la vigencia
más reciente. No registra precios.

    python tests/Test_Testing/Test_Modulo6/RF-89/TC-M06-G77/ejecutar_tc_m06_g77.py
"""
from __future__ import annotations

import html
import json
import os
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

CARPETA = Path(__file__).resolve().parent
RESULTADOS = CARPETA / "resultados"
BASE_API = "https://api.inmero.co/api-sgpmp-test"
ZONA = "America/Bogota"
HOY = datetime.now(timezone(timedelta(hours=-5))).date()
PRIORIDAD = ("MERCADO_ACTIVO", "UPRA", "ESTIMADA")
SECRETOS = {"token", "access_token", "contrasena", "password", "hash_integridad", "numero_id_tributaria", "evidencia", "identificador"}


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
        return {k: ({"omitido": True} if k in SECRETOS else limpiar(v, profundidad + 1)) for k, v in valor.items()}
    if isinstance(valor, list):
        return [limpiar(v, profundidad + 1) for v in valor[:40]]
    if isinstance(valor, str) and len(valor) > 220:
        return valor[:220]
    return valor


def evidencia(metodo, ruta, codigo, duracion, respuesta) -> dict:
    return {"metodo": metodo, "consulta": ruta, "codigo": codigo, "duracion_ms": duracion,
            "en": datetime.now(timezone.utc).isoformat(), "respuesta": limpiar(respuesta)}


def fecha(valor) -> date | None:
    if isinstance(valor, str) and len(valor) >= 10:
        return date.fromisoformat(valor[:10])
    return None


def aplicable(precio: dict, dia: date) -> bool:
    vigencia = fecha(precio.get("fecha_vigencia"))
    vencimiento = fecha(precio.get("fecha_vencimiento"))
    if vigencia is None or vigencia > dia:
        return False
    return vencimiento is None or vencimiento >= dia


def ficha(precio: dict) -> dict:
    return {
        "id": precio.get("id_precio_mercado"),
        "fuente": precio.get("fuente"),
        "precio_unitario": precio.get("precio_unitario"),
        "fecha_vigencia": precio.get("fecha_vigencia"),
        "fecha_vencimiento": precio.get("fecha_vencimiento"),
        "estado": precio.get("estado"),
        "es_aplicado": precio.get("es_aplicado"),
        "categoria": precio.get("categoria"),
    }


def esperado_por_diseno(precios: list[dict], dia: date) -> dict | None:
    validos = [p for p in precios if aplicable(p, dia)]
    for fuente in PRIORIDAD:
        mismos = [p for p in validos if p.get("fuente") == fuente]
        if not mismos:
            continue
        vigencia = max(fecha(p.get("fecha_vigencia")) for p in mismos)
        return {"fuente": fuente, "fecha_vigencia": vigencia.isoformat(), "candidatos": [ficha(p) for p in mismos if fecha(p.get("fecha_vigencia")) == vigencia]}
    return None


def subcaso(codigo: str, objetivo: str) -> dict:
    return {"subcaso": codigo, "objetivo": objetivo, "post_ejecutado": False, "estado": "BLOQUEADO", "motivo": "", "comparacion": {}}


def render(informe: dict) -> str:
    filas = "".join(
        f"<tr><td>{html.escape(e['subcaso'])}</td><td class='b'>{html.escape(e['estado'])}</td><td>{html.escape(e['motivo'])}</td></tr>"
        for e in informe["escenarios"]
    )
    hallazgos = "".join(f"<li>{html.escape(h)}</li>" for h in informe["hallazgos"])
    return f"""<!DOCTYPE html><html lang="es"><head><meta charset="utf-8"><title>TC-M06-G77</title>
<style>body{{font-family:Segoe UI,sans-serif;margin:2rem;line-height:1.45}}table{{border-collapse:collapse;width:100%}}
th,td{{border:1px solid #ccc;padding:.45rem .6rem;text-align:left;vertical-align:top}}th{{background:#f3f3f3}}.b{{font-weight:700}}
pre{{white-space:pre-wrap;background:#fafafa;padding:.8rem}}</style></head><body>
<h1>Módulo 6 — RF-89 — TC-M06-G77</h1>
<p>Selección de precio por fuente y vigencia. Fecha de consulta: {html.escape(informe['fecha'])}. Generado: {html.escape(informe['generado_en'])}.</p>
<table>
<tr><th>Aprobados</th><td>{informe['aprobados']}</td></tr>
<tr><th>Rechazados</th><td>{informe['rechazados']}</td></tr>
<tr><th>Bloqueados</th><td>{informe['bloqueados']}</td></tr>
<tr><th>Porcentaje</th><td class="b">{informe['porcentaje_aprobacion']} %</td></tr>
</table>
<h2>Subcasos</h2><table><tr><th>Subcaso</th><th>Estado</th><th>Motivo</th></tr>{filas}</table>
<h2>Inventario</h2><pre>{html.escape(json.dumps(informe['inventario'], ensure_ascii=False, indent=2))}</pre>
<h2>Comparaciones</h2><pre>{html.escape(json.dumps([e['comparacion'] for e in informe['escenarios']], ensure_ascii=False, indent=2))}</pre>
<h2>Hallazgos</h2><ul>{hallazgos}</ul>
</body></html>"""


def guardar(informe: dict) -> None:
    RESULTADOS.mkdir(parents=True, exist_ok=True)
    (RESULTADOS / "resultado_ejecucion_TC-M06-G77.html").write_text(render(informe), encoding="utf-8")
    (RESULTADOS / "resumen_ejecucion_TC-M06-G77.json").write_text(json.dumps(informe, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (RESULTADOS / "evidencia_peticiones_TC-M06-G77.json").write_text(json.dumps({
        "caso": "TC-M06-G77", "generado_en": informe["generado_en"], "peticiones": informe["peticiones"],
    }, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def main() -> int:
    inicio = time.perf_counter()
    peticiones = []
    escenarios = [
        subcaso("TC-M06-27", "Seleccionar MERCADO_ACTIVO antes que UPRA y ESTIMADA."),
        subcaso("TC-M06-28", "Dentro de una fuente, seleccionar la vigencia más reciente."),
    ]
    hallazgos = [
        "La prueba unitaria test_prioridad_de_fuente_prevalece_sobre_fecha_y_vencimiento cubre la regla en memoria. No sustituye esta consulta al API.",
        "Cuando dos precios de la misma fuente comparten la fecha de vigencia, el código desempata por el identificador más alto. El diseño del caso no define ese empate.",
    ]
    informe = {
        "caso": "TC-M06-G77", "rf": "RF-89", "ambiente": BASE_API, "fecha": HOY.isoformat(),
        "generado_en": datetime.now(timezone.utc).isoformat(), "escrituras": False,
        "inventario": {}, "escenarios": escenarios, "peticiones": peticiones, "hallazgos": hallazgos,
        "aprobados": 0, "rechazados": 0, "bloqueados": 2, "porcentaje_aprobacion": 0,
    }
    correo, contrasena = os.environ.get("QA_CORREO"), os.environ.get("QA_CONTRASENA")
    if not correo or not contrasena:
        raise SystemExit("Defina QA_CORREO y QA_CONTRASENA.")
    codigo, login, duracion = pedir("POST", "/sesiones/", {"correo_electronico": correo, "contrasena": contrasena})
    token = login.get("token") if isinstance(login, dict) else None
    peticiones.append(evidencia("POST", "/sesiones/", codigo, duracion, limpiar(login if isinstance(login, dict) else {})))
    if codigo != 200 or not token:
        for esc in escenarios:
            esc["motivo"] = "No fue posible autenticar al Contador."
        guardar(informe)
        print("BLOQUEADO")
        return 2

    codigo, precios, duracion = pedir("GET", "/finanzas/precios", token=token)
    lista = precios if isinstance(precios, list) else []
    grupos: dict[str, list] = {}
    for precio in lista:
        if isinstance(precio, dict):
            grupos.setdefault(str(precio.get("id_especie")), []).append(precio)
    inventario = {}
    for especie, items in grupos.items():
        inventario[especie] = {
            "fuentes": sorted({p.get("fuente") for p in items}),
            "aplicables": [ficha(p) for p in items if aplicable(p, HOY)],
            "no_aplicables": [ficha(p) for p in items if not aplicable(p, HOY)],
        }
    informe["inventario"] = inventario
    peticiones.append(evidencia("GET", "/finanzas/precios", codigo, duracion, {"total": len(lista), "especies": list(inventario)}))

    codigo, activos, duracion = pedir("GET", "/finanzas/activos", token=token)
    por_especie_activo = {}
    if isinstance(activos, list):
        for activo in activos:
            if isinstance(activo, dict) and activo.get("estado") == "ACTIVO":
                por_especie_activo.setdefault(str(activo.get("id_especie")), activo.get("id_activo_biologico"))
    peticiones.append(evidencia("GET", "/finanzas/activos", codigo, duracion, {"reconocidos": len(activos) if isinstance(activos, list) else None}))

    def simular(especie: str) -> dict:
        activo = por_especie_activo.get(especie)
        if activo is None:
            return {"id_especie": int(especie), "activo": None, "http": None}
        codigo_sim, sim, duracion_sim = pedir("GET", f"/finanzas/activos/{activo}/simulacion", token=token)
        precio = sim.get("precio") if isinstance(sim, dict) and isinstance(sim.get("precio"), dict) else {}
        resultado = {
            "id_especie": int(especie), "activo": activo, "http": codigo_sim,
            "es_valido": sim.get("es_valido") if isinstance(sim, dict) else None,
            "motivo": sim.get("motivo") if isinstance(sim, dict) else None,
            "id_precio": precio.get("id_precio_mercado"), "fuente": precio.get("fuente"),
            "precio_unitario": precio.get("precio_unitario"), "fecha_vigencia": precio.get("fecha_vigencia"),
        }
        peticiones.append(evidencia("GET", f"/finanzas/activos/{activo}/simulacion", codigo_sim, duracion_sim, resultado))
        return resultado

    especie_prioridad = next((
        especie for especie, datos in inventario.items()
        if len({p["fuente"] for p in datos["aplicables"]}) >= 2 and por_especie_activo.get(especie)
    ), None)
    if especie_prioridad is None:
        escenarios[0]["motivo"] = "Ninguna especie visible tiene dos fuentes aplicables al mismo tiempo y un activo para simular."
    else:
        datos = inventario[especie_prioridad]
        designado = esperado_por_diseno(grupos[especie_prioridad], HOY)
        real = simular(especie_prioridad)
        fuentes = sorted({p["fuente"] for p in datos["aplicables"]})
        escenarios[0]["comparacion"] = {"especie": int(especie_prioridad), "fuentes_aplicables": fuentes, "esperado": designado, "seleccionado": real}
        if real.get("http") == 200 and real.get("fuente") == (designado or {}).get("fuente") and real.get("id_precio") in {c["id"] for c in designado["candidatos"]}:
            escenarios[0]["estado"] = "APROBADO"
            escenarios[0]["motivo"] = (
                f"La simulación del activo {real['activo']} usó el precio {real['id_precio']} de {real['fuente']}. "
                f"Las fuentes aplicables eran {', '.join(fuentes)}. UPRA no tiene un precio aplicable simultáneo en esta especie."
                if "UPRA" not in fuentes else
                f"La simulación del activo {real['activo']} usó el precio {real['id_precio']} de {real['fuente']}."
            )
        elif real.get("http") == 200 and real.get("fuente"):
            escenarios[0]["estado"] = "RECHAZADO"
            escenarios[0]["motivo"] = f"La simulación seleccionó {real.get('fuente')} {real.get('id_precio')} y el diseño indica {designado}."
        else:
            escenarios[0]["motivo"] = "La simulación no devolvió el precio seleccionado."

    especie_fecha = next((
        especie for especie, items in grupos.items()
        if any(
            len([p for p in items if p.get("fuente") == fuente and aplicable(p, HOY)]) >= 2
            and len({fecha(p.get("fecha_vigencia")) for p in items if p.get("fuente") == fuente and aplicable(p, HOY)}) >= 2
            for fuente in PRIORIDAD
        ) and por_especie_activo.get(especie)
    ), None)
    if especie_fecha is None:
        escenarios[1]["motivo"] = "Ninguna especie visible tiene dos precios aplicables de la misma fuente con vigencias distintas y un activo para simular."
    else:
        items = grupos[especie_fecha]
        fuente = next(fuente for fuente in PRIORIDAD if len({fecha(p.get("fecha_vigencia")) for p in items if p.get("fuente") == fuente and aplicable(p, HOY)}) >= 2)
        mismos = [p for p in items if p.get("fuente") == fuente and aplicable(p, HOY)]
        reciente = max(fecha(p.get("fecha_vigencia")) for p in mismos)
        esperados = [ficha(p) for p in mismos if fecha(p.get("fecha_vigencia")) == reciente]
        real = simular(especie_fecha) if escenarios[0]["comparacion"].get("especie") != int(especie_fecha) else escenarios[0]["comparacion"]["seleccionado"]
        if escenarios[0]["comparacion"].get("especie") == int(especie_fecha):
            real = escenarios[0]["comparacion"]["seleccionado"]
        escenarios[1]["comparacion"] = {"especie": int(especie_fecha), "fuente": fuente, "candidatos": [ficha(p) for p in mismos], "esperado": esperados, "seleccionado": real}
        if real.get("http") == 200 and real.get("fuente") == fuente and real.get("id_precio") in {p["id"] for p in esperados}:
            escenarios[1]["estado"] = "APROBADO"
            escenarios[1]["motivo"] = f"La simulación usó el precio {real['id_precio']}, con vigencia {real.get('fecha_vigencia')}, la más reciente de {fuente}."
        elif real.get("http") == 200 and real.get("fuente"):
            escenarios[1]["estado"] = "RECHAZADO"
            escenarios[1]["motivo"] = f"La simulación usó el precio {real.get('id_precio')} y la vigencia más reciente corresponde a {[p['id'] for p in esperados]}."
        else:
            escenarios[1]["motivo"] = "La simulación no devolvió el precio seleccionado."

    informe["aprobados"] = sum(e["estado"] == "APROBADO" for e in escenarios)
    informe["rechazados"] = sum(e["estado"] == "RECHAZADO" for e in escenarios)
    informe["bloqueados"] = sum(e["estado"] == "BLOQUEADO" for e in escenarios)
    informe["porcentaje_aprobacion"] = round(informe["aprobados"] / 2 * 100)
    informe["duracion_ms"] = round((time.perf_counter() - inicio) * 1000)
    guardar(informe)
    print(" ".join(f"{e['subcaso']} {e['estado']}" for e in escenarios) + f" | PCT {informe['porcentaje_aprobacion']}")
    return 0 if informe["aprobados"] == 2 else 2


if __name__ == "__main__":
    raise SystemExit(main())
