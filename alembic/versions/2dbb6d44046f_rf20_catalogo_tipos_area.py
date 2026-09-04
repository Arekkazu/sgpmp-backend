"""rf20 catalogo administrable de tipos de area

Revision ID: 2dbb6d44046f
Revises: b5d1e0c93a77
Create Date: 2026-09-04 08:00:00.000000

RF-20 / #1668 — Catálogo tipo_area extensible, no hardcodeado.

`modulo9.infraestructuras.tipo` estaba restringida al enum fijo de Postgres
`enum_tipo_infraestructura` (5 valores en minúscula y sin tilde: `galpon`,
`corral`, `potrero`, `estanque`, `invernadero`). El RF exige que el
Administrador pueda ampliar ese catálogo desde Configuración (M09), lo cual es
imposible contra un tipo ENUM sin una migración por cada valor nuevo.

Se crea `modulo9.tipos_area` (id, nombre, es_activo, fecha_creacion,
fecha_actualizacion — mismo shape que `especies`/`variables_ambientales`),
sembrada con los 5 valores por defecto en su forma canónica capitalizada y
con tilde (`Galpón`, no `galpon`): es la misma forma que el frontend ya
mostraba y enviaba, así que de paso corrige un 422 latente — el DTO nunca
coincidía con el enum en minúsculas sin acentos.

Tres vistas dependen del tipo de la columna: `vw_rf20_areas_finca_resumen`,
`vw_rf20_areas_productivas_dispositivos` y `vw_rf22_areas_destino_disponibles`.
Sus cuerpos se copian **verbatim** de `alembic/baseline/esquema_baseline.sql`
(líneas 36516-36538, 36547-36569 y 36732-36740 respectivamente) — son
anteriores a Alembic y ninguna hace cast contra el enum, así que se recrean
sin cambios tras el `ALTER COLUMN`.

El recurso RBAC `tipos_area` (id 58, el siguiente libre en `modulo1.recursos`
al momento de escribir esta revisión — ver `alembic/baseline/esquema_baseline.sql`
línea ~47592) y sus permisos NO se crean aquí: la RBAC de este proyecto se
aplica siempre directo contra la base de datos, igual que el resto de recursos
de M09 (confirmado contra `anotaciones/modulo_9/rf15-19-20-rbac-mod9/resumen_rbac_1634.md`).
Aplicar antes de desplegar este backend:

    INSERT INTO modulo1.recursos (id_recurso, nombre_recurso, descripcion, es_proceso_especial)
    VALUES (58, 'tipos_area', 'Catálogo de tipos de área productiva (RF-20)', false);

    -- Confirmar id_rol de Administrador/Productor contra modulo1.roles antes de correr esto.
    INSERT INTO modulo1.permisos (nombre, id_recurso, id_accion, id_rol, es_activo) VALUES
      ('tipos_area.crear',      58, 1, <id_rol_admin>, true),
      ('tipos_area.leer_admin', 58, 2, <id_rol_admin>, true),
      ('tipos_area.desactivar', 58, 4, <id_rol_admin>, true),
      ('tipos_area.leer_prod',  58, 2, <id_rol_productor>, true);
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "2dbb6d44046f"
down_revision: Union[str, Sequence[str], None] = "b5d1e0c93a77"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TIPOS_DEFAULT = ["Galpón", "Corral", "Potrero", "Estanque", "Invernadero"]
_TIPOS_ENUM = ["galpon", "corral", "potrero", "estanque", "invernadero"]

# Copiados verbatim de alembic/baseline/esquema_baseline.sql — ninguno hace
# cast contra el tipo enum de la columna, por eso se recrean sin cambios.
_VISTA_AREAS_FINCA_RESUMEN = """
SELECT i.id_finca,
    i.id_infraestructura,
    i.nombre,
    i.descripcion,
    i.tipo,
    i.superficie,
    i.es_activo,
    count(d.id_dispositivo_iot) FILTER (WHERE (d.es_activo IS TRUE)) AS dispositivos_activos,
    count(d.id_dispositivo_iot) AS total_dispositivos
   FROM (modulo9.infraestructuras i
     LEFT JOIN ( SELECT DISTINCT ON (d0.id_dispositivo_iot) d0.id_dispositivo_iot,
            d0.serial,
            d0.descripcion,
            d0.es_activo,
            d0.fecha_creacion,
            COALESCE(saa.id_infraestructura, ab.id_infraestructura) AS id_infraestructura
           FROM (((modulo9.dispositivos_iot d0
             LEFT JOIN modulo9.sensores s ON ((s.id_dispositivo_iot = d0.id_dispositivo_iot)))
             LEFT JOIN modulo9.sensores_areas_asociadas saa ON (((saa.id_sensor = s.id_sensores) AND ((saa.fecha_finalizacion IS NULL) OR (saa.fecha_finalizacion > now())))))
             LEFT JOIN modulo2.activos_biologicos ab ON ((ab.id_dispositivo_iot = d0.id_dispositivo_iot)))
          ORDER BY d0.id_dispositivo_iot, saa.fecha_asociacion DESC NULLS LAST, saa.id_sensores_area_asociada DESC NULLS LAST) d ON ((d.id_infraestructura = i.id_infraestructura)))
  GROUP BY i.id_finca, i.id_infraestructura, i.nombre, i.descripcion, i.tipo, i.superficie, i.es_activo
"""

_VISTA_AREAS_DISPOSITIVOS = """
SELECT i.id_infraestructura,
    i.id_finca,
    i.nombre AS area,
    i.tipo,
    i.es_activo,
    f.nombre AS finca,
    (f.ubicacion ->> 'municipio'::text) AS municipio,
    count(d.id_dispositivo_iot) AS total_dispositivos
   FROM ((modulo9.infraestructuras i
     JOIN modulo9.fincas f ON ((f.id_finca = i.id_finca)))
     LEFT JOIN ( SELECT DISTINCT ON (d0.id_dispositivo_iot) d0.id_dispositivo_iot,
            d0.serial,
            d0.descripcion,
            d0.es_activo,
            d0.fecha_creacion,
            COALESCE(saa.id_infraestructura, ab.id_infraestructura) AS id_infraestructura
           FROM (((modulo9.dispositivos_iot d0
             LEFT JOIN modulo9.sensores s ON ((s.id_dispositivo_iot = d0.id_dispositivo_iot)))
             LEFT JOIN modulo9.sensores_areas_asociadas saa ON (((saa.id_sensor = s.id_sensores) AND ((saa.fecha_finalizacion IS NULL) OR (saa.fecha_finalizacion > now())))))
             LEFT JOIN modulo2.activos_biologicos ab ON ((ab.id_dispositivo_iot = d0.id_dispositivo_iot)))
          ORDER BY d0.id_dispositivo_iot, saa.fecha_asociacion DESC NULLS LAST, saa.id_sensores_area_asociada DESC NULLS LAST) d ON ((d.id_infraestructura = i.id_infraestructura)))
  GROUP BY i.id_infraestructura, i.id_finca, i.nombre, i.tipo, i.es_activo, f.nombre, f.ubicacion
"""

_VISTA_AREAS_DESTINO_DISPONIBLES = """
SELECT i.id_infraestructura,
    i.nombre,
    i.tipo,
    f.id_finca,
    f.nombre AS finca
   FROM (modulo9.infraestructuras i
     JOIN modulo9.fincas f ON ((f.id_finca = i.id_finca)))
  WHERE ((i.es_activo IS TRUE) AND (f.es_activo IS TRUE))
"""


def _crear_vistas() -> None:
    op.execute(f"CREATE VIEW modulo9.vw_rf20_areas_finca_resumen AS {_VISTA_AREAS_FINCA_RESUMEN}")
    op.execute(f"CREATE VIEW modulo9.vw_rf20_areas_productivas_dispositivos AS {_VISTA_AREAS_DISPOSITIVOS}")
    op.execute(f"CREATE VIEW modulo9.vw_rf22_areas_destino_disponibles AS {_VISTA_AREAS_DESTINO_DISPONIBLES}")


def _borrar_vistas() -> None:
    op.execute("DROP VIEW IF EXISTS modulo9.vw_rf20_areas_finca_resumen")
    op.execute("DROP VIEW IF EXISTS modulo9.vw_rf20_areas_productivas_dispositivos")
    op.execute("DROP VIEW IF EXISTS modulo9.vw_rf22_areas_destino_disponibles")


def upgrade() -> None:
    op.create_table(
        "tipos_area",
        sa.Column("id_tipo_area", sa.Integer, sa.Identity(start=1, increment=1), primary_key=True),
        sa.Column("nombre", sa.String(30), nullable=False),
        sa.Column("es_activo", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("fecha_creacion", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("fecha_actualizacion", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("nombre", name="uq_tipo_area_nombre"),
        schema="modulo9",
    )

    op.bulk_insert(
        sa.table("tipos_area", sa.column("nombre", sa.String), schema="modulo9"),
        [{"nombre": nombre} for nombre in _TIPOS_DEFAULT],
    )

    _borrar_vistas()

    op.alter_column(
        "infraestructuras",
        "tipo",
        type_=sa.String(30),
        schema="modulo9",
        postgresql_using="tipo::text",
    )

    for viejo, nuevo in zip(_TIPOS_ENUM, _TIPOS_DEFAULT):
        op.execute(
            sa.text("UPDATE modulo9.infraestructuras SET tipo = :nuevo WHERE tipo = :viejo").bindparams(
                nuevo=nuevo, viejo=viejo
            )
        )

    _crear_vistas()

    # El tipo enum queda sin uso; se deja en el esquema (limpieza opcional, no bloqueante).


def downgrade() -> None:
    _borrar_vistas()

    for viejo, nuevo in zip(_TIPOS_ENUM, _TIPOS_DEFAULT):
        op.execute(
            sa.text("UPDATE modulo9.infraestructuras SET tipo = :viejo WHERE tipo = :nuevo").bindparams(
                nuevo=nuevo, viejo=viejo
            )
        )

    op.execute(
        "ALTER TABLE modulo9.infraestructuras "
        "ALTER COLUMN tipo TYPE modulo9.enum_tipo_infraestructura "
        "USING tipo::modulo9.enum_tipo_infraestructura"
    )

    _crear_vistas()

    op.drop_table("tipos_area", schema="modulo9")
