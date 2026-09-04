"""baseline: esquema existente antes de Alembic

Revision ID: f7fe43537842
Revises:
Create Date: 2026-08-20 08:49:27.316240

Esta revisión era un ``pass``. La idea original era razonable: el esquema hasta
este punto se había construido a mano (Paso 0 de cada módulo, aplicado directo
vía SQL), así que la revisión solo marcaba el punto de partida sin intentar
recrear lo que ya existía en dev.

La consecuencia no lo era. Con el baseline vacío, **``alembic upgrade head`` no
podía levantar una base desde cero**: solo aplicaba los deltas posteriores y
fallaba en cuanto intentaba ``ALTER`` sobre una tabla que no existía. La primera
migración posterior al baseline ya toca ``modulo9`` y revienta ahí. Por eso la
base de pruebas vivió con solo ``modulo1``, la integración de módulo 9 nunca
corrió, y ningún entorno se ha construido jamás solo con migraciones — lo que
significa que las pruebas no verificaban que las migraciones produjeran el
esquema correcto.

Ahora la revisión ejecuta ``alembic/baseline/esquema_baseline.sql``: el esquema
completo (``auditoria`` y ``modulo1``…``modulo9``) más los catálogos de
referencia, tal como estaban justo antes de que Alembic entrara en juego.

Ese archivo no se escribió a mano. Se derivó ejecutando los diecisiete
``downgrade()`` de la cadena sobre una copia del esquema de dev, hasta llegar a
esta revisión, y volcando el resultado. Se verificó al revés: base vacía →
``alembic upgrade head`` → el esquema resultante coincide con el de dev. La
única diferencia del volcado comparado es cosmética (PostgreSQL re-renderiza los
``CHECK`` al recrearlos, y coloca una restricción en un ``ALTER`` aparte).

Es idempotente. Un entorno construido a mano antes de Alembic ya tiene el
esquema, así que la revisión no hace nada y solo queda sellada — el
comportamiento que tenía hasta ahora.
"""
from pathlib import Path
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f7fe43537842'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ESQUEMA_BASELINE = (
    Path(__file__).resolve().parents[1] / "baseline" / "esquema_baseline.sql"
)


def upgrade() -> None:
    bind = op.get_bind()
    ya_construido = bind.execute(
        sa.text("SELECT 1 FROM pg_namespace WHERE nspname = 'modulo1'")
    ).scalar()
    if ya_construido:
        # Entorno anterior a Alembic: el esquema ya está, solo hay que sellarlo.
        return

    # pgcrypto vive en public y alguna función de módulo la usa vía
    # public.digest. El volcado no la trae porque public queda fuera: ahí viven
    # tablas de otra aplicación que no tienen por qué acabar en una base nueva.
    # Cursor crudo a propósito: el volcado trae `%` (patrones LIKE dentro de
    # funciones PL/pgSQL, entre otros) y cualquier ejecución con parámetros hace
    # que psycopg2 los tome como marcadores de interpolación y falle.
    cursor = bind.connection.cursor()
    try:
        cursor.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
        cursor.execute(_ESQUEMA_BASELINE.read_text(encoding="utf-8"))
        # El volcado deja `search_path` vacío (pg_dump lo hace para forzar
        # nombres calificados). Sin restaurarlo, Alembic no encuentra su propia
        # tabla `alembic_version` al sellar esta revisión.
        cursor.execute("SET search_path TO public")
    finally:
        cursor.close()


def downgrade() -> None:
    # Bajar de esta revisión significa borrar los nueve schemas del sistema. No
    # se automatiza: en los entornos donde el esquema es anterior a Alembic,
    # `upgrade()` no lo creó y no le corresponde destruirlo.
    raise NotImplementedError(
        "El baseline no se revierte automáticamente: hacerlo borraría los "
        "schemas auditoria y modulo1..modulo9 completos, que en los entornos "
        "existentes son anteriores a Alembic. Si de verdad quieres partir de "
        "cero, borra y recrea la base."
    )
