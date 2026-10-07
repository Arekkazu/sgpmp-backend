"""inc_m09_253 especies del contexto RF-25 por finca, no globales

Revision ID: 5764b9af852e
Revises: 0618e6f7b308
Create Date: 2026-10-07 02:00:00.000000

#253 (QA M09, TC-DIS-69). ``vw_rf25_contexto_usuario.especies_en_finca`` salía
de un LATERAL sin correlación con la finca: agregaba toda especie activa con
umbrales activos en cualquier finca. Una finca sin especies ni áreas recibía las
12 especies del sistema (igual que un usuario sin finca), ``finca_sin_catalogo``
nunca era verdadero y el contexto respondía 200 en vez del 204 del flujo
alterno "Finca sin especies productivas configuradas".

RF-25 habla de "las especies productivas configuradas en la finca". Se toman de
las áreas activas de la finca y de los activos biológicos vivos en ellas.
Verificado en solo lectura contra sgpmp_dev: las fincas 1-3 conservan sus
especies, la 4 (áreas sin especie) sigue en 200 y las 9-18 (sin áreas ni
especies) pasan a 204; los usuarios sin finca ya no reciben especies.

Mismas columnas y mismo JOIN de acceso que 1b9536d4411c, para poder usar
CREATE OR REPLACE VIEW sin perder los GRANT de la vista.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '5764b9af852e'
down_revision: Union[str, Sequence[str], None] = '0618e6f7b308'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_VISTA_CONTEXTO = """
CREATE OR REPLACE VIEW modulo9.vw_rf25_contexto_usuario AS
 SELECT u.id_usuario,
    concat_ws(' '::text, u.nombre, u.apellidos) AS nombre_completo,
    r.id_rol,
    r.nombre_rol,
    f.id_finca,
    f.nombre AS finca_activa,
    (f.ubicacion ->> 'departamento'::text) AS departamento,
    f.es_activo AS finca_activa_estado,
    especies.especies_configuradas AS especies_en_finca
   FROM modulo1.usuarios u
     JOIN modulo1.roles r ON r.id_rol = u.id_rol
     LEFT JOIN (modulo9.usuarios_fincas uf
         JOIN modulo9.fincas f ON f.id_finca = uf.id_finca AND f.es_activo IS TRUE)
       ON uf.id_usuario = u.id_usuario AND uf.es_activo IS TRUE
     LEFT JOIN LATERAL ( SELECT COALESCE(array_agg(DISTINCT (e.nombre)::text ORDER BY (e.nombre)::text), ARRAY[]::text[]) AS especies_configuradas
{especies}) especies ON (true)
"""

# Dos fuentes, ambas de la finca: la especie de cada área activa (RF-20 v1.1) y
# la de los activos biológicos vivos en esas áreas. La segunda cubre las áreas
# anteriores a RF-20 v1.1, que tienen ``id_especie`` NULL. Los estados se
# filtran por nombre, no por id, porque los ids son datos.
_ESPECIES_DE_LA_FINCA = """           FROM (( SELECT i.id_especie
                   FROM modulo9.infraestructuras i
                  WHERE ((i.id_finca = f.id_finca) AND (i.es_activo IS TRUE))
                UNION
                 SELECT a.id_especie
                   FROM ((modulo2.activos_biologicos a
                     JOIN modulo9.infraestructuras i ON ((i.id_infraestructura = a.id_infraestructura)))
                     JOIN modulo2.estados_activos_biologicos ea ON ((ea.id_estado_activo_biologico = a.id_estado)))
                  WHERE ((i.id_finca = f.id_finca) AND (i.es_activo IS TRUE) AND ((ea.nombre)::text <> ALL (ARRAY['INACTIVO'::text, 'CERRADO'::text, 'BAJA'::text])))) en_finca
             JOIN modulo9.especies e ON (((e.id_especie = en_finca.id_especie) AND (e.es_activo IS TRUE))))"""

# Definición anterior (1b9536d4411c), para el downgrade.
_ESPECIES_GLOBALES = """           FROM (modulo9.umbrales_ambientales ua
             JOIN modulo9.especies e ON ((e.id_especie = ua.id_especie)))
          WHERE ((ua.es_activo IS TRUE) AND (e.es_activo IS TRUE))"""


def upgrade() -> None:
    op.execute(_VISTA_CONTEXTO.format(especies=_ESPECIES_DE_LA_FINCA))


def downgrade() -> None:
    op.execute(_VISTA_CONTEXTO.format(especies=_ESPECIES_GLOBALES))
