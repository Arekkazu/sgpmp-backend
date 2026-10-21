# | Fecha      | Nombre  | Que se hizo                                      |
# |------------|---------|--------------------------------------------------|
# | 2026-10-21 | Leandro | DEV-40 RF-53: persiste codigo y categoria en M09   |
"""DEV-40 RF-53: metadatos del catálogo dinámico de telemetría.

Revision ID: f40c53a37834
Revises: e5a3c9b17d42
Create Date: 2026-10-21

RF-53 define códigos y categorías, pero M09 solo persistía nombre/unidad/rango.
Dos columnas permiten retirar el mapa de Python sin inferir la categoría por
unidad o por ID. El nombre normalizado sigue siendo un alias dinámico del código.
La inicialización solo completa las columnas nuevas de las variables conocidas;
no cambia IDs, nombres, unidades, rangos, estado ni criticidad existentes.
No se crean variables ni se ejecuta esta migración desde la ingesta.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'f40c53a37834'
down_revision: Union[str, Sequence[str], None] = 'e5a3c9b17d42'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Fotografía de compatibilidad del RF-53. Solo se usa al migrar: los IDs,
# unidades y rangos siempre proceden de las filas reales de cada instalación.
_METADATOS_RF53 = (
    ('Temperatura Ambiental', 'TEMPERATURA_AMBIENTAL', 'AMBIENTAL'),
    ('Humedad Relativa', 'HUMEDAD_RELATIVA', 'AMBIENTAL'),
    ('Amoniaco (NH3)', 'NH3', 'AMBIENTAL'),
    ('Dióxido de Carbono (CO2)', 'CO2', 'AMBIENTAL'),
    ('Temperatura Corporal', 'TEMP_CORPORAL', 'ANIMAL'),
    ('Frecuencia Cardiaca', 'FRECUENCIA_CARDIACA', 'ANIMAL'),
    ('Frecuencia Respiratoria', 'FRECUENCIA_RESPIRATORIA', 'ANIMAL'),
    ('Actividad/Movimiento', 'ACTIVIDAD', 'ANIMAL'),
    ('pH del agua', 'PH_AGUA', 'HIDRICA'),
    ('Oxígeno disuelto', 'OXIGENO_DISUELTO', 'HIDRICA'),
    ('Conductividad eléctrica', 'TDS', 'HIDRICA'),
)


def upgrade() -> None:
    op.add_column('variables_ambientales', sa.Column('codigo_telemetria', sa.String(40)), schema='modulo9')
    op.add_column('variables_ambientales', sa.Column('categoria_variable', sa.String(20)), schema='modulo9')
    op.create_unique_constraint('uq_variable_ambiental_codigo_telemetria', 'variables_ambientales', ['codigo_telemetria'], schema='modulo9')
    op.create_check_constraint(
        'ck_variable_ambiental_codigo_telemetria', 'variables_ambientales',
        "codigo_telemetria IS NULL OR codigo_telemetria ~ '^[A-Z][A-Z0-9_]{1,39}$'", schema='modulo9',
    )
    op.create_check_constraint(
        'ck_variable_ambiental_categoria_variable', 'variables_ambientales',
        "categoria_variable IS NULL OR categoria_variable IN ('AMBIENTAL','ANIMAL','HIDRICA')", schema='modulo9',
    )
    for nombre, codigo, categoria in _METADATOS_RF53:
        op.execute(sa.text('''
            UPDATE modulo9.variables_ambientales
            SET codigo_telemetria = :codigo, categoria_variable = :categoria
            WHERE nombre = :nombre
        ''').bindparams(nombre=nombre, codigo=codigo, categoria=categoria))
    op.execute("COMMENT ON COLUMN modulo9.variables_ambientales.codigo_telemetria IS 'RF-53: identificador público de variable; el nombre normalizado también se reconoce. Gestionado por el sistema.'")
    op.execute("COMMENT ON COLUMN modulo9.variables_ambientales.categoria_variable IS 'RF-53: categoría persistida AMBIENTAL/ANIMAL/HIDRICA. NULL indica catálogo sin configurar para ingesta escalar.'")


def downgrade() -> None:
    op.drop_constraint('ck_variable_ambiental_categoria_variable', 'variables_ambientales', schema='modulo9', type_='check')
    op.drop_constraint('ck_variable_ambiental_codigo_telemetria', 'variables_ambientales', schema='modulo9', type_='check')
    op.drop_constraint('uq_variable_ambiental_codigo_telemetria', 'variables_ambientales', schema='modulo9', type_='unique')
    op.drop_column('variables_ambientales', 'categoria_variable', schema='modulo9')
    op.drop_column('variables_ambientales', 'codigo_telemetria', schema='modulo9')
