# | Fecha      | Nombre   | Que se hizo                                                          |
# |------------|----------|----------------------------------------------------------------------|
# | 2026-10-30 | Arekkazu | INC-M04-230-G72 RF-72/RF-67: INSERT del historial con alcance de finca |
"""rf67: el usuario materializa eventos del historial de los activos que puede ver

Revision ID: 7efe47d6c76a
Revises: 67e33de11180
Create Date: 2026-10-30

Por qué va por Alembic: es el patrón del repo y CI solo despliega lo que está
en `alembic/versions/`.

INC-M04-230-G72 (#869). Consultar el historial diagnóstico (RF-67) materializa
los eventos nuevos en `modulo4.historial_diagnostico_eventos` con la identidad
del usuario de la petición. La tabla solo tenía INSERT para el usuario de
servicio, así que la primera consulta después de una retroalimentación nueva
fallaba con `InsufficientPrivilege` (HTTP 500) y las siguientes también, porque
el evento seguía pendiente.

Se agrega una política INSERT con el mismo criterio que la de lectura
(`pol_historial_diagnostico_evento_select`): solo eventos de activos que están
en las infraestructuras del usuario. No hay BYPASSRLS ni superusuario, RLS
sigue forzada y el alcance no crece: el usuario solo escribe lo que ya puede
leer. La tabla sigue siendo inmutable (triggers de `4e7a1c9d2f60`).
"""
from typing import Sequence, Union

from alembic import op


revision: str = '7efe47d6c76a'
down_revision: Union[str, Sequence[str], None] = '67e33de11180'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE POLICY pol_historial_diagnostico_evento_insert
            ON modulo4.historial_diagnostico_eventos
            FOR INSERT
            WITH CHECK (EXISTS (
                SELECT 1
                FROM modulo2.activos_biologicos ab
                WHERE ab.id_activo_biologico = historial_diagnostico_eventos.id_activo_biologico
                  AND ab.id_infraestructura IN (
                      SELECT i.id_infraestructura
                      FROM modulo9.fn_infraestructuras_del_usuario(
                          (SELECT modulo1.fn_id_usuario_actual())
                      ) i(id_infraestructura)
                  )
            ));
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP POLICY pol_historial_diagnostico_evento_insert ON modulo4.historial_diagnostico_eventos;"
    )
