# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-31 | Arekkazu | CP17/TC-DIS-160 RF-59: índices para que el historial de 30-90 días responda |
# | 2026-10-31 | Arekkazu | CP17/TC-DIS-160 RF-59: encadena tras f6b8d0e2a457; telemetrias ya es particionada (#891) |
"""RF-59: índices para el historial de lecturas (rangos de 30, 60 y 90 días)

Revision ID: c3f1a9d27e48
Revises: f6b8d0e2a457
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

El de `alertas` se crea con CONCURRENTLY para no bloquear las escrituras del broker;
por eso todo corre fuera de la transacción de la migración. `telemetrias` es una tabla
particionada desde e5a1c7d39f62 (#891) y PostgreSQL no admite CONCURRENTLY sobre ella:
su índice se crea normal sobre el padre, que lo construye en cada partición (bloquea las
escrituras de telemetría solo mientras se construye) y lo hereda a las particiones nuevas.
"""
from __future__ import annotations

from alembic import op

revision = 'c3f1a9d27e48'
down_revision = 'f6b8d0e2a457'
branch_labels = None
depends_on = None

# SQL literal por índice (sin f-strings): el SAST trata la interpolación como CWE-89.
_INDICES = (
    (
        "SELECT 1 FROM pg_index i JOIN pg_class c ON c.oid = i.indexrelid "
        "WHERE c.oid = to_regclass('modulo3.idx_telemetria_timestamp_captura') AND NOT i.indisvalid",
        'DROP INDEX modulo3.idx_telemetria_timestamp_captura',
        # Tabla particionada: sin CONCURRENTLY (no lo admite) ni en la creación ni al retirarlo.
        'CREATE INDEX IF NOT EXISTS idx_telemetria_timestamp_captura '
        'ON modulo3.telemetrias (timestamp_captura DESC)',
        'DROP INDEX IF EXISTS modulo3.idx_telemetria_timestamp_captura',
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
            # Un índice interrumpido queda INVALID; IF NOT EXISTS lo
            # daría por bueno en el reintento, así que se retira antes de crearlo.
            if op.get_bind().exec_driver_sql(consulta_invalido).scalar():
                op.execute(retirar)
            op.execute(crear)


def downgrade() -> None:
    with op.get_context().autocommit_block():
        for _, _, _, retirar in _INDICES:
            op.execute(retirar)
