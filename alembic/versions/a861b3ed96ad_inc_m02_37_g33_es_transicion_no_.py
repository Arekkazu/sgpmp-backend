"""inc_m02_37_g33_es_transicion_no_estandar_gestiones_fases

Revision ID: a861b3ed96ad
Revises: 3cb8965cdc6d
Create Date: 2026-09-26 13:00:00.000000

INC-M02-37-G33 (#462), RF-37. Un cambio de fase fuera de la secuencia estándar
con `confirmacion_no_estandar = true` respondía 201 con
`es_transicion_no_estandar: true`, pero el historial (`GET
/activos-biologicos/{id}/fases`) mostraba `false` para esa misma fase: la tabla
`modulo2.gestiones_fases` no tenía dónde guardar el dato y el INSERT no lo
enviaba. El único rastro era el evento `FASE_CAMBIADA` de la bitácora de M02,
que no es el historial que consulta el usuario.

Esta migración agrega la columna `es_transicion_no_estandar` (convención de
nomenclatura: booleano con prefijo `es_`, español, snake_case) y recupera el
valor de las filas ya creadas a partir de esa bitácora.

Backfill: cada evento `FASE_CAMBIADA` guarda en `detalle_tecnico` el flag y la
llave `registros_rf46 = [{"tabla": "gestiones_fases", "id": <id_gestion_fases>}]`
que lo une con la fila del historial. Solo se marcan las filas que esa llave
identifica con exactitud; un evento anterior a RF-52 E5 sin la llave no se puede
asociar sin adivinar, así que esa fila queda en `false` y la migración lo
informa con un NOTICE (no aborta: es un dato histórico irrecuperable, no un
error de la migración).

`trg_fase_activo_estado_valido` (BEFORE UPDATE, sin filtro de columna) rechaza
cualquier UPDATE sobre la tabla si el activo está en BAJA, y hay filas reales de
activos en BAJA. Igual que hizo `69d26aea234c`, se desactiva solo durante el
UPDATE del backfill -- que no toca fechas ni `es_activa` -- y se reactiva de
inmediato; como el DDL de PostgreSQL es transaccional, un fallo a mitad de
camino revierte también el ENABLE/DISABLE.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "a861b3ed96ad"
down_revision: Union[str, Sequence[str], None] = "3cb8965cdc6d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        DECLARE
            v_eventos_no_estandar INT;
            v_filas_marcadas      INT;
            v_sin_fila_asociada   INT;
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'modulo2' AND table_name = 'bitacora_auditoria_m02'
                  AND column_name = 'detalle_tecnico'
            ) THEN
                RAISE EXCEPTION 'RF-37: bitacora_auditoria_m02.detalle_tecnico no existe -- revisar supuestos de esta migración';
            END IF;

            -- 1) Columna nueva. DEFAULT constante: no reescribe la tabla ni dispara triggers de fila.
            ALTER TABLE modulo2.gestiones_fases
                ADD COLUMN IF NOT EXISTS es_transicion_no_estandar BOOLEAN NOT NULL DEFAULT FALSE;

            COMMENT ON COLUMN modulo2.gestiones_fases.es_transicion_no_estandar IS
                'RF-37: TRUE si esta fase se registró como transición fuera de la secuencia estándar (salto o retroceso) con confirmacion_no_estandar = true. Evidencia consultable desde el historial de fases.';

            -- 2) Backfill desde la bitácora de M02 (ver docstring). trg_fase_activo_estado_valido
            -- se desactiva solo para este UPDATE.
            ALTER TABLE modulo2.gestiones_fases DISABLE TRIGGER trg_fase_activo_estado_valido;

            UPDATE modulo2.gestiones_fases gf
            SET es_transicion_no_estandar = TRUE
            FROM modulo2.bitacora_auditoria_m02 b
            CROSS JOIN LATERAL jsonb_array_elements(
                CASE WHEN jsonb_typeof(b.detalle_tecnico -> 'registros_rf46') = 'array'
                     THEN b.detalle_tecnico -> 'registros_rf46'
                     ELSE '[]'::jsonb END
            ) AS reg
            WHERE b.tipo_evento = 'FASE_CAMBIADA'
              AND b.resultado = 'EXITOSO'
              AND b.detalle_tecnico ->> 'es_transicion_no_estandar' = 'true'
              AND reg ->> 'tabla' = 'gestiones_fases'
              AND reg ->> 'id' = gf.id_gestion_fases::text
              AND gf.es_transicion_no_estandar = FALSE;

            GET DIAGNOSTICS v_filas_marcadas = ROW_COUNT;

            ALTER TABLE modulo2.gestiones_fases ENABLE TRIGGER trg_fase_activo_estado_valido;

            -- 3) Informar cuántos eventos no estándar de la bitácora no tienen fila asociada
            -- (sin llave registros_rf46 o llave que no apunta a gestiones_fases). Conteo
            -- directo, no por diferencia, para que sea correcto también al re-ejecutarse.
            SELECT COUNT(*) INTO v_eventos_no_estandar
            FROM modulo2.bitacora_auditoria_m02 b
            WHERE b.tipo_evento = 'FASE_CAMBIADA'
              AND b.resultado = 'EXITOSO'
              AND b.detalle_tecnico ->> 'es_transicion_no_estandar' = 'true';

            SELECT COUNT(*) INTO v_sin_fila_asociada
            FROM modulo2.bitacora_auditoria_m02 b
            WHERE b.tipo_evento = 'FASE_CAMBIADA'
              AND b.resultado = 'EXITOSO'
              AND b.detalle_tecnico ->> 'es_transicion_no_estandar' = 'true'
              AND NOT EXISTS (
                  SELECT 1
                  FROM jsonb_array_elements(
                           CASE WHEN jsonb_typeof(b.detalle_tecnico -> 'registros_rf46') = 'array'
                                THEN b.detalle_tecnico -> 'registros_rf46'
                                ELSE '[]'::jsonb END
                       ) AS reg
                  JOIN modulo2.gestiones_fases gf
                    ON reg ->> 'tabla' = 'gestiones_fases'
                   AND reg ->> 'id' = gf.id_gestion_fases::text
              );

            RAISE NOTICE 'RF-37 backfill: % evento(s) FASE_CAMBIADA no estándar en la bitácora; % fila(s) de gestiones_fases marcadas ahora; % evento(s) sin fila asociada (esas filas quedan en FALSE).',
                v_eventos_no_estandar, v_filas_marcadas, v_sin_fila_asociada;
        END
        $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE modulo2.gestiones_fases
            DROP COLUMN IF EXISTS es_transicion_no_estandar;
        """
    )
