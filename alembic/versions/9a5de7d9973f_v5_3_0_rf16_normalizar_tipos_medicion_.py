"""v5.3.0_rf16_normalizar_tipos_medicion_legacy.

Revision ID: 9a5de7d9973f
Revises: 1147428cd8fb
Create Date: 2026-09-17 01:55:51.131812

RF-16 / INC-M09-06-G15 / #303.

Las métricas globales históricas usaban ``tipo_medicion`` como método de
captura (``manual``/``calculada``), mientras RF-16 lo redefine como magnitud
(``PESO``/``VOLUMEN``/``LONGITUD``/``CONTEO``/``OTRO``). La revisión
``192872fafd40`` agregó el CHECK como NOT VALID, pero dejó esas filas sin
normalizar. Esto hacía que la hidratación del repositorio lanzara ValueError
antes de evaluar las dependencias de una métrica.

Esta revisión convierte los valores históricos, corrige ``tipo_dato`` y
valida definitivamente el CHECK. También repara los ocho indicadores globales
si un entorno los convirtió previamente a CONTEO de forma indiscriminada.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '9a5de7d9973f'
down_revision: Union[str, Sequence[str], None] = '1147428cd8fb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Los ids 1..8 son el catálogo global legado documentado desde el baseline.
    # Su clasificación no se infiere del valor actual porque algunos entornos
    # ya lo habían reemplazado incorrectamente por CONTEO para todas las filas.
    op.execute(
        """
        WITH normalizadas AS (
            SELECT
                id_metrica_produccion,
                CASE
                    WHEN id_especie IS NULL
                         AND id_metrica_produccion IN (1, 2)
                        THEN 'PESO'
                    WHEN id_especie IS NULL
                         AND id_metrica_produccion IN (3, 4, 5, 6, 7, 8)
                        THEN 'OTRO'
                    WHEN id_metrica_produccion = 14
                         AND lower(trim(nombre)) = 'talla tilapia'
                         AND lower(trim(unidad_medida)) IN ('cm', 'm')
                        THEN 'LONGITUD'
                    WHEN upper(trim(tipo_medicion)) = 'TALLA'
                        THEN 'LONGITUD'
                    WHEN upper(trim(tipo_medicion)) IN
                         ('PESO', 'VOLUMEN', 'LONGITUD', 'CONTEO', 'OTRO')
                        THEN upper(trim(tipo_medicion))
                    WHEN lower(trim(tipo_medicion)) IN ('manual', 'calculada')
                        THEN CASE
                            WHEN lower(trim(unidad_medida)) IN ('kg', 'g', 'lb')
                                THEN 'PESO'
                            WHEN lower(trim(unidad_medida)) IN ('litros', 'l', 'ml')
                                THEN 'VOLUMEN'
                            WHEN lower(trim(unidad_medida)) IN ('cm', 'm')
                                THEN 'LONGITUD'
                            WHEN lower(trim(unidad_medida)) = 'unidades'
                                THEN 'CONTEO'
                            ELSE 'OTRO'
                        END
                    ELSE NULL
                END AS nuevo_tipo,
                CASE
                    WHEN id_especie IS NULL
                         AND id_metrica_produccion BETWEEN 1 AND 8
                        THEN 'NUMERICO'
                    WHEN id_metrica_produccion = 14
                         AND lower(trim(nombre)) = 'talla tilapia'
                        THEN 'NUMERICO'
                    WHEN upper(trim(tipo_medicion)) = 'TALLA'
                        THEN 'NUMERICO'
                    WHEN lower(trim(tipo_medicion)) IN ('manual', 'calculada')
                         AND lower(trim(unidad_medida)) = 'unidades'
                        THEN 'ENTERO'
                    WHEN lower(trim(tipo_medicion)) IN ('manual', 'calculada')
                        THEN 'NUMERICO'
                    ELSE tipo_dato
                END AS nuevo_tipo_dato
            FROM modulo9.metricas_produccion
        )
        UPDATE modulo9.metricas_produccion AS metrica
        SET tipo_medicion = normalizadas.nuevo_tipo,
            tipo_dato = normalizadas.nuevo_tipo_dato
        FROM normalizadas
        WHERE normalizadas.id_metrica_produccion = metrica.id_metrica_produccion
          AND normalizadas.nuevo_tipo IS NOT NULL
          AND (
              metrica.tipo_medicion IS DISTINCT FROM normalizadas.nuevo_tipo
              OR metrica.tipo_dato IS DISTINCT FROM normalizadas.nuevo_tipo_dato
          );
        """
    )

    # No reinterpretar silenciosamente un valor desconocido. Si aparece uno,
    # el despliegue se detiene y exige clasificarlo explícitamente.
    op.execute(
        """
        DO $$
        DECLARE
            valores_invalidos text;
        BEGIN
            SELECT string_agg(
                id_metrica_produccion || ':' || tipo_medicion,
                ', ' ORDER BY id_metrica_produccion
            )
            INTO valores_invalidos
            FROM modulo9.metricas_produccion
            WHERE tipo_medicion NOT IN
                  ('PESO', 'VOLUMEN', 'LONGITUD', 'CONTEO', 'OTRO');

            IF valores_invalidos IS NOT NULL THEN
                RAISE EXCEPTION
                    'RF-16: tipos_medicion legados sin clasificar: %',
                    valores_invalidos;
            END IF;
        END
        $$;
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'chk_metricas_tipo_medicion'
                  AND conrelid = 'modulo9.metricas_produccion'::regclass
            ) THEN
                ALTER TABLE modulo9.metricas_produccion
                    ADD CONSTRAINT chk_metricas_tipo_medicion
                    CHECK (
                        tipo_medicion IN
                        ('PESO', 'VOLUMEN', 'LONGITUD', 'CONTEO', 'OTRO')
                    ) NOT VALID;
            END IF;
        END
        $$;

        ALTER TABLE modulo9.metricas_produccion
            VALIDATE CONSTRAINT chk_metricas_tipo_medicion;
        """
    )


def downgrade() -> None:
    # La revisión no agrega estructura propia. Reintroducir
    # manual/calculada/TALLA restauraría el 500 y volvería a dejar inválido el
    # CHECK creado por 192872fafd40, por lo que la corrección de datos se
    # conserva deliberadamente al bajar la revisión.
    pass
