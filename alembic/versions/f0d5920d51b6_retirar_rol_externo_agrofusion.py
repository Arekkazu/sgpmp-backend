# | Fecha      | Nombre   | Que se hizo                                                          |
# |------------|----------|----------------------------------------------------------------------|
# | 2026-11-13 | Arekkazu | SSO AgroFusion: retira el rol Externo AgroFusion; sus usuarios pasan a Administrador |
"""sso agrofusion: retirar el rol «Externo AgroFusion»

Revision ID: f0d5920d51b6
Revises: 31b14f2fce93
Create Date: 2026-11-13

Quien entra a SIGAB desde AgroFusion compró los módulos para su finca y AgroFusion
todavía no es multi-tenant, así que la cuenta que crea el SSO nace con el rol
Administrador (`SsoLoginUseCase`). El rol «Externo AgroFusion» (cero permisos) ya no lo
usa nadie: sus usuarios pasan al Administrador y el rol se elimina.

El rol se resuelve por nombre (es el id 9 del baseline, pero no se asume) y el
Administrador por `es_protegido`. Si la base no tiene el rol, la migración no hace nada.

`downgrade()` recrea el rol vacío: los usuarios no vuelven a él porque
`trg_proteger_reasignacion_rol_admin` impide sacar a alguien del rol protegido.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'f0d5920d51b6'
down_revision: Union[str, Sequence[str], None] = '31b14f2fce93'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ROL = 'Externo AgroFusion'
_TABLAS = ('modulo1.usuarios', 'modulo1.roles')


def _rls(force: bool) -> None:
    # usuarios y roles tienen FORCE RLS: sin contexto de usuario la migración no vería filas.
    for tabla in _TABLAS:
        op.execute(sa.text(f"ALTER TABLE {tabla} {'FORCE' if force else 'NO FORCE'} ROW LEVEL SECURITY"))


def _actor() -> None:
    # Los triggers de M01 (auditoría DML) piden un actor en la sesión.
    op.execute(sa.text("SELECT set_config('app.current_role', 'Administrador', true), "
                       "set_config('app.current_user_id', '1', true)"))


def upgrade() -> None:
    _rls(False)
    try:
        _actor()
        op.execute(sa.text("""
            UPDATE modulo1.usuarios u
               SET id_rol = (SELECT id_rol FROM modulo1.roles WHERE es_protegido ORDER BY id_rol LIMIT 1)
              FROM modulo1.roles r
             WHERE r.id_rol = u.id_rol AND r.nombre_rol = :rol
        """).bindparams(rol=_ROL))
        # permisos y dashboard_layouts_default caen por ON DELETE CASCADE (el rol no tiene permisos).
        op.execute(sa.text("DELETE FROM modulo1.roles WHERE nombre_rol = :rol").bindparams(rol=_ROL))
    finally:
        _rls(True)


def downgrade() -> None:
    _rls(False)
    try:
        _actor()
        op.execute(sa.text("""
            INSERT INTO modulo1.roles (nombre_rol, descripcion, es_protegido)
            SELECT :rol, 'Cuenta auto-provista vía SSO sin sincronización previa de datos completos', FALSE
            WHERE NOT EXISTS (SELECT 1 FROM modulo1.roles WHERE nombre_rol = :rol)
        """).bindparams(rol=_ROL))
    finally:
        _rls(True)
