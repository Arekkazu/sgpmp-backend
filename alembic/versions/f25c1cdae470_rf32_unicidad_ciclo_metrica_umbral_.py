"""rf32_unicidad_ciclo_metrica_umbral_ignora_inactivas

Revision ID: f25c1cdae470
Revises: 52f259545ea8
Create Date: 2026-09-05 11:40:57.092922

RF-32 (issues #128, #129) — aplicar una plantilla desactiva las filas vigentes
(`es_activo = false`) e inserta las nuevas, pero 3 de las 4 reglas de
unicidad de `modulo9` comparaban contra TODAS las filas, activas o no:

- `trg_fn_ciclos_biologicos_nombre_unique_ci` (DUPLICATE_STAGE, P0104)
- `trg_fn_metricas_produccion_nombre_unique_ci` (DUPLICATE_METRIC, P0109)
- `uq_umbral_especie_variable` (UNIQUE plano, sin filtro)

Por eso reaplicar una plantilla sobre la misma especie que ya tenía esos
nombres/variables (el caso normal de uso) chocaba con la fila recién
desactivada y el endpoint respondía 500 (el error custom del trigger no lo
traduce `db_error_translator`, cae al catch-all).

Esta migración hace que las 3 reglas ignoren filas desactivadas:
- Los dos triggers de nombre único agregan `AND es_activo = true` al conteo.
- `uq_umbral_especie_variable` pasa de UNIQUE constraint a índice único
  parcial `WHERE es_activo = true` (un CONSTRAINT normal no admite WHERE).
  Mismo nombre: ya cumple la convención `uq_<columnas>`.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f25c1cdae470'
down_revision: Union[str, Sequence[str], None] = '52f259545ea8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
    CREATE OR REPLACE FUNCTION modulo9.trg_fn_ciclos_biologicos_nombre_unique_ci()
    RETURNS trigger
    LANGUAGE plpgsql
    AS $function$
    DECLARE
        v_count INTEGER;
    BEGIN
        SELECT COUNT(*) INTO v_count
        FROM modulo9.ciclos_biologicos
        WHERE LOWER(TRIM(nombre)) = LOWER(TRIM(NEW.nombre))
          AND id_especie          = NEW.id_especie
          AND es_activo           = true
          AND id_ciclo_biologico <> COALESCE(NEW.id_ciclo_biologico, -1);

        IF v_count > 0 THEN
            RAISE EXCEPTION 'DUPLICATE_STAGE: Ya existe una etapa llamada "%" para esta especie. Los nombres de etapa deben ser únicos por especie (case-insensitive).',
                NEW.nombre
                USING ERRCODE = 'P0104';
        END IF;

        RETURN NEW;
    END;
    $function$
    """)
    op.execute("""
    CREATE OR REPLACE FUNCTION modulo9.trg_fn_metricas_produccion_nombre_unique_ci()
    RETURNS trigger
    LANGUAGE plpgsql
    AS $function$
    DECLARE
        v_count INTEGER;
    BEGIN
        SELECT COUNT(*) INTO v_count
        FROM modulo9.metricas_produccion
        WHERE LOWER(TRIM(nombre))    = LOWER(TRIM(NEW.nombre))
          AND es_activo              = true
          AND id_metrica_produccion <> COALESCE(NEW.id_metrica_produccion, -1);

        IF v_count > 0 THEN
            RAISE EXCEPTION 'DUPLICATE_METRIC: Ya existe una métrica productiva con el nombre "%" (case-insensitive).',
                NEW.nombre
                USING ERRCODE = 'P0109';
        END IF;

        RETURN NEW;
    END;
    $function$
    """)
    op.execute("ALTER TABLE modulo9.umbrales_ambientales DROP CONSTRAINT uq_umbral_especie_variable;")
    op.execute("""
        CREATE UNIQUE INDEX uq_umbral_especie_variable
            ON modulo9.umbrales_ambientales (id_especie, id_variable_ambiental)
            WHERE es_activo = true;
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS modulo9.uq_umbral_especie_variable;")
    op.execute("""
        ALTER TABLE modulo9.umbrales_ambientales
        ADD CONSTRAINT uq_umbral_especie_variable UNIQUE (id_especie, id_variable_ambiental);
    """)
    op.execute("""
    CREATE OR REPLACE FUNCTION modulo9.trg_fn_metricas_produccion_nombre_unique_ci()
    RETURNS trigger
    LANGUAGE plpgsql
    AS $function$
    DECLARE
        v_count INTEGER;
    BEGIN
        SELECT COUNT(*) INTO v_count
        FROM modulo9.metricas_produccion
        WHERE LOWER(TRIM(nombre))    = LOWER(TRIM(NEW.nombre))
          AND id_metrica_produccion <> COALESCE(NEW.id_metrica_produccion, -1);

        IF v_count > 0 THEN
            RAISE EXCEPTION 'DUPLICATE_METRIC: Ya existe una métrica productiva con el nombre "%" (case-insensitive).',
                NEW.nombre
                USING ERRCODE = 'P0109';
        END IF;

        RETURN NEW;
    END;
    $function$
    """)
    op.execute("""
    CREATE OR REPLACE FUNCTION modulo9.trg_fn_ciclos_biologicos_nombre_unique_ci()
    RETURNS trigger
    LANGUAGE plpgsql
    AS $function$
    DECLARE
        v_count INTEGER;
    BEGIN
        SELECT COUNT(*) INTO v_count
        FROM modulo9.ciclos_biologicos
        WHERE LOWER(TRIM(nombre)) = LOWER(TRIM(NEW.nombre))
          AND id_especie          = NEW.id_especie
          AND id_ciclo_biologico <> COALESCE(NEW.id_ciclo_biologico, -1);

        IF v_count > 0 THEN
            RAISE EXCEPTION 'DUPLICATE_STAGE: Ya existe una etapa llamada "%" para esta especie. Los nombres de etapa deben ser únicos por especie (case-insensitive).',
                NEW.nombre
                USING ERRCODE = 'P0104';
        END IF;

        RETURN NEW;
    END;
    $function$
    """)
