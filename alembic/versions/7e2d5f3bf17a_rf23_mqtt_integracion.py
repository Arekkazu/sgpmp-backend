"""rf23 mqtt integracion

Revision ID: 7e2d5f3bf17a
Revises: f7fe43537842
Create Date: 2026-08-20 08:50:11.659675

RF-23 — integración MQTT real para configuración remota de dispositivos IoT.

1. Nuevo estado terminal NO_CONF en modulo9.configuraciones_remotas (timeout
   de ACK del dispositivo). "NO_CONF" y no "NO_CONFIRMADA": el frontend ya
   tiene el badge de ConfiguracionRemotaSection.tsx codificado con esa clave
   exacta.
2. Índice único parcial que impide dos configuraciones PENDIENTE simultáneas
   para el mismo dispositivo (antes era solo un chequeo de aplicación sin
   respaldo en BD -- TOCTOU real bajo requests concurrentes).
3. Tabla modulo1.credenciales_servicio para autenticar al backend contra
   BROKER-MQTT-SGPMP (hash sha256 sin sal, mismo formato que
   modulo1.tokens.hash_valor, pero sin su semántica de un solo uso atado a
   sesión -- por eso tabla nueva y no reutilizar modulo1.tokens).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7e2d5f3bf17a'
down_revision: Union[str, Sequence[str], None] = 'f7fe43537842'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ESTADOS_ANTERIORES = "estado IN ('PENDIENTE','APLICADA','CANCELADA')"
_ESTADOS_NUEVOS = "estado IN ('PENDIENTE','APLICADA','CANCELADA','NO_CONF')"


def upgrade() -> None:
    op.drop_constraint(
        "configuraciones_remotas_estado_check",
        "configuraciones_remotas",
        schema="modulo9",
        type_="check",
    )
    op.create_check_constraint(
        "configuraciones_remotas_estado_check",
        "configuraciones_remotas",
        _ESTADOS_NUEVOS,
        schema="modulo9",
    )

    op.create_index(
        "uq_config_remota_pendiente_por_dispositivo",
        "configuraciones_remotas",
        ["id_dispositivo_iot"],
        unique=True,
        schema="modulo9",
        postgresql_where=sa.text("estado = 'PENDIENTE'"),
    )

    op.create_table(
        "credenciales_servicio",
        sa.Column("id_credencial_servicio", sa.Integer, primary_key=True),
        sa.Column("nombre_servicio", sa.String(50), nullable=False, unique=True),
        sa.Column("hash_valor", sa.String(64), nullable=False),
        sa.Column("es_activo", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column(
            "fecha_creacion",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("fecha_revocacion", sa.TIMESTAMP(timezone=True), nullable=True),
        schema="modulo1",
    )


def downgrade() -> None:
    op.drop_table("credenciales_servicio", schema="modulo1")
    op.drop_index(
        "uq_config_remota_pendiente_por_dispositivo",
        table_name="configuraciones_remotas",
        schema="modulo9",
    )
    op.drop_constraint(
        "configuraciones_remotas_estado_check",
        "configuraciones_remotas",
        schema="modulo9",
        type_="check",
    )
    op.create_check_constraint(
        "configuraciones_remotas_estado_check",
        "configuraciones_remotas",
        _ESTADOS_ANTERIORES,
        schema="modulo9",
    )
