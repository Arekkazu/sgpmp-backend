"""RF-10: cola asíncrona para exportaciones grandes de auditoría.

Revision ID: f1c62d8b04a7
Revises: d9a47c30e5b1
Create Date: 2026-08-31 11:20:00.000000

La exportación síncrona (``GET /auditoria/exportar``) resuelve el caso normal,
pero mantiene la petición abierta mientras arma el archivo. Por encima del umbral
configurable eso deja de ser razonable, así que el trabajo se encola y el cliente
consulta el estado hasta poder descargar.

Son tres tablas y no cuatro como en ``modulo5``: allí existe además una tabla de
fallos por intento para alimentar un panel de administración que auditoría no
tiene. El contador de intentos y el último error viven en la propia cola.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'f1c62d8b04a7'
down_revision: Union[str, Sequence[str], None] = 'd9a47c30e5b1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'cola_exportaciones_auditoria',
        sa.Column('id_cola', sa.Integer(), primary_key=True, autoincrement=True),
        # Los filtros de la exportación, tal como llegaron al endpoint.
        sa.Column('parametros', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            'estado',
            sa.String(20),
            nullable=False,
            server_default=sa.text("'PENDIENTE'::character varying"),
        ),
        sa.Column('id_usuario_solicitante', sa.Integer(), nullable=False),
        sa.Column('intentos', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column(
            'fecha_solicitud',
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text('now()'),
        ),
        sa.Column('fecha_procesado', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ['id_usuario_solicitante'],
            ['modulo1.usuarios.id_usuario'],
            name='cola_exportaciones_auditoria_id_usuario_solicitante_fkey',
        ),
        sa.CheckConstraint(
            "estado IN ('PENDIENTE', 'EN_PROCESO', 'COMPLETADO', 'FALLIDO')",
            name='cola_exportaciones_auditoria_estado_check',
        ),
        schema='modulo1',
    )
    # El poller busca siempre por estado ordenando por antigüedad.
    op.create_index(
        'idx_cola_export_auditoria_estado',
        'cola_exportaciones_auditoria',
        ['estado', 'fecha_solicitud'],
        schema='modulo1',
    )

    op.create_table(
        'ejecuciones_exportaciones_auditoria',
        sa.Column('id_ejecucion', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('id_cola', sa.Integer(), nullable=False, unique=True),
        # El CSV ya generado, listo para descargar.
        sa.Column('contenido_csv', sa.Text(), nullable=False),
        sa.Column('nombre_archivo', sa.String(120), nullable=False),
        sa.Column('total_exportado', sa.Integer(), nullable=False),
        sa.Column('total_disponible', sa.Integer(), nullable=False),
        sa.Column(
            'creado_en',
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text('now()'),
        ),
        sa.ForeignKeyConstraint(
            ['id_cola'],
            ['modulo1.cola_exportaciones_auditoria.id_cola'],
            name='ejecuciones_exportaciones_auditoria_id_cola_fkey',
            ondelete='CASCADE',
        ),
        schema='modulo1',
    )

    op.create_table(
        'configuracion_batch_exportacion_auditoria',
        sa.Column('id_configuracion', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('num_workers_max', sa.Integer(), nullable=False, server_default=sa.text('2')),
        sa.Column('max_reintentos', sa.Integer(), nullable=False, server_default=sa.text('3')),
        # Por encima de esto la exportación síncrona responde 422 y redirige aquí.
        sa.Column(
            'umbral_exportacion_async',
            sa.Integer(),
            nullable=False,
            server_default=sa.text('10000'),
        ),
        sa.Column(
            'limite_concurrencia',
            sa.Integer(),
            nullable=False,
            server_default=sa.text('3'),
        ),
        sa.Column(
            'intervalo_poll_segundos',
            sa.Integer(),
            nullable=False,
            server_default=sa.text('15'),
        ),
        sa.Column('es_activo', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column(
            'actualizado_en',
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text('now()'),
        ),
        schema='modulo1',
    )
    # Fila única con los valores por defecto: sin ella el poller no arranca.
    op.execute(
        """
        INSERT INTO modulo1.configuracion_batch_exportacion_auditoria DEFAULT VALUES
        """
    )


def downgrade() -> None:
    op.drop_table('configuracion_batch_exportacion_auditoria', schema='modulo1')
    op.drop_table('ejecuciones_exportaciones_auditoria', schema='modulo1')
    op.drop_index(
        'idx_cola_export_auditoria_estado',
        table_name='cola_exportaciones_auditoria',
        schema='modulo1',
    )
    op.drop_table('cola_exportaciones_auditoria', schema='modulo1')
