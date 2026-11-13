# | Fecha      | Nombre     | Que se hizo                                                                          |
# |------------|------------|--------------------------------------------------------------------------------------|
# | 2026-11-12 | HulkyZeus  | TC-M06-G109 RF-89: reescrito; siembra en sandbox, dispara el aviso y hace rollback    |
# | 2026-11-12 | HulkyZeus  | TC-M06-G109 RF-89: modo --parcial (sin endpoint): siembra y verifica dentro del sandbox |
# | 2026-11-12 | HulkyZeus  | TC-M06-G109 RF-89: modos --sembrar/--verificar (real, sin sandbox, dos días)          |
"""TC-M06-G109 (TC-M06-34, RF-89): alertas previas al vencimiento de precios, sin duplicados.

Todo corre dentro del sandbox transaccional de TEST (X-Test-Run-Id + X-Sandbox-Secret) y
termina con DELETE /test-control/runs/{run_id}: no queda ningún dato en la BD.

Requiere un endpoint de prueba que el backend aún NO tiene (ver Solicitud_Endpoint_G109.md):
    POST /test-control/ejecutar-alertas-precios  ->  {"avisos_enviados": <int>}
que ejecute AlertarVencimientoPreciosUseCase con la sesión del run. Sin él, el script se
detiene ANTES de escribir nada y deja el caso BLOQUEADO con ese motivo.

Variables de entorno: QA_CORREO, QA_CONTRASENA (Contador), SANDBOX_SECRET (nunca en el
código), opcional BASE_API, ID_ESPECIE_QA.

    python tests/Test_Testing/Test_Modulo6/RF-89/TC-M06-G109/ejecutar_tc_m06_g109.py [--parcial]

--sembrar / --verificar (REAL, sin sandbox; deja datos permanentes en TEST): ver main_real().

--parcial: no usa el endpoint de prueba. Dentro del sandbox verifica que la ventana de 30 días se
guarda y que los precios con vencimiento a 7, 15 y 30 días se registran y quedan ACTIVOS, y comprueba
el rollback. NO prueba el aviso ni los duplicados: ese subcaso queda BLOQUEADO (caso Pendiente).
"""
from __future__ import annotations

import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

CARPETA = Path(__file__).resolve().parent
RESULTADOS = CARPETA / "resultados"
BASE_API = os.environ.get("BASE_API", "https://api.inmero.co/api-sgpmp-test").rstrip("/")
RUTA_EJECUTAR = "/test-control/ejecutar-alertas-precios"
ZONA = "America/Bogota"
VENTANA = 30
SECRETOS = {"token", "access_token", "contrasena", "password", "hash_integridad", "evidencia", "hash_evidencia"}
# Tres precios de la misma especie que coexisten porque cada fuente es una serie distinta.
PRECIOS = [("MERCADO_ACTIVO", 30), ("UPRA", 15), ("ESTIMADA", 7)]

PETICIONES: list[dict] = []
RUN_ID = f"G109-{uuid.uuid4().hex[:12]}"
SECRETO = os.environ.get("SANDBOX_SECRET", "")


def limpiar(v, n: int = 0):
    if n > 5:
        return "..."
    if isinstance(v, dict):
        return {k: ({"omitido": True} if k in SECRETOS else limpiar(x, n + 1)) for k, x in v.items()}
    if isinstance(v, list):
        return [limpiar(x, n + 1) for x in v[:40]]
    return v[:240] if isinstance(v, str) and len(v) > 240 else v


def pedir(metodo: str, ruta: str, cuerpo: dict | None = None, token: str | None = None, sandbox: bool = True):
    headers = {"Accept": "application/json", "X-Zona-Horaria": ZONA}
    if sandbox:
        headers["X-Test-Run-Id"] = RUN_ID
        headers["X-Sandbox-Secret"] = SECRETO
    if cuerpo is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(BASE_API + ruta, data=None if cuerpo is None else json.dumps(cuerpo).encode(),
                                 headers=headers, method=metodo)
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw, codigo = r.read().decode(), r.status
    except urllib.error.HTTPError as e:
        raw, codigo = e.read().decode("utf-8", "replace"), e.code
    except urllib.error.URLError as e:
        raw, codigo = json.dumps({"message": str(e.reason)}), 0
    try:
        payload = json.loads(raw) if raw else None
    except json.JSONDecodeError:
        payload = {"message": raw[:200]}
    PETICIONES.append({"metodo": metodo, "ruta": ruta, "codigo": codigo, "sandbox": sandbox,
                       "duracion_ms": round((time.perf_counter() - t0) * 1000),
                       "respuesta": {"omitido": "openapi.json completo"} if ruta == "/openapi.json" else limpiar(payload)})
    return codigo, payload


def estado_final(escenarios: list[dict]) -> str:
    est = [e["estado"] for e in escenarios]
    if "RECHAZADO" in est:
        return "RECHAZADO"
    return "APROBADO" if est and all(e == "APROBADO" for e in est) else "BLOQUEADO"


def guardar(informe: dict) -> None:
    RESULTADOS.mkdir(parents=True, exist_ok=True)
    esc = informe["escenarios"]
    filas = "".join(
        f"<tr><td>{html.escape(e['subcaso'])}</td><td>{html.escape(e['estado'])}</td>"
        f"<td>{html.escape(e['motivo'])}</td></tr>" for e in esc)
    (RESULTADOS / "resultado_ejecucion_TC-M06-G109.html").write_text(f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><title>TC-M06-G109</title>
<style>body{{font-family:system-ui,sans-serif;margin:2rem}}table{{border-collapse:collapse}}td,th{{border:1px solid #ccc;padding:.4rem .7rem;text-align:left}}pre{{white-space:pre-wrap;background:#fafafa;padding:.8rem}}</style></head><body>
<h1>Módulo 6 — RF-89 — TC-M06-G109</h1>
<p>Alertas previas al vencimiento (TC-M06-34). Generado: {html.escape(informe['generado_en'])}. Sandbox: {html.escape(RUN_ID)}, rollback: {html.escape(str(informe['rollback']))}.</p>
<table><tr><th>Subcaso</th><th>Estado</th><th>Motivo</th></tr>{filas}</table>
<h2>Detalle</h2><pre>{html.escape(json.dumps(informe['detalle'], ensure_ascii=False, indent=2, default=str))}</pre>
</body></html>""", encoding="utf-8")
    (RESULTADOS / "resumen_ejecucion_TC-M06-G109.json").write_text(
        json.dumps(informe, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (RESULTADOS / "evidencia_peticiones_TC-M06-G109.json").write_text(json.dumps(
        {"caso": "TC-M06-G109", "generado_en": informe["generado_en"], "peticiones": PETICIONES},
        ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def informe_base(hoy: date) -> dict:
    return {"caso": "TC-M06-G109", "subcaso": "TC-M06-34", "rf": ["RF-89"], "ambiente": BASE_API,
            "generado_en": datetime.now(timezone.utc).isoformat(), "hoy": hoy.isoformat(), "run_id": RUN_ID,
            "rollback": "no aplica", "escenarios": [], "detalle": {}}


def cerrar(informe: dict, motivo_bloqueo: str | None = None) -> int:
    if motivo_bloqueo:
        informe["escenarios"] = [{"subcaso": "TC-M06-34", "estado": "BLOQUEADO", "motivo": motivo_bloqueo}]
    informe["dictamen_general"] = estado_final(informe["escenarios"])
    informe["subcasos"] = informe["escenarios"]
    informe["peticiones"] = PETICIONES
    guardar(informe)
    print(informe["dictamen_general"], "-", "; ".join(f"{e['subcaso']}: {e['estado']}" for e in informe["escenarios"]))
    return {"APROBADO": 0, "RECHAZADO": 1}.get(informe["dictamen_general"], 2)



ESTADO = RESULTADOS / "siembra_real" / "estado_siembra.json"


def leer_bandeja(token: str) -> list[str]:
    textos, pagina = [], 1
    while pagina <= 10:
        _, b = pedir("GET", f"/notificaciones?pagina={pagina}&tamano=50", token=token, sandbox=False)
        items = (b or {}).get("items") or []
        textos += [str(i.get("mensaje") or "") for i in items]
        if len(items) < 50:
            break
        pagina += 1
    return textos


def ahora_utc() -> datetime:
    """G109_AHORA_UTC (ISO) permite probar los modos sin esperar a la corrida diaria."""
    v = os.environ.get("G109_AHORA_UTC")
    return datetime.fromisoformat(v).replace(tzinfo=timezone.utc) if v else datetime.now(timezone.utc)


def main_real(modo: str) -> int:
    """Prueba REAL del aviso diario, sin sandbox (TEST no tiene endpoint para dispararlo en un run).

    El proceso de fondo calcula "hoy" en UTC (sin X-Zona-Horaria) y corre una vez por día UTC.
    --sembrar: registra 3 precios (permanentes: POST /finanzas/precios es append-only) con vencimiento a
               30, 15 y 7 días contados desde la PRÓXIMA corrida diaria (próxima medianoche UTC).
    --verificar: día 1 (corrida D): un aviso por precio. Día 2 (corrida D+1): ninguno nuevo (sin duplicados,
               porque a 29, 14 y 6 días caen en los mismos umbrales ya marcados).
    """
    correo, clave = os.environ.get("QA_CORREO"), os.environ.get("QA_CONTRASENA")
    if not correo or not clave:
        raise SystemExit("Defina QA_CORREO y QA_CONTRASENA.")
    ahora = ahora_utc()
    hoy_bogota = ahora.astimezone(ZoneInfo(ZONA)).date()
    informe = informe_base(hoy_bogota)
    informe["modo"] = "real-" + modo
    informe["rollback"] = "no aplica (sin sandbox: los datos quedan en TEST)"
    codigo, login = pedir("POST", "/sesiones/", {"correo_electronico": correo, "contrasena": clave}, sandbox=False)
    token = (login or {}).get("token") if isinstance(login, dict) else None
    if codigo != 200 or not token:
        print(f"Login fallido (HTTP {codigo}).")
        return 2

    if modo == "sembrar":
        if ESTADO.exists():
            print(f"Ya hay una siembra registrada en {ESTADO}. No se siembra dos veces.")
            return 2
        _, cfg = pedir("GET", "/finanzas/configuracion", token=token, sandbox=False)
        general = (cfg or {}).get("general") if isinstance(cfg, dict) else {}
        ventana = general.get("dias_alerta_vencimiento_precio")
        if ventana != VENTANA:
            print(f"La ventana de alerta es {ventana}, no {VENTANA}: no se cambia la configuración compartida. Nada sembrado.")
            return 2
        id_especie = int(os.environ.get("ID_ESPECIE_QA", 0)) or None
        if not id_especie:
            esp = (cfg or {}).get("especies")
            id_especie = esp[0].get("id_especie") if esp else None
        if not id_especie:
            print("No hay especie: defina ID_ESPECIE_QA. Nada sembrado.")
            return 2
        corrida = (ahora + timedelta(days=1)).date()  # próxima medianoche UTC
        sembrados = []
        for fuente, dias in PRECIOS:
            venc = corrida + timedelta(days=dias)
            cuerpo = {"id_especie": id_especie, "categoria": "PESO_KG", "precio_unitario": "1000.00",
                      "fecha_vigencia": hoy_bogota.isoformat(), "fecha_vencimiento": venc.isoformat(),
                      "fuente": fuente, "evidencia_documental": "QA-G109 siembra real TC-M06-34", "confirmar_desviacion": True}
            if fuente == "ESTIMADA":
                cuerpo["justificacion_estimacion"] = "Precio sembrado por QA para verificar el aviso de vencimiento (TC-M06-34)."
            codigo, r = pedir("POST", "/finanzas/precios", cuerpo, token, sandbox=False)
            if codigo not in (200, 201) or not isinstance(r, dict):
                print(f"Falló el precio {fuente} (HTTP {codigo}). Ya sembrados: {sembrados}")
                break
            sembrados.append({"id": r.get("id_precio_mercado"), "fuente": fuente, "dias": dias, "vence": venc.isoformat(),
                              "estado": r.get("estado")})
        ESTADO.parent.mkdir(parents=True, exist_ok=True)
        ESTADO.write_text(json.dumps({
            "sembrado_en": ahora.isoformat(), "id_especie": id_especie, "vigencia": hoy_bogota.isoformat(),
            "primera_corrida_utc": corrida.isoformat(), "precios": sembrados, "verificaciones": []},
            ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Sembrados {len(sembrados)} precios; primera corrida esperada el {corrida} 00:00 UTC. Estado en {ESTADO}")
        return 0 if len(sembrados) == len(PRECIOS) else 2

    # --verificar
    if not ESTADO.exists():
        print("No hay siembra registrada: corra primero --sembrar.")
        return 2
    est = json.loads(ESTADO.read_text(encoding="utf-8"))
    corrida = date.fromisoformat(est["primera_corrida_utc"])
    dia = len(est["verificaciones"]) + 1
    if dia > 2:
        print("Las dos verificaciones ya se hicieron.")
        return 0
    inicio = datetime.combine(corrida + timedelta(days=dia - 1), datetime.min.time(), tzinfo=timezone.utc)
    if ahora < inicio:
        print(f"Aún no corre el proceso diario del día {dia} ({inicio.isoformat()}). No se registra la verificación.")
        return 3
    textos = leer_bandeja(token)
    vigente = f"vigente desde {est['vigencia']}"
    conteo = {p["vence"]: sum(1 for t in textos if f"vence el {p['vence']}" in t and vigente in t) for p in est["precios"]}
    est["verificaciones"].append({"dia": dia, "en": ahora.isoformat(), "avisos_por_vencimiento": conteo})
    ESTADO.write_text(json.dumps(est, ensure_ascii=False, indent=2), encoding="utf-8")

    esc = [{"subcaso": f"TC-M06-34 precio a {p['dias']} días registrado", "estado": "APROBADO" if p.get("estado") == "ACTIVO" else "RECHAZADO",
            "motivo": f"Precio {p['id']} ({p['fuente']}), vence {p['vence']}: estado {p.get('estado')} al registrarlo."} for p in est["precios"]]
    dia1 = est["verificaciones"][0]["avisos_por_vencimiento"]
    for p in est["precios"]:
        n = dia1.get(p["vence"], 0)
        esc.append({"subcaso": f"TC-M06-34 aviso a {p['dias']} días", "estado": "APROBADO" if n == 1 else "RECHAZADO",
                    "motivo": f"Día 1 ({est['verificaciones'][0]['en'][:16]} UTC): {n} aviso(s) al Contador por el precio que vence el {p['vence']}; se esperaba 1."})
    if dia == 1:
        esc.append({"subcaso": "TC-M06-34 sin duplicados", "estado": "BLOQUEADO",
                    "motivo": "Pendiente de la verificación del día 2 (la corrida del día siguiente no debe repetir ningún aviso)."})
    else:
        dia2 = est["verificaciones"][1]["avisos_por_vencimiento"]
        repetidos = {v: dia2.get(v, 0) - dia1.get(v, 0) for v in dia1 if dia2.get(v, 0) != dia1.get(v, 0)}
        esc.append({"subcaso": "TC-M06-34 sin duplicados", "estado": "APROBADO" if not repetidos else "RECHAZADO",
                    "motivo": f"Día 2: avisos por vencimiento {dia2} frente a {dia1} del día 1; diferencias: {repetidos or 'ninguna'}."})
    informe["escenarios"] = esc
    informe["detalle"] = {"siembra": est}
    return cerrar(informe)


def main() -> int:
    for m in ("sembrar", "verificar"):
        if f"--{m}" in sys.argv:
            return main_real(m)
    hoy = datetime.now(ZoneInfo(ZONA)).date()
    informe = informe_base(hoy)
    correo, clave = os.environ.get("QA_CORREO"), os.environ.get("QA_CONTRASENA")
    if not correo or not clave or not SECRETO:
        raise SystemExit("Defina QA_CORREO, QA_CONTRASENA y SANDBOX_SECRET. Sin sandbox no se escribe nada.")

    parcial = "--parcial" in sys.argv
    informe["modo"] = "parcial" if parcial else "completo"
    # Precondición (modo completo): el endpoint de prueba debe existir en el OpenAPI de TEST. Nada se escribe antes.
    codigo, oa = pedir("GET", "/openapi.json", sandbox=False)
    if not parcial and (codigo != 200 or RUTA_EJECUTAR not in (oa or {}).get("paths", {})):
        return cerrar(informe, f"TEST no expone {RUTA_EJECUTAR}: no hay forma de disparar el aviso dentro del "
                               "sandbox (el proceso diario usa otra sesión y no ve datos sin confirmar). No se escribió nada.")

    precios_creados: list[dict] = []
    token = None
    try:
        codigo, login = pedir("POST", "/sesiones/", {"correo_electronico": correo, "contrasena": clave})
        token = (login or {}).get("token") if isinstance(login, dict) else None
        if codigo != 200 or not token:
            return cerrar(informe, f"Login fallido (HTTP {codigo}).")

        # El PUT exige los tres campos: se reenvían los vigentes y solo cambia la ventana (dentro del sandbox).
        _, cfg_actual = pedir("GET", "/finanzas/configuracion", token=token)
        actual = (cfg_actual or {}).get("general") if isinstance(cfg_actual, dict) else None
        if not isinstance(actual, dict) or "tipo_cierre" not in actual or "pct_umbral_desviacion_precio" not in actual:
            return cerrar(informe, "No se pudo leer la configuración financiera vigente para reenviarla.")
        codigo, _ = pedir("PUT", "/finanzas/configuracion", {
            "tipo_cierre": actual["tipo_cierre"], "pct_umbral_desviacion_precio": actual["pct_umbral_desviacion_precio"],
            "dias_alerta_vencimiento_precio": VENTANA}, token)
        if codigo != 200:
            return cerrar(informe, f"No se pudo fijar la ventana de alerta en {VENTANA} días (HTTP {codigo}).")

        id_especie = int(os.environ.get("ID_ESPECIE_QA", 0)) or None
        if not id_especie:
            codigo, cfg = pedir("GET", "/finanzas/configuracion", token=token)
            esp = (cfg or {}).get("especies") if isinstance(cfg, dict) else None
            id_especie = esp[0].get("id_especie") if esp else None
        if not id_especie:
            return cerrar(informe, "No hay especie para el escenario: defina ID_ESPECIE_QA.")

        for fuente, dias in PRECIOS:
            cuerpo = {"id_especie": id_especie, "categoria": "PESO_KG", "precio_unitario": "1000.00",
                      "fecha_vigencia": hoy.isoformat(), "fecha_vencimiento": (hoy + timedelta(days=dias)).isoformat(),
                      "fuente": fuente, "evidencia_documental": f"QA-G109 {RUN_ID}", "confirmar_desviacion": True}
            if fuente == "ESTIMADA":
                cuerpo["justificacion_estimacion"] = "Precio sembrado por QA dentro del sandbox; se revierte."
            codigo, r = pedir("POST", "/finanzas/precios", cuerpo, token)
            if codigo not in (200, 201) or not isinstance(r, dict):
                return cerrar(informe, f"No se pudo sembrar el precio {fuente} a {dias} días (HTTP {codigo}).")
            precios_creados.append({"id": r.get("id_precio_mercado"), "fuente": fuente, "dias": dias,
                                    "vence": cuerpo["fecha_vencimiento"]})
        informe["detalle"]["precios_sembrados"] = precios_creados

        if parcial:
            _, cfg = pedir("GET", "/finanzas/configuracion", token=token)
            general = (cfg or {}).get("general") if isinstance(cfg, dict) else {}
            ventana = general.get("dias_alerta_vencimiento_precio") if isinstance(general, dict) else None
            informe["escenarios"].append({
                "subcaso": "TC-M06-34 ventana de alerta", "estado": "APROBADO" if ventana == VENTANA else "RECHAZADO",
                "motivo": f"La configuración guardó dias_alerta_vencimiento_precio={ventana}; se esperaba {VENTANA}."})
            _, lista = pedir("GET", "/finanzas/precios", token=token)
            por_id = {x.get("id_precio_mercado"): x for x in lista if isinstance(x, dict)} if isinstance(lista, list) else {}
            for p in precios_creados:
                x = por_id.get(p["id"]) or {}
                ok = x.get("estado") == "ACTIVO" and str(x.get("fecha_vencimiento")) == p["vence"]
                informe["escenarios"].append({
                    "subcaso": f"TC-M06-34 precio a {p['dias']} días", "estado": "APROBADO" if ok else "RECHAZADO",
                    "motivo": f"Precio {p['id']} ({p['fuente']}): estado={x.get('estado')}, vence={x.get('fecha_vencimiento')}; se esperaba ACTIVO y {p['vence']}."})
            informe["escenarios"].append({
                "subcaso": "TC-M06-34 avisos y duplicados", "estado": "BLOQUEADO",
                "motivo": f"No verificado: el aviso solo lo dispara el proceso diario y TEST no expone {RUTA_EJECUTAR}."})
            return cerrar(informe)

        def bandeja() -> list[str]:
            textos, pagina = [], 1
            while pagina <= 10:
                _, b = pedir("GET", f"/notificaciones?pagina={pagina}&tamano=50", token=token)
                items = (b or {}).get("items") or []
                textos += [str(i.get("mensaje") or "") for i in items]
                if len(items) < 50:
                    break
                pagina += 1
            return textos

        def avisos_de(textos: list[str], vence: str) -> int:
            return sum(1 for t in textos if f"vence el {vence}" in t and f"vigente desde {hoy:%Y-%m-%d}" in t)

        antes = bandeja()
        codigo, r1 = pedir("POST", RUTA_EJECUTAR, {}, token)
        tras1 = bandeja()
        codigo2, r2 = pedir("POST", RUTA_EJECUTAR, {}, token)
        tras2 = bandeja()
        informe["detalle"].update({"primera_ejecucion": r1, "segunda_ejecucion": r2,
                                   "bandeja_antes": len(antes), "bandeja_tras_1": len(tras1), "bandeja_tras_2": len(tras2)})
        if codigo != 200 or codigo2 != 200:
            return cerrar(informe, f"El endpoint de prueba respondió HTTP {codigo}/{codigo2}.")

        for p in precios_creados:
            n1 = avisos_de(tras1, p["vence"]) - avisos_de(antes, p["vence"])
            informe["escenarios"].append({
                "subcaso": f"TC-M06-34 aviso a {p['dias']} días", "estado": "APROBADO" if n1 == 1 else "RECHAZADO",
                "motivo": f"Precio {p['id']} ({p['fuente']}) vence el {p['vence']}: {n1} aviso(s) nuevo(s) al Contador; se esperaba 1."})
        n2 = sum(avisos_de(tras2, p["vence"]) - avisos_de(tras1, p["vence"]) for p in precios_creados)
        enviados2 = (r2 or {}).get("avisos_enviados") if isinstance(r2, dict) else None
        ok = n2 == 0 and enviados2 == 0
        informe["escenarios"].append({
            "subcaso": "TC-M06-34 sin duplicados", "estado": "APROBADO" if ok else "RECHAZADO",
            "motivo": f"Segunda ejecución el mismo día: {n2} aviso(s) repetido(s) en la bandeja y avisos_enviados={enviados2}; se esperaba 0."})
        return cerrar(informe)
    finally:
        # Rollback del sandbox siempre, incluso si algo falló a medias.
        req =urllib.request.Request(f"{BASE_API}/test-control/runs/{RUN_ID}", method="DELETE",
                                     headers={"X-Sandbox-Secret": SECRETO, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                informe["rollback"] = f"HTTP {r.status}"
        except urllib.error.HTTPError as e:
            informe["rollback"] = f"HTTP {e.code}" + (" (run no existía: no se abrió ninguna transacción)" if e.code == 404 else "")
        except urllib.error.URLError as e:
            informe["rollback"] = f"error: {e.reason}"
        # Comprobación independiente: sin el header del run, los precios sembrados no deben existir.
        if precios_creados and token:
            codigo_v, lista = pedir("GET", "/finanzas/precios", token=token, sandbox=False)
            if codigo_v == 401:
                # El login se hizo dentro del run: si el token ya no sirve, la transacción del run se revirtió.
                # Es evidencia indirecta; confirmar los ids con una consulta de otro usuario si se necesita certeza.
                informe["detalle"]["rollback_verificado"] = "indirecto: el token creado dentro del run dejó de ser válido (401)"
                quedan = []
            elif isinstance(lista, list):
                ids = {p.get("id_precio_mercado") for p in lista if isinstance(p, dict)}
                quedan = [p["id"] for p in precios_creados if p["id"] in ids]
                informe["detalle"]["rollback_verificado"] = not quedan
            else:
                informe["detalle"]["rollback_verificado"] = f"no verificado (HTTP {codigo_v})"
                quedan = []
            informe["detalle"]["precios_que_quedaron"] = quedan
            if quedan:
                informe["escenarios"].append({"subcaso": "Limpieza", "estado": "RECHAZADO",
                                              "motivo": f"El rollback dejó precios en la BD: {quedan}."})
        informe["dictamen_general"] = estado_final(informe["escenarios"])
        informe["subcasos"] = informe["escenarios"]
        informe["peticiones"] = PETICIONES
        guardar(informe)  # reescribe el reporte con el estado real del rollback


if __name__ == "__main__":
    sys.exit(main())
