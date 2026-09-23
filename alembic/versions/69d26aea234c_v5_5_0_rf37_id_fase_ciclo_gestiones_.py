"""v5.5.0_rf37_id_fase_ciclo_gestiones_fases

Revision ID: 69d26aea234c
Revises: c8d4f1a9b7e2
Create Date: 2026-09-23 02:00:00.000000

Tarea Taiga "RF-37: fase_destino/confirmacion_no_estandar, fecha no futura,
RBAC". RF-37 exige un flujo alterno "transición no estándar sin confirmación"
(409), pero el modelo actual de `modulo2.gestiones_fases` no tiene ninguna
columna que registre A QUÉ fase específica del ciclo corresponde cada fila --
`paso_actual`/`nombre_fase_actual` se reconstruyen contando filas en orden
cronológico y asumiendo avance estrictamente secuencial (confirmado en vivo
vía MCP Postgres: `information_schema.columns` de `gestiones_fases` no tiene
ninguna columna de referencia a `ciclos_productivos_biologicos`).

Sin esta columna, permitir una transición "no estándar" (saltar fases o
retroceder) dejaría el sistema sin forma de saber en qué fase quedó el activo
después de esa transición -- el siguiente cálculo de "fase estándar
siguiente" volvería a asumir secuencia estricta y quedaría mal. Se agrega
`id_ciclos_productivo_biologico` (incluida `s` para calzar con el nombre
exacto de la PK que referencia, `modulo9.ciclos_productivos_biologicos.id_ciclos_productivo_biologico`,
según la convención de nomenclatura del proyecto).

Backfill seguro: verificado en vivo que las 19 filas existentes de
`gestiones_fases` siguen el patrón estrictamente secuencial que el código
siempre asumió (posición máxima alcanzada = 2, y todos los ciclos referenciados
tienen suficientes fases para esa posición) -- no existe ninguna fila que
pueda representar un "salto", porque esa capacidad no existía hasta ahora.
Se backfillea con la misma lógica de conteo que ya usa el código
(`ROW_NUMBER() OVER (PARTITION BY id_activo_biologico, id_ciclo_productiva
ORDER BY fecha_inicio, id_gestion_fases)` mapeado a la fase en esa posición),
y la migración verifica que el backfill cubrió el 100% de las filas antes de
dejar la columna `NOT NULL`.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "69d26aea234c"
down_revision: Union[str, Sequence[str], None] = "c8d4f1a9b7e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        DECLARE
            v_sin_backfill INT;
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'modulo2' AND table_name = 'gestiones_fases'
                  AND column_name = 'id_ciclo_productiva'
            ) THEN
                RAISE EXCEPTION 'RF-37: gestiones_fases.id_ciclo_productiva no existe -- revisar supuestos de esta migración';
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'modulo9' AND table_name = 'ciclos_productivos_biologicos'
                  AND column_name = 'id_ciclos_productivo_biologico'
            ) THEN
                RAISE EXCEPTION 'RF-37: ciclos_productivos_biologicos.id_ciclos_productivo_biologico no existe';
            END IF;

            -- 1) Columna nueva (nullable por ahora, se cierra a NOT NULL al final)
            ALTER TABLE modulo2.gestiones_fases
                ADD COLUMN IF NOT EXISTS id_ciclos_productivo_biologico INT;

            -- 2) Backfill: misma lógica de conteo secuencial que ya asume el código
            -- (ver activo_biologico_repository.py::obtener_gestiones_fases).
            -- trg_fase_activo_estado_valido (BEFORE UPDATE, sin filtro de
            -- columna) rechaza CUALQUIER UPDATE sobre esta tabla si el activo
            -- está en BAJA -- confirmado en vivo: existen filas reales de
            -- activos en BAJA. Este backfill no cambia fecha_inicio/
            -- fecha_finalizacion/es_activa, solo agrega metadata histórica,
            -- así que se desactiva puntualmente ese trigger para el UPDATE y
            -- se reactiva de inmediato después.
            ALTER TABLE modulo2.gestiones_fases DISABLE TRIGGER trg_fase_activo_estado_valido;

            WITH posiciones AS (
                SELECT
                    gf.id_gestion_fases,
                    gf.id_ciclo_productiva,
                    ROW_NUMBER() OVER (
                        PARTITION BY gf.id_activo_biologico, gf.id_ciclo_productiva
                        ORDER BY gf.fecha_inicio, gf.id_gestion_fases
                    ) AS posicion
                FROM modulo2.gestiones_fases gf
                WHERE gf.id_ciclos_productivo_biologico IS NULL
            ),
            fases_ordenadas AS (
                SELECT
                    cpb.id_ciclo_productivo,
                    cpb.id_ciclos_productivo_biologico,
                    ROW_NUMBER() OVER (
                        PARTITION BY cpb.id_ciclo_productivo
                        ORDER BY cpb.id_ciclos_productivo_biologico ASC
                    ) AS posicion
                FROM modulo9.ciclos_productivos_biologicos cpb
            )
            UPDATE modulo2.gestiones_fases gf
            SET id_ciclos_productivo_biologico = fo.id_ciclos_productivo_biologico
            FROM posiciones p
            JOIN fases_ordenadas fo
              ON fo.id_ciclo_productivo = p.id_ciclo_productiva
             AND fo.posicion = p.posicion
            WHERE gf.id_gestion_fases = p.id_gestion_fases;

            ALTER TABLE modulo2.gestiones_fases ENABLE TRIGGER trg_fase_activo_estado_valido;

            -- 3) Verificar cobertura total antes de cerrar NOT NULL -- si alguna fila
            -- quedó sin backfillear (posición fuera de rango de fases del ciclo, dato
            -- inconsistente), la migración se detiene en vez de dejar NULLs silenciosos.
            SELECT COUNT(*) INTO v_sin_backfill
            FROM modulo2.gestiones_fases
            WHERE id_ciclos_productivo_biologico IS NULL;

            IF v_sin_backfill > 0 THEN
                RAISE EXCEPTION
                    'RF-37: % fila(s) de gestiones_fases no se pudieron backfillear -- '
                    'requiere revisión manual antes de continuar (posible posición fuera '
                    'de rango de fases del ciclo).', v_sin_backfill;
            END IF;

            ALTER TABLE modulo2.gestiones_fases
                ALTER COLUMN id_ciclos_productivo_biologico SET NOT NULL;

            ALTER TABLE modulo2.gestiones_fases
                ADD CONSTRAINT gestiones_fases_id_ciclos_productivo_biologico_fkey
                FOREIGN KEY (id_ciclos_productivo_biologico)
                REFERENCES modulo9.ciclos_productivos_biologicos(id_ciclos_productivo_biologico);

            COMMENT ON COLUMN modulo2.gestiones_fases.id_ciclos_productivo_biologico IS
                'Fase específica del ciclo (modulo9.ciclos_productivos_biologicos) que representa esta gestión. RF-37: necesaria para soportar transiciones no estándar (saltos/retrocesos) sin perder la posición real del activo en la secuencia.';
        END
        $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE modulo2.gestiones_fases
            DROP CONSTRAINT IF EXISTS gestiones_fases_id_ciclos_productivo_biologico_fkey;
        """
    )
    op.execute(
        """
        ALTER TABLE modulo2.gestiones_fases
            DROP COLUMN IF EXISTS id_ciclos_productivo_biologico;
        """
    )
