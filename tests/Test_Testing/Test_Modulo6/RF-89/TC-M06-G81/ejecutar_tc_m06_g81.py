"""TC-M06-G81 contra TEST. Solo consultas.

El aviso diario no tiene endpoint. No se registran precios, no se cambian
fechas y no se dispara el proceso sobre el catálogo compartido.

    python tests/Test_Testing/Test_Modulo6/RF-89/TC-M06-G81/ejecutar_tc_m06_g81.py
"""
from __future__ import annotations

import html
import json
import os
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

CARPETA = Path(__file__).resolve().parent
RESULTADOS = CARPETA / "resultados"
BASE_API = "https://api.inmero.co/api-sgpmp-test"
ZONA = "America/Bogota"
SECRETOS = {"token", "access_token", "contrasena", "password", "hash_integridad", "numero_id_tributaria", "evidencia", "hash_evidencia"}


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
        return [limpiar(v, profundidad + 1) for v in valor[:40]]
    if isinstance(valor, str) and len(valor) > 240:
        return valor[:240]
    return valor


def evidencia(metodo, ruta, codigo, duracion, respuesta) -> dict:
    return {"metodo": metodo, "consulta": ruta, "codigo": codigo, "duracion_ms": duracion,
            "escritura": False, "en": datetime.now(timezone.utc).isoformat(), "respuesta": limpiar(respuesta)}


def dias(vencimiento: str | None, hoy: date) -> int | None:
    if not vencimiento:
        return None
    return (date.fromisoformat(vencimiento[:10]) - hoy).days


def ficha(precio: dict, hoy: date) -> dict:
    faltan = dias(precio.get("fecha_vencimiento"), hoy)
    return {
        "id": precio.get("id_precio_mercado"),
        "id_especie": precio.get("id_especie"),
        "categoria": precio.get("categoria"),
        "fuente": precio.get("fuente"),
        "precio_unitario": precio.get("precio_unitario"),
        "fecha_vigencia": precio.get("fecha_vigencia"),
        "fecha_vencimiento": precio.get("fecha_vencimiento"),
        "estado": precio.get("estado"),
        "dias_para_vencer": faltan,
    }


def plazos_que_avisan(ventana: int | None) -> list[int]:
    if ventana is None:
        return []
    marcas = {ventana, 7, 0}
    if ventana > 15:
        marcas.add(15)
    return sorted(marcas, reverse=True)


def render(informe: dict) -> str:
    esc = informe["escenarios"][0]
    return f"""<!DOCTYPE html><html lang="es"><head><meta charset="utf-8"><title>TC-M06-G81</title>
<style>body{{font-family:Segoe UI,sans-serif;margin:2rem;line-height:1.45}}table{{border-collapse:collapse;width:100%}}
th,td{{border:1px solid #ccc;padding:.45rem .6rem;text-align:left;vertical-align:top}}th{{background:#f3f3f3}}.b{{font-weight:700}}
pre{{white-space:pre-wrap;background:#fafafa;padding:.8rem}}</style></head><body>
<h1>Módulo 6 — RF-89 — TC-M06-G81</h1>
<p>Alertas previas al vencimiento. Generado: {html.escape(informe['generado_en'])}. Escrituras: no.</p>
<table>
<tr><th>Subcaso</th><td>TC-M06-34</td></tr>
<tr><th>Estado</th><td class="b">{html.escape(esc['estado'])}</td></tr>
<tr><th>Porcentaje</th><td>{informe['porcentaje_aprobacion']} %</td></tr>
<tr><th>Plazo configurado</th><td>{html.escape(str(informe['dias_alerta']))} días</td></tr>
<tr><th>Marcas que el código avisa</th><td>{html.escape(str(informe['marcas']))}</td></tr>
<tr><th>Precios en esas marcas</th><td>{informe['precios_en_marca']}</td></tr>
<tr><th>Avisos de precio en la bandeja</th><td>{informe['avisos_precio']}</td></tr>
</table>
<h2>Motivo</h2><p>{html.escape(esc['motivo'])}</p>
<h2>Contrato observado en el código</h2><pre>{html.escape(informe['contrato'])}</pre>
<h2>Precios</h2><pre>{html.escape(json.dumps(informe['precios'], ensure_ascii=False, indent=2))}</pre>
<h2>Avisos encontrados</h2><pre>{html.escape(json.dumps(informe['avisos'], ensure_ascii=False, indent=2))}</pre>
<h2>Hallazgos</h2><ul>{''.join(f'<li>{html.escape(h)}</li>' for h in informe['hallazgos'])}</ul>
</body></html>"""


def guardar(informe: dict) -> None:
    RESULTADOS.mkdir(parents=True, exist_ok=True)
    (RESULTADOS / "resultado_ejecucion_TC-M06-G81.html").write_text(render(informe), encoding="utf-8")
    (RESULTADOS / "resumen_ejecucion_TC-M06-G81.json").write_text(json.dumps(informe, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (RESULTADOS / "evidencia_peticiones_TC-M06-G81.json").write_text(json.dumps({
        "caso": "TC-M06-G81", "generado_en": informe["generado_en"], "peticiones": informe["peticiones"],
    }, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def main() -> int:
    inicio = time.perf_counter()
    peticiones = []
    hoy = datetime.now(timezone.utc).date()
    contrato = (
        "No hay endpoint para disparar el aviso. main.py ejecuta _procesar_m06_periodicamente cada 60 segundos. "
        "El aviso de precios corre una vez por día UTC mientras el proceso sigue vivo; la marca ultimo_diario está en memoria. "
        "AlertarVencimientoPreciosUseCase lee dias_alerta_vencimiento_precio, un solo valor 7, 15 o 30 guardado en "
        "modulo6.configuraciones_contables. El valor inicial es 30. "
        "Busca vencimientos entre ayer y hoy más esa ventana. Avisa si los días restantes son la ventana configurada, "
        "7, 0 y, solo cuando la ventana es mayor que 15, también 15. "
        "Un vencimiento ya pasado solo se avisa si cayó dentro de ese rango y la especie no tiene otro precio vigente. "
        "El mensaje va a todos los usuarios con rol Contador, tipo ALERTA_FINANCIERA_NIC41, tabla modulo1.notificaciones. "
        "Ese mismo tipo se usa al registrar un precio activo. No hay un evento de auditoría financiera propio del aviso. "
        "a_contadores no llama verificar_anti_spam y la tabla no tiene una clave única por precio, plazo y destinatario. "
        "Un reinicio del proceso el mismo día UTC puede volver a notificar. La bandeja se consulta con GET /notificaciones "
        "y cada usuario solo ve la suya."
    )
    motivo = (
        "No se ejecutó el proceso. No existe un endpoint público, no hay precios aislados en las marcas de 7, 15 y 30 días "
        "y repetir el proceso sobre el catálogo compartido podría crear avisos en las cuentas reales de los contadores. "
        "La bandeja consultada no demuestra la generación de esas tres alertas ni la ausencia de duplicados."
    )
    informe = {
        "caso": "TC-M06-G81", "subcaso": "TC-M06-34", "rf": ["RF-89"], "ambiente": BASE_API,
        "generado_en": datetime.now(timezone.utc).isoformat(), "hoy_utc": hoy.isoformat(), "contrato": contrato,
        "proceso_ejecutado": False, "dias_alerta": None, "marcas": [], "precios": [], "precios_en_marca": 0,
        "avisos": [], "avisos_precio": 0, "auditoria_precio_vencido": None,
        "escenarios": [{"subcaso": "TC-M06-34", "escenario": "Alertas a 7, 15 y 30 días y prevención de duplicados",
                        "estado": "BLOQUEADO", "motivo": motivo, "proceso_ejecutado": False}],
        "peticiones": peticiones,
        "hallazgos": [
            "QUESTION-M06-G81-01: el caso espera plazos configurados de 7, 15 y 30 días a la vez. El sistema guarda un solo plazo y solo incluye 15 cuando ese plazo es mayor que 15.",
            "BLOQUEO DE PRUEBA: no hay datos aislados ni un endpoint para ejecutar el aviso sin notificar sobre el catálogo compartido.",
        ],
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
        print("BLOQUEADO")
        return 2

    codigo, config, duracion = pedir("GET", "/finanzas/configuracion", token=token)
    general = config.get("general") if isinstance(config, dict) else {}
    ventana = general.get("dias_alerta_vencimiento_precio") if isinstance(general, dict) else None
    informe["dias_alerta"] = ventana
    informe["marcas"] = plazos_que_avisan(ventana if isinstance(ventana, int) else None)
    peticiones.append(evidencia("GET", "/finanzas/configuracion", codigo, duracion, {"dias_alerta_vencimiento_precio": ventana}))

    codigo, precios, duracion = pedir("GET", "/finanzas/precios", token=token)
    fichas = [ficha(p, hoy) for p in precios if isinstance(p, dict)] if isinstance(precios, list) else []
    informe["precios"] = fichas
    informe["por_dias"] = dict(Counter("sin_vencimiento" if p["dias_para_vencer"] is None else p["dias_para_vencer"] for p in fichas))
    informe["en_7"] = [p for p in fichas if p["dias_para_vencer"] == 7]
    informe["en_15"] = [p for p in fichas if p["dias_para_vencer"] == 15]
    informe["en_30"] = [p for p in fichas if p["dias_para_vencer"] == 30]
    informe["en_marca"] = [p for p in fichas if p["dias_para_vencer"] in informe["marcas"]]
    informe["precios_en_marca"] = len(informe["en_marca"])
    peticiones.append(evidencia("GET", "/finanzas/precios", codigo, duracion, {
        "total": len(fichas), "en_7": len(informe["en_7"]), "en_15": len(informe["en_15"]),
        "en_30": len(informe["en_30"]), "en_marca": informe["precios_en_marca"],
    }))

    avisos = []
    total_bandeja = None
    pagina = 1
    while pagina <= 20:
        ruta = f"/notificaciones?pagina={pagina}&tamano=50"
        codigo_n, bandeja, duracion = pedir("GET", ruta, token=token)
        items = bandeja.get("items") if isinstance(bandeja, dict) else []
        total_bandeja = bandeja.get("total") if isinstance(bandeja, dict) else None
        coincidencias = []
        for item in items or []:
            texto = str(item.get("mensaje") or "")
            if "precio" in texto.lower() or "vence" in texto.lower():
                aviso = {"id_notificacion": item.get("id_notificacion"), "id_evento": item.get("id_evento"),
                         "fecha_envio": item.get("fecha_envio"), "es_leido": item.get("es_leido"), "mensaje": texto[:240]}
                avisos.append(aviso)
                coincidencias.append(aviso["id_notificacion"])
        peticiones.append(evidencia("GET", ruta, codigo_n, duracion, {"total": total_bandeja, "coincidencias": coincidencias}))
        if not isinstance(bandeja, dict) or codigo_n != 200 or pagina * 50 >= (total_bandeja or 0) or not items:
            break
        pagina += 1
    informe["avisos"] = avisos
    informe["avisos_precio"] = len(avisos)
    informe["total_bandeja"] = total_bandeja
    informe["mensajes_repetidos"] = [m for m, n in Counter(a["mensaje"] for a in avisos).items() if n > 1]

    ruta = "/finanzas/auditoria?tipo_evento=PRECIO_REFERENCIA_VENCIDO&formato=TECNICO&tamano=1"
    codigo_a, auditoria, duracion = pedir("GET", ruta, token=token)
    informe["auditoria_precio_vencido"] = auditoria.get("total_registros") if isinstance(auditoria, dict) else None
    peticiones.append(evidencia("GET", ruta, codigo_a, duracion, {"total_registros": informe["auditoria_precio_vencido"]}))
    informe["duracion_ms"] = round((time.perf_counter() - inicio) * 1000)
    guardar(informe)
    print(
        f"TC-M06-34 BLOQUEADO ventana {ventana} marcas {informe['marcas']} "
        f"en_7 {len(informe['en_7'])} en_15 {len(informe['en_15'])} en_30 {len(informe['en_30'])} avisos {len(avisos)}"
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
