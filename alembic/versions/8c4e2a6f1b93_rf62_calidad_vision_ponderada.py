# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-25 | Arekkazu | INC-M03-134-G192 RF-62: calidad de visión ponderada, asíncrona y persistida |
"""RF-62: calidad de visión ponderada (AIOT-SPEC-01), evaluada después de la ingesta

Revision ID: 8c4e2a6f1b93
Revises: 517bee7b766c
Create Date: 2026-10-25

Por qué va por Alembic: es el patrón del repo y CI solo despliega lo que está
en `alembic/versions/`.

RF-62 (completación del 2026-10-16) define el índice de visión como suma
ponderada con modificador de calibración, clases OPTIMA/DEGRADADA/NO_APTA y un
proceso asíncrono que no retrasa la ingesta (INC-M03-134-G192, #689). El
esquema solo admitía el cálculo heredado:

- `indice_calidad SMALLINT NOT NULL` → `indice_calidad_vision NUMERIC(5,2)`,
  nombre de RF-62; el índice ponderado tiene decimales (p. ej. 91.6).
- `clasificacion_calidad` pasa de APTO/APTO_CON_RESERVA/NO_APTO a
  OPTIMA/DEGRADADA/NO_APTA. Los tramos (80/40) son los mismos, así que las filas
  históricas se renombran 1:1; su índice heredado no se recalcula.
- Las columnas de evaluación admiten NULL mientras la observación espera su
  evaluación, y `fecha_evaluacion_calidad` marca cuándo se evaluó. Un CHECK
  exige que se llenen todas juntas.
- `sgpmp_app` recibe UPDATE solo sobre las columnas de evaluación: los
  indicadores crudos y el vector siguen sin poder modificarse desde la API.

`apto_para_nic41` no se persiste: es `false` para toda observación de visión
(RF-62), una columna constante sería un dato derivado.
"""
from __future__ import annotations

from alembic import op

revision = '8c4e2a6f1b93'
down_revision = '517bee7b766c'
branch_labels = None
depends_on = None

TABLA = 'modulo3.observaciones_vision'
_EVALUACION = (
    'indice_calidad_vision, clasificacion_calidad, es_apto_para_ia, '
    'es_confianza_baja, json_flags_detectados, fecha_evaluacion_calidad'
)


def upgrade() -> None:
    op.execute(f"""
        ALTER TABLE {TABLA} DROP CONSTRAINT ck_observacion_vision_indice_calidad;
        ALTER TABLE {TABLA} DROP CONSTRAINT ck_observacion_vision_clasificacion_calidad;
        ALTER TABLE {TABLA} RENAME COLUMN indice_calidad TO indice_calidad_vision;
        ALTER TABLE {TABLA}
            ALTER COLUMN indice_calidad_vision TYPE numeric(5,2) USING indice_calidad_vision::numeric,
            ALTER COLUMN indice_calidad_vision DROP NOT NULL,
            ALTER COLUMN clasificacion_calidad DROP NOT NULL,
            ALTER COLUMN es_apto_para_ia DROP NOT NULL,
            ADD COLUMN fecha_evaluacion_calidad timestamptz;

        UPDATE {TABLA}
        SET clasificacion_calidad = CASE clasificacion_calidad
                WHEN 'APTO' THEN 'OPTIMA'
                WHEN 'APTO_CON_RESERVA' THEN 'DEGRADADA'
                ELSE 'NO_APTA'
            END,
            es_confianza_baja = (clasificacion_calidad = 'APTO_CON_RESERVA'),
            fecha_evaluacion_calidad = fecha_creacion;

        ALTER TABLE {TABLA}
            ADD CONSTRAINT ck_observacion_vision_indice_calidad_vision
                CHECK (indice_calidad_vision BETWEEN 0 AND 100),
            ADD CONSTRAINT ck_observacion_vision_clasificacion_calidad
                CHECK (clasificacion_calidad IN ('OPTIMA', 'DEGRADADA', 'NO_APTA')),
            ADD CONSTRAINT ck_observacion_vision_evaluacion_completa CHECK (
                (fecha_evaluacion_calidad IS NULL
                    AND indice_calidad_vision IS NULL AND clasificacion_calidad IS NULL
                    AND es_apto_para_ia IS NULL AND es_confianza_baja IS NULL)
                OR (fecha_evaluacion_calidad IS NOT NULL
                    AND indice_calidad_vision IS NOT NULL AND clasificacion_calidad IS NOT NULL
                    AND es_apto_para_ia IS NOT NULL AND es_confianza_baja IS NOT NULL)
            );

        COMMENT ON COLUMN {TABLA}.indice_calidad_vision IS
            'RF-62: 100 x (w1*cobertura + w2*fps + w3*continuidad) x factor de calibración. NULL hasta evaluarse.';
        COMMENT ON COLUMN {TABLA}.fecha_evaluacion_calidad IS
            'RF-62: instante de la evaluación asíncrona de calidad. NULL = pendiente.';

        GRANT UPDATE ({_EVALUACION}) ON {TABLA} TO sgpmp_app;
    """)


def downgrade() -> None:
    op.execute(f"""
        REVOKE UPDATE ({_EVALUACION}) ON {TABLA} FROM sgpmp_app;
        ALTER TABLE {TABLA} DROP CONSTRAINT ck_observacion_vision_evaluacion_completa;
        ALTER TABLE {TABLA} DROP CONSTRAINT ck_observacion_vision_clasificacion_calidad;
        ALTER TABLE {TABLA} DROP CONSTRAINT ck_observacion_vision_indice_calidad_vision;

        -- Las pendientes no tienen evaluación que conservar: quedan NO_APTO.
        UPDATE {TABLA}
        SET clasificacion_calidad = CASE clasificacion_calidad
                WHEN 'OPTIMA' THEN 'APTO'
                WHEN 'DEGRADADA' THEN 'APTO_CON_RESERVA'
                ELSE 'NO_APTO'
            END,
            indice_calidad_vision = round(coalesce(indice_calidad_vision, 0)),
            es_apto_para_ia = coalesce(es_apto_para_ia, false);

        ALTER TABLE {TABLA} DROP COLUMN fecha_evaluacion_calidad;
        ALTER TABLE {TABLA}
            ALTER COLUMN indice_calidad_vision TYPE smallint USING indice_calidad_vision::smallint,
            ALTER COLUMN indice_calidad_vision SET NOT NULL,
            ALTER COLUMN clasificacion_calidad SET NOT NULL,
            ALTER COLUMN es_apto_para_ia SET NOT NULL;
        ALTER TABLE {TABLA} RENAME COLUMN indice_calidad_vision TO indice_calidad;
        ALTER TABLE {TABLA}
            ADD CONSTRAINT ck_observacion_vision_indice_calidad
                CHECK (indice_calidad >= 0 AND indice_calidad <= 100),
            ADD CONSTRAINT ck_observacion_vision_clasificacion_calidad
                CHECK (clasificacion_calidad IN ('APTO', 'APTO_CON_RESERVA', 'NO_APTO'));
    """)
