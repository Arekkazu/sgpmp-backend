"""TC-M09-150-v2.0 — Atomicidad del registro de calibración ante fallo real de auditoría.

RF-24 v2.0 / CU05 Flujo D. Laboratorio LOCAL AISLADO con PostgreSQL real y backend HTTP real.
Sin fakes ni mocks de Session, repositorios, use case o transacción: el POST viaja por HTTP al
backend real y el rollback se comprueba con SQL contra la base.

Cadena que debe demostrarse:
    calibración válida -> la escritura alcanza la transacción de persistencia
    -> falla el INSERT de auditoría por privilegios -> rollback -> HTTP 500 con el mensaje del FA
    -> ninguna calibración nueva persistida.

Presupuesto de escrituras funcionales del RUN: 1 POST de control positivo y 1 POST objetivo.
Nunca se reintenta un POST. La restauración de privilegios ocurre en `finally`, de modo que no
depende de que una assertion pase ni del orden de los tests.

Ejecución:
    pytest test_tc_m09_150_v2.py -v
con el entorno del laboratorio ya preparado (ver README.md).
"""

from __future__ import annotations

import json
import os
from decimal import Decimal

import pytest

import helpers_g79_v2 as H

RUN_ID = os.environ["G79_RUN_ID"]
EV = H.Evidencia(RUN_ID)


def _dec(valor) -> Decimal:
    return Decimal(str(valor))


@pytest.fixture(scope="module")
def conn():
    c = H.conexion_admin()
    yield c
    c.close()


@pytest.fixture(scope="module")
def api():
    return H.ApiCliente()


def test_tc_m09_150_v2_atomicidad_ante_fallo_de_auditoria(conn, api):
    resultado: dict = {
        "grupo": H.GROUP_ID, "caso": H.CASO, "requisito": H.RF, "casoDeUso": H.CU,
        "runId": RUN_ID, "ambiente": "LOCAL AISLADO",
        "postgresReal": True, "backendHttpReal": True, "fakesDePersistencia": False,
    }

    # ----------------------------------------------------- 1. safety guard de BD local
    guard = H.safety_guard(conn)
    EV.json("environment_guard.json", guard)
    resultado["safetyGuard"] = guard["resultado"]
    assert guard["resultado"] == "PASS"

    version = H.uno(conn, "SELECT version()")
    EV.texto("postgres_version.txt", str(version))
    resultado["postgresVersion"] = str(version)

    # ----------------------------------------------------- 2. migraciones al día
    alembic_actual = H.uno(conn, "SELECT version_num FROM alembic_version")
    rc_heads, heads = H.run_cmd(["docker", "exec", H.CONTAINER_DB, "psql", "-U", H.OWNER_ESPERADO,
                                 "-d", H.BD_ESPERADA, "-tAc", "SELECT version_num FROM alembic_version"])
    EV.texto("alembic_state.txt",
             f"alembic_version en la BD: {alembic_actual}\n"
             f"consulta de control (rc={rc_heads}): {heads.strip()}\n")
    resultado["alembicVersion"] = str(alembic_actual)
    assert alembic_actual, "la base no tiene estado de alembic: migraciones no aplicadas"

    EV.json("db_identity_pre.json", H.filas(conn, "SELECT current_database() AS db, current_user AS usuario"))

    # ----------------------------------------------------- 3. rol de BD de la aplicación
    rol = H.rol_app(conn)
    owners = H.owners_tablas(conn)
    EV.json("db_role_pre.json", rol)
    EV.json("table_owners_pre.json", owners)
    resultado["appRole"] = rol
    resultado["ownersTablas"] = owners

    assert rol["rolcanlogin"] is True, "el rol de la aplicación debe poder autenticarse"
    # Condición crítica: si la app fuese owner o superusuario, el REVOKE no sería un fault real.
    assert rol["rolsuper"] is False, "el rol de la aplicación NO puede ser superusuario"
    assert all(o["tableowner"] != H.APP_ROLE for o in owners), \
        "el rol de la aplicación NO puede ser owner de las tablas implicadas"

    # ----------------------------------------------------- 4. fixture del laboratorio
    fixture = H.filas(conn, """
        SELECT d.id_dispositivo_iot, d.serial, d.es_activo AS dispositivo_activo,
               s.id_sensores AS id_sensor, s.categoria::text AS categoria, s.es_activo AS sensor_activo,
               a.id_infraestructura, a.tiene_estado, a.fecha_finalizacion,
               r.valor_min, r.valor_max
        FROM modulo9.sensores s
        JOIN modulo9.dispositivos_iot d ON d.id_dispositivo_iot = s.id_dispositivo_iot
        JOIN modulo9.sensores_areas_asociadas a
          ON a.id_sensor = s.id_sensores AND a.tiene_estado = true AND a.fecha_finalizacion IS NULL
        JOIN modulo9.rangos_calibracion r ON r.categoria = s.categoria::text
        WHERE d.es_activo = true AND s.es_activo = true
        ORDER BY (s.categoria::text = 'TEMPERATURA') DESC, s.id_sensores
        LIMIT 1
    """)
    assert fixture, "BLOQUEADO: no hay fixture válido en el laboratorio (dispositivo activo + sensor activo + asociación vigente + rango)"
    fx = fixture[0]
    id_sensor = int(fx["id_sensor"])
    id_dispositivo = int(fx["id_dispositivo_iot"])
    id_area = int(fx["id_infraestructura"])
    # Valor estrictamente interior: punto medio exacto del rango, nunca una frontera.
    valor = (_dec(fx["valor_min"]) + _dec(fx["valor_max"])) / Decimal(2)
    assert _dec(fx["valor_min"]) < valor < _dec(fx["valor_max"]), "el valor debe ser interior, no una frontera"

    actor_db = H.filas(conn, """
        SELECT u.id_usuario, u.correo_electronico, r.nombre_rol, e.nombre AS estado_cuenta
        FROM modulo1.usuarios u
        JOIN modulo1.roles r ON r.id_rol = u.id_rol
        JOIN modulo1.cuentas_usuarios c ON c.id_usuario = u.id_usuario
        JOIN modulo1.estados_cuentas e ON e.id_estado_cuenta = c.id_estado_cuenta
        WHERE u.correo_electronico = %s
    """, (H.ACTOR_CORREO,))
    assert actor_db, f"BLOQUEADO: no existe la identidad {H.ACTOR_CORREO} en el laboratorio"
    actor = actor_db[0]
    assert actor["nombre_rol"] == H.ROL_ESPERADO
    assert actor["estado_cuenta"] == "Activo"

    EV.json("fixture.json", {
        "origen": "seed del laboratorio (sql/seed_fixture.sql) sobre migraciones reales",
        "id_dispositivo_iot": id_dispositivo, "serial": fx["serial"],
        "dispositivo_activo": fx["dispositivo_activo"],
        "id_sensor": id_sensor, "categoria": fx["categoria"], "sensor_activo": fx["sensor_activo"],
        "id_infraestructura": id_area, "asociacion_vigente": fx["tiene_estado"],
        "rango": {"min": str(fx["valor_min"]), "max": str(fx["valor_max"])},
        "valor_interior": str(valor),
    })
    resultado["fixture"] = {
        "id_dispositivo_iot": id_dispositivo, "serial": fx["serial"], "id_sensor": id_sensor,
        "categoria": fx["categoria"], "id_infraestructura": id_area,
        "rango": {"min": str(fx["valor_min"]), "max": str(fx["valor_max"])},
        "valor": str(valor),
    }

    # ----------------------------------------------------- preflight de salud y contrato
    assert api.health() == 200, "el backend local no responde /health"
    openapi = api.openapi()
    ruta_post = "/configuracion/sensores/{id_sensor}/calibrar"
    assert ruta_post in openapi.get("paths", {}) and "post" in openapi["paths"][ruta_post], \
        "el endpoint de calibración no está en el contrato del backend local"
    resultado["contrato"] = {
        "endpoint": f"POST {ruta_post}",
        "codigosDeclarados": sorted(openapi["paths"][ruta_post]["post"].get("responses", {}).keys()),
    }

    # ----------------------------------------------------- 5. token ANTES del fault
    login = api.login(H.ACTOR_CORREO, os.environ["G79_ING_PASSWORD"])
    assert login["status"] == 200 and login["tiene_token"], f"BLOQUEADO: el Ingeniero no autentica ({login})"
    perfil_status, perfil = api.get("/usuarios/me")
    assert perfil_status == 200
    assert perfil["nombre_rol"] == H.ROL_ESPERADO
    permisos_status, permisos = api.get("/sesiones/me/permisos")
    assert permisos_status == 200
    acciones_12 = sorted({p["id_accion"] for p in (permisos.get("permisos") or []) if p.get("id_recurso") == 12})
    assert 1 in acciones_12, "el actor debe tener permiso de registro de calibración"

    EV.json("actor.json", {
        "correo_electronico": perfil["correo_electronico"], "id_usuario": perfil["id_usuario"],
        "nombre_rol": perfil["nombre_rol"], "estado_cuenta": actor["estado_cuenta"],
        "credencial": "[REDACTED]", "loginHttp": login["status"],
        "tokenObtenidoAntesDelFault": True,
        "accionesSobreRecurso12": acciones_12,
    })
    id_usuario = int(perfil["id_usuario"])
    resultado["actor"] = {"id_usuario": id_usuario, "correo": perfil["correo_electronico"],
                          "rol": perfil["nombre_rol"], "tokenAntesDelFault": True}

    # ----------------------------------------------------- 6-7. CONTROL POSITIVO (1 POST)
    priv_control = H.privilegios_app(conn)
    assert priv_control["calibraciones_insert"] and priv_control["audit_m9_insert"], \
        "BLOQUEADO: la app no tiene privilegios normales antes del fault"

    body_control = H.cuerpo_calibracion(id_dispositivo, id_area, str(valor), H.OBSERVACIONES_CONTROL)
    EV.json("control_request.json", {
        "endpoint": f"/configuracion/sensores/{id_sensor}/calibrar", "metodo": "POST",
        "headers": {"Authorization": "[REDACTED]", "Content-Type": "application/json"},
        "body": body_control,
    })
    marca_control = H.ahora_iso()
    status_control, cuerpo_control = api.calibrar(id_sensor, body_control)
    EV.json("control_response.json", {"http": status_control, "cuerpo": cuerpo_control})

    assert 200 <= status_control < 300, (
        f"BLOQUEADO / ENTORNO NO APTO PARA FAULT INJECTION: el control positivo falló "
        f"(HTTP {status_control}: {json.dumps(cuerpo_control, ensure_ascii=False)[:300]})"
    )
    id_control = cuerpo_control["id_calibracion"]
    fila_control = [f for f in H.rows_calibraciones(conn, id_sensor) if f["id_calibracion"] == id_control]
    assert fila_control, "el control positivo no persistió la calibración"
    auditoria_control = H.auditorias_de(conn, id_control)
    eventos_control = H.eventos_desde(conn, marca_control)

    EV.json("control_db_calibracion.json", fila_control)
    EV.json("control_db_auditoria_m9.json", auditoria_control)
    EV.json("control_db_eventos.json", {
        "eventosDesdeElControl": eventos_control,
        "nota": ("Se registra el comportamiento real del camino de éxito. G79 no añade una "
                 "expectativa de evento RF-10: su oráculo es la atomicidad de la calibración "
                 "ante el fallo de auditoría."),
    })
    assert auditoria_control, "el camino de éxito debe dejar auditoría en modulo9.auditorias_calibraciones"
    resultado["controlPositivo"] = {
        "http": status_control, "id_calibracion": id_control,
        "calibracionPersistida": True, "auditoriaM9Creada": bool(auditoria_control),
        "eventoRf10Observado": bool(eventos_control),
    }

    # ----------------------------------------------------- 8. snapshot PRE del objetivo
    count_before = H.count_calibraciones(conn, id_sensor)
    rows_before = H.rows_calibraciones(conn, id_sensor)
    EV.json("count_target_before.json", {"id_sensor": id_sensor, "count": count_before})
    EV.json("rows_target_before.json", rows_before)

    # ----------------------------------------------------- 9. snapshot de privilegios
    priv_pre = H.privilegios_app(conn)
    grants_pre = H.grants_auditoria(conn)
    EV.json("privilegios_pre.json", {
        "rol": H.rol_app(conn), "owners": H.owners_tablas(conn),
        "grantsAuditoria": grants_pre, "hasTablePrivilege": priv_pre,
    })
    rc_snap, salida_snap = H.psql_owner(sql_file=H.SQL_DIR / "snapshot_privilegios.sql")
    EV.texto("privilegios_pre_snapshot.txt", salida_snap)
    assert rc_snap == 0
    # Solo se restaurará lo que el snapshot demuestre disponible.
    assert priv_pre["audit_m9_insert"] is True and priv_pre["eventos_insert"] is True

    huerfanas_pre = H.auditorias_huerfanas(conn)

    restaurado = {"ejecutado": False, "ok": None, "privilegios": None}
    try:
        # ------------------------------------------- 10-11. FAULT INJECTION y verificación
        rc_rev, salida_rev = H.psql_owner(sql_file=H.SQL_DIR / "revoke_auditoria.sql")
        EV.texto("revoke_output.txt", salida_rev)
        assert rc_rev == 0, f"el REVOKE no se aplicó: {salida_rev}"

        priv_revoke = H.privilegios_app(conn)
        EV.json("privilegios_revoke.json", priv_revoke)
        # Si el REVOKE no es efectivo, el laboratorio es inválido: no se ejecuta el POST.
        assert priv_revoke["audit_m9_insert"] is False, \
            "BLOQUEADO: el REVOKE no eliminó el INSERT de auditoría (¿app owner, superuser o privilegio heredado?)"
        assert priv_revoke["eventos_insert"] is False, "BLOQUEADO: el REVOKE no eliminó el INSERT de eventos"
        # El punto de fallo debe ser la auditoría, no la calibración.
        assert priv_revoke["calibraciones_insert"] is True, \
            "BLOQUEADO: se revocó también el INSERT de calibraciones; el punto de fallo sería otro"

        # ------------------------------------------- 12. ÚNICO POST OBJETIVO
        body_objetivo = H.cuerpo_calibracion(id_dispositivo, id_area, str(valor), H.OBSERVACIONES_OBJETIVO)
        EV.json("target_request.json", {
            "endpoint": f"/configuracion/sensores/{id_sensor}/calibrar", "metodo": "POST",
            "headers": {"Authorization": "[REDACTED]", "Content-Type": "application/json"},
            "body": body_objetivo,
        })
        marca_objetivo = H.ahora_iso()
        status_objetivo, cuerpo_objetivo = api.calibrar(id_sensor, body_objetivo)
        EV.json("target_response.json", {"http": status_objetivo, "cuerpo": cuerpo_objetivo})

        # Logs del backend durante el POST objetivo: prueban dónde ocurrió el fallo.
        log_fault = H.logs_backend(desde=marca_objetivo)
        EV.texto("backend_fault.log", log_fault)

        # ------------------------------------------- 15-16. rollback en PostgreSQL
        count_after = H.count_calibraciones(conn, id_sensor)
        rows_after = H.rows_calibraciones(conn, id_sensor)
        EV.json("count_target_after.json", {"id_sensor": id_sensor, "count": count_after})
        EV.json("rows_target_after.json", rows_after)

        ids_before = [f["id_calibracion"] for f in rows_before]
        ids_after = [f["id_calibracion"] for f in rows_after]
        nuevos = [i for i in ids_after if i not in ids_before]
        desaparecidos = [i for i in ids_before if i not in ids_after]
        alterados = []
        for antes in rows_before:
            despues = next((f for f in rows_after if f["id_calibracion"] == antes["id_calibracion"]), None)
            if despues is None:
                continue
            if any(str(antes[k]) != str(despues[k]) for k in
                   ("id_dispositivo_iot", "id_sensor", "valor_referencia", "fecha_calibracion",
                    "id_usuario", "observaciones")):
                alterados.append(antes["id_calibracion"])

        # ------------------------------------------- 17. sin datos parciales
        huerfanas_post = H.auditorias_huerfanas(conn)
        huerfanas_nuevas = [h for h in huerfanas_post
                            if h["id_auditoria_calibracion"] not in
                            {x["id_auditoria_calibracion"] for x in huerfanas_pre}]
        eventos_objetivo = H.eventos_desde(conn, marca_objetivo)
        EV.json("audit_partial_check.json", {
            "auditoriasHuerfanasAntes": huerfanas_pre,
            "auditoriasHuerfanasDespues": huerfanas_post,
            "auditoriasHuerfanasNuevas": huerfanas_nuevas,
            "eventosDesdeElPostObjetivo": eventos_objetivo,
            "calibracionesNuevas": nuevos,
        })

        mensaje_obtenido = (cuerpo_objetivo or {}).get("message")
        resultado["postObjetivo"] = {
            "httpEsperado": 500, "httpObtenido": status_objetivo,
            "error_code": (cuerpo_objetivo or {}).get("error_code"),
            "mensajeEsperado": H.MENSAJE_500, "mensajeObtenido": mensaje_obtenido,
            "mensajeCoincide": mensaje_obtenido == H.MENSAJE_500,
            "fechaEnviada": body_objetivo["fecha_calibracion"],
            "devuelveIdCalibracion": "id_calibracion" in (cuerpo_objetivo or {}),
        }
        resultado["rollback"] = {
            "countBefore": count_before, "countAfter": count_after,
            "idsBefore": ids_before, "idsAfter": ids_after,
            "calibracionesNuevas": nuevos, "historicosDesaparecidos": desaparecidos,
            "historicosAlterados": alterados,
            "auditoriasHuerfanasNuevas": [h["id_auditoria_calibracion"] for h in huerfanas_nuevas],
        }
        resultado["puntoDeFallo"] = {
            "permissionDeniedEnAuditoria": "permission denied for table auditorias_calibraciones" in log_fault,
            "permissionDeniedEnEventos": "permission denied for table eventos" in log_fault,
            "permissionDeniedEnCalibraciones": "permission denied for table calibraciones" in log_fault,
        }

        # ------------------------------------------- oráculo
        # El fallo tuvo que ocurrir en la auditoría, no antes.
        assert not resultado["puntoDeFallo"]["permissionDeniedEnCalibraciones"], \
            "ejecución inválida: el fallo ocurrió en el INSERT de calibraciones, no en la auditoría"

        # Rollback real: esto es lo que el caso exige demostrar.
        assert count_after == count_before, \
            f"la calibración quedó persistida pese al fallo de auditoría: {count_before} -> {count_after}"
        assert nuevos == [], f"apareció una calibración nueva tras el fallo: {nuevos}"
        assert desaparecidos == [], f"desaparecieron filas históricas: {desaparecidos}"
        assert alterados == [], f"se alteraron filas históricas: {alterados}"
        assert huerfanas_nuevas == [], f"quedó auditoría huérfana del intento fallido: {huerfanas_nuevas}"

        # Respuesta pública: 500 con el mensaje funcional exacto del FA.
        assert status_objetivo == 500, f"HTTP esperado 500, obtenido {status_objetivo}"
        assert mensaje_obtenido == H.MENSAJE_500, (
            "el mensaje no coincide con el FA de RF-24 v2.0.\n"
            f"  esperado: {H.MENSAJE_500}\n  obtenido: {mensaje_obtenido}"
        )

    finally:
        # ------------------------------------------- 18-19. restauración, siempre
        rc_res, salida_res = H.psql_owner(sql_file=H.SQL_DIR / "restore_auditoria.sql")
        EV.texto("restore_output.txt", salida_res)
        priv_post = H.privilegios_app(conn)
        ok = (priv_post["audit_m9_insert"] is True and priv_post["eventos_insert"] is True
              and priv_post["calibraciones_insert"] is True)
        restaurado = {"ejecutado": rc_res == 0, "ok": ok, "privilegios": priv_post}
        EV.json("privilegios_post_restore.json", {
            "hasTablePrivilege": priv_post, "privilegiosPre": priv_pre,
            "coincideConElPre": (priv_post == priv_pre),
            "restauracionPendiente": not ok,
            "nota": ("Solo se devolvieron los privilegios que el snapshot PRE demostró "
                     "disponibles. No se usó GRANT ALL, SUPERUSER ni ALTER OWNER."),
        })
        resultado["restauracion"] = {
            "grantEjecutado": rc_res == 0, "privilegiosRestaurados": ok,
            "restauracionPendiente": not ok,
        }
        EV.json(f"{H.GROUP_ID}.json", resultado)

    assert restaurado["ok"] is True, "RESTAURACIÓN PENDIENTE: los privilegios no volvieron al estado PRE"
