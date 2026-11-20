# | Fecha      | Nombre                   | Que se hizo                                                                                     |
# |------------|--------------------------|-------------------------------------------------------------------------------------------------|
# | 2026-11-15 | Juan Sebastian Gutierrez | Verificacion de solo lectura del formato de detalle_causa (RF-80 CA-12) en TEST: API y catalogo de BD |
"""Verificacion SOLO LECTURA del formato de detalle_causa en TEST (RF-80 v2.0 CA-12; hallazgo A04b de G37 reintento 2).

Parte A (API, evidencia valida): corrida sandbox propia, UN login de Administrador, GET /suministros/auditoria
(ultimas paginas) y GET /suministros/auditoria/{id} de muestras; cierre DELETE /test-control/runs/{run_id}.
No crea, modifica ni borra nada (todo GET + rollback del sandbox).

Parte B (BD, conexion directa en modo read_only): codigo fuente desplegado del trigger
modulo5.fn_sellar_auditoria_m05 (pg_proc), version de alembic y conteo de filas visibles de
modulo5.auditorias_suministros. Si RLS oculta filas, el conteo se informa como NO CONCLUYENTE.

Credenciales: solo desde .env.test, en memoria; nunca se imprimen. El informe se escanea al final
(exit 4 si contiene un secreto). Exit 0 = informe generado; 2 = no verificable (falta configuracion).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from dotenv import dotenv_values

ZONA = timezone(timedelta(hours=-5))
PAGINAS = 10
POR_PAGINA = 100

# Nombres de campo de la Restriccion 8 (como en la ficha y en la API) y su forma "visible" del PR #1145.
CAMPOS = ("id_activo_biologico", "id_ciclo_productivo", "id_registro_suministro", "id_tipo_suministro",
          "costo_afectado", "origen_precio", "numero_reintentos", "timestamps_intentos", "fecha_intentos")
VISIBLES = ("activo biológico", "ciclo productivo", "registro de suministro", "tipo de suministro",
            "costo afectado", "origen del precio", "número de reintentos", "fechas de los intentos")


def _formato(detalle: str) -> str:
    """Clasifica la lista que sigue a 'Campos faltantes:' como NOMBRE_CAMPO, PALABRAS, MIXTO o SIN_LISTA."""
    if "Campos faltantes:" not in detalle:
        return "SIN_LISTA"
    lista = detalle.split("Campos faltantes:", 1)[1]
    con_nombre = any(re.search(rf"(?<![A-Za-z0-9_]){c}(?![A-Za-z0-9_])", lista) for c in CAMPOS)
    con_palabras = any(v in lista for v in VISIBLES)
    if con_nombre and con_palabras:
        return "MIXTO"
    if con_nombre:
        return "NOMBRE_CAMPO"
    if con_palabras:
        return "PALABRAS"
    return "OTRO"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", required=True)
    ap.add_argument("--salida", required=True)
    args = ap.parse_args()

    env = dotenv_values(Path(args.repo_root) / ".env.test")
    base = (env.get("TEST_BASE_URL") or "").rstrip("/")
    secreto = env.get("TEST_SANDBOX_SECRET") or ""
    correo = env.get("TEST_ADMIN_EMAIL") or ""
    clave = env.get("TEST_ADMIN_PASSWORD") or ""
    secretos = [v for k, v in env.items() if v and any(t in k for t in ("PASSWORD", "SECRET", "TOKEN", "EMAIL", "DATABASE_URL"))]
    secretos += [v[-20:] for v in list(secretos) if len(v) >= 20]

    L: list[str] = [
        "VERIFICACION SOLO LECTURA - FORMATO DE detalle_causa (RF-80 v2.0 CA-12) - TC-M05-G37 / A04b",
        f"Fecha/Hora: {datetime.now(ZONA).strftime('%Y-%m-%d %H:%M:%S')} (America/Bogota)",
        "Esperado (RF-80 v2.0 CA-12): detalle_causa = 'Campos faltantes: numero_reintentos, timestamps_intentos' (nombres de campo)",
        "",
    ]
    if not (base and secreto and correo and clave):
        L.append("RESULTADO: NO_VERIFICABLE (faltan variables en .env.test)")
        Path(args.salida).write_text("\n".join(L) + "\n", encoding="utf-8")
        return 2

    # ---------------- PARTE A: API ----------------
    L.append("== PARTE A: API autenticada (corrida sandbox, solo GET)")
    run_id = f"tc-m05-g37-verifca12-{uuid.uuid4().hex[:8]}"
    s = requests.Session()
    s.headers.update({"X-Test-Run-Id": run_id, "X-Sandbox-Secret": secreto})
    r_cierre = None
    try:
        r = s.post(f"{base}/sesiones/", json={"correo_electronico": correo, "contrasena": clave}, timeout=30)
        L.append(f"POST /sesiones/ -> HTTP {r.status_code} [X-Request-Id={r.headers.get('X-Request-Id')}]")
        if r.status_code not in (200, 201):
            L.append("RESULTADO PARTE A: NO_VERIFICABLE (login fallido)")
        else:
            cuerpo = r.json()
            token = cuerpo.get("token") or cuerpo.get("access_token")
            s.headers["Authorization"] = f"Bearer {token}"
            token = None
            eventos = []
            for pagina in range(1, PAGINAS + 1):
                rp = s.get(f"{base}/suministros/auditoria", timeout=30,
                           params={"pagina": pagina, "registros_por_pagina": POR_PAGINA, "ordenar_por": "fecha_evento"})
                L.append(f"GET /suministros/auditoria pagina={pagina} -> HTTP {rp.status_code} [X-Request-Id={rp.headers.get('X-Request-Id')}]")
                if rp.status_code != 200:
                    break
                datos = rp.json()
                if pagina == 1:
                    L.append(f"  total en la bitacora: {datos.get('total')}")
                items = datos.get("items") or []
                eventos.extend(items)
                if len(items) < POR_PAGINA:
                    break
            incompletos = [e for e in eventos if e.get("registro_incompleto") is True]
            conteo: dict[str, int] = {}
            for e in incompletos:
                f = _formato(e.get("detalle_causa") or "")
                conteo[f] = conteo.get(f, 0) + 1
            ids = [int(e["id_auditoria_suministro"]) for e in eventos] or [0]
            L.append(f"Eventos leidos: {len(eventos)} (ids {min(ids)}..{max(ids)}); con registro_incompleto=true: {len(incompletos)}")
            L.append(f"Formato de la lista tras 'Campos faltantes:' en los incompletos: {json.dumps(conteo, ensure_ascii=False)}")
            L.append("Muestras (hasta 10 incompletos mas recientes con lista de campos):")
            muestras = [e for e in incompletos if "Campos faltantes:" in (e.get("detalle_causa") or "")][:10]
            for e in muestras:
                L.append("  " + json.dumps({
                    "id": e.get("id_auditoria_suministro"), "tipo_operacion": e.get("tipo_operacion"),
                    "resultado": e.get("resultado"), "fecha_emision": e.get("fecha_emision"),
                    "version_hash_integridad": e.get("version_hash_integridad"),
                    "hash_integridad_12": (e.get("hash_integridad") or "")[:12],
                    "formato": _formato(e.get("detalle_causa") or ""),
                    "detalle_causa": e.get("detalle_causa"),
                }, ensure_ascii=False))
            for e in muestras[:3]:
                rd = s.get(f"{base}/suministros/auditoria/{e['id_auditoria_suministro']}", timeout=30)
                igual = rd.status_code == 200 and rd.json().get("detalle_causa") == e.get("detalle_causa")
                L.append(f"GET /suministros/auditoria/{e['id_auditoria_suministro']} -> HTTP {rd.status_code} "
                         f"[X-Request-Id={rd.headers.get('X-Request-Id')}] detalle_causa igual a la lista: {igual}")
            if not muestras:
                L.append("  (ninguno: en las ultimas paginas no hay eventos incompletos persistidos con lista de campos)")
    except requests.RequestException as exc:
        L.append(f"ERROR_CONEXION API: {type(exc).__name__}")
    finally:
        try:
            r_cierre = s.delete(f"{base}/test-control/runs/{run_id}", timeout=30)
            L.append(f"DELETE /test-control/runs/{{run_id}} -> HTTP {r_cierre.status_code} [X-Request-Id={r_cierre.headers.get('X-Request-Id')}]")
        except requests.RequestException as exc:
            L.append(f"DELETE /test-control/runs/{{run_id}} -> ERROR_CONEXION {type(exc).__name__}")
        s.close()

    # ---------------- PARTE B: BD (read_only) ----------------
    L.append("")
    L.append("== PARTE B: base de datos de TEST (conexion directa, default_transaction_read_only=on)")
    try:
        import psycopg2
    except ImportError:
        psycopg2 = None
        L.append("psycopg2 no disponible: PARTE B NO_VERIFICABLE")
    url = (env.get("TEST_DATABASE_URL") or "").replace("postgresql+psycopg2://", "postgresql://")
    if psycopg2 is not None and url:
        con = None
        try:
            con = psycopg2.connect(url, connect_timeout=15, options="-c default_transaction_read_only=on")
            cur = con.cursor()
            cur.execute("SHOW transaction_read_only")
            L.append(f"transaction_read_only = {cur.fetchone()[0]}")
            cur.execute("SELECT version_num FROM public.alembic_version")
            L.append(f"alembic_version: {[f[0] for f in cur.fetchall()]}")
            cur.execute(
                "SELECT p.prosrc FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace "
                "WHERE n.nspname = 'modulo5' AND p.proname = 'fn_sellar_auditoria_m05'"
            )
            fila = cur.fetchone()
            if fila is None:
                L.append("fn_sellar_auditoria_m05: NO EXISTE en TEST")
            else:
                src = fila[0]
                appends = re.findall(r"array_append\(v_faltantes,\s*'([^']*)'\)", src)
                L.append(f"fn_sellar_auditoria_m05 desplegada: si; valores que agrega a 'Campos faltantes': {appends}")
                L.append(f"  usa nombres de campo (id_activo_biologico / id_ciclo_productivo): "
                         f"{any(a in ('id_activo_biologico', 'id_ciclo_productivo') for a in appends)}")
                L.append(f"  calcula el hash DESPUES de escribir detalle_causa: "
                         f"{src.find('detalle_causa :=') != -1 and src.find('hash_integridad :=') > src.find('detalle_causa :=')}")
            cur.execute("SELECT count(*) FROM modulo5.auditorias_suministros")
            visibles = cur.fetchone()[0]
            L.append(f"Filas visibles en modulo5.auditorias_suministros para este usuario: {visibles}"
                     + ("  (0 = oculto por RLS; NO CONCLUYENTE, no se usa como evidencia)" if visibles == 0 else ""))
            if visibles:
                cur.execute(
                    "SELECT id_auditoria_suministro, tipo_operacion::text, detalle_causa FROM modulo5.auditorias_suministros "
                    "WHERE registro_incompleto AND detalle_causa LIKE '%%Campos faltantes:%%' "
                    "ORDER BY id_auditoria_suministro DESC LIMIT 5"
                )
                for fid, tipo, det in cur.fetchall():
                    L.append("  BD " + json.dumps({"id": fid, "tipo_operacion": tipo, "formato": _formato(det or ""), "detalle_causa": det}, ensure_ascii=False))
            con.rollback()
        except Exception as exc:
            L.append(f"PARTE B NO_VERIFICABLE: {type(exc).__name__}")
        finally:
            if con is not None:
                con.close()

    texto = "\n".join(L) + "\n"
    hallazgos = [i for i, v in enumerate(secretos) if v and len(v) > 3 and v in texto]
    prefijo = "ey" + "J"
    if prefijo in texto:
        hallazgos.append(-1)
    Path(args.salida).write_text(texto, encoding="utf-8")
    print(texto)
    if hallazgos:
        print(f"ESCANEO DE SECRETOS: {len(hallazgos)} hallazgo(s) en el informe. NO compartir.")
        return 4
    print("ESCANEO DE SECRETOS: LIMPIO")
    return 0


if __name__ == "__main__":
    sys.exit(main())
