# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-12 | Arekkazu | M06 RF-82: el rol Auditor lee la configuración contable (propuestas de reconocimiento daban 500) |
"""rbac m06: el rol Auditor lee la configuración contable

Revision ID: 0884ba08a944
Revises: 603631775892
Create Date: 2026-11-12

El rol «Auditor» (creado desde la gestión de roles, no por el seed) lee el reconocimiento
inicial pero no `configuracion_contable`. La propuesta de reconocimiento (RF-82) lee esa
configuración y la RLS de `modulo6.configuraciones_contables` le ocultaba la fila: el
endpoint `GET /reconocimientos/propuestas` respondía 500.

Rol, recurso y acción se resuelven por nombre (el Auditor es id 27 en DEV y 81 en TEST).
Si la base no tiene rol Auditor (PROD, `pruebas`), la migración no hace nada.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '0884ba08a944'
down_revision: Union[str, Sequence[str], None] = '603631775892'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NOMBRE = 'audit_leer_configuracion_contable'


def _rls(force: bool) -> None:
    # modulo1.permisos tiene FORCE RLS: sin contexto de usuario la migración no vería filas.
    op.execute(sa.text(f"ALTER TABLE modulo1.permisos {'FORCE' if force else 'NO FORCE'} ROW LEVEL SECURITY"))


def _actor() -> None:
    # Los triggers de M01 (auditoría DML) piden un actor en la sesión.
    op.execute(sa.text("SELECT set_config('app.current_role', 'Administrador', true), "
                       "set_config('app.current_user_id', '1', true)"))


def _sincronizar_secuencia() -> None:
    op.execute(sa.text("""
        SELECT setval('modulo1.permisos_id_permiso_seq',
            GREATEST((SELECT COALESCE(MAX(id_permiso), 0) + 1 FROM modulo1.permisos),
                     (SELECT CASE WHEN is_called THEN last_value + 1 ELSE last_value END
                      FROM modulo1.permisos_id_permiso_seq)), false)
    """))


def upgrade() -> None:
    _rls(False)
    try:
        _actor()
        _sincronizar_secuencia()
        op.execute(sa.text(f"""
            INSERT INTO modulo1.permisos (nombre, descripcion, es_activo, id_recurso, id_accion, id_rol)
            SELECT '{_NOMBRE}', 'Auditor consulta configuracion contable (solo lectura).', TRUE,
                   rec.id_recurso, a.id_accion, r.id_rol
            FROM modulo1.roles r, modulo1.recursos rec, modulo1.acciones a
            WHERE r.nombre_rol = 'Auditor' AND rec.nombre_recurso = 'configuracion_contable' AND a.codigo = 'R'
            ON CONFLICT (id_rol, id_recurso, id_accion) DO UPDATE SET es_activo = TRUE, fecha_actualizacion = now()
        """))
    finally:
        _rls(True)


def downgrade() -> None:
    _rls(False)
    try:
        _actor()
        op.execute(sa.text(f"DELETE FROM modulo1.permisos WHERE nombre = '{_NOMBRE}'"))
    finally:
        _rls(True)
