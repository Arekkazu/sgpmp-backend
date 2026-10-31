# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-31 | Arekkazu | CP17/TC-DIS-160 RF-59: índices para que el historial de 30-90 días responda |
"""RF-59: índices para el historial de lecturas (rangos de 30, 60 y 90 días)

Revision ID: c3f1a9d27e48
Revises: 6bd01d026ac4
Create Date: 2026-10-31

Por qué va por Alembic: es el patrón del repo y CI solo despliega lo que está
en `alembic/versions/`.

QA (CP17, TC-DIS-160) reporta que los rangos rápidos de 30, 60 y 90 días del
Historial terminan en "Error al cargar el historial": el front corta a los 15 s.
La consulta del historial (y su conteo y estadísticas) hace dos cosas sin índice:

- filtra `modulo3.telemetrias` solo por `timestamp_captura` cuando no hay sensor
  ni variable; los índices existentes empiezan por `id_sensor`, `id_variable`,
  `id_dispositivo_iot`, `estado_calidad` u `origen`, así que el rango sin otro
  filtro termina en un Seq Scan de toda la tabla;
- cuenta, por cada lectura, sus alertas en `modulo3.alertas` por `id_telemetria`
  (LATERAL `alc`), columna que no tenía índice: un Seq Scan de alertas por lectura.

Se crean con CONCURRENTLY para no bloquear las escrituras del broker mientras se
construyen; por eso corren fuera de la transacción de la migración.
"""
from __future__ import annotations

from alembic import op

revision = 'c3f1a9d27e48'
down_revision = '6bd01d026ac4'
branch_labels = None
depends_on = None

# SQL literal por índice (sin f-strings): el SAST trata la interpolación como CWE-89.
_INDICES = (
    (
        "SELECT 1 FROM pg_index i JOIN pg_class c ON c.oid = i.indexrelid "
        "WHERE c.oid = to_regclass('modulo3.idx_telemetria_timestamp_captura') AND NOT i.indisvalid",
        'DROP INDEX CONCURRENTLY modulo3.idx_telemetria_timestamp_captura',
        'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_telemetria_timestamp_captura '
        'ON modulo3.telemetrias (timestamp_captura DESC)',
        'DROP INDEX CONCURRENTLY IF EXISTS modulo3.idx_telemetria_timestamp_captura',
    ),
    (
        "SELECT 1 FROM pg_index i JOIN pg_class c ON c.oid = i.indexrelid "
        "WHERE c.oid = to_regclass('modulo3.idx_alerta_id_telemetria') AND NOT i.indisvalid",
        'DROP INDEX CONCURRENTLY modulo3.idx_alerta_id_telemetria',
        'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_alerta_id_telemetria ON modulo3.alertas (id_telemetria)',
        'DROP INDEX CONCURRENTLY IF EXISTS modulo3.idx_alerta_id_telemetria',
    ),
)


def upgrade() -> None:
    with op.get_context().autocommit_block():
        for consulta_invalido, retirar, crear, _ in _INDICES:
            # Un CONCURRENTLY interrumpido deja el índice INVALID; IF NOT EXISTS lo
            # daría por bueno en el reintento, así que se retira antes de crearlo.
            if op.get_bind().exec_driver_sql(consulta_invalido).scalar():
                op.execute(retirar)
            op.execute(crear)


def downgrade() -> None:
    with op.get_context().autocommit_block():
        for _, _, _, retirar in _INDICES:
            op.execute(retirar)
