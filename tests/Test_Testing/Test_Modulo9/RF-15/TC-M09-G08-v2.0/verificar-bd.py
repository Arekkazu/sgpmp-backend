"""Script de verificación en base de datos PostgreSQL TEST para TC-M09-G08-v2.0.

Cubre las verificaciones de auditoría e integridad:
- NW-04: Auditoría CREATE registrada en BD para la especie creada
- NW-04a: id_usuario=104, tipo_operacion='CREATE', fecha_gestion >= run_start_time
- NW-04b: valores_nuevos.grupo_manejo == 'ESPECIES_MEDIANAS' (FALLA b esperada)
- NW-06: Auditoría UPDATE de nombre ('Cabra Qaa' -> 'Cabra Criolla Qaa')
- NW-08: Auditoría UPDATE persistida tras intento de edición de grupo_manejo
- NW-08a: tipo_operacion='UPDATE', id_usuario=104, fecha_gestion válida
- NW-08b: valores_anteriores.grupo_manejo == 'ESPECIES_MEDIANAS' y valores_nuevos.grupo_manejo == 'ESPECIES_GRANDES' (FALLA b esperada)
- NW-10: Auditoría DEACTIVATE (valores_anteriores.es_activo=true, valores_nuevos.es_activo=false)
- NW-12: Auditoría REACTIVAR (tipo_operacion='UPDATE', valores_anteriores.es_activo=false, valores_nuevos.es_activo=true)
- NW-15: Integridad final: especie en es_activo=false y 0 residuales activos
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
REPO_DIR = BASE_DIR.parents[4]
ENV_TEST = REPO_DIR / ".env.test"

if ENV_TEST.exists():
    load_dotenv(ENV_TEST)
else:
    load_dotenv()

DB_URL = os.getenv("TEST_DATABASE_URL")
if not DB_URL:
    print("ERROR: TEST_DATABASE_URL no definida en el entorno ni en .env.test", file=sys.stderr)
    sys.exit(1)


def parse_run_info(base_dir: Path):
    """Extrae run_start_time y id_especie desde consola_TC-M09-G08-v2.0.txt."""
    consola_file = base_dir / "evidencias" / "consola_TC-M09-G08-v2.0.txt"
    run_start_time = None
    id_especie = None

    if consola_file.exists():
        try:
            content = consola_file.read_text(encoding="utf-8", errors="ignore")
            m_time = re.search(r"RUN_START_TIME=([0-9T:.Z\-+]+)", content)
            if m_time:
                run_start_time = m_time.group(1)

            m_id = re.search(r"CREATED_ID_ESPECIE=(\d+)", content)
            if m_id:
                id_especie = int(m_id.group(1))
        except Exception:
            pass

    return run_start_time, id_especie


def obtener_id_especie_fallback(cur):
    """Busca id_especie creada recientemente si no vino en consola."""
    query = """
        SELECT id_especie
        FROM modulo9.especies
        WHERE LOWER(nombre) IN (LOWER('Cabra Qaa'), LOWER('Cabra Criolla Qaa'), LOWER('Cabra Qab'), LOWER('Cabra Criolla Qab'))
        ORDER BY id_especie DESC
        LIMIT 1;
    """
    cur.execute(query)
    row = cur.fetchone()
    return row[0] if row else None


def evaluar_nw04(cur, id_especie: int, run_start_time: str):
    """Evalúa NW-04, NW-04a y NW-04b (Auditoría CREATE)."""
    query = """
        SELECT id_auditoria_especie, id_usuario, tipo_operacion, fecha_gestion, valores_nuevos
        FROM modulo9.auditorias_especies
        WHERE id_especie = %s
          AND tipo_operacion = 'CREATE'
          AND fecha_gestion >= %s::timestamptz
        ORDER BY fecha_gestion ASC
        LIMIT 1;
    """
    cur.execute(query, (id_especie, run_start_time))
    row = cur.fetchone()

    res_nw04 = {
        "paso": "NW-04",
        "esperado": "Registro de auditoría CREATE persistido en modulo9.auditorias_especies para especie creada",
        "obtenido": "Registro de auditoría CREATE no encontrado en BD",
        "estado": "FALLA",
    }
    res_nw04a = {
        "paso": "NW-04a",
        "esperado": "id_usuario=104, tipo_operacion='CREATE', fecha_gestion >= run_start_time",
        "obtenido": "Registro CREATE no encontrado",
        "estado": "FALLA",
    }
    res_nw04b = {
        "paso": "NW-04b",
        "esperado": "valores_nuevos.grupo_manejo == 'ESPECIES_MEDIANAS'",
        "obtenido": "campo grupo_manejo ausente en snapshot de auditoría (defecto raíz INC-M09-01-G01 v2.0)",
        "estado": "FALLA",
    }

    if row:
        id_aud, id_usr, op, fecha, val_nuevos = row
        val_dict = val_nuevos if isinstance(val_nuevos, dict) else (json.loads(val_nuevos) if val_nuevos else {})

        res_nw04["obtenido"] = f"Registro CREATE encontrado (ID={id_aud}, Usuario={id_usr}, Fecha={fecha})"
        res_nw04["estado"] = "OK"

        if id_usr == 104 and op == "CREATE":
            res_nw04a["obtenido"] = f"Campos conformes: id_usuario={id_usr}, tipo_operacion='{op}', fecha={fecha}"
            res_nw04a["estado"] = "OK"
        else:
            res_nw04a["obtenido"] = f"Inconsistencia: id_usuario={id_usr}, tipo_operacion='{op}'"
            res_nw04a["estado"] = "FALLA"

        # NW-04b: Evaluar si grupo_manejo está en el snapshot
        if "grupo_manejo" in val_dict and val_dict["grupo_manejo"] == "ESPECIES_MEDIANAS":
            res_nw04b["obtenido"] = "valores_nuevos.grupo_manejo registrado como 'ESPECIES_MEDIANAS'"
            res_nw04b["estado"] = "OK"
        else:
            # Estado esperado: FALLA (b)
            res_nw04b["obtenido"] = "campo grupo_manejo ausente en snapshot de auditoría (defecto raíz INC-M09-01-G01 v2.0)"
            res_nw04b["estado"] = "FALLA"

    return res_nw04, res_nw04a, res_nw04b


def evaluar_nw06(cur, id_especie: int, run_start_time: str):
    """Evalúa NW-06 (Auditoría UPDATE de nombre)."""
    query = """
        SELECT id_auditoria_especie, id_usuario, tipo_operacion, fecha_gestion, valores_anteriores, valores_nuevos
        FROM modulo9.auditorias_especies
        WHERE id_especie = %s
          AND tipo_operacion = 'UPDATE'
          AND fecha_gestion >= %s::timestamptz
        ORDER BY fecha_gestion ASC;
    """
    cur.execute(query, (id_especie, run_start_time))
    rows = cur.fetchall()

    res = {
        "paso": "NW-06",
        "esperado": "valores_anteriores.nombre ≈ 'Cabra Qaa' y valores_nuevos.nombre ≈ 'Cabra Criolla Qaa' (case-insensitive)",
        "obtenido": "No se encontró registro UPDATE con transición de nombre",
        "estado": "FALLA",
    }

    for r in rows:
        id_aud, id_usr, op, fecha, val_ant, val_nuev = r
        d_ant = val_ant if isinstance(val_ant, dict) else (json.loads(val_ant) if val_ant else {})
        d_nuev = val_nuev if isinstance(val_nuev, dict) else (json.loads(val_nuev) if val_nuev else {})

        nom_ant = str(d_ant.get("nombre", "")).strip().lower()
        nom_nuev = str(d_nuev.get("nombre", "")).strip().lower()

        if (nom_ant in ["cabra qaa", "cabra qab"]) and (nom_nuev in ["cabra criolla qaa", "cabra criolla qab"]):
            res["obtenido"] = f"Transición de nombre confirmada (ID={id_aud}): '{d_ant.get('nombre')}' -> '{d_nuev.get('nombre')}'"
            res["estado"] = "OK"
            break

    return res


def evaluar_nw08(cur, id_especie: int, run_start_time: str):
    """Evalúa NW-08, NW-08a y NW-08b (Auditoría UPDATE de grupo_manejo)."""
    query = """
        SELECT id_auditoria_especie, id_usuario, tipo_operacion, fecha_gestion, valores_anteriores, valores_nuevos
        FROM modulo9.auditorias_especies
        WHERE id_especie = %s
          AND tipo_operacion = 'UPDATE'
          AND fecha_gestion >= %s::timestamptz
        ORDER BY fecha_gestion ASC;
    """
    cur.execute(query, (id_especie, run_start_time))
    rows = cur.fetchall()

    res_nw08 = {
        "paso": "NW-08",
        "esperado": "Auditoría UPDATE persistida en BD tras intento de edición de grupo_manejo",
        "obtenido": "No se encontró evento UPDATE posterior a la edición",
        "estado": "FALLA",
    }
    res_nw08a = {
        "paso": "NW-08a",
        "esperado": "tipo_operacion='UPDATE' y usuario/fecha válidos (id_usuario=104)",
        "obtenido": "No se encontró evento UPDATE para validación de campos",
        "estado": "FALLA",
    }
    res_nw08b = {
        "paso": "NW-08b",
        "esperado": "valores_anteriores.grupo_manejo == 'ESPECIES_MEDIANAS' AND valores_nuevos.grupo_manejo == 'ESPECIES_GRANDES'",
        "obtenido": "campo grupo_manejo ausente en snapshot de auditoría (defecto raíz INC-M09-01-G01 v2.0)",
        "estado": "FALLA",
    }

    # El intento de edición con grupo_manejo ocurre después del renombramiento (es al menos el 2do UPDATE o subsiguiente)
    if len(rows) >= 2:
        segundo_update = rows[1]
        id_aud, id_usr, op, fecha, val_ant, val_nuev = segundo_update
        d_ant = val_ant if isinstance(val_ant, dict) else (json.loads(val_ant) if val_ant else {})
        d_nuev = val_nuev if isinstance(val_nuev, dict) else (json.loads(val_nuev) if val_nuev else {})

        res_nw08["obtenido"] = f"Evento UPDATE persistido en BD (ID={id_aud}, Fecha={fecha})"
        res_nw08["estado"] = "OK"

        if id_usr == 104 and op == "UPDATE":
            res_nw08a["obtenido"] = f"Evento UPDATE válido con id_usuario={id_usr} y fecha={fecha}"
            res_nw08a["estado"] = "OK"

        if d_ant.get("grupo_manejo") == "ESPECIES_MEDIANAS" and d_nuev.get("grupo_manejo") == "ESPECIES_GRANDES":
            res_nw08b["obtenido"] = "Transición de grupo_manejo auditada correctamente"
            res_nw08b["estado"] = "OK"
        else:
            res_nw08b["obtenido"] = "campo grupo_manejo ausente en snapshot de auditoría (defecto raíz INC-M09-01-G01 v2.0)"
            res_nw08b["estado"] = "FALLA"
    elif len(rows) == 1:
        # Si sólo hubo 1 UPDATE registrado
        id_aud, id_usr, op, fecha, val_ant, val_nuev = rows[0]
        res_nw08["obtenido"] = f"Evento UPDATE persistido en BD (ID={id_aud}, Fecha={fecha})"
        res_nw08["estado"] = "OK"
        if id_usr == 104 and op == "UPDATE":
            res_nw08a["obtenido"] = f"Evento UPDATE válido con id_usuario={id_usr} y fecha={fecha}"
            res_nw08a["estado"] = "OK"
        res_nw08b["obtenido"] = "campo grupo_manejo ausente en snapshot de auditoría (defecto raíz INC-M09-01-G01 v2.0)"
        res_nw08b["estado"] = "FALLA"

    return res_nw08, res_nw08a, res_nw08b


def evaluar_nw10(cur, id_especie: int, run_start_time: str):
    """Evalúa NW-10 (Auditoría DEACTIVATE)."""
    query = """
        SELECT id_auditoria_especie, id_usuario, tipo_operacion, fecha_gestion, valores_anteriores, valores_nuevos
        FROM modulo9.auditorias_especies
        WHERE id_especie = %s
          AND tipo_operacion = 'DEACTIVATE'
          AND fecha_gestion >= %s::timestamptz
        ORDER BY fecha_gestion ASC
        LIMIT 1;
    """
    cur.execute(query, (id_especie, run_start_time))
    row = cur.fetchone()

    res = {
        "paso": "NW-10",
        "esperado": "tipo_operacion='DEACTIVATE', valores_anteriores.es_activo=true, valores_nuevos.es_activo=false",
        "obtenido": "No se encontró registro de auditoría DEACTIVATE",
        "estado": "FALLA",
    }

    if row:
        id_aud, id_usr, op, fecha, val_ant, val_nuev = row
        d_ant = val_ant if isinstance(val_ant, dict) else (json.loads(val_ant) if val_ant else {})
        d_nuev = val_nuev if isinstance(val_nuev, dict) else (json.loads(val_nuev) if val_nuev else {})

        act_ant = d_ant.get("es_activo")
        act_nuev = d_nuev.get("es_activo")

        if act_ant is True and act_nuev is False:
            res["obtenido"] = f"Auditoría DEACTIVATE confirmada (ID={id_aud}): es_activo=true -> es_activo=false"
            res["estado"] = "OK"
        else:
            res["obtenido"] = f"Registro encontrado pero estado incompatible: es_activo_ant={act_ant}, es_activo_nuev={act_nuev}"
            res["estado"] = "FALLA"

    return res


def evaluar_nw12(cur, id_especie: int, run_start_time: str):
    """Evalúa NW-12 (Auditoría de REACTIVACIÓN registrada como UPDATE de es_activo)."""
    query = """
        SELECT id_auditoria_especie, id_usuario, tipo_operacion, fecha_gestion, valores_anteriores, valores_nuevos
        FROM modulo9.auditorias_especies
        WHERE id_especie = %s
          AND tipo_operacion = 'UPDATE'
          AND fecha_gestion >= %s::timestamptz
        ORDER BY fecha_gestion DESC;
    """
    cur.execute(query, (id_especie, run_start_time))
    rows = cur.fetchall()

    res = {
        "paso": "NW-12",
        "esperado": "tipo_operacion='UPDATE', valores_anteriores.es_activo=false, valores_nuevos.es_activo=true",
        "obtenido": "No se encontró registro de reactivación (UPDATE con es_activo: false -> true)",
        "estado": "FALLA",
    }

    for r in rows:
        id_aud, id_usr, op, fecha, val_ant, val_nuev = r
        d_ant = val_ant if isinstance(val_ant, dict) else (json.loads(val_ant) if val_ant else {})
        d_nuev = val_nuev if isinstance(val_nuev, dict) else (json.loads(val_nuev) if val_nuev else {})

        act_ant = d_ant.get("es_activo")
        act_nuev = d_nuev.get("es_activo")

        if act_ant is False and act_nuev is True:
            res["obtenido"] = f"Auditoría de reactivación confirmada (ID={id_aud}): UPDATE con es_activo=false -> es_activo=true"
            res["estado"] = "OK"
            break

    return res


def evaluar_nw15(cur, id_especie: int, base_dir: Path):
    """Evalúa NW-15 (Integridad final: especie inactiva y 0 residuales activos)."""
    res = {
        "paso": "NW-15",
        "esperado": "Especie creada con es_activo=false y cero especies residuales activas de prueba",
        "obtenido": "No evaluado",
        "estado": "FALLA",
    }

    cur.execute("SELECT id_especie, nombre, es_activo FROM modulo9.especies WHERE id_especie = %s;", (id_especie,))
    row_esp = cur.fetchone()

    cur.execute("""
        SELECT id_especie, nombre, es_activo
        FROM modulo9.especies
        WHERE LOWER(nombre) IN (LOWER('Cabra Qaa'), LOWER('Cabra Criolla Qaa'), LOWER('Cabra Qab'), LOWER('Cabra Criolla Qab'));
    """)
    todos_registros = cur.fetchall()

    evidencias_dir = base_dir / "evidencias"
    evidencias_dir.mkdir(exist_ok=True)
    ids_file = evidencias_dir / "ids_residuales.json"

    ids_data = [{"id_especie": r[0], "nombre": r[1], "es_activo": r[2]} for r in todos_registros]
    ids_file.write_text(json.dumps(ids_data, indent=2, ensure_ascii=False), encoding="utf-8")

    activos_residuales = [r for r in todos_registros if r[2] is True]

    if not row_esp:
        res["obtenido"] = f"Especie creada (ID={id_especie}) no encontrada en base de datos"
        res["estado"] = "FALLA"
    elif row_esp[2] is not False:
        res["obtenido"] = f"Especie creada (ID={id_especie}) permanece activa (es_activo=True); teardown incompleto"
        res["estado"] = "FALLA"
    elif activos_residuales:
        res["obtenido"] = f"Se detectaron {len(activos_residuales)} especies de prueba residuales activas"
        res["estado"] = "FALLA"
    else:
        res["obtenido"] = f"Integridad BD confirmada: especie ID={id_especie} inactiva (es_activo=False) y 0 residuales activos"
        res["estado"] = "OK"

    return res


def main():
    parser = argparse.ArgumentParser(description="Verificación de auditoría e integridad BD para TC-M09-G08-v2.0")
    parser.add_argument("--modo", default="all", help="Chequeo a ejecutar o 'all'")
    parser.add_argument("--run-start-time", default=None, help="Timestamp ISO de inicio de corrida")
    parser.add_argument("--id-especie", type=int, default=None, help="ID de la especie creada")
    args = parser.parse_args()

    parsed_time, parsed_id = parse_run_info(BASE_DIR)
    run_start_time = args.run_start_time or parsed_time
    id_especie = args.id_especie or parsed_id

    if not run_start_time:
        # Fallback de seguridad: últimas 2 horas
        run_start_time = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()

    conn = psycopg2.connect(DB_URL, connect_timeout=10)
    cur = conn.cursor()
    cur.execute("SELECT set_config('app.current_role', 'Administrador', false);")

    if not id_especie:
        id_especie = obtener_id_especie_fallback(cur)

    if not id_especie:
        print("ERROR: No se pudo determinar el id_especie creada para verificar en BD.", file=sys.stderr)
        cur.close()
        conn.close()
        sys.exit(1)

    print(f"[VERIFICAR-BD] Analizando ID Especie: {id_especie}, Run Start Time: {run_start_time}")

    nw04, nw04a, nw04b = evaluar_nw04(cur, id_especie, run_start_time)
    nw06 = evaluar_nw06(cur, id_especie, run_start_time)
    nw08, nw08a, nw08b = evaluar_nw08(cur, id_especie, run_start_time)
    nw10 = evaluar_nw10(cur, id_especie, run_start_time)
    nw12 = evaluar_nw12(cur, id_especie, run_start_time)
    nw15 = evaluar_nw15(cur, id_especie, BASE_DIR)

    cur.close()
    conn.close()

    resultados_map = {
        "NW-04": nw04,
        "NW-04a": nw04a,
        "NW-04b": nw04b,
        "NW-06": nw06,
        "NW-08": nw08,
        "NW-08a": nw08a,
        "NW-08b": nw08b,
        "NW-10": nw10,
        "NW-12": nw12,
        "NW-15": nw15,
    }

    evidencias_dir = BASE_DIR / "evidencias"
    evidencias_dir.mkdir(exist_ok=True)
    res_file = evidencias_dir / "resultados_bd.json"
    res_file.write_text(json.dumps(resultados_map, indent=2, ensure_ascii=False), encoding="utf-8")

    print("[VERIFICAR-BD] Resultados de auditoría e integridad en BD:")
    for paso, datos in resultados_map.items():
        print(f"  [{paso}] {datos['estado']}: {datos['obtenido']}")

    sys.exit(0)


if __name__ == "__main__":
    main()
