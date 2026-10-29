"""TC-M09-105 — Verifica en BD la auditoría de las operaciones de la colección TC-M09-G53.

`modulo9.auditorias_infraestructuras` no tiene endpoint REST y su política RLS de
SELECT solo muestra filas a sesiones con rol Administrador, así que este script
necesita una credencial de BD autorizada para leer esa tabla (no la de member_qa).

Uso:
    DB_USER=<usuario> DB_PASSWORD=<clave> python verificar_auditoria_g53.py --id 169

Espera, en orden, para el área indicada:
    CREATE -> GET -> UPDATE (edición) -> DEACTIVATE -> UPDATE (reactivación)
y en particular que la reactivación sea UPDATE con es_activo false -> true, sin un
segundo CREATE.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import psycopg2

ESPERADO = ["CREATE", "GET", "UPDATE", "DEACTIVATE", "UPDATE"]


def activo(snapshot):
    return None if snapshot is None else snapshot.get("es_activo")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", type=int, required=True, help="id_infraestructura usado por la corrida de Newman")
    args = parser.parse_args()

    for var in ("DB_USER", "DB_PASSWORD"):
        if not os.getenv(var):
            print(f"Falta la variable de entorno {var} (credencial autorizada a leer la auditoría).")
            return 2

    conn = psycopg2.connect(
        host=os.getenv("DB_HOST", "158.69.200.27"),
        port=os.getenv("DB_PORT", "5448"),
        dbname=os.getenv("DB_NAME", "sgpmp_test"),
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        connect_timeout=10,
    )
    with conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id_auditoria_infraestructura, id_usuario, tipo_operacion, valores_anteriores, "
            "valores_nuevos, fecha_gestion FROM modulo9.auditorias_infraestructuras "
            "WHERE id_infraestructura = %s ORDER BY id_auditoria_infraestructura",
            (args.id,),
        )
        filas = cur.fetchall()

    print(f"Filas de auditoría del área {args.id}: {len(filas)}")
    for f in filas:
        print(f"  #{f[0]} usuario={f[1]} {f[2]:<10} {f[5].isoformat()}  "
              f"anteriores={json.dumps(f[3], ensure_ascii=False)}  nuevos={json.dumps(f[4], ensure_ascii=False)}")

    tipos = [f[2] for f in filas]
    checks = [
        ("Secuencia CREATE, GET, UPDATE, DEACTIVATE, UPDATE", tipos == ESPERADO),
        ("Un solo CREATE (la reactivación no crea un área nueva)", tipos.count("CREATE") == 1),
    ]
    if tipos == ESPERADO:
        create, _, edicion, desact, react = filas
        checks += [
            ("CREATE sin valores_anteriores y con es_activo=true", create[3] is None and activo(create[4]) is True),
            ("UPDATE de edición registra el cambio de nombre",
             (edicion[3] or {}).get("nombre") != (edicion[4] or {}).get("nombre")),
            ("DEACTIVATE es_activo true -> false", activo(desact[3]) is True and activo(desact[4]) is False),
            ("Reactivación auditada como UPDATE con es_activo false -> true",
             react[2] == "UPDATE" and activo(react[3]) is False and activo(react[4]) is True),
        ]
    checks.append(("Todas las filas con id_usuario del Administrador (1)", bool(filas) and all(f[1] == 1 for f in filas)))

    print()
    for nombre, ok in checks:
        print(f"  [{'OK' if ok else 'FALLA'}] {nombre}")
    return 0 if all(ok for _, ok in checks) else 1


if __name__ == "__main__":
    sys.exit(main())
