"""v5.4.0_inc_m09_103_g28_precision_niveles_alerta_ambiental

Revision ID: b9edb971f005
Revises: 1147428cd8fb
Create Date: 2026-09-18 15:08:56.470257

INC-M09-103-G28 (RF-17, TC-M09-G28, #294): QA reevaluó TC-M09-60/61 como
APROBADOS pero encontró que `umbrales_ambientales.valor_min`/`valor_max`
estaban en NUMERIC(8,2) mientras RF-17 especifica NUMERIC(5,2) -- ya
corregido por la migración 1147428cd8fb (otro desarrollador, mergeada a dev
el mismo día). Esta migración cierra el hallazgo adicional: los niveles de
alerta (`niveles_alerta_ambientales.limite_inferior`/`limite_superior`)
seguían en NUMERIC(8,2) aunque, por regla de negocio (`_validar_rangos` en
`registrar_umbral_use_case.py`), un nivel siempre cae dentro de
[valor_min, valor_max] del umbral padre -- misma capacidad numérica
esperada. QA no probó específicamente esta tabla, así que no era un defecto
confirmado, pero es la misma inconsistencia esquema/RF-17 en la tabla hija.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b9edb971f005'
down_revision: Union[str, Sequence[str], None] = '1147428cd8fb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# `vw_rf17_umbrales_detalle_niveles` depende de limite_inferior/limite_superior (las agrega en
# un json_build_object dentro de un json_agg) -- Postgres no permite ALTER COLUMN TYPE mientras
# exista esa dependencia, así que hay que dropearla y recrearla idéntica alrededor del ALTER.
_VISTA = """
CREATE VIEW modulo9.vw_rf17_umbrales_detalle_niveles AS
 SELECT ua.id_umbral_ambiental,
    ua.id_especie,
    e.nombre AS especie,
    ua.nombre,
    ua.unidad_medida,
    ua.descripcion,
    ua.es_activo,
    va.id_variable_ambiental,
    va.nombre AS variable,
    va.unidad,
    va.valor_fisico_min,
    va.valor_fisico_max,
    COALESCE(json_agg(json_build_object('id', na.id_nivel_alerta_ambiental, 'nivel', na.nivel, 'limite_inferior', na.limite_inferior, 'limite_superior', na.limite_superior) ORDER BY na.limite_inferior) FILTER (WHERE na.id_nivel_alerta_ambiental IS NOT NULL), '[]'::json) AS niveles_alerta
   FROM modulo9.umbrales_ambientales ua
     JOIN modulo9.especies e ON e.id_especie = ua.id_especie
     JOIN modulo9.variables_ambientales va ON va.id_variable_ambiental = ua.id_variable_ambiental
     LEFT JOIN modulo9.niveles_alerta_ambientales na ON na.id_umbral_ambiental = ua.id_umbral_ambiental
  GROUP BY ua.id_umbral_ambiental, ua.id_especie, e.nombre, ua.nombre, ua.unidad_medida, ua.descripcion, ua.es_activo, va.id_variable_ambiental, va.nombre, va.unidad, va.valor_fisico_min, va.valor_fisico_max;
"""

# DROP VIEW no conserva los GRANT del objeto original -- se re-otorgan los mismos permisos que
# ya tienen las vistas hermanas del módulo (vw_rf17_umbral_activo_por_especie_variable,
# vw_rf17_variables_configuracion_especie), verificados en sgpmp_dev antes de esta migración.
_GRANTS = """
GRANT INSERT, SELECT, UPDATE, DELETE ON modulo9.vw_rf17_umbrales_detalle_niveles TO rol_dev, rol_impl, rol_migracion;
GRANT INSERT, SELECT ON modulo9.vw_rf17_umbrales_detalle_niveles TO rol_aiot;
"""


def upgrade() -> None:
    op.execute("DROP VIEW modulo9.vw_rf17_umbrales_detalle_niveles;")
    op.execute("ALTER TABLE modulo9.niveles_alerta_ambientales ALTER COLUMN limite_inferior TYPE NUMERIC(5,2);")
    op.execute("ALTER TABLE modulo9.niveles_alerta_ambientales ALTER COLUMN limite_superior TYPE NUMERIC(5,2);")
    op.execute(_VISTA)
    op.execute(_GRANTS)


def downgrade() -> None:
    op.execute("DROP VIEW modulo9.vw_rf17_umbrales_detalle_niveles;")
    op.execute("ALTER TABLE modulo9.niveles_alerta_ambientales ALTER COLUMN limite_inferior TYPE NUMERIC(8,2);")
    op.execute("ALTER TABLE modulo9.niveles_alerta_ambientales ALTER COLUMN limite_superior TYPE NUMERIC(8,2);")
    op.execute(_VISTA)
    op.execute(_GRANTS)
