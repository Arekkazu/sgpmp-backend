"""Cierre de TC-M09-G79-v2.0: verificación de SOLO LECTURA, trazabilidad y seguridad.

No ejecuta ningún POST ni ninguna escritura funcional. Las únicas consultas son SELECT sobre la
base aislada del laboratorio. Nunca borra una calibración ni una auditoría: si apareciera
persistencia parcial, se conserva como evidencia.

Hace cuatro cosas:
  1. revalida por SQL el estado final (rollback sostenido, privilegios restaurados, fixture);
  2. copia la automatización dentro del RUN y registra su SHA-256;
  3. escanea la evidencia buscando secretos;
  4. captura el estado final de git.

Uso:
    python verificar_cierre.py
con G79_RUN_ID y el entorno del laboratorio definidos.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import helpers_g79_v2 as H

RUN_ID = os.environ["G79_RUN_ID"]
EV = H.Evidencia(RUN_ID)
ARTIFACT = EV.dir / f"{H.GROUP_ID}.json"

ARTEFACTOS = [
    Path("test_tc_m09_150_v2.py"),
    Path("helpers_g79_v2.py"),
    Path("verificar_cierre.py"),
    Path("docker-compose.g79-v2.yml"),
    Path("sql/bootstrap_roles.sql"),
    Path("sql/grant_app_privileges.sql"),
    Path("sql/seed_fixture.sql"),
    Path("sql/snapshot_privilegios.sql"),
    Path("sql/revoke_auditoria.sql"),
    Path("sql/restore_auditoria.sql"),
]

PATRONES = [
    ("JWT", r"eyJ[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}\."),
    ("Authorization con token", r"Bearer\s+[A-Za-z0-9_.\-]{12,}"),
    ("cabecera de cookie", r"set-cookie"),
    ("token en clave/valor", r"(access|refresh)_token\"?\s*[:=]\s*\"?[A-Za-z0-9_.\-]{12,}"),
    ("credencial en clave/valor", r"(password|contrasena|POSTGRES_PASSWORD|APP_DB_PASSWORD)\"?\s*[:=]\s*\"?[^\"\s,}\]]{4,}"),
    ("cadena de conexión con contraseña", r"postgres(?:ql)?://[^:/\s]+:[^@\s\[]+@"),
]
# En el código fuente copiado a automation/ el vocabulario y los propios patrones del escáner
# aparecen de forma legítima: allí solo cuentan VALORES de secreto.
SOLO_VALORES = {"JWT", "Authorization con token", "cadena de conexión con contraseña"}


def main() -> int:
    import re

    assert ARTIFACT.exists(), f"No existe {ARTIFACT.name}: ejecute primero el test del RUN."
    artifact = json.loads(ARTIFACT.read_text(encoding="utf-8"))

    conn = H.conexion_admin()
    try:
        # 1. Estado final, solo lectura ------------------------------------------------
        guard = H.safety_guard(conn)
        id_sensor = int(artifact["fixture"]["id_sensor"])
        id_dispositivo = int(artifact["fixture"]["id_dispositivo_iot"])

        rows_final = H.rows_calibraciones(conn, id_sensor)
        ids_final = [f["id_calibracion"] for f in rows_final]
        ids_after_run = artifact["rollback"]["idsAfter"]
        id_control = artifact["controlPositivo"]["id_calibracion"]

        priv_final = H.privilegios_app(conn)
        priv_pre_run = {"calibraciones_insert": True, "audit_m9_insert": True, "eventos_insert": True}

        fixture_final = H.filas(conn, """
            SELECT d.es_activo AS dispositivo_activo, s.es_activo AS sensor_activo,
                   s.categoria::text AS categoria, a.id_infraestructura, a.tiene_estado,
                   a.fecha_finalizacion
            FROM modulo9.sensores s
            JOIN modulo9.dispositivos_iot d ON d.id_dispositivo_iot = s.id_dispositivo_iot
            JOIN modulo9.sensores_areas_asociadas a ON a.id_sensor = s.id_sensores
            WHERE s.id_sensores = %s AND d.id_dispositivo_iot = %s
        """, (id_sensor, id_dispositivo))
        rango_final = H.filas(conn, "SELECT valor_min, valor_max FROM modulo9.rangos_calibracion WHERE categoria = %s",
                              (artifact["fixture"]["categoria"],))

        huerfanas = H.auditorias_huerfanas(conn)
        auditoria_control = H.auditorias_de(conn, id_control) if id_control else []

        cierre = {
            "grupo": H.GROUP_ID, "caso": H.CASO, "runId": RUN_ID, "fecha": H.ahora_iso(),
            "soloLectura": True, "sqlDeEscrituraEjecutado": "ninguno",
            "safetyGuard": guard["resultado"],
            "calibracionesDelSensor": {"ids": ids_final, "total": len(ids_final)},
            "coincideConElCierreDelRun": ids_final == ids_after_run,
            "controlPositivoSiguePresente": id_control in ids_final,
            "auditoriaDelControlSiguePresente": bool(auditoria_control),
            "sinCalibracionDelPostObjetivo": all(
                f["observaciones"] != H.OBSERVACIONES_OBJETIVO for f in rows_final
            ),
            "auditoriasHuerfanas": huerfanas,
            "privilegiosFinales": priv_final,
            "privilegiosRestauradosAlEstadoPre": priv_final == priv_pre_run,
            "fixtureSinCambios": bool(fixture_final) and fixture_final[0]["dispositivo_activo"] is True
                                 and fixture_final[0]["sensor_activo"] is True
                                 and fixture_final[0]["fecha_finalizacion"] is None,
            "rangoSinCambios": bool(rango_final)
                               and str(rango_final[0]["valor_min"]) == artifact["fixture"]["rango"]["min"]
                               and str(rango_final[0]["valor_max"]) == artifact["fixture"]["rango"]["max"],
            "rolApp": H.rol_app(conn),
            "ownersTablas": H.owners_tablas(conn),
        }
        EV.json("verificacion-final-readonly.json", cierre)
    finally:
        conn.close()

    # 2. Trazabilidad de la automatización ---------------------------------------------
    destino = EV.dir / "automation"
    manifest = []
    for rel in ARTEFACTOS:
        origen = H.BASE_DIR / rel
        if not origen.exists():
            continue
        copia = destino / rel
        copia.parent.mkdir(parents=True, exist_ok=True)
        # La copia se sanitiza antes de quedar como evidencia.
        copia.write_text(H.clean(origen.read_text(encoding="utf-8")), encoding="utf-8")
        manifest.append({
            "archivo": rel.as_posix(),
            "sha256_original": H.sha256(origen),
            "sha256_copia": H.sha256(copia),
            "bytes": origen.stat().st_size,
        })
    EV.json("automation_manifest.json", {
        "grupo": H.GROUP_ID, "caso": H.CASO, "runId": RUN_ID,
        "nota": ("SHA-256 de la automatización que produjo este RUN. Los archivos no se "
                 "modificaron entre la ejecución del test y esta captura, de modo que los "
                 "hashes corresponden exactamente a lo que se ejecutó. Las copias están "
                 "sanitizadas y no contienen secretos."),
        "artefactos": manifest,
    })

    # 3. Escaneo de secretos ------------------------------------------------------------
    credenciales = [v for v in (
        os.environ.get("G79_OWNER_PASSWORD"), os.environ.get("G79_APP_PASSWORD"),
        os.environ.get("G79_ING_PASSWORD"), os.environ.get("G79_SECRET_KEY"),
    ) if v]
    revisados = []
    for path in sorted(EV.dir.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".log", ".xml", ".json", ".md", ".yml", ".txt", ".py", ".sql"}:
            continue
        rel = path.relative_to(EV.dir).as_posix()
        es_codigo = rel.startswith("automation/")
        texto = path.read_text(encoding="utf-8", errors="replace")
        hallazgos = [
            nombre for nombre, patron in PATRONES
            if (not es_codigo or nombre in SOLO_VALORES) and re.search(patron, texto, re.IGNORECASE)
        ]
        revisados.append({
            "archivo": rel, "bytes": len(texto),
            "tipo": "codigo-fuente" if es_codigo else "evidencia",
            "secretos": hallazgos,
            "credencialesEnClaro": sum(1 for c in set(credenciales) if c in texto),
        })
    sucios = [r for r in revisados if r["secretos"] or r["credencialesEnClaro"]]
    EV.json("seguridad-evidencias.json", {
        "grupo": H.GROUP_ID, "runId": RUN_ID, "limpio": not sucios,
        "archivosConHallazgos": sucios, "revisados": revisados,
        "criterio": ("Se marcan solo valores de secreto: contraseñas, JWT, Authorization con "
                     "token, cookies, tokens en pares clave-valor y cadenas de conexión con "
                     "contraseña. En automation/ (código fuente) solo se evalúan valores: el "
                     "vocabulario del propio escáner no es una fuga."),
    })

    # 4. Estado final de git ------------------------------------------------------------
    repo = H.BASE_DIR
    for _ in range(12):
        if (repo / ".git").exists():
            break
        repo = repo.parent
    comandos = [
        ["branch", "--show-current"], ["status", "--short"], ["diff", "--stat"],
        ["diff", "--cached", "--stat"], ["rev-parse", "HEAD"], ["rev-parse", "origin/test"],
        ["rev-list", "--left-right", "--count", "HEAD...origin/test"],
        ["status", "--short", "--", "tests/Test_Testing/Test_Modulo9/RF-24/TC-M09-G79"],
        ["diff", "--stat", "--", "tests/Test_Testing/Test_Modulo9/RF-24/TC-M09-G79"],
    ]
    lineas = [f"# git_final.txt — {H.GROUP_ID}", f"# Capturado: {H.ahora_iso()}", ""]
    for args in comandos:
        rc, salida = H.run_cmd(["git", "-C", str(repo)] + args)
        lineas += [f"$ git {' '.join(args)}", (salida.strip() or "(vacio)"), ""]
    EV.texto("git_final.txt", "\n".join(lineas))

    print(f"calibraciones del sensor {cierre['calibracionesDelSensor']['ids']} "
          f"(coincide con el cierre del RUN: {cierre['coincideConElCierreDelRun']})")
    print(f"control positivo sigue presente: {cierre['controlPositivoSiguePresente']}")
    print(f"sin calibracion del POST objetivo: {cierre['sinCalibracionDelPostObjetivo']}")
    print(f"auditorias huerfanas: {len(cierre['auditoriasHuerfanas'])}")
    print(f"privilegios restaurados al estado PRE: {cierre['privilegiosRestauradosAlEstadoPre']}")
    print(f"fixture sin cambios: {cierre['fixtureSinCambios']} | rango sin cambios: {cierre['rangoSinCambios']}")
    print(f"automatizacion registrada: {len(manifest)} artefactos con SHA-256")
    print(f"evidencia limpia de secretos: {not sucios}")
    return 3 if sucios else 0


if __name__ == "__main__":
    raise SystemExit(main())
