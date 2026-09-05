"""rf09 columna token_usado y tabla de intentos anonimos por ip

Revision ID: b7d2a4f8e1c6
Revises: f19e0ca62445
Create Date: 2026-09-05 00:00:00.000000

NOTA: encadena sobre f19e0ca62445 (head real de dev al momento de crear esta
migracion), NO sobre a1c3f6e0b2d4 (migracion de la PR #123, rama distinta).
Ambas ramas se crearon en paralelo desde el mismo head y son independientes
entre si (tablas distintas, sin relacion). Si las dos se mergean a dev, va a
quedar mas de un head y hay que resolverlo con `alembic merge heads` en ese
momento — no antes, mientras siguen siendo PRs separadas sin mergear.

INC-M01-15-054 (#100) y INC-M01-17-058 (#102) — POST /contrasena/restablecer.

- #100: reutilizar un token de recuperacion ya consumido con exito debe
  responder 409 (Conflict), no 401 — hoy no hay forma de distinguirlo de un
  token que nunca existio porque el hash se borra al usarlo. Se agrega
  `es_token_usado` a `cuentas_usuarios`: el hash se conserva al consumir el
  token (antes se ponia NULL) y esta columna marca que ya fue gastado.

- #102: enviar tokens invalidos de forma repetida a este endpoint no tiene
  ningun limite de intentos, a diferencia de cambiar_contrasena (bloqueo tras
  5 fallos). No existe una `cuenta` a la cual atarle el contador porque el
  token no coincide con ninguna, asi que el bloqueo se hace por IP. No puede
  reusarse `modulo1.eventos` para esto: `id_usuario` es NOT NULL con FK a
  usuarios, y aqui no hay ningun usuario identificado. Se agrega la tabla
  `intentos_anonimos_ip`, de solo insercion, para este y futuros casos de
  rate limiting sin actor identificado (ver tambien #86).

Nomenclatura (docs/Nomenclatura.xlsx): PK `id_<tabla_singular>`, booleano con
prefijo `es_`/`tiene_`, fecha con descriptor (`fecha_<algo>`, nunca `fecha` a
secas), indice regular con prefijo `idx_`.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b7d2a4f8e1c6'
down_revision: Union[str, Sequence[str], None] = 'f19e0ca62445'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "cuentas_usuarios",
        sa.Column(
            "es_token_usado",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment=(
                'Marca si token_activacion_actual (de RECUPERACION) ya fue consumido '
                'en un restablecimiento exitoso. Se mantiene el hash al usarlo (no se '
                'limpia) para poder distinguir "token ya utilizado" (409) de "token '
                'nunca existio" (401) en un reintento.'
            ),
        ),
        schema="modulo1",
    )

    op.create_table(
        "intentos_anonimos_ip",
        sa.Column("id_intento_anonimo_ip", sa.Integer, primary_key=True),
        sa.Column("tipo", sa.String(40), nullable=False),
        sa.Column("ip", sa.String(45), nullable=False),
        sa.Column("fecha_intento", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema="modulo1",
    )
    op.create_index(
        "idx_intentos_anonimos_ip_tipo_ip_fecha",
        "intentos_anonimos_ip",
        ["tipo", "ip", "fecha_intento"],
        schema="modulo1",
    )


def downgrade() -> None:
    op.drop_index("idx_intentos_anonimos_ip_tipo_ip_fecha", table_name="intentos_anonimos_ip", schema="modulo1")
    op.drop_table("intentos_anonimos_ip", schema="modulo1")
    op.drop_column("cuentas_usuarios", "es_token_usado", schema="modulo1")
