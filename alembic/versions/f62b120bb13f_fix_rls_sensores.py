"""fix_rls_sensores

Revision ID: f62b120bb13f
Revises: c32b50fa71e7
Create Date: 2026-10-25 16:36:33.758172

INC-M03-150-G92 (RUN-G92-V1-20261025-075632):
La política SELECT de modulo9.sensores usaba fn_sensores_del_usuario(), que
consulta la propia tabla sensores. Durante un INSERT ... RETURNING (flush/refresh
de SQLAlchemy), la fila recién creada no satisface la política de visibilidad
porque la resolución vuelve a consultar sensores y no ve la fila en curso,
generando "new row violates row-level security policy for table sensores".

Corrección: SELECT y UPDATE pasan a derivar la visibilidad directamente del
dispositivo asociado (id_dispositivo_iot IN fn_dispositivos_del_usuario(uid)),
el MISMO criterio que ya usa la política INSERT. Se elimina la dependencia
circular SIN ampliar permisos: el conjunto de filas visibles es idéntico,
solo cambia el camino para resolverlo.

No se modifica bd9cea80dea6; esta es una migración correctiva nueva.
No se toca pol_sensores_insert (ya es correcta) ni pol_sensores_servicio.


"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f62b120bb13f'
down_revision: Union[str, Sequence[str], None] = 'c32b50fa71e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UID = "(SELECT modulo1.fn_id_usuario_actual())"


def upgrade() -> None:
    _disp_subq = (
        "SELECT d.id_dispositivo_iot "
        f"FROM modulo9.fn_dispositivos_del_usuario({UID}) d"
    )

    # ---- SELECT: romper la dependencia circular ----
    # Antes: id_sensores IN fn_sensores_del_usuario()  → consulta sensores (circular)
    # Ahora: id_dispositivo_iot IN fn_dispositivos_del_usuario()  → consulta dispositivos (directo)
    op.execute("DROP POLICY IF EXISTS pol_sensores_select ON modulo9.sensores;")
    op.execute(f"""
        CREATE POLICY pol_sensores_select ON modulo9.sensores
          FOR SELECT
          USING (id_dispositivo_iot IN ({_disp_subq}));
    """)

    # ---- UPDATE: mismo criterio directo ----
    # USING: el sensor debe estar hoy en un dispositivo del alcance del usuario.
    # WITH CHECK: tras el UPDATE el sensor debe SEGUIR en un dispositivo del
    #             alcance. Esto impide trasladar un sensor a un dispositivo
    #             no autorizado (restricción explícita del issue).
    op.execute("DROP POLICY IF EXISTS pol_sensores_update ON modulo9.sensores;")
    op.execute(f"""
        CREATE POLICY pol_sensores_update ON modulo9.sensores
          FOR UPDATE
          USING (id_dispositivo_iot IN ({_disp_subq}))
          WITH CHECK (id_dispositivo_iot IN ({_disp_subq}));
    """)

    # pol_sensores_insert YA usa fn_dispositivos_del_usuario y es correcta: no se toca.
    # pol_sensores_servicio tampoco se toca.
    # RLS y FORCE ROW LEVEL SECURITY permanecen habilitados: no se tocan.


def downgrade() -> None:
    # Restaura las políticas originales (circulares) de bd9cea80dea6.
    _sensor_subq = (
        "SELECT s.id_sensores "
        f"FROM modulo9.fn_sensores_del_usuario({UID}) s"
    )

    op.execute("DROP POLICY IF EXISTS pol_sensores_select ON modulo9.sensores;")
    op.execute(f"""
        CREATE POLICY pol_sensores_select ON modulo9.sensores
          FOR SELECT
          USING (id_sensores IN ({_sensor_subq}));
    """)

    op.execute("DROP POLICY IF EXISTS pol_sensores_update ON modulo9.sensores;")
    op.execute(f"""
        CREATE POLICY pol_sensores_update ON modulo9.sensores
          FOR UPDATE
          USING (id_sensores IN ({_sensor_subq}))
          WITH CHECK (id_sensores IN ({_sensor_subq}));
    """)