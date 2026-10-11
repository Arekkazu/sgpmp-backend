"""rf20_rf34_recurso_tipos_area_y_historial_vigente

Revision ID: 4c1700760710
Revises: 96621b225009
Create Date: 2026-10-02 23:50:00.000000

Dos huecos de datos que QA encontró en TEST (SGPMP-FRONT-END-PWA #167 y #226).
Ninguno cambia el esquema.

1. #167 (RF-20): el router de `/configuracion/tipos-area` exige el recurso RBAC
   58 (`tipos_area`), pero la migración que creó el catálogo (2dbb6d44046f) no
   lo sembró. En DEV se insertó a mano; en TEST no existe, así que el
   Administrador recibe 403 al listar tipos de área. Se siembra con el mismo id
   y los mismos permisos que ya tiene DEV.

2. #226 (RF-34): `GET /activos-biologicos/{id}/infraestructura?tipo_consulta=ACTIVA`
   lee la fila vigente (`fecha_fin IS NULL`) de `historial_infraestructura_activo`.
   El registro por la API la crea desde RF-33, pero los activos cargados por
   SQL (semilla de mayo y fixtures de QA) no la tienen: 22 de 602 en TEST, 17
   de 27 en DEV. Se crea una fila vigente con la infraestructura que el activo
   ya declara en `activos_biologicos.id_infraestructura`, desde el cierre de su
   último período (o su fecha de registro si nunca tuvo uno).
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '4c1700760710'
down_revision: Union[str, Sequence[str], None] = '96621b225009'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ID_RECURSO = 58


def upgrade() -> None:
    op.execute(
        f"""
        DO $$
        DECLARE
            v_id_recurso INTEGER;
        BEGIN
            IF EXISTS (SELECT 1 FROM modulo1.recursos WHERE nombre_recurso = 'tipos_area') THEN
                SELECT id_recurso INTO v_id_recurso
                FROM modulo1.recursos WHERE nombre_recurso = 'tipos_area';
            ELSIF EXISTS (SELECT 1 FROM modulo1.recursos WHERE id_recurso = {_ID_RECURSO}) THEN
                RAISE EXCEPTION 'RF20: id_recurso={_ID_RECURSO} ya esta en uso por otro recurso; el router de tipos de area lo tiene fijo.';
            ELSE
                INSERT INTO modulo1.recursos (id_recurso, nombre_recurso, descripcion)
                VALUES ({_ID_RECURSO}, 'tipos_area', 'Catálogo administrable de tipos de área productiva');
                v_id_recurso := {_ID_RECURSO};
            END IF;

            IF v_id_recurso <> {_ID_RECURSO} THEN
                RAISE EXCEPTION 'RF20: tipos_area tiene id_recurso=% pero el router usa {_ID_RECURSO}.', v_id_recurso;
            END IF;

            INSERT INTO modulo1.permisos (nombre, descripcion, id_rol, id_recurso, id_accion, es_activo)
            VALUES
                ('admin_crear_tipos_area', 'Administrador puede crear tipos de área', 1, v_id_recurso, 1, TRUE),
                ('admin_leer_tipos_area', 'Administrador puede consultar tipos de área', 1, v_id_recurso, 2, TRUE),
                ('admin_desactivar_tipos_area', 'Administrador puede desactivar tipos de área', 1, v_id_recurso, 4, TRUE),
                ('prod_leer_tipos_area', 'Productor puede consultar tipos de área', 2, v_id_recurso, 2, TRUE)
            ON CONFLICT (id_rol, id_recurso, id_accion) DO NOTHING;
        END
        $$;
        """
    )

    op.execute(
        """
        INSERT INTO modulo2.historial_infraestructura_activo
            (id_activo_biologico, id_infraestructura, fecha_inicio, fecha_fin, id_usuario_registro)
        SELECT a.id_activo_biologico,
               a.id_infraestructura,
               COALESCE(
                   (SELECT MAX(h.fecha_fin) FROM modulo2.historial_infraestructura_activo h
                    WHERE h.id_activo_biologico = a.id_activo_biologico),
                   a.fecha_creacion
               ),
               NULL,
               a.id_usuario
        FROM modulo2.activos_biologicos a
        WHERE a.id_infraestructura IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM modulo2.historial_infraestructura_activo h
              WHERE h.id_activo_biologico = a.id_activo_biologico AND h.fecha_fin IS NULL
          );
        """
    )


def downgrade() -> None:
    # No-op a propósito:
    # - los permisos del Administrador son inmutables (trg_proteger_permisos_admin_delete)
    #   y en DEV el recurso 58 ya existía antes de esta migración;
    # - las filas de historial son indistinguibles de las que crea RF-33, y
    #   borrarlas devolvería el 404 que este cambio corrige.
    pass
