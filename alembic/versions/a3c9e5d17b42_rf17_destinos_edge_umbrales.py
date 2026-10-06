"""RF-17: Gateway Edge destino de los umbrales ambientales de una especie

Revision ID: a3c9e5d17b42
Revises: 78f6f579b5ba
Create Date: 2026-10-05

INC-M09-104-G29 (#493): al crear o editar un umbral ambiental, el backend lo
propaga a los Gateway Edge de las áreas de esa especie. Esta función responde
"¿a qué Gateway Edge le corresponde un umbral de la especie X?":

- áreas (`infraestructuras`) activas con `id_especie = X`;
- de ellas, los Gateway Edge activos (tipo `GATEWAY_EDGE`) instalados en el área
  o que atienden un dispositivo activo del área (`id_dispositivo_gateway`).

`SECURITY DEFINER` porque la propagación no puede depender de quién edita el
umbral: la política de `dispositivos_iot` solo deja leer a Administrador e
Ingeniero de Campo, pero un Veterinario también edita umbrales; y la búsqueda
corre después del primer commit del use case. Solo devuelve seriales, nada
más de las tablas. Dueña `sgpmp_owner` (dueña de las tablas, RLS no forzado)
cuando quien migra puede asignarla; si no, queda de quien migra, como
`modulo9.fn_fincas_del_usuario` (hoy `dba`).
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'a3c9e5d17b42'
down_revision: Union[str, Sequence[str], None] = '78f6f579b5ba'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_FIRMA = 'modulo9.fn_seriales_gateway_edge_por_especie(integer)'


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION modulo9.fn_seriales_gateway_edge_por_especie(p_id_especie integer)
        RETURNS TABLE (serial varchar)
        LANGUAGE sql
        STABLE
        SECURITY DEFINER
        SET search_path = pg_catalog, modulo9
        AS $$
            SELECT DISTINCT g.serial
            FROM modulo9.infraestructuras i
            JOIN modulo9.dispositivos_iot d
              ON d.id_infraestructura = i.id_infraestructura
             AND d.es_activo
            JOIN modulo9.dispositivos_iot g
              ON g.id_dispositivo_iot = COALESCE(d.id_dispositivo_gateway, d.id_dispositivo_iot)
             AND g.es_activo
            JOIN modulo9.tipos_dispositivo_iot t
              ON t.id_tipo_dispositivo = g.id_tipo_dispositivo
             AND t.nombre = 'GATEWAY_EDGE'
            WHERE i.id_especie = p_id_especie
              AND i.es_activo
            ORDER BY g.serial;
        $$;
        """
    )
    op.execute(
        f"""
        DO $$
        DECLARE r text;
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sgpmp_owner')
               AND pg_has_role(current_user, 'sgpmp_owner', 'MEMBER') THEN
                ALTER FUNCTION {_FIRMA} OWNER TO sgpmp_owner;
            END IF;
            REVOKE ALL ON FUNCTION {_FIRMA} FROM PUBLIC;
            FOR r IN SELECT rolname FROM pg_roles
                     WHERE rolname IN ('sgpmp_app', 'rol_app', 'rol_dev', 'rol_impl') LOOP
                EXECUTE format('GRANT EXECUTE ON FUNCTION {_FIRMA} TO %I', r);
            END LOOP;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute(f'DROP FUNCTION IF EXISTS {_FIRMA};')
