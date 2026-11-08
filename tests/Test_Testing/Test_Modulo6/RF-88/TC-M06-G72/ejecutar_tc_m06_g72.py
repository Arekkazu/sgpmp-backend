"""TC-M06-G72 contra TEST.

Lee el activo 10. Solo confirma el reconocimiento si está en BAJA, no tiene
reconocimiento y el primer bloqueo es ACTIVO_NO_VALORABLE sin el bloqueo que
sí se audita. El resultado esperado es HTTP 422.

    python tests/Test_Testing/Test_Modulo6/RF-88/TC-M06-G72/ejecutar_tc_m06_g72.py
"""
from __future__ import annotations

import html
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

CARPETA = Path(__file__).resolve().parent
RESULTADOS = CARPETA / "resultados"
BASE_API = "https://api.inmero.co/api-sgpmp-test"
ACTIVO = 10
SECRETOS = {"token", "access_token", "contrasena", "password", "hash_integridad", "numero_id_tributaria", "finca", "identificador"}


def pedir(metodo: str, ruta: str, cuerpo: dict | None = None, token: str | None = None):
    datos = None if cuerpo is None else json.dumps(cuerpo).encode("utf-8")
    headers = {"Accept": "application/json"}
    if cuerpo is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(BASE_API + ruta, data=datos, headers=headers, method=metodo)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = {"message": raw[:240]}
        return exc.code, parsed


def limpiar(valor, profundidad: int = 0):
    if profundidad > 5:
        return "..."
    if isinstance(valor, dict):
        return {k: limpiar(v, profundidad + 1) for k, v in valor.items() if k not in SECRETOS}
    if isinstance(valor, list):
        return [limpiar(v, profundidad + 1) for v in valor[:20]]
    if isinstance(valor, str) and len(valor) > 240:
        return valor[:240]
    return valor


def autenticar() -> tuple[int, str | None, dict]:
    correo = os.environ.get("QA_CORREO")
    contrasena = os.environ.get("QA_CONTRASENA")
    if not correo or not contrasena:
        raise SystemExit("Defina QA_CORREO y QA_CONTRASENA en el entorno. No las escriba en el archivo.")
    codigo, payload = pedir("POST", "/sesiones/", {"correo_electronico": correo, "contrasena": contrasena})
    token = payload.get("token") if isinstance(payload, dict) else None
    publico = limpiar(payload if isinstance(payload, dict) else {})
    return codigo, token, publico if isinstance(publico, dict) else {}


def foto(token: str) -> tuple[list[dict], dict]:
    evidencias = []
    rutas = {
        "biologico": f"/activos-biologicos/{ACTIVO}",
        "financiero": f"/finanzas/activos/{ACTIVO}",
        "propuesta": f"/finanzas/reconocimientos/propuestas/{ACTIVO}",
        "auditoria": f"/finanzas/auditoria?id_activo_biologico={ACTIVO}&formato=TECNICO&tamano=100",
    }
    datos = {}
    for nombre, ruta in rutas.items():
        codigo, payload = pedir("GET", ruta, token=token)
        evidencias.append({"metodo": "GET", "consulta": ruta, "codigo": codigo, "lectura": True, "escritura": False, "respuesta": resumir(nombre, codigo, payload)})
        datos[nombre] = payload if codigo == 200 else {"http": codigo, **(limpiar(payload) if isinstance(payload, dict) else {})}
    return evidencias, resumir_foto(datos)


def resumir(nombre: str, codigo: int, payload) -> dict:
    if codigo != 200 or not isinstance(payload, dict):
        return limpiar(payload) if isinstance(payload, dict) else {"codigo": codigo}
    if nombre == "biologico":
        return {"estado": payload.get("nombre_estado"), "id_especie": payload.get("id_especie")}
    if nombre == "financiero":
        return {
            "reconocimientos": len(payload.get("reconocimientos") or []),
            "valoracion_costo": bool(payload.get("valoracion_costo")),
            "lineas": len(payload.get("lineas") or []),
        }
    if nombre == "propuesta":
        bloqueos = payload.get("bloqueos") or []
        return {
            "estado": payload.get("estado"),
            "id_especie": payload.get("id_especie"),
            "es_confirmable": payload.get("es_confirmable"),
            "indicador_valoracion": payload.get("indicador_valoracion"),
            "bloqueos": [b.get("codigo") for b in bloqueos if isinstance(b, dict)],
        }
    return {"total_registros": payload.get("total_registros")}


def resumir_foto(datos: dict) -> dict:
    bio = datos.get("biologico") if isinstance(datos.get("biologico"), dict) else {}
    fin = datos.get("financiero") if isinstance(datos.get("financiero"), dict) else {}
    prop = datos.get("propuesta") if isinstance(datos.get("propuesta"), dict) else {}
    aud = datos.get("auditoria") if isinstance(datos.get("auditoria"), dict) else {}
    bloqueos = [b.get("codigo") for b in (prop.get("bloqueos") or []) if isinstance(b, dict)]
    if "bloqueos" in prop and prop.get("bloqueos") and isinstance(prop["bloqueos"][0], str):
        bloqueos = prop["bloqueos"]
    return {
        "financiero_http": fin.get("http", 200 if "reconocimientos" in fin or "valoracion_costo" in fin else None),
        "propuesta_http": prop.get("http", 200 if "es_confirmable" in prop or "bloqueos" in prop else None),
        "estado": bio.get("nombre_estado") or prop.get("estado"),
        "id_especie": bio.get("id_especie") if bio.get("id_especie") is not None else prop.get("id_especie"),
        "reconocimientos": len(fin.get("reconocimientos") or []) if "reconocimientos" in fin else fin.get("reconocimientos"),
        "valoracion_costo": bool(fin.get("valoracion_costo")),
        "lineas": len(fin.get("lineas") or []) if isinstance(fin.get("lineas"), list) else fin.get("lineas"),
        "es_confirmable": prop.get("es_confirmable"),
        "indicador_valoracion": prop.get("indicador_valoracion"),
        "bloqueos": bloqueos,
        "auditoria": aud.get("total_registros"),
    }


def seguro(antes: dict) -> tuple[bool, str]:
    bloqueos = antes.get("bloqueos") or []
    if antes.get("financiero_http") == 404 or antes.get("propuesta_http") == 404:
        return False, (
            "La cuenta que puede confirmar el reconocimiento no ve el activo: "
            "el historial y la propuesta responden ACTIVO_NO_ENCONTRADO. "
            "El POST no llegaría a ACTIVO_NO_VALORABLE."
        )
    if antes.get("propuesta_http") != 200 or antes.get("financiero_http") != 200:
        return False, "No se pudo leer la propuesta o el historial financiero."
    if antes.get("estado") != "BAJA":
        return False, "El activo no está en BAJA."
    if antes.get("reconocimientos") not in (0, None):
        return False, "El activo ya tiene reconocimiento. El POST respondería por esa causa."
    if not bloqueos or bloqueos[0] != "ACTIVO_NO_VALORABLE":
        return False, "El primer bloqueo no es ACTIVO_NO_VALORABLE."
    if "RECONOCIMIENTO_BLOQUEADO_SIN_VALOR" in bloqueos:
        return False, "Ese bloqueo se audita y se confirma antes del rechazo."
    if antes.get("es_confirmable") is not False:
        return False, "La propuesta sigue confirmable."
    return True, "La baja bloquea antes del registro y este conjunto de bloqueos no se audita."


def render(informe: dict) -> str:
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <title>TC-M06-G72</title>
  <style>
    body {{ font-family: Segoe UI, sans-serif; margin: 2rem; line-height: 1.45; }}
    table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; }}
    th, td {{ border: 1px solid #ccc; padding: .45rem .6rem; vertical-align: top; text-align: left; }}
    th {{ background: #f3f3f3; }}
    .b {{ font-weight: 700; }}
    code {{ font-family: Consolas, monospace; }}
  </style>
</head>
<body>
  <h1>Módulo 6 — RF-88 — TC-M06-G72</h1>
  <p>Subcaso TC-M06-13. Fecha: {html.escape(informe['generado_en'])}. Ambiente: {html.escape(informe['ambiente'])}.</p>
  <p>Activo {informe['activo']}. POST ejecutado: {informe['post_ejecutado']}. Escrituras financieras persistidas: {informe['persistio']}.</p>
  <h2>Resumen</h2>
  <table>
    <tr><th>Estado</th><td class="b">{html.escape(informe['estado'])}</td></tr>
    <tr><th>Porcentaje</th><td>{informe['porcentaje_aprobacion']} %</td></tr>
    <tr><th>HTTP esperado</th><td>422 ACTIVO_NO_VALORABLE</td></tr>
    <tr><th>HTTP obtenido</th><td>{html.escape(str(informe.get('http_obtenido')))} {html.escape(str(informe.get('codigo_negocio') or ''))}</td></tr>
  </table>
  <h2>Antes</h2>
  <pre>{html.escape(json.dumps(informe['antes'], ensure_ascii=False, indent=2))}</pre>
  <h2>Respuesta</h2>
  <pre>{html.escape(json.dumps(informe.get('respuesta') or {}, ensure_ascii=False, indent=2))}</pre>
  <h2>Después</h2>
  <pre>{html.escape(json.dumps(informe.get('despues') or {}, ensure_ascii=False, indent=2))}</pre>
  <p>{html.escape(informe['motivo'])}</p>
</body>
</html>
"""


def guardar(informe: dict) -> None:
    RESULTADOS.mkdir(parents=True, exist_ok=True)
    (RESULTADOS / "resumen_ejecucion_TC-M06-G72.json").write_text(json.dumps(informe, ensure_ascii=False, indent=2), encoding="utf-8")
    (RESULTADOS / "evidencia_peticiones_TC-M06-G72.json").write_text(json.dumps({
        "caso": informe["caso"], "generado_en": informe["generado_en"], "http": informe["http"],
        "antes": informe["antes"], "respuesta": informe.get("respuesta"), "despues": informe.get("despues"),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    (RESULTADOS / "resultado_ejecucion_TC-M06-G72.html").write_text(render(informe), encoding="utf-8")


def main() -> int:
    codigo, token, login = autenticar()
    base = {
        "caso": "TC-M06-G72", "subcaso": "TC-M06-13", "rf": "RF-88", "ambiente": BASE_API,
        "generado_en": datetime.now(timezone.utc).isoformat(), "activo": ACTIVO,
        "login_http": codigo, "login": login, "post_ejecutado": False, "persistio": False,
        "antes": {}, "despues": None, "respuesta": None, "http": [], "http_obtenido": None,
        "codigo_negocio": None, "estado": "BLOQUEADO", "porcentaje_aprobacion": 0, "motivo": "",
    }
    if not token:
        base["motivo"] = f"POST /sesiones/ respondió {codigo}."
        guardar(base)
        print("BLOQUEADO 0")
        return 2
    codigo_lista, lista = pedir("GET", "/finanzas/activos", token=token)
    bajas = [
        a.get("id_activo_biologico") for a in lista
        if isinstance(a, dict) and str(a.get("estado") or "").upper() == "BAJA"
    ] if isinstance(lista, list) else []
    base["visibles"] = {"http": codigo_lista, "reconocidos": len(lista) if isinstance(lista, list) else None, "baja": bajas}
    evidencias, antes = foto(token)
    base["http"].extend(evidencias)
    base["antes"] = antes
    puede, razon = seguro(antes)
    if not puede:
        base["motivo"] = razon + " No se envió el POST."
        guardar(base)
        print("BLOQUEADO 0")
        return 2
    codigo_post, respuesta = pedir("POST", f"/finanzas/reconocimientos/{ACTIVO}", {}, token)
    publico = limpiar(respuesta) if isinstance(respuesta, dict) else {"tipo": type(respuesta).__name__}
    base["http"].append({
        "metodo": "POST", "consulta": f"/finanzas/reconocimientos/{ACTIVO}", "codigo": codigo_post,
        "lectura": False, "escritura": False, "cuerpo": {}, "respuesta": publico,
        "validacion": "Rechazo de reconocimiento por estado BAJA",
    })
    base["post_ejecutado"] = True
    base["http_obtenido"] = codigo_post
    base["codigo_negocio"] = publico.get("error_code") if isinstance(publico, dict) else None
    base["respuesta"] = publico
    evidencias_despues, despues = foto(token)
    for item in evidencias_despues:
        item["validacion"] = "Consulta posterior"
    base["http"].extend(evidencias_despues)
    base["despues"] = despues
    iguales = (
        despues.get("estado") == antes.get("estado")
        and despues.get("reconocimientos") == antes.get("reconocimientos")
        and despues.get("valoracion_costo") == antes.get("valoracion_costo")
        and despues.get("lineas") == antes.get("lineas")
        and despues.get("auditoria") == antes.get("auditoria")
    )
    base["persistio"] = not iguales
    mensaje = str(publico.get("message") or "").lower() if isinstance(publico, dict) else ""
    if codigo_post == 422 and publico.get("error_code") == "ACTIVO_NO_VALORABLE" and "baja" in mensaje and iguales:
        base["estado"] = "APROBADO"
        base["porcentaje_aprobacion"] = 100
        base["motivo"] = razon + " El rechazo no cambió estado, reconocimiento, líneas ni auditoría."
    elif not iguales:
        base["estado"] = "RECHAZADO"
        base["motivo"] = "La respuesta dejó diferencias entre la lectura anterior y la posterior."
    else:
        base["estado"] = "RECHAZADO"
        base["motivo"] = "La petición se ejecutó y no devolvió 422 ACTIVO_NO_VALORABLE por el estado BAJA."
    guardar(base)
    print(f"{base['estado']} {base['porcentaje_aprobacion']} HTTP {codigo_post} {base['codigo_negocio']}")
    return 0 if base["estado"] == "APROBADO" else 2


if __name__ == "__main__":
    sys.exit(main())
