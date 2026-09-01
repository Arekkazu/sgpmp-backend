"""Compara alembic_version contra marcadores reales de esquema. Solo lectura.

INC-M01-03-119: la DB de test quedo con alembic_version apuntando a una
revision ('cf8df1369e08') que no existe en el repo. Antes de reparar con
`alembic stamp`, hay que saber que migraciones estan realmente aplicadas
en el esquema, no confiar en lo que dice la tabla de control.
"""
import os

import psycopg2

MARCADORES = [
    (
        "e8bb4f321a44",
        "rf06 trigger revoca tokens al inactivar/bloquear/eliminar",
        """
        SELECT EXISTS (
            SELECT 1 FROM pg_proc p
            JOIN pg_namespace n ON n.oid = p.pronamespace
            WHERE n.nspname = 'modulo1'
              AND p.proname = 'trg_fn_invalidar_sesiones_por_estado'
              AND p.prosrc LIKE '%modulo1.tokens%'
        )
        """,
    ),
    (
        "d9a47c30e5b1",
        "RF-10 tipo de evento EXPORTACION_AUDITORIA (id 26)",
        "SELECT EXISTS (SELECT 1 FROM modulo1.tipos_eventos WHERE id_tipo_evento = 26)",
    ),
    (
        "f1c62d8b04a7",
        "RF-10 tabla cola_exportaciones_auditoria",
        """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'modulo1' AND table_name = 'cola_exportaciones_auditoria'
        )
        """,
    ),
    (
        "c4a19e7d2b63",
        "RF-03 fk_recurso_rol ON DELETE CASCADE",
        """
        SELECT COALESCE(
            (SELECT confdeltype = 'c'
             FROM pg_constraint con
             JOIN pg_class rel ON rel.oid = con.conrelid
             JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
             WHERE nsp.nspname = 'modulo1' AND rel.relname = 'permisos'
               AND con.conname = 'fk_recurso_rol'),
            false
        )
        """,
    ),
]


def main() -> None:
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    conn.set_session(readonly=True)
    cur = conn.cursor()

    cur.execute("SELECT current_database()")
    print(f"database: {cur.fetchone()[0]}")

    try:
        cur.execute("SELECT version_num FROM alembic_version")
        row = cur.fetchone()
        print(f"alembic_version: {row[0] if row else '(vacia)'}")
    except Exception as exc:
        print(f"alembic_version: error leyendo tabla -> {exc}")
        conn.rollback()

    for revision, descripcion, query in MARCADORES:
        cur.execute(query)
        aplicado = cur.fetchone()[0]
        estado = "SI" if aplicado else "no"
        print(f"{revision}  {descripcion}: {estado}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
