"""SELECT read-only en la BD TEST para TC-M09-267.

CLI --days y --snapshot para el runner; pytest compara el snapshot POST contra
el digest PRE. Ninguna ruta de este módulo ejecuta escrituras SQL.
"""
import hashlib
import json
import os
import sys

import psycopg2


def connection():
    db = psycopg2.connect(
        host=os.environ["QA_DB_HOST"],
        port=int(os.environ["QA_DB_PORT"]),
        user=os.environ["QA_DB_USER"],
        password=os.environ["QA_DB_PASSWORD"],
        dbname=os.environ["QA_DB_NAME"],
        connect_timeout=10,
        options="-c default_transaction_read_only=on",
    )
    db.set_session(readonly=True, autocommit=False)
    return db


def read_only(cursor):
    cursor.execute("SELECT current_setting('transaction_read_only')")
    if cursor.fetchone()[0] != "on":
        raise RuntimeError("La conexión de TEST no está en modo read-only")


def historical_days(sensor):
    db = connection()
    try:
        with db.cursor() as cursor:
            read_only(cursor)
            cursor.execute(
                "SELECT CAST(timestamp_captura AS date), COUNT(*) "
                "FROM modulo3.telemetrias "
                "WHERE id_sensor = %s AND timestamp_captura < CURRENT_DATE "
                "GROUP BY CAST(timestamp_captura AS date) "
                "ORDER BY 1 DESC LIMIT 30",
                (sensor,),
            )
            return [{"dia": day.isoformat(), "cantidad": count} for day, count in cursor.fetchall()]
    finally:
        db.rollback()
        db.close()


def historical_sensors():
    db = connection()
    try:
        with db.cursor() as cursor:
            read_only(cursor)
            cursor.execute(
                "SELECT id_sensor, COUNT(*) FROM modulo3.telemetrias "
                "WHERE timestamp_captura < CURRENT_DATE "
                "GROUP BY id_sensor ORDER BY COUNT(*) DESC, id_sensor"
            )
            return [{"sensor": sensor, "cantidad": count} for sensor, count in cursor.fetchall()]
    finally:
        db.rollback()
        db.close()


def snapshot(sensor, start, end_exclusive, post_before):
    db = connection()
    try:
        with db.cursor() as cursor:
            read_only(cursor)
            cursor.execute(
                "SELECT id_telemetria, valor_crudo, valor_ajustado, calibrado "
                "FROM modulo3.telemetrias "
                "WHERE id_sensor = %s "
                "AND timestamp_captura >= %s "
                "AND timestamp_captura < %s "
                "AND timestamp_captura < %s "
                "ORDER BY id_telemetria",
                (sensor, start, end_exclusive, post_before),
            )
            rows = [
                {"id_telemetria": row[0], "valor_crudo": str(row[1]) if row[1] is not None else None,
                 "valor_ajustado": str(row[2]) if row[2] is not None else None,
                 "calibrado": row[3]}
                for row in cursor.fetchall()
            ]
            canonical = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            return {"cantidad": len(rows), "sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
                    "filas": rows, "read_only": True}
    finally:
        db.rollback()
        db.close()


def test_historico_inmutable():
    result = snapshot(
        int(os.environ["G134_SENSOR"]), os.environ["G134_START"],
        os.environ["G134_END_EXCLUSIVE"], os.environ["G134_POST_BEFORE"]
    )
    assert result["cantidad"] > 0, "No existe telemetría histórica en el período cerrado"
    assert result["cantidad"] == int(os.environ["G134_EXPECTED_COUNT"]), "Cambió la cantidad de filas históricas"
    assert result["sha256"] == os.environ["G134_EXPECTED_SHA256"], "Cambió el snapshot SQL histórico"


if __name__ == "__main__":
    if sys.argv[1:] == ["--sensors"]:
        print(json.dumps(historical_sensors(), ensure_ascii=False))
    elif sys.argv[1:] == ["--days"]:
        print(json.dumps(historical_days(int(os.environ["G134_SENSOR"])), ensure_ascii=False))
    elif sys.argv[1:] == ["--snapshot"]:
        print(json.dumps(snapshot(
            int(os.environ["G134_SENSOR"]), os.environ["G134_START"],
            os.environ["G134_END_EXCLUSIVE"], os.environ["G134_POST_BEFORE"]
        ), ensure_ascii=False))
    else:
        raise SystemExit("Use --days, --snapshot o python -m pytest test_tc_m09_267.py")
