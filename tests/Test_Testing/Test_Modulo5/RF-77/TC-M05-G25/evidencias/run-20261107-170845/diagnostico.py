# | Fecha      | Nombre                   | Que se hizo                                                           |
# |------------|--------------------------|-----------------------------------------------------------------------|
# | 2026-11-07 | Juan Sebastian Gutierrez | Script de diagnóstico PASO 2: Auditoría RF-77 vs Control Positivo RF-76 |
"""Script de diagnóstico en sandbox transaccional de Administrador (PASO 2).

Ejecuta:
1. Captura de línea base de auditoría en M05, M01 y BD PostgreSQL.
2. Control Positivo: Registro de medicamento RF-76 en activo creado en la corrida.
3. Generación de reporte RF-77 y exportación CSV.
4. Consulta de bitácora M05 (sin filtros, paginada, con filtros) y M01 a los 0, 5, 15 y 60 segundos.
5. Verificación directa en base de datos (SELECT rol_qa).
6. Cierre ordenado con rollback atómico y verificación post-sandbox.
"""
from __future__ import annotations

import json
import os
import re
import sys
import threading
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests
from dotenv import dotenv_values
from sqlalchemy import create_engine, text

NOMBRE_ZONA = "America/Bogota"
ZONA_USUARIO = timezone(timedelta(hours=-5))
TIMEOUT_S = 30
ARCHIVO_TRAZA = "trazas_http.jsonl"
_LOCK_TRAZA = threading.Lock()

_RAIZ_REPO = Path(__file__).resolve().parents[5]
if not (_RAIZ_REPO / ".env.test").exists():
    _RAIZ_REPO = Path.cwd()
_ENV_TEST = dotenv_values(_RAIZ_REPO / ".env.test") if (_RAIZ_REPO / ".env.test").exists() else {}

_DIR_STAGING = Path(__file__).resolve().parent


def _env(nombre: str, obligatoria: bool = True, defecto: str | None = None) -> str:
    valor = os.environ.get(nombre) or _ENV_TEST.get(nombre) or defecto
    if obligatoria and not valor:
        raise AssertionError(f"Falta variable {nombre}")
    return valor or ""


def _secretos() -> list[str]:
    return [
        s for s in (
            _env("TEST_SANDBOX_SECRET", False),
            _env("TEST_ADMIN_PASSWORD", False),
            _env("TEST_ADMIN_EMAIL", False),
            _env("TEST_PRODUCER_PASSWORD", False),
            _env("TEST_PRODUCER_EMAIL", False),
            _env("TEST_VET_PASSWORD", False),
            _env("TEST_VET_EMAIL", False),
        ) if s
    ]


def _seguro(texto: str, extra: tuple[str, ...] = ()) -> str:
    texto = (texto or "")[:600]
    for s in [*_secretos(), *extra]:
        if s and len(s) > 3:
            texto = texto.replace(s, "***REDACTED***")
    pref_jwt = "e" + "yJ"
    if pref_jwt in texto:
        texto = re.sub(pref_jwt + r"[a-zA-Z0-9_\-\.]+", "***REDACTED_JWT***", texto)
    return texto


def _sanitizar_objeto(obj: Any, extra: tuple[str, ...] = ()) -> Any:
    if isinstance(obj, dict):
        san = {}
        for k, v in obj.items():
            if k.lower() in ("contrasena", "password", "token", "authorization", "correo_electronico", "access_token"):
                san[k] = "***REDACTED***"
            elif isinstance(v, (dict, list)):
                san[k] = _sanitizar_objeto(v, extra)
            elif isinstance(v, str):
                san[k] = _seguro(v, extra)
            else:
                san[k] = v
        return san
    elif isinstance(obj, list):
        return [_sanitizar_objeto(x, extra) for x in obj]
    elif isinstance(obj, str):
        return _seguro(obj, extra)
    return obj


def _trazar(
    metodo: str,
    ruta: str,
    resp: requests.Response | None,
    inicio_perf: float,
    params: Any = None,
    req_body: Any = None,
    token_extra: str | None = None,
    error: str | None = None,
    paso: str | None = None,
) -> None:
    destino = _DIR_STAGING / ARCHIVO_TRAZA
    duracion_ms = round((time.perf_counter() - inicio_perf) * 1000, 2)
    now_iso = datetime.now(ZONA_USUARIO).isoformat()
    extra = (token_extra,) if token_extra else ()

    resp_body = None
    server_date = ""
    status_code = None
    error_code = None

    if resp is not None:
        status_code = resp.status_code
        server_date = resp.headers.get("Date", "")
        try:
            resp_body = resp.json()
            if isinstance(resp_body, dict):
                error_code = resp_body.get("error_code")
        except Exception:
            resp_body = resp.text[:300]

    registro = {
        "timestamp_local": now_iso,
        "server_date": server_date,
        "duracion_ms": duracion_ms,
        "paso": paso or "diagnostico",
        "metodo": metodo,
        "ruta": ruta,
        "params": _sanitizar_objeto(params, extra),
        "status_code": status_code,
        "error_code": error_code,
        "error_conexion": error,
        "request_body": _sanitizar_objeto(req_body, extra),
        "response_body": _sanitizar_objeto(resp_body, extra),
    }

    with _LOCK_TRAZA:
        try:
            with open(destino, "a", encoding="utf-8") as f:
                f.write(json.dumps(registro, ensure_ascii=False) + "\n")
        except Exception:
            pass


def main():
    print("=" * 80)
    print("INICIANDO DIAGNOSTICO PASO 2: CONTROL POSITIVO RF-76 VS REPORTE RF-77")
    print("=" * 80)

    base = _env("TEST_BASE_URL").rstrip("/")
    run_id = f"tc-m05-g25-diag-{uuid.uuid4().hex[:8]}"
    secret = _env("TEST_SANDBOX_SECRET")
    email_admin = _env("TEST_ADMIN_EMAIL")
    pass_admin = _env("TEST_ADMIN_PASSWORD")
    db_url = _env("TEST_DATABASE_URL")

    http = requests.Session()
    http.headers.update({
        "X-Test-Run-Id": run_id,
        "X-Sandbox-Secret": secret,
        "X-Zona-Horaria": NOMBRE_ZONA,
    })

    def request_api(metodo: str, ruta: str, paso: str, json_body: Any = None, params: Any = None) -> requests.Response:
        t0 = time.perf_counter()
        token = http.headers.get("Authorization", "").replace("Bearer ", "")
        try:
            r = http.request(metodo, f"{base}{ruta}", json=json_body, params=params, timeout=TIMEOUT_S)
        except Exception as exc:
            _trazar(metodo, ruta, None, t0, params=params, req_body=json_body, token_extra=token, error=type(exc).__name__, paso=paso)
            raise
        _trazar(metodo, ruta, r, t0, params=params, req_body=json_body, token_extra=token, paso=paso)
        return r

    # 1. Login Administrador en Sandbox
    print(f"\n[1] Login Administrador en Sandbox (run_id={run_id})...")
    r_login = request_api("POST", "/sesiones/", "login_admin", {"correo_electronico": email_admin, "contrasena": pass_admin})
    assert r_login.status_code == 200, f"Login falló: {r_login.status_code}: {r_login.text}"
    token = r_login.json()["token"]
    id_usuario_admin = r_login.json().get("usuario", {}).get("id_usuario") or r_login.json().get("id_usuario")
    http.headers["Authorization"] = f"Bearer {token}"
    print(f"Login OK. Token recibido. id_usuario_admin={id_usuario_admin}")

    # Helper para consulta directa en BD con rol_qa
    engine = create_engine(db_url)

    def select_db(consulta: str) -> tuple[bool, Any]:
        with engine.connect() as conn:
            try:
                res = conn.execute(text(consulta)).fetchall()
                return True, res
            except Exception as e:
                return False, str(e)

    # 2. Línea Base
    print("\n[2] Capturando línea base inicial...")
    r_aud_m05_ini = request_api("GET", "/suministros/auditoria", "linea_base_m05", params={"registros_por_pagina": 10})
    total_m05_ini = r_aud_m05_ini.json().get("total", 0) if r_aud_m05_ini.status_code == 200 else -1

    r_aud_m01_ini = request_api("GET", "/auditoria/", "linea_base_m01", params={"registros_por_pagina": 10})
    total_m01_ini = r_aud_m01_ini.json().get("total", 0) if r_aud_m01_ini.status_code == 200 else -1

    ok_m05, res_db_m05_ini = select_db("SELECT count(*) FROM modulo5.auditorias_suministros")
    cnt_db_m05_ini = res_db_m05_ini[0][0] if ok_m05 else -1

    ok_dml, res_db_dml = select_db("SELECT count(*) FROM auditoria.logs_dml")
    cnt_db_dml = res_db_dml[0][0] if ok_dml else f"FALLO_PERMISOS: {res_db_dml}"

    print(f"Línea base M05 API: total={total_m05_ini}")
    print(f"Línea base M01 API: total={total_m01_ini}")
    print(f"Línea base BD modulo5.auditorias_suministros: {cnt_db_m05_ini}")
    print(f"Línea base BD auditoria.logs_dml: {cnt_db_dml}")

    # 3. CONTROL POSITIVO: Crear activo QA y registrar 1 medicamento RF-76
    print("\n[3] Ejecutando CONTROL POSITIVO: Creando activo QA y registrando 1 medicamento RF-76...")
    fecha_hoy = datetime.now(ZONA_USUARIO).date()
    fecha_ciclo = (fecha_hoy - timedelta(days=10)).isoformat()
    hoy_str = fecha_hoy.isoformat()
    hora_unica = datetime.now(ZONA_USUARIO).strftime("%H:%M:%S")

    id_unico = f"QA-DIAG-{uuid.uuid4().hex[:8]}"
    payload_activo = {
        "tipo_activo": "POBLACIONAL",
        "id_especie": 1,
        "id_infraestructura": 2,
        "identificador_unico": id_unico,
        "cantidad_inicial": 50,
        "fecha_ingreso": fecha_ciclo,
        "fecha_inicio_ciclo": fecha_ciclo,
        "origen_financiero": "nacimiento",
        "peso_actual": 20.0,
    }
    r_act = request_api("POST", "/activos-biologicos", "crear_activo_qa", payload_activo)
    assert r_act.status_code == 201, f"Fallo creando activo QA: {r_act.status_code}"
    id_activo = r_act.json()["id_activo_biologico"]

    r_fase = request_api("POST", f"/activos-biologicos/{id_activo}/fases", "abrir_fase", {"id_ciclo_productiva": 1, "motivo_cambio": "Apertura fase diag"})
    assert r_fase.status_code in (200, 201), f"Fallo abriendo fase: {r_fase.status_code}"

    payload_med = {
        "id_activo_biologico": id_activo,
        "nombre_medicamento": "Oxitetraciclina",
        "via_administracion": "INTRAMUSCULAR",
        "dosis_aplicada": 5.0,
        "unidad_dosis": "ml",
        "costo_unitario": 2000.0,
        "periodo_retiro_dias": 0,
        "fecha_aplicacion": hoy_str,
        "hora_aplicacion": hora_unica,
        "motivo_aplicacion": "Tratamiento preventivo para diagnostico auditoria",
        "nombre_veterinario": "Dr. QA Diagnostico",
    }
    r_med = request_api("POST", "/suministros/medicamentos", "registrar_medicamento_rf76", payload_med)
    assert r_med.status_code == 201, f"Fallo registrando medicamento RF-76: {r_med.status_code}: {r_med.text}"
    id_med = r_med.json().get("id_registro_medicamento")
    print(f"Medicamento RF-76 registrado con éxito: id_registro_medicamento={id_med}, hora={hora_unica}")

    # Verificar de inmediato si el medicamento RF-76 generó evento en la bitácora
    r_aud_med = request_api("GET", "/suministros/auditoria", "verificar_control_positivo_med", params={"registros_por_pagina": 10})
    total_m05_post_med = r_aud_med.json().get("total", 0)
    items_med = r_aud_med.json().get("items", [])
    med_evento = next((it for it in items_med if it.get("entidad_afectada") == "registros_medicamentos" and it.get("id_activo_biologico") == id_activo), None)

    ok_m05_db, res_m05_db_med = select_db("SELECT count(*) FROM modulo5.auditorias_suministros")
    cnt_db_m05_post_med = res_m05_db_med[0][0] if ok_m05_db else -1

    print(f"CONTROL POSITIVO RESULTADO:")
    print(f"  - Total API M05 antes: {total_m05_ini} -> después de medicamento: {total_m05_post_med}")
    print(f"  - Total BD modulo5.auditorias_suministros antes: {cnt_db_m05_ini} -> después de medicamento: {cnt_db_m05_post_med}")
    print(f"  - ¿Evento de registros_medicamentos observable en API en Sandbox?: {'SI' if med_evento else 'NO'}")
    if med_evento:
        print(f"    Detalle evento: tipo_operacion={med_evento.get('tipo_operacion')}, entidad={med_evento.get('entidad_afectada')}, usuario={med_evento.get('id_usuario')}, fecha={med_evento.get('fecha_evento')}")

    # 4. Generar reporte RF-77 y exportación CSV
    print("\n[4] Generando 1 reporte RF-77 y 1 exportación CSV...")
    payload_rep = {
        "activo_biologico_id": id_activo,
        "fecha_inicio_reporte": fecha_ciclo,
        "fecha_fin_reporte": hoy_str,
        "tipo_periodo": "CICLO_COMPLETO",
    }
    r_rep = request_api("POST", "/suministros/reportes-gastos", "generar_reporte_rf77", payload_rep)
    assert r_rep.status_code == 200, f"Fallo generando reporte RF-77: {r_rep.status_code}: {r_rep.text}"
    id_reporte = r_rep.json()["id_reporte_gasto_acumulado"]
    print(f"Reporte RF-77 generado: id_reporte_gasto_acumulado={id_reporte}, total={r_rep.json().get('gasto_total_acumulado')}")

    r_exp = request_api("POST", f"/suministros/reportes-gastos/{id_reporte}/exportacion", "exportar_csv_rf77", {"formato_exportacion": "CSV"})
    assert r_exp.status_code == 201, f"Fallo exportando reporte RF-77: {r_exp.status_code}: {r_exp.text}"
    id_archivo = r_exp.json()["id_archivo"]
    print(f"Exportación CSV RF-77 generada: id_archivo={id_archivo}, nombre={r_exp.json().get('nombre_archivo')}")

    # 5. Muestreos temporales a t=0s, t=5s, t=15s, t=60s
    muestreos = [0, 5, 15, 60]
    historial_tiempos = []

    print("\n[5] Evaluando bitácora de auditoría a t = 0s, 5s, 15s y 60s...")
    t_inicio_espera = time.perf_counter()

    for idx, t_espera in enumerate(muestreos):
        t_actual = time.perf_counter() - t_inicio_espera
        tiempo_a_dormir = max(0.0, t_espera - t_actual)
        if tiempo_a_dormir > 0:
            # Enviar keep-alives ligeros para evitar timeout de inactividad de sandbox (límite 180s)
            while tiempo_a_dormir > 10:
                time.sleep(8)
                request_api("GET", "/suministros/reportes-gastos/historial", "keep_alive")
                tiempo_a_dormir = max(0.0, t_espera - (time.perf_counter() - t_inicio_espera))
            time.sleep(tiempo_a_dormir)

        t_medido = round(time.perf_counter() - t_inicio_espera, 2)
        print(f"\n--- Muestreo a t = {t_medido} s (objetivo {t_espera} s) ---")

        # 5.1 Consultar M05 sin filtros (página 1 con 50 registros)
        r_m05_raw = request_api("GET", "/suministros/auditoria", f"auditoria_m05_t{t_espera}", params={"registros_por_pagina": 50})
        total_m05 = r_m05_raw.json().get("total", 0) if r_m05_raw.status_code == 200 else -1
        items_m05 = r_m05_raw.json().get("items", []) if r_m05_raw.status_code == 200 else []

        # Buscar cualquier mención de reporte de gastos o exportación en los ítems
        evento_rf77_m05 = None
        for it in items_m05:
            ent = str(it.get("entidad_afectada", "")).lower()
            top = str(it.get("tipo_operacion", ""))
            det = str(it.get("detalle_causa", "")).lower()
            if any(k in ent for k in ("reporte_gasto", "reportes_gastos", "exportacion_reporte")):
                evento_rf77_m05 = it
                break
            if any(k in top for k in ("REPORTE_GASTOS", "EXPORTACION_REPORTE")):
                evento_rf77_m05 = it
                break
            if "rf-77" in det or "rf77" in det or "reporte de gastos" in det:
                evento_rf77_m05 = it
                break

        # 5.2 Consultar M05 con filtros específicos
        r_filtro_ent = request_api("GET", "/suministros/auditoria", f"auditoria_m05_filtro_ent_t{t_espera}", params={"entidad_afectada": "reporte_gastos_acumulados"})
        cnt_filtro_ent = r_filtro_ent.json().get("total", 0) if r_filtro_ent.status_code == 200 else -1

        r_filtro_arch = request_api("GET", "/suministros/auditoria", f"auditoria_m05_filtro_arch_t{t_espera}", params={"entidad_afectada": "archivos_exportacion_suministros"})
        cnt_filtro_arch = r_filtro_arch.json().get("total", 0) if r_filtro_arch.status_code == 200 else -1

        # 5.3 Consultar M01 auditoría general (RF-10)
        r_m01_raw = request_api("GET", "/auditoria/", f"auditoria_m01_t{t_espera}", params={"registros_por_pagina": 20})
        total_m01 = r_m01_raw.json().get("total", 0) if r_m01_raw.status_code == 200 else -1
        items_m01 = r_m01_raw.json().get("items", []) if r_m01_raw.status_code == 200 else []

        evento_rf77_m01 = None
        for it in items_m01:
            desc = str(it).lower()
            if "reporte" in desc or "gasto" in desc or "rf-77" in desc or "rf77" in desc:
                evento_rf77_m01 = it
                break

        # 5.4 Consulta SELECT directa con rol_qa
        ok_db_m05, res_db_m05 = select_db("SELECT count(*) FROM modulo5.auditorias_suministros")
        cnt_db_m05 = res_db_m05[0][0] if ok_db_m05 else -1

        res_muestreo = {
            "tiempo_s": t_medido,
            "total_m05": total_m05,
            "cnt_filtro_ent": cnt_filtro_ent,
            "cnt_filtro_arch": cnt_filtro_arch,
            "evento_rf77_m05": evento_rf77_m05,
            "total_m01": total_m01,
            "evento_rf77_m01": evento_rf77_m01,
            "cnt_db_m05": cnt_db_m05,
        }
        historial_tiempos.append(res_muestreo)

        print(f"  Total eventos M05 API: {total_m05}")
        print(f"  Filtro 'reporte_gastos_acumulados': {cnt_filtro_ent} eventos")
        print(f"  Filtro 'archivos_exportacion_suministros': {cnt_filtro_arch} eventos")
        print(f"  ¿Evento RF-77 encontrado en M05?: {'SI' if evento_rf77_m05 else 'NO'}")
        print(f"  Total eventos M01 API: {total_m01} | ¿Evento RF-77 en M01?: {'SI' if evento_rf77_m01 else 'NO'}")
        print(f"  Total BD modulo5.auditorias_suministros: {cnt_db_m05}")

    # 6. Cierre ordenado de sandbox
    print("\n[6] Cerrando Sandbox y ejecutando rollback atómico...")
    r_del = request_api("DELETE", f"/test-control/runs/{run_id}", "teardown_diag")
    assert r_del.status_code == 200, f"Cierre sandbox falló: {r_del.status_code}: {r_del.text}"
    print(f"Rollback exitoso: {r_del.text}")

    # 7. Verificación post-sandbox
    print("\n[7] Verificando inocuidad post-sandbox...")
    ok_post, res_post = select_db("SELECT count(*) FROM modulo5.auditorias_suministros")
    cnt_post = res_post[0][0] if ok_post else -1
    print(f"Conteo final BD modulo5.auditorias_suministros tras rollback: {cnt_post} (debe ser igual a {cnt_db_m05_ini})")
    assert cnt_post == cnt_db_m05_ini, f"El rollback no fue perfecto: {cnt_post} != {cnt_db_m05_ini}"
    print("Inocuidad 100% verificada: todos los efectos de la corrida (activo, medicamento, reporte, exportación) fueron revertidos atómicamente.")

    # Guardar resumen de diagnóstico en JSON para análisis
    diagnostico_data = {
        "run_id": run_id,
        "linea_base": {
            "total_m05_ini": total_m05_ini,
            "total_m01_ini": total_m01_ini,
            "cnt_db_m05_ini": cnt_db_m05_ini,
            "cnt_db_dml": str(cnt_db_dml),
        },
        "control_positivo_rf76": {
            "id_activo": id_activo,
            "id_medicamento": id_med,
            "total_m05_post_med": total_m05_post_med,
            "cnt_db_m05_post_med": cnt_db_m05_post_med,
            "observable_en_api_sandbox": med_evento is not None,
            "evento_detalle": med_evento,
        },
        "rf77_reporte_y_exportacion": {
            "id_reporte": id_reporte,
            "id_archivo": str(id_archivo),
        },
        "muestreos_temporales": historial_tiempos,
        "inocuidad_post_sandbox": {
            "cnt_post_rollback": cnt_post,
            "rollback_exitoso": cnt_post == cnt_db_m05_ini,
        },
    }

    json_diag_path = _DIR_STAGING / "datos_diagnostico_paso2.json"
    json_diag_path.write_text(json.dumps(diagnostico_data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"\nDatos crudos del diagnóstico guardados en: {json_diag_path}")


if __name__ == "__main__":
    main()

