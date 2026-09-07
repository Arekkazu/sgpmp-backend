"""RF-33: CHECK soporte_documental obligatorio si costo_adquisicion no es nulo

Revision ID: 2898e45d9813
Revises: 3d0b4cbfb11c
Create Date: 2026-09-06 10:05:00.000000

Issue #28 — el RF-33 exige que todo activo con costo de adquisición registrado
tenga también su soporte documental, pero esa regla solo se validaba en
`registrar_activo_dto.py` (Pydantic), nunca a nivel de base de datos.
Confirmado con datos reales de dev: el activo `BOV-003` tiene
`origen_financiero='compra'`, `costo_adquisicion=8000000.0000` y
`soporte_documental=NULL` — viola la regla que esta migración agrega.

Por esa fila (y cualquier otra que pueda existir sin haberse verificado en
vivo, dado que el servidor MCP de Postgres no estaba disponible al momento de
escribir esta migración), el CHECK **no puede** crearse validado de una vez:
Postgres escanearía la tabla completa al aplicar la migración y fallaría en la
primera fila inconsistente. Se usa el patrón estándar de Postgres para este
caso — `NOT VALID`:

- Se aplica de inmediato a todo INSERT/UPDATE nuevo (no es una promesa a
  futuro, es efectivo ya para escritura).
- No escanea ni valida las filas ya existentes en la tabla — la migración no
  falla aunque haya datos inconsistentes como BOV-003.
- Deja el constraint marcado como "no validado" (`convalidated = false` en
  `pg_constraint`) hasta que el equipo limpie los datos existentes (backfill
  de `soporte_documental` o anulación de `costo_adquisicion` en las filas que
  correspondan) y corra `VALIDATE CONSTRAINT` en una migración posterior —
  operación que sí escanea la tabla pero solo toma `SHARE UPDATE EXCLUSIVE`
  (no bloquea lecturas/escrituras concurrentes), a diferencia de crear el
  CHECK ya validado desde cero.

Pendiente de seguimiento: limpiar BOV-003 (y cualquier otra fila que la
consulta de abajo identifique) y aplicar la migración de `VALIDATE CONSTRAINT`.

    SELECT id_activo_biologico, identificador, origen_financiero,
           costo_adquisicion, soporte_documental
    FROM modulo2.activos_biologicos
    WHERE costo_adquisicion IS NOT NULL AND soporte_documental IS NULL;
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '2898e45d9813'
down_revision: Union[str, Sequence[str], None] = '3d0b4cbfb11c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CONSTRAINT = 'ck_activo_biologico_soporte_documental_requerido'


def upgrade() -> None:
    op.execute(f"""
        ALTER TABLE modulo2.activos_biologicos
        ADD CONSTRAINT {_CONSTRAINT}
        CHECK (costo_adquisicion IS NULL OR soporte_documental IS NOT NULL)
        NOT VALID;
    """)


def downgrade() -> None:
    op.execute(f"""
        ALTER TABLE modulo2.activos_biologicos
        DROP CONSTRAINT IF EXISTS {_CONSTRAINT};
    """)
