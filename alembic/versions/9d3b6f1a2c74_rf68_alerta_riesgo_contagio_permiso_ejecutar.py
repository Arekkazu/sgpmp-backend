# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-26 | Arekkazu | INC-M04-196-G026 RF-68: tipo de alerta RIESGO_CONTAGIO y permiso para ejecutar el modelo |
"""RF-68: alerta RIESGO_CONTAGIO y permiso para ejecutar el modelo de contagio.

- ``modulo3.enum_tipo_alerta`` + ``RIESGO_CONTAGIO``: RF-68 paso 8 / CA-3 generan la
  alerta en RF-57 con ese tipo. Las tablas del modelo (``modulo4.resultados_riesgo_contagio``)
  y sus eventos de RF-73 ya existían.
- ``POST /prediccion/riesgo-contagio`` se autoriza con Ejecutar (E=5) sobre
  ``configuracion_motor_ia``: Administrador y Veterinario, los mismos que configuran el
  motor (C/R). El recurso se resuelve por nombre (su id no coincide entre bases).

Revision ID: 9d3b6f1a2c74
Revises: 30168ab97bd4
Create Date: 2026-10-26 10:30:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "9d3b6f1a2c74"
down_revision: Union[str, Sequence[str], None] = "30168ab97bd4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PERMISOS = (
    # (id_rol, nombre_rol, nombre_permiso)
    (1, "administrador", "admin_ejecutar_configuracion_motor_ia"),
    (3, "veterinario", "vet_ejecutar_configuracion_motor_ia"),
)


def upgrade() -> None:
    op.execute("ALTER TYPE modulo3.enum_tipo_alerta ADD VALUE IF NOT EXISTS 'RIESGO_CONTAGIO'")
    for id_rol, nombre_rol, nombre in _PERMISOS:
        op.execute(f"""
        DO $$
        DECLARE
            v_recurso integer;
        BEGIN
            SELECT id_recurso INTO STRICT v_recurso
            FROM modulo1.recursos WHERE nombre_recurso = 'configuracion_motor_ia';

            IF NOT EXISTS (
                SELECT 1 FROM modulo1.roles
                WHERE id_rol = {id_rol} AND lower(btrim(nombre_rol)) = '{nombre_rol}'
            ) THEN
                RAISE EXCEPTION 'RF-68: id_rol={id_rol} no corresponde al rol {nombre_rol}';
            END IF;

            INSERT INTO modulo1.permisos (nombre, descripcion, id_rol, id_recurso, id_accion, es_activo)
            VALUES ('{nombre}', 'Ejecutar el modelo de riesgo de contagio (RF-68)', {id_rol}, v_recurso, 5, TRUE)
            ON CONFLICT (id_rol, id_recurso, id_accion) DO NOTHING;
        END $$;
        """)


def downgrade() -> None:
    # Postgres no permite quitar un valor de un ENUM: RIESGO_CONTAGIO queda sin uso. El
    # permiso del Administrador tampoco se borra: ADMIN_PERM_NO_DELETE lo hace permanente.
    op.execute("DELETE FROM modulo1.permisos WHERE nombre = 'vet_ejecutar_configuracion_motor_ia'")
