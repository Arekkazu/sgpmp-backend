"""Fase 1 Task B (solo lectura) para TC-M05-G18 (RF-76) en ambiente TEST via sandbox."""
from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests
from dotenv import dotenv_values

try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    try:
        ZONA_USUARIO = ZoneInfo("America/Bogota")
    except ZoneInfoNotFoundError:
        ZONA_USUARIO = timezone(timedelta(hours=-5), "America/Bogota")
except ImportError:
    ZONA_USUARIO = timezone(timedelta(hours=-5), "America/Bogota")

RAIZ = Path(__file__).resolve().parents[7]
if not (RAIZ / ".env.test").exists():
    RAIZ = Path.cwd()
ENV_TEST = dotenv_values(RAIZ / ".env.test") if (RAIZ / ".env.test").exists() else {}
OUT_JSON = Path(__file__).resolve().parent / "b_resultado.json"

VARS_CHECK = [
    "TEST_BASE_URL",
    "TEST_SANDBOX_SECRET",
    "TEST_ADMIN_EMAIL",
    "TEST_ADMIN_PASSWORD",
    "TEST_PRODUCER_EMAIL",
    "TEST_PRODUCER_PASSWORD",
    "TEST_VET_EMAIL",
    "TEST_VET_PASSWORD",
    "TEST_ACCOUNTANT_EMAIL",
    "TEST_ACCOUNTANT_PASSWORD",
    "TEST_FISCAL_REVIEWER_EMAIL",
    "TEST_FISCAL_REVIEWER_PASSWORD",
    "TEST_FIELD_ENGINEER_EMAIL",
    "TEST_FIELD_ENGINEER_PASSWORD",
    "TEST_FARM_MANAGER_EMAIL",
    "TEST_FARM_MANAGER_PASSWORD",
    "TEST_M05_ACTIVO_ID",
    "TEST_DATABASE_URL",
]


def _env(nombre: str) -> str:
    return (os.environ.get(nombre) or ENV_TEST.get(nombre) or "").strip()


def _secretos() -> list[str]:
    res = []
    for k in (
        "TEST_SANDBOX_SECRET",
        "TEST_ADMIN_PASSWORD",
        "TEST_ADMIN_EMAIL",
        "TEST_PRODUCER_PASSWORD",
        "TEST_PRODUCER_EMAIL",
        "TEST_VET_PASSWORD",
        "TEST_VET_EMAIL",
        "TEST_FIELD_ENGINEER_PASSWORD",
        "TEST_FIELD_ENGINEER_EMAIL",
        "TEST_DATABASE_URL",
    ):
        v = _env(k)
        if v:
            res.append(v)
    return res


def _sanitizar(obj: Any) -> Any:
    if isinstance(obj, str):
        s = obj
        for sec in _secretos():
            s = s.replace(sec, "***")
        jwt_pref = "ey" + "J"
        if jwt_pref in s:
            s = s.replace(jwt_pref, "[JWT_OMITIDO]")
        return s
    if isinstance(obj, list):
        return [_sanitizar(x) for x in obj]
    if isinstance(obj, dict):
        return {str(k): _sanitizar(v) for k, v in obj.items()}
    return obj


def main() -> None:
    base = _env("TEST_BASE_URL").rstrip("/")
    secret = _env("TEST_SANDBOX_SECRET")
    admin_email = _env("TEST_ADMIN_EMAIL")
    admin_pwd = _env("TEST_ADMIN_PASSWORD")
    assert base and secret and admin_email and admin_pwd, "Faltan variables base en .env.test"

    resultado: dict[str, Any] = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "timestamp_bogota": datetime.now(ZONA_USUARIO).isoformat(),
        "env_check": {k: ("PRESENTE" if _env(k) else "AUSENTE") for k in VARS_CHECK},
        "run_id": f"tc-m05-g18-fase1-b-{uuid.uuid4().hex[:8]}",
        "login": {},
        "queries": {},
        "api_gets": {},
        "close": {},
    }

    s = requests.Session()
    s.headers.update(
        {
            "X-Test-Run-Id": resultado["run_id"],
            "X-Sandbox-Secret": secret,
            "X-Zona-Horaria": "America/Bogota",
        }
    )

    try:
        # Un solo login por run_id
        for intento in range(7):
            r_login = s.post(
                f"{base}/sesiones/",
                json={"correo_electronico": admin_email, "contrasena": admin_pwd},
                timeout=45,
            )
            if r_login.status_code in (423, 429) and intento < 6:
                time.sleep(30)
                continue
            break

        body_login = {}
        try:
            body_login = r_login.json()
        except ValueError:
            pass
        token = body_login.get("token")
        resultado["login"] = {
            "http": r_login.status_code,
            "tiene_token": bool(token),
            "claves_body": sorted(body_login.keys()) if isinstance(body_login, dict) else [],
            "usuario": {
                k: body_login.get("usuario", {}).get(k)
                for k in ("id_usuario", "id_rol", "nombre_rol")
                if isinstance(body_login.get("usuario"), dict)
            },
        }
        assert r_login.status_code == 200 and token, f"Login fallo HTTP {r_login.status_code}"
        s.headers["Authorization"] = f"Bearer {token}"

        queries = {
            "b1_db_identity": "SELECT current_user, session_user, current_database()",
            "b1_permisos_48": (
                "SELECT p.id_permiso, p.id_rol, r.nombre_rol, p.id_recurso, rec.nombre_recurso, "
                "p.id_accion, p.nombre, p.es_activo "
                "FROM modulo1.permisos p "
                "JOIN modulo1.roles r ON r.id_rol = p.id_rol "
                "JOIN modulo1.recursos rec ON rec.id_recurso = p.id_recurso "
                "WHERE p.id_recurso = 48 OR rec.nombre_recurso = 'medicamentos' "
                "ORDER BY p.id_rol, p.id_accion"
            ),
            "b1_acciones": "SELECT * FROM modulo1.acciones ORDER BY 1",
            "b1_roles": "SELECT id_rol, nombre_rol, es_protegido FROM modulo1.roles ORDER BY id_rol",
            "b2_estados_cat": "SELECT * FROM modulo2.estados_activos_biologicos ORDER BY 1",
            "b2_activos_853_5": (
                "SELECT a.id_activo_biologico, a.tipo, a.id_estado, e.nombre AS estado, "
                "a.fecha_inicio_ciclo, a.id_especie, a.id_infraestructura "
                "FROM modulo2.activos_biologicos a "
                "JOIN modulo2.estados_activos_biologicos e ON e.id_estado_activo_biologico = a.id_estado "
                "WHERE a.id_activo_biologico IN (853, 5) "
                "ORDER BY a.id_activo_biologico"
            ),
            "b2_fases_853_5": (
                "SELECT id_gestion_fases, id_activo_biologico, id_ciclo_productiva, "
                "fecha_inicio, fecha_finalizacion, es_activa "
                "FROM modulo2.gestiones_fases "
                "WHERE id_activo_biologico IN (853, 5) "
                "ORDER BY id_activo_biologico, id_gestion_fases DESC"
            ),
            "b2_historico_estados_853_5": (
                "SELECT id_historico_estado_activo, id_activo_biologico, id_estado_anterior, "
                "id_estado_nuevo, fecha_cambio, modulo_origen "
                "FROM modulo2.historicos_estados_activos "
                "WHERE id_activo_biologico IN (853, 5) "
                "ORDER BY id_activo_biologico, id_historico_estado_activo DESC"
            ),
            "b2_meds_853_5": (
                "SELECT id_registro_medicamento, id_activo_biologico, nombre_medicamento, "
                "via_aplicacion, fecha_aplicacion, hora_aplicacion, periodo_retiro_dias, "
                "fecha_fin_retiro, estado_registro "
                "FROM modulo5.registros_medicamentos "
                "WHERE id_activo_biologico IN (853, 5) "
                "ORDER BY id_activo_biologico, id_registro_medicamento DESC"
            ),
            "b3_meds_catalogo_uso": (
                "SELECT lower(nombre_medicamento) AS med, periodo_retiro_dias, via_aplicacion, "
                "unidad_dosis, count(*) AS cnt "
                "FROM modulo5.registros_medicamentos "
                "GROUP BY lower(nombre_medicamento), periodo_retiro_dias, via_aplicacion, unidad_dosis "
                "ORDER BY cnt DESC"
            ),
            "b3_oxitetraciclina": (
                "SELECT id_registro_medicamento, id_activo_biologico, nombre_medicamento, "
                "via_aplicacion, cantidad, unidad_dosis, periodo_retiro_dias, costo_unitario_medicamento, "
                "estado_registro "
                "FROM modulo5.registros_medicamentos "
                "WHERE lower(nombre_medicamento) LIKE '%oxitetraciclina%' "
                "ORDER BY id_registro_medicamento DESC"
            ),
            "b3_tablas_m5_m9": (
                "SELECT table_schema, table_name FROM information_schema.tables "
                "WHERE table_schema IN ('modulo5', 'modulo9', 'modulo2') "
                "ORDER BY table_schema, table_name"
            ),
            "b4_activos_en_tratamiento_cnt": (
                "SELECT count(*) AS total_en_tratamiento FROM modulo2.activos_biologicos WHERE id_estado = 3"
            ),
            "b4_activos_en_tratamiento_detalle": (
                "SELECT a.id_activo_biologico, a.id_estado, max(m.fecha_fin_retiro) AS max_retiro, "
                "count(m.id_registro_medicamento) AS meds_validados, "
                "CURRENT_DATE AS pg_current_date, (now() AT TIME ZONE 'America/Bogota')::date AS bogota_date "
                "FROM modulo2.activos_biologicos a "
                "LEFT JOIN modulo5.registros_medicamentos m "
                "ON m.id_activo_biologico = a.id_activo_biologico AND m.estado_registro = 'VALIDADO' "
                "WHERE a.id_estado = 3 "
                "GROUP BY a.id_activo_biologico, a.id_estado "
                "ORDER BY a.id_activo_biologico"
            ),
            "b4_triggers_registros_med": (
                "SELECT tgname, tgenabled "
                "FROM pg_trigger "
                "WHERE tgrelid = 'modulo5.registros_medicamentos'::regclass AND NOT tgisinternal "
                "ORDER BY tgname"
            ),
            "b4_tablas_batch_cron": (
                "SELECT table_schema, table_name FROM information_schema.tables "
                "WHERE table_name ILIKE '%batch%' OR table_name ILIKE '%job%' "
                "OR table_name ILIKE '%retiro%' OR table_schema = 'cron' "
                "ORDER BY table_schema, table_name"
            ),
            "b5_conteo_853_5": (
                "SELECT id_activo_biologico, estado_registro, count(*) AS total "
                "FROM modulo5.registros_medicamentos "
                "WHERE id_activo_biologico IN (853, 5) "
                "GROUP BY id_activo_biologico, estado_registro "
                "ORDER BY id_activo_biologico, estado_registro"
            ),
            "b5_conteo_global": (
                "SELECT count(*) AS total_meds, "
                "(SELECT count(*) FROM modulo5.auditorias_suministros) AS total_auditoria "
                "FROM modulo5.registros_medicamentos"
            ),
        }

        for nombre, sql in queries.items():
            rq = s.post(f"{base}/test-control/query", json={"query": sql}, timeout=45)
            try:
                qbody = rq.json()
            except ValueError:
                qbody = {"raw": rq.text[:400]}
            resultado["queries"][nombre] = {
                "http": rq.status_code,
                "body": qbody,
            }

        for label, ruta in (
            ("me_permisos", "/sesiones/me/permisos"),
            ("activos_en_tratamiento", "/activos-biologicos?id_estado=3&page_size=100"),
            ("activo_853", "/activos-biologicos/853"),
            ("activo_853_fases", "/activos-biologicos/853/fases"),
            ("activo_853_ciclos", "/activos-biologicos/853/ciclos-productivos"),
            ("meds_853", "/suministros/medicamentos?id_activo_biologico=853"),
            ("activo_5", "/activos-biologicos/5"),
            ("activo_5_fases", "/activos-biologicos/5/fases"),
            ("meds_5", "/suministros/medicamentos?id_activo_biologico=5"),
        ):
            rg = s.get(f"{base}{ruta}", timeout=45)
            try:
                gbody = rg.json()
            except ValueError:
                gbody = {"raw": rg.text[:400]}
            resultado["api_gets"][label] = {
                "http": rg.status_code,
                "body": gbody,
            }

        # Si hay activos EN_TRATAMIENTO, consultar sus medicamentos VALIDADOS
        et_body = resultado["api_gets"].get("activos_en_tratamiento", {}).get("body") or {}
        et_items = et_body.get("registros") or et_body.get("items") or []
        et_meds = {}
        et_ids = []
        for item in et_items[:30]:
            aid = item.get("id_activo_biologico")
            if aid:
                et_ids.append(int(aid))
                rm = s.get(
                    f"{base}/suministros/medicamentos",
                    params={"id_activo_biologico": aid, "estado_registro": "VALIDADO"},
                    timeout=45,
                )
                try:
                    mb = rm.json()
                except ValueError:
                    mb = {"raw": rm.text[:300]}
                et_meds[str(aid)] = {"http": rm.status_code, "body": mb}
        resultado["api_gets"]["activos_en_tratamiento_meds"] = et_meds
        if et_ids:
            ids_csv = ", ".join(str(x) for x in et_ids)
            rq_et = s.post(
                f"{base}/test-control/query",
                json={
                    "query": (
                        "SELECT id_activo_biologico, max(fecha_fin_retiro) AS max_retiro, "
                        "count(*) AS cnt_validados, "
                        "(now() AT TIME ZONE 'America/Bogota')::date AS bogota_hoy "
                        "FROM modulo5.registros_medicamentos "
                        f"WHERE estado_registro = 'VALIDADO' AND id_activo_biologico IN ({ids_csv}) "
                        "GROUP BY id_activo_biologico ORDER BY id_activo_biologico"
                    )
                },
                timeout=45,
            )
            resultado["queries"]["b4_en_tratamiento_sql_meds"] = {
                "http": rq_et.status_code,
                "body": rq_et.json(),
            }

    finally:
        try:
            rc = s.delete(f"{base}/test-control/runs/{resultado['run_id']}", timeout=45)
            try:
                cbody = rc.json()
            except ValueError:
                cbody = {"raw": rc.text[:200]}
            resultado["close"] = {"http": rc.status_code, "body": cbody}
        except Exception as exc:
            resultado["close"] = {"error": f"{type(exc).__name__}: {exc}"}
        s.close()

    # Verificar permisos sobre recurso 48 de otros roles disponibles en .env.test (corridas secuenciales)
    roles_env_permisos: dict[str, Any] = {}
    for etiqueta, k_email, k_pwd in (
        ("vet", "TEST_VET_EMAIL", "TEST_VET_PASSWORD"),
        ("producer", "TEST_PRODUCER_EMAIL", "TEST_PRODUCER_PASSWORD"),
        ("field_engineer", "TEST_FIELD_ENGINEER_EMAIL", "TEST_FIELD_ENGINEER_PASSWORD"),
    ):
        u_email = _env(k_email)
        u_pwd = _env(k_pwd)
        if not u_email or not u_pwd:
            roles_env_permisos[etiqueta] = {"omitido": "credenciales ausentes"}
            continue
        rid = f"tc-m05-g18-fase1-rbac-{etiqueta}-{uuid.uuid4().hex[:6]}"
        sr = requests.Session()
        sr.headers.update(
            {
                "X-Test-Run-Id": rid,
                "X-Sandbox-Secret": secret,
                "X-Zona-Horaria": "America/Bogota",
            }
        )
        info_r: dict[str, Any] = {"run_id": rid}
        try:
            rl = sr.post(
                f"{base}/sesiones/",
                json={"correo_electronico": u_email, "contrasena": u_pwd},
                timeout=45,
            )
            bl = rl.json() if rl.headers.get("content-type", "").startswith("application/json") else {}
            tok = bl.get("token")
            info_r["login_http"] = rl.status_code
            if rl.status_code == 200 and tok:
                sr.headers["Authorization"] = f"Bearer {tok}"
                rp = sr.get(f"{base}/sesiones/me/permisos", timeout=45)
                bp = rp.json() if rp.status_code == 200 else {}
                perms = [p for p in bp.get("permisos", []) if p.get("id_recurso") == 48]
                info_r["permisos_http"] = rp.status_code
                info_r["recurso_48_acciones"] = sorted(
                    {p.get("id_accion") for p in perms if p.get("id_accion") is not None}
                )
            else:
                info_r["error_code"] = bl.get("error_code")
        finally:
            try:
                rc = sr.delete(f"{base}/test-control/runs/{rid}", timeout=45)
                info_r["close"] = {"http": rc.status_code, "body": rc.json()}
            except Exception as exc:
                info_r["close"] = {"error": str(exc)}
            sr.close()
        roles_env_permisos[etiqueta] = info_r
    resultado["roles_env_permisos"] = roles_env_permisos

    # Inspeccion adicional solo lectura sobre TEST_DATABASE_URL (verifica rol_qa / RLS / B1 / B4)
    db_url = _env("TEST_DATABASE_URL")
    direct_db: dict[str, Any] = {}
    if db_url:
        import psycopg2

        conn = psycopg2.connect(db_url)
        conn.set_session(readonly=True, autocommit=True)
        try:
            cur = conn.cursor()
            checks = {
                "identidad": "SELECT current_user, session_user, current_database()",
                "privilegios_fn": (
                    "SELECT "
                    "has_function_privilege(current_user, 'modulo2.fn_activos_del_usuario(integer)', 'EXECUTE') AS fn_m2, "
                    "has_function_privilege(current_user, 'modulo1.fn_id_usuario_por_correo(character varying)', 'EXECUTE') AS fn_m1"
                ),
                "permisos_recurso_48": (
                    "SELECT p.id_permiso, p.id_rol, r.nombre_rol, p.id_recurso, rec.nombre_recurso, "
                    "p.id_accion, a.codigo AS accion_codigo, p.nombre, p.es_activo "
                    "FROM modulo1.permisos p "
                    "JOIN modulo1.roles r ON r.id_rol = p.id_rol "
                    "JOIN modulo1.recursos rec ON rec.id_recurso = p.id_recurso "
                    "JOIN modulo1.acciones a ON a.id_accion = p.id_accion "
                    "WHERE p.id_recurso = 48 "
                    "ORDER BY p.id_rol, p.id_accion"
                ),
                "activos_853_5": (
                    "SELECT a.id_activo_biologico, a.tipo, a.id_estado, e.nombre AS estado, a.fecha_inicio_ciclo "
                    "FROM modulo2.activos_biologicos a "
                    "JOIN modulo2.estados_activos_biologicos e ON e.id_estado_activo_biologico = a.id_estado "
                    "WHERE a.id_activo_biologico IN (853, 5) ORDER BY a.id_activo_biologico"
                ),
                "gestiones_fases_853": (
                    "SELECT id_gestion_fases, id_activo_biologico, es_activa "
                    "FROM modulo2.gestiones_fases WHERE id_activo_biologico = 853"
                ),
                "en_tratamiento_detalle": (
                    "SELECT a.id_activo_biologico, a.id_estado, max(m.fecha_fin_retiro) AS max_retiro, "
                    "count(m.id_registro_medicamento) AS meds_validados, "
                    "(now() AT TIME ZONE 'America/Bogota')::date AS bogota_date "
                    "FROM modulo2.activos_biologicos a "
                    "LEFT JOIN modulo5.registros_medicamentos m "
                    "ON m.id_activo_biologico = a.id_activo_biologico AND m.estado_registro = 'VALIDADO' "
                    "WHERE a.id_estado = 3 "
                    "GROUP BY a.id_activo_biologico, a.id_estado "
                    "ORDER BY a.id_activo_biologico"
                ),
                "triggers_medicamentos": (
                    "SELECT t.tgname, pg_get_triggerdef(t.oid) AS def "
                    "FROM pg_trigger t "
                    "WHERE t.tgrelid = 'modulo5.registros_medicamentos'::regclass AND NOT t.tgisinternal "
                    "ORDER BY t.tgname"
                ),
            }
            for k, sql in checks.items():
                try:
                    cur.execute(sql)
                    cols = [d[0] for d in cur.description] if cur.description else []
                    rows = [dict(zip(cols, row)) for row in cur.fetchall()]
                    direct_db[k] = {"ok": True, "rows": rows}
                except Exception as exc:
                    direct_db[k] = {"ok": False, "error": f"{type(exc).__name__}: {str(exc).splitlines()[0]}"}
        finally:
            conn.close()
    resultado["direct_db_readonly"] = direct_db

    OUT_JSON.write_text(
        json.dumps(_sanitizar(resultado), indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print(f"OK escrito {OUT_JSON}")
    print("Close:", resultado["close"])


if __name__ == "__main__":
    main()
