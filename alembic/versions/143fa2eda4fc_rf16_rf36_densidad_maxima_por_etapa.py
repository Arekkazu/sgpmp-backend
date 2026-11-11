# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-10 | Arekkazu | #391/#394 RF-16/RF-36: densidad y biomasa máximas por etapa con aviso preventivo |
"""rf16 rf36 densidad maxima por etapa

Revision ID: 143fa2eda4fc
Revises: 4fa0e24ea021
Create Date: 2026-11-10

#391 y #394. La densidad máxima por especie de RFC-012 (RF-15, ``especies.densidad_maxima_por_especie``)
sigue limitando la capacidad del área. Esta migración agrega a cada etapa (``modulo9.ciclos_biologicos``)
un límite propio, opcional, para el lote que está en esa fase:

- ``densidad_maxima``: animales por m², mayor que 0 y hasta 200.
- ``biomasa_maxima``: kg por m², mayor que 0. Opcional.
- ``aviso_preventivo_pct``: porcentaje del máximo desde el que la ficha avisa: 80, 85, 90 o 95 (90 por defecto).

Una etapa sin ``densidad_maxima`` no bloquea nada: la ficha del lote la reporta como sin configurar.

También da lectura del recurso ``ciclos_biologicos`` a Productor, Ingeniero de Campo y Contador, que ven las
etapas y su densidad sin poder editarlas (#392). Se resuelve por nombre de rol y de recurso, no por id.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "143fa2eda4fc"
down_revision: Union[str, Sequence[str], None] = "4fa0e24ea021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_LECTORES = (("Productor", "prod"), ("Ingeniero de Campo", "ing"), ("Contador", "cont"))


def upgrade() -> None:
    op.execute("""
        ALTER TABLE modulo9.ciclos_biologicos
            ADD COLUMN densidad_maxima numeric(6, 2),
            ADD COLUMN biomasa_maxima numeric(8, 2),
            ADD COLUMN aviso_preventivo_pct smallint NOT NULL DEFAULT 90,
            ADD CONSTRAINT ck_ciclo_biologico_densidad_maxima
                CHECK (densidad_maxima IS NULL OR (densidad_maxima > 0 AND densidad_maxima <= 200)),
            ADD CONSTRAINT ck_ciclo_biologico_biomasa_maxima
                CHECK (biomasa_maxima IS NULL OR biomasa_maxima > 0),
            ADD CONSTRAINT ck_ciclo_biologico_aviso_preventivo_pct
                CHECK (aviso_preventivo_pct IN (80, 85, 90, 95))
    """)
    op.execute("COMMENT ON COLUMN modulo9.ciclos_biologicos.densidad_maxima IS "
               "'Animales por m2 que admite un lote en esta etapa (RF-16, RF-36). NULL: sin límite propio.'")
    op.execute("COMMENT ON COLUMN modulo9.ciclos_biologicos.biomasa_maxima IS 'Kg por m2 en esta etapa. Opcional.'")
    op.execute("COMMENT ON COLUMN modulo9.ciclos_biologicos.aviso_preventivo_pct IS "
               "'Porcentaje de la densidad máxima desde el que la ficha del lote avisa.'")
    for rol, prefijo in _LECTORES:
        op.execute(f"""
            INSERT INTO modulo1.permisos (nombre, descripcion, id_rol, id_recurso, id_accion, es_activo)
            SELECT '{prefijo}_leer_ciclo_biologico', 'Consultar etapas del ciclo productivo y su densidad máxima',
                   r.id_rol, re.id_recurso, a.id_accion, TRUE
            FROM modulo1.roles r, modulo1.recursos re, modulo1.acciones a
            WHERE r.nombre_rol = '{rol}' AND re.nombre_recurso = 'ciclos_biologicos' AND btrim(a.codigo) = 'R'
            ON CONFLICT (id_rol, id_recurso, id_accion) DO NOTHING
        """)  # nosec B608 - constantes del módulo


def downgrade() -> None:
    op.execute("""
        DELETE FROM modulo1.permisos
        WHERE nombre IN ('prod_leer_ciclo_biologico', 'ing_leer_ciclo_biologico', 'cont_leer_ciclo_biologico')
    """)
    op.execute("""
        ALTER TABLE modulo9.ciclos_biologicos
            DROP COLUMN aviso_preventivo_pct,
            DROP COLUMN biomasa_maxima,
            DROP COLUMN densidad_maxima
    """)
