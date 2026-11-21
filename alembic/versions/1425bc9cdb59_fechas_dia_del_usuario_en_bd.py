# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-23 | Arekkazu | PR-667: fecha de nacimiento del activo como date y "hoy" del usuario en la BD |
"""Fechas: nacimiento del activo como día calendario y "hoy" del usuario en la BD

Revision ID: 1425bc9cdb59
Revises: bf404c6f1018
Create Date: 2026-10-23

Por qué va por Alembic: es el patrón del repo, CI solo despliega lo que está en
`alembic/versions/` y cambia el tipo de una columna con vistas encima.

Regla de fechas (src/shared/fechas.py): los instantes se guardan en UTC y se
muestran en la zona del usuario; los días calendario no tienen zona.

1. `modulo2.detalles_activos_individuales.fecha_nacimeinto` pasa de
   `timestamptz` a `date`. Es un día ("nació el 12"), no un instante: guardado
   como hora exacta, la medianoche UTC del 12 se veía el 11 en Colombia. Los
   valores existentes se convierten con su día UTC, que es el que se eligió
   (el frontend enviaba la medianoche UTC del día). Las vistas que leen la
   columna (`vw_rf35`, `vw_rf47`, `vw_rf52`) se recrean con su misma
   definición, opciones, dueño, permisos y comentarios.

2. `modulo1.fn_hoy_usuario()`: el día de hoy en la zona que declara la API en
   `app.zona_horaria` (cabecera `X-Zona-Horaria`, `src/shared/database.py`);
   sin ella, UTC, que es lo mismo que `CURRENT_DATE` con la sesión en UTC.
   Reemplaza a `CURRENT_DATE` en las funciones y el CHECK de los módulos de
   este backend (1, 2, 4 y 5), para que la BD y la API coincidan en qué es
   "hoy" o "fecha futura". Los cuerpos se toman de la BD (`pg_get_functiondef`)
   y solo se sustituye esa palabra: así no se pisa ninguna versión que difiera
   entre ambientes. Los objetos de los módulos 6, 7 y 8 no son de este backend
   y no se tocan.
"""
from __future__ import annotations

import re

import sqlalchemy as sa
from alembic import op

revision = '1425bc9cdb59'
down_revision = 'bf404c6f1018'
branch_labels = None
depends_on = None

_TABLA = 'modulo2.detalles_activos_individuales'
_COLUMNA = 'fecha_nacimeinto'

# Funciones y procedimientos con CURRENT_DATE de los módulos de este backend.
_FUNCIONES = (
    'modulo1.sp_registrar_usuario',
    'modulo2.trg_fn_activo_fecha_inicio_valida',
    'modulo4.sp_evaluar_degradacion_modelo',
    'modulo5.fn_trg_medicamento_fecha_no_futura',
    'modulo5.fn_trg_reporte_gastos_fechas_coherentes',
    'modulo5.sp_calcular_ica',
    'modulo5.sp_ejecutar_batch_ica_automatizado',
)
_CHECKS = (('modulo2.activos_biologicos', 'chk_activos_fecha_inicio_ciclo_no_futura'),)

_HOY = 'modulo1.fn_hoy_usuario()'
_RE_CURRENT_DATE = re.compile(r'\bCURRENT_DATE\b', re.IGNORECASE)
_RE_HOY = re.compile(re.escape(_HOY), re.IGNORECASE)


def _vistas_dependientes(conn) -> list[dict]:
    """Definición completa de cada vista que lee la columna, para recrearla igual."""
    filas = conn.execute(sa.text("""
        SELECT DISTINCT v.oid, v.oid::regclass::text AS nombre
        FROM pg_depend d
        JOIN pg_rewrite r ON r.oid = d.objid
        JOIN pg_class v ON v.oid = r.ev_class
        WHERE d.refobjid = CAST(:tabla AS regclass)
          AND d.refobjsubid = (SELECT attnum FROM pg_attribute
                               WHERE attrelid = CAST(:tabla AS regclass) AND attname = :col)
          AND v.oid <> d.refobjid
    """), {'tabla': _TABLA, 'col': _COLUMNA}).fetchall()
    vistas = []
    for oid, nombre in filas:
        info = conn.execute(sa.text("""
            SELECT pg_get_viewdef(c.oid) AS definicion, c.reloptions AS opciones,
                   pg_get_userbyid(c.relowner) AS dueno, obj_description(c.oid, 'pg_class') AS comentario
            FROM pg_class c WHERE c.oid = :oid
        """), {'oid': oid}).mappings().one()
        permisos = conn.execute(sa.text("""
            SELECT CASE WHEN a.grantee = 0 THEN 'PUBLIC' ELSE quote_ident(pg_get_userbyid(a.grantee)) END,
                   a.privilege_type
            FROM pg_class c, aclexplode(c.relacl) a
            WHERE c.oid = :oid AND a.grantee <> c.relowner
        """), {'oid': oid}).fetchall()
        columnas = conn.execute(sa.text("""
            SELECT quote_ident(attname), col_description(attrelid, attnum)
            FROM pg_attribute WHERE attrelid = :oid AND attnum > 0 AND col_description(attrelid, attnum) IS NOT NULL
        """), {'oid': oid}).fetchall()
        vistas.append({'nombre': nombre, **info, 'permisos': permisos, 'columnas': columnas})
    return vistas


def _recrear_vistas(conn, vistas: list[dict]) -> None:
    for v in vistas:
        opciones = f" WITH ({', '.join(v['opciones'])})" if v['opciones'] else ''
        op.execute(f"CREATE VIEW {v['nombre']}{opciones} AS {v['definicion']}")
        dueno_actual = conn.execute(sa.text('SELECT current_user')).scalar()
        if v['dueno'] != dueno_actual:
            op.execute(f'ALTER VIEW {v["nombre"]} OWNER TO "{v["dueno"]}"')
        for grantee, privilegio in v['permisos']:
            op.execute(f"GRANT {privilegio} ON {v['nombre']} TO {grantee}")
        if v['comentario'] is not None:
            conn.execute(sa.text(f"COMMENT ON VIEW {v['nombre']} IS {_literal(conn, v['comentario'])}"))
        for columna, comentario in v['columnas']:
            conn.execute(sa.text(f"COMMENT ON COLUMN {v['nombre']}.{columna} IS {_literal(conn, comentario)}"))


def _literal(conn, texto: str) -> str:
    return conn.execute(sa.text('SELECT quote_literal(:t)'), {'t': texto}).scalar()


def _cambiar_tipo(nuevo_tipo: str, conversion: str) -> None:
    conn = op.get_bind()
    vistas = _vistas_dependientes(conn)
    for v in vistas:
        op.execute(f"DROP VIEW {v['nombre']}")
    op.execute(f'ALTER TABLE {_TABLA} ALTER COLUMN {_COLUMNA} TYPE {nuevo_tipo} USING {conversion}')
    _recrear_vistas(conn, vistas)


def _sustituir(origen: re.Pattern, destino: str) -> None:
    """Reescribe cada función y CHECK de la lista cambiando solo `origen` por `destino`."""
    conn = op.get_bind()
    for nombre in _FUNCIONES:
        nsp, proname = nombre.split('.')
        definiciones = conn.execute(sa.text("""
            SELECT pg_get_functiondef(p.oid) FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
            WHERE n.nspname = :nsp AND p.proname = :proname
        """), {'nsp': nsp, 'proname': proname}).scalars().all()
        for definicion in definiciones:
            if origen.search(definicion):
                op.execute(origen.sub(destino, definicion))
    for tabla, check in _CHECKS:
        definicion = conn.execute(sa.text("""
            SELECT pg_get_constraintdef(oid) FROM pg_constraint
            WHERE conrelid = CAST(:tabla AS regclass) AND conname = :check
        """), {'tabla': tabla, 'check': check}).scalar()
        if definicion is not None and origen.search(definicion):
            op.execute(f'ALTER TABLE {tabla} DROP CONSTRAINT {check}, '
                       f'ADD CONSTRAINT {check} {origen.sub(destino, definicion)}')


def upgrade() -> None:
    op.execute(f"""
        CREATE OR REPLACE FUNCTION {_HOY.removesuffix('()')}()
        RETURNS date
        LANGUAGE plpgsql
        STABLE
        AS $$
        DECLARE
            zona text := NULLIF(current_setting('app.zona_horaria', true), '');
        BEGIN
            -- Día de hoy en la zona del usuario (cabecera X-Zona-Horaria de la API).
            -- Sin zona, o con una que Postgres no reconoce, el día UTC.
            IF zona IS NULL THEN
                RETURN (now() AT TIME ZONE 'UTC')::date;
            END IF;
            RETURN (now() AT TIME ZONE zona)::date;
        EXCEPTION WHEN invalid_parameter_value THEN
            RETURN (now() AT TIME ZONE 'UTC')::date;
        END
        $$
    """)
    op.execute(f"COMMENT ON FUNCTION {_HOY} IS "
               "'Hoy en la zona de app.zona_horaria (X-Zona-Horaria); UTC si no hay. Ver src/shared/fechas.py.'")
    _cambiar_tipo('date', f"({_COLUMNA} AT TIME ZONE 'UTC')::date")
    _sustituir(_RE_CURRENT_DATE, _HOY)


def downgrade() -> None:
    _sustituir(_RE_HOY, 'CURRENT_DATE')
    _cambiar_tipo('timestamp with time zone', f"{_COLUMNA}::timestamp AT TIME ZONE 'UTC'")
    op.execute(f'DROP FUNCTION {_HOY}')
