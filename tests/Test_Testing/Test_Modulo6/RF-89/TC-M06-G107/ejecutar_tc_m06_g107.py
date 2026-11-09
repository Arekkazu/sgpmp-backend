"""TC-M06-G107 contra TEST. Solo consultas.

El flujo de recepción y confirmación de precios de M07 no está publicado.
No se registran ni se confirman precios.

    python tests/Test_Testing/Test_Modulo6/RF-89/TC-M06-G107/ejecutar_tc_m06_g107.py
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
from pathlib import Path

CARPETA = Path(__file__).resolve().parent
RESULTADOS = CARPETA / "resultados"
BASE_API = "https://api.inmero.co/api-sgpmp-test"
ZONA = "America/Bogota"
SECRETOS = {"token", "access_token", "contrasena", "password", "hash_integridad", "numero_id_tributaria",
            "evidencia", "hash_evidencia", "client_secret", "secreto", "ip_origen", "json_detalle"}


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


def sesion(correo: str, contrasena: str, peticiones: list) -> str | None:
    codigo, login, duracion = pedir("POST", "/sesiones/", {"correo_electronico": correo, "contrasena": contrasena})
    peticiones.append(evidencia("POST", "/sesiones/", codigo, duracion, limpiar(login if isinstance(login, dict) else {})))
    return login.get("token") if codigo == 200 and isinstance(login, dict) else None


def caminos_relevantes(openapi: dict) -> list[dict]:
    salida = []
    for ruta, metodos in (openapi.get("paths") or {}).items():
        texto = ruta.lower()
        if "precio" in texto or texto.startswith("/integracion") or "agrofusion" in texto:
            salida.append({"ruta": ruta, "metodos": sorted(k for k in metodos if k in {"get", "post", "put", "patch", "delete"})})
    return salida


def render(informe: dict) -> str:
    esc = informe["escenarios"][0]
    return f"""<!DOCTYPE html><html lang="es"><head><meta charset="utf-8"><title>TC-M06-G107</title>
<style>body{{font-family:Segoe UI,sans-serif;margin:2rem;line-height:1.45}}table{{border-collapse:collapse;width:100%}}
th,td{{border:1px solid #ccc;padding:.45rem .6rem;text-align:left;vertical-align:top}}th{{background:#f3f3f3}}.b{{font-weight:700}}
pre{{white-space:pre-wrap;background:#fafafa;padding:.8rem}}</style></head><body>
<h1>Módulo 6 — RF-89 / M07 — TC-M06-G107</h1>
<p>Recepción y confirmación de precios externos. Generado: {html.escape(informe['generado_en'])}. Escrituras de precios: no.</p>
<table>
<tr><th>Subcaso</th><td>TC-M06-31</td></tr>
<tr><th>Estado</th><td class="b">{html.escape(esc['estado'])}</td></tr>
<tr><th>Porcentaje</th><td>{informe['porcentaje_aprobacion']} %</td></tr>
<tr><th>Precios consultados</th><td>{informe['total_precios']}</td></tr>
<tr><th>Pendientes de confirmación</th><td>{informe['pendientes']}</td></tr>
<tr><th>Confirmación ejecutada</th><td>no</td></tr>
</table>
<h2>Motivo</h2><p>{html.escape(esc['motivo'])}</p>
<h2>Contrato observado</h2><pre>{html.escape(informe['contrato'])}</pre>
<h2>Rutas publicadas</h2><pre>{html.escape(json.dumps(informe['rutas'], ensure_ascii=False, indent=2))}</pre>
<h2>Estados de los precios</h2><pre>{html.escape(json.dumps(informe['estados'], ensure_ascii=False, indent=2))}</pre>
<h2>Auditoría</h2><pre>{html.escape(json.dumps(informe['auditoria'], ensure_ascii=False, indent=2))}</pre>
<h2>Hallazgos</h2><ul>{''.join(f'<li>{html.escape(h)}</li>' for h in informe['hallazgos'])}</ul>
</body></html>"""


def guardar(informe: dict) -> None:
    RESULTADOS.mkdir(parents=True, exist_ok=True)
    (RESULTADOS / "resultado_ejecucion_TC-M06-G107.html").write_text(render(informe), encoding="utf-8")
    (RESULTADOS / "resumen_ejecucion_TC-M06-G107.json").write_text(json.dumps(informe, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (RESULTADOS / "evidencia_peticiones_TC-M06-G107.json").write_text(json.dumps({
        "caso": "TC-M06-G107", "generado_en": informe["generado_en"], "peticiones": informe["peticiones"],
    }, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def main() -> int:
    inicio = time.perf_counter()
    peticiones = []
    contrato = (
        "M07 publica la consulta AAEF y la administración de clientes, contratos y su propia auditoría. "
        "Ninguna ruta de /integracion recibe ni confirma precios. "
        "M06 solo publica GET y POST /finanzas/precios. El POST guarda el origen MANUAL y el estado PROGRAMADO o ACTIVO. "
        "La base declara el origen API_M07 y el comentario de la columna menciona PENDIENTE_CONFIRMACION, "
        "pero el enumerado de estado del precio solo admite ACTIVO, PROGRAMADO, VENCIDO y SUPERADO. "
        "No hay caso de uso que asigne API_M07 ni un endpoint para confirmar un precio externo. "
        "El selector usa la fuente y las fechas. No conoce un estado pendiente. "
        "DESVIACION_PRECIO_REQUIERE_CONFIRMACION es la confirmación de una desviación de un precio manual, no la aprobación de M07. "
        "La auditoría de precios contempla PRECIO_REGISTRADO, PRECIO_MARCADO_REEMPLAZADO y PRECIO_REFERENCIA_VENCIDO. "
        "La auditoría de M07 no tiene eventos de recepción ni de confirmación de precios."
    )
    motivo = (
        "No se puede ejecutar la recepción ni la confirmación. El contrato publicado no define el endpoint, "
        "el estado persistible PENDIENTE_CONFIRMACION ni el evento de auditoría de ese flujo. "
        "GET /finanzas/precios tampoco informa el origen del registro. "
        "Confirmar o insertar un precio en el catálogo compartido cambiaría las valoraciones, y no hay un precio externo aislado."
    )
    informe = {
        "caso": "TC-M06-G107", "subcaso": "TC-M06-31", "rf": ["RF-89", "M07"], "ambiente": BASE_API,
        "generado_en": datetime.now(timezone.utc).isoformat(), "contrato": contrato,
        "escritura_ejecutada": False, "total_precios": None, "pendientes": None, "estados": {},
        "campos_respuesta": [], "rutas": [], "auditoria": {},
        "escenarios": [{"subcaso": "TC-M06-31", "estado": "REQUIERE ACLARACION", "motivo": motivo,
                        "recepcion_ejecutada": False, "confirmacion_ejecutada": False}],
        "peticiones": peticiones,
        "hallazgos": [
            "QUESTION-M06-G79-01: el comentario de precios_mercado describe la recepción por API_M07 en estado PENDIENTE_CONFIRMACION, pero ese valor no existe en el enumerado de estado y ningún caso de uso lo utiliza.",
            "QUESTION-M06-G79-02: M07 publicado intercambia el documento AAEF. No publica la entrega ni la confirmación de precios.",
            "BLOQUEO DE PRUEBA: no hay un precio externo aislado ni un endpoint real sobre el cual completar TC-M06-31 sin modificar el catálogo compartido.",
        ],
        "aprobados": 0, "rechazados": 0, "bloqueados": 0, "requiere_aclaracion": 1, "porcentaje_aprobacion": 0,
    }
    contador_correo, contador_clave = os.environ.get("QA_CORREO"), os.environ.get("QA_CONTRASENA")
    admin_correo, admin_clave = os.environ.get("QA_ADMIN_CORREO"), os.environ.get("QA_ADMIN_CONTRASENA")
    if not all((contador_correo, contador_clave, admin_correo, admin_clave)):
        raise SystemExit("Defina QA_CORREO, QA_CONTRASENA, QA_ADMIN_CORREO y QA_ADMIN_CONTRASENA.")

    codigo, openapi, duracion = pedir("GET", "/openapi.json")
    rutas = caminos_relevantes(openapi) if codigo == 200 and isinstance(openapi, dict) else []
    informe["rutas"] = rutas
    rutas_precio = [r for r in rutas if "precio" in r["ruta"].lower()]
    peticiones.append(evidencia("GET", "/openapi.json", codigo, duracion, {"rutas_relevantes": len(rutas), "rutas_precio": rutas_precio}))

    token = sesion(contador_correo, contador_clave, peticiones)
    if not token:
        informe["escenarios"][0]["motivo"] = "No fue posible autenticar al Contador."
        guardar(informe)
        print("REQUIERE ACLARACION")
        return 2
    codigo, precios, duracion = pedir("GET", "/finanzas/precios", token=token)
    lista = precios if isinstance(precios, list) else []
    informe["total_precios"] = len(lista)
    informe["campos_respuesta"] = sorted(lista[0].keys()) if lista and isinstance(lista[0], dict) else []
    estados = Counter(p.get("estado") for p in lista if isinstance(p, dict))
    informe["estados"] = dict(estados)
    informe["pendientes"] = estados.get("PENDIENTE_CONFIRMACION", 0)
    informe["con_origen"] = sum(1 for p in lista if isinstance(p, dict) and p.get("origen_registro"))
    peticiones.append(evidencia("GET", "/finanzas/precios", codigo, duracion, {
        "total": len(lista), "estados": dict(estados), "campos": informe["campos_respuesta"],
        "pendientes": informe["pendientes"], "con_origen": informe["con_origen"],
    }))
    for tipo in ("PRECIO_REGISTRADO", "PRECIO_MARCADO_REEMPLAZADO", "PRECIO_REFERENCIA_VENCIDO"):
        ruta = f"/finanzas/auditoria?tipo_evento={tipo}&formato=TECNICO&tamano=1"
        codigo_aud, auditoria, duracion = pedir("GET", ruta, token=token)
        total = auditoria.get("total_registros") if isinstance(auditoria, dict) else None
        informe["auditoria"][tipo] = {"http": codigo_aud, "total": total}
        peticiones.append(evidencia("GET", ruta, codigo_aud, duracion, {"total_registros": total}))

    token_admin = sesion(admin_correo, admin_clave, peticiones)
    if token_admin:
        ruta = "/integracion/auditoria?pagina=1&tamano=1"
        codigo_m07, auditoria_m07, duracion = pedir("GET", ruta, token=token_admin)
        total = auditoria_m07.get("total") if isinstance(auditoria_m07, dict) else None
        informe["auditoria"]["integracion"] = {"http": codigo_m07, "total": total}
        peticiones.append(evidencia("GET", ruta, codigo_m07, duracion, {"total": total}))
    informe["duracion_ms"] = round((time.perf_counter() - inicio) * 1000)
    guardar(informe)
    print(f"TC-M06-31 REQUIERE ACLARACION precios {informe['total_precios']} pendientes {informe['pendientes']} estados {informe['estados']}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
