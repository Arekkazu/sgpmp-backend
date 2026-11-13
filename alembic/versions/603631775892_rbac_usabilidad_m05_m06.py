# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-11 | Arekkazu | USAB-M05-M06 M5-08 RF-74 / M6-05 RF-88/92: Productor sin el cálculo automático del ICA; Administrador lee valoración sin mercado y revelaciones |
"""rbac m05/m06: permisos por rol del reporte de usabilidad del 11-11

Revision ID: 603631775892
Revises: 143fa2eda4fc
Create Date: 2026-11-11

Reporte de usabilidad M05/M06 (Equipo de diseño, 11-11-2026). Los permisos son datos
(CLAUDE.md, RBAC): el router, el menú del front y la RLS los leen en cada request.

- M5-08 (RF-74): el cálculo automático del ICA es un proceso del sistema; el Productor
  solo consulta el ICA de sus activos. Se desactivan (no se borran) sus permisos Leer y
  Ejecutar sobre `administracion_batch_ica`; conserva `eficiencia_alimenticia`.
- M6-05: el Administrador no veía «Valoración sin mercado» (RF-88) ni «Revelaciones NIC 41»
  (RF-92), y las demás secciones del módulo financiero sí. Se le da solo Leer.

Rol, recurso y acción se resuelven por nombre (los ids difieren entre bases).

Downgrade: reactiva los permisos del Productor. Los del Administrador NO se pueden retirar:
`trg_proteger_permisos_admin_update/delete` bloquean tocar un permiso de ese rol, a propósito.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '603631775892'
down_revision: Union[str, Sequence[str], None] = '143fa2eda4fc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_BATCH_ICA = 'administracion_batch_ica'
_PRODUCTOR = 'Productor'
_ADMIN_LECTURA = {  # recurso -> descripción del permiso
    'valoracion_por_costo': 'USAB M6-05 RF-88: consultar la valoración sin mercado',
    'revelaciones_nic41': 'USAB M6-05 RF-92: consultar las revelaciones NIC 41',
}


def _rls(force: bool) -> None:
    # modulo1.permisos tiene FORCE RLS: sin contexto de usuario la migración no vería filas.
    op.execute(sa.text(f"ALTER TABLE modulo1.permisos {'FORCE' if force else 'NO FORCE'} ROW LEVEL SECURITY"))


def _actor() -> None:
    # Los triggers de M01 (auditoría DML) piden un actor en la sesión.
    op.execute(sa.text("SELECT set_config('app.current_role', 'Administrador', true), "
                       "set_config('app.current_user_id', '1', true)"))


def _exigir(sql: str, descripcion: str) -> None:
    if op.get_bind().execute(sa.text(f'SELECT count(*) FROM ({sql}) s')).scalar() != 1:
        raise RuntimeError(f'RBAC usabilidad M05/M06: se esperaba exactamente 1 {descripcion}.')


def _validar() -> None:
    for rol in ('Administrador', _PRODUCTOR):
        _exigir(f"SELECT 1 FROM modulo1.roles WHERE nombre_rol = '{rol}'", f"rol '{rol}'")
    for recurso in (_BATCH_ICA, *_ADMIN_LECTURA):
        _exigir(f"SELECT 1 FROM modulo1.recursos WHERE nombre_recurso = '{recurso}'", f"recurso '{recurso}'")


def _batch_productor(es_activo: bool) -> None:
    op.execute(sa.text(f"""
        UPDATE modulo1.permisos p SET es_activo = {str(es_activo).upper()}, fecha_actualizacion = now()
        FROM modulo1.roles r, modulo1.recursos rec, modulo1.acciones a
        WHERE p.id_rol = r.id_rol AND p.id_recurso = rec.id_recurso AND p.id_accion = a.id_accion
          AND r.nombre_rol = '{_PRODUCTOR}' AND rec.nombre_recurso = '{_BATCH_ICA}' AND a.codigo IN ('R', 'E')
    """))


def _sincronizar_secuencia() -> None:
    op.execute(sa.text("""
        SELECT setval('modulo1.permisos_id_permiso_seq',
            GREATEST((SELECT COALESCE(MAX(id_permiso), 0) + 1 FROM modulo1.permisos),
                     (SELECT CASE WHEN is_called THEN last_value + 1 ELSE last_value END
                      FROM modulo1.permisos_id_permiso_seq)), false)
    """))


def _lectura_admin() -> None:
    # Un permiso del Administrador ya existente no se puede actualizar (trigger): si existe, se deja.
    for recurso, descripcion in _ADMIN_LECTURA.items():
        op.execute(sa.text(f"""
            INSERT INTO modulo1.permisos (nombre, descripcion, es_activo, id_recurso, id_accion, id_rol)
            SELECT 'admin_leer_{recurso}', '{descripcion}', TRUE, rec.id_recurso, a.id_accion, r.id_rol
            FROM modulo1.roles r, modulo1.recursos rec, modulo1.acciones a
            WHERE r.nombre_rol = 'Administrador' AND rec.nombre_recurso = '{recurso}' AND a.codigo = 'R'
            ON CONFLICT (id_rol, id_recurso, id_accion) DO NOTHING
        """))


def upgrade() -> None:
    _rls(False)
    try:
        _validar()
        _actor()
        _batch_productor(False)
        _sincronizar_secuencia()
        _lectura_admin()
    finally:
        _rls(True)


def downgrade() -> None:
    _rls(False)
    try:
        _actor()
        _batch_productor(True)
    finally:
        _rls(True)
