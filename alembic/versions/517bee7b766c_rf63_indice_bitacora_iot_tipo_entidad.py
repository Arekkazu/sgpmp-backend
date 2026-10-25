# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-25 | Arekkazu | RF-63: índice (tipo_evento, entidad_afectada_id) para que el worker postcommit no pase el statement_timeout |
"""RF-63: índice compuesto en la bitácora IoT para las consultas del worker postcommit

Revision ID: 517bee7b766c
Revises: 1425bc9cdb59
Create Date: 2026-10-25

Por qué va por Alembic: es el patrón del repo y CI solo despliega lo que está
en `alembic/versions/`.

El worker postcommit busca, por cada etapa, los registros sin evidencia
`POSTCOMMIT_<ETAPA>_COMPLETADO` en `modulo3.bitacora_auditoria_iot` (filtro por
`tipo_evento` + `entidad_afectada_id`). Solo había índices de una columna, y en
TEST (1,96 M filas) el planner estimaba 152 completados donde había 15 300:
eligió un Nested Loop con Materialize (117,8 M comparaciones, 16,8 s) y la
consulta de `RF53_AUDITORIA` pasaba el `statement_timeout` de 10 s en cada ciclo,
así que ninguna etapa posterior volvía a correr. Con este índice cada búsqueda
es un Index Scan: 139 ms (RF53_AUDITORIA) y 4 ms (RF57) sobre una copia de los
datos de TEST.

`idx_bitacora_iot_tipo` (solo `tipo_evento`) es prefijo del nuevo y se retira
para no pagar dos índices en cada INSERT de la bitácora.

Se crea con CONCURRENTLY para no bloquear las escrituras del broker mientras se
construye; por eso corre fuera de la transacción de la migración.
"""
from __future__ import annotations

from alembic import op

revision = '517bee7b766c'
down_revision = '1425bc9cdb59'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute('''CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_bitacora_iot_tipo_evento_entidad_afectada_id
            ON modulo3.bitacora_auditoria_iot (tipo_evento, entidad_afectada_id)''')
        op.execute('DROP INDEX CONCURRENTLY IF EXISTS modulo3.idx_bitacora_iot_tipo')


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute('''CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_bitacora_iot_tipo
            ON modulo3.bitacora_auditoria_iot (tipo_evento)''')
        op.execute('DROP INDEX CONCURRENTLY IF EXISTS modulo3.idx_bitacora_iot_tipo_evento_entidad_afectada_id')
