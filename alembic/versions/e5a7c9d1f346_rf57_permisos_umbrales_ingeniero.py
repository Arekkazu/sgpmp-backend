# | Fecha      | Nombre | Que se hizo                                                                  |
# |------------|--------|------------------------------------------------------------------------------|
# | 2026-10-31 | Claude | INC-M03-175-G57A RF-57: umbrales los configuran Administrador e Ingeniero de Campo |
"""rf57: permisos sobre umbrales_ambientales para Ingeniero de Campo, no Veterinario

Revision ID: e5a7c9d1f346
Revises: d4f6a8b0c235
Create Date: 2026-10-31

INC-M03-175-G57A (#880). RF-57 (Restricción 3, CA-14, CA-17): los umbrales de las
alertas ambientales los configuran el Administrador y el Ingeniero de Campo; los
demás roles reciben 403. En la BD estaba invertido para esos dos roles:

- Ingeniero de Campo: sin permisos sobre `umbrales_ambientales` → 403 al editar.
- Veterinario: C/R/U/D activos → creaba, editaba y desactivaba umbrales.

Resultado:
- Ingeniero de Campo: C, R, U y D (crear, ver, editar y desactivar).
- Veterinario: solo R. Conserva la consulta (las pantallas de especie la usan);
  pierde C, U y D.

Nota para Análisis: RF-17 (M09, v1.0) nombra "Administrador o Veterinario" para
modificar umbrales. Esta migración sigue RF-57, que es lo que QA verifica sobre el
mismo endpoint. Si se decide lo contrario basta con revertir esta revisión.

Los permisos son datos (CLAUDE.md, RBAC): el router y la RLS
(`fn_tiene_permiso('umbrales_ambientales', ...)`) los leen en cada request, sin
cambiar código. Se resuelven rol, recurso y acción por nombre, no por id.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'e5a7c9d1f346'
down_revision: Union[str, Sequence[str], None] = 'd4f6a8b0c235'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_RECURSO = 'umbrales_ambientales'
_INGENIERO = 'Ingeniero de Campo'
_VETERINARIO = 'Veterinario'
# codigo de modulo1.acciones -> verbo del nombre del permiso ({rol}_{accion}_{recurso})
_ACCIONES = {'C': 'crear', 'R': 'leer', 'U': 'actualizar', 'D': 'desactivar'}
_PREFIJO = {_INGENIERO: 'ing', _VETERINARIO: 'vet'}


def _rls(force: bool) -> None:
    # modulo1.permisos tiene FORCE RLS: sin contexto de usuario la migración no vería filas.
    op.execute(sa.text(f"ALTER TABLE modulo1.permisos {'FORCE' if force else 'NO FORCE'} ROW LEVEL SECURITY"))


def _exigir(sql: str, descripcion: str) -> None:
    if op.get_bind().execute(sa.text(f'SELECT count(*) FROM ({sql}) s')).scalar() != 1:
        raise RuntimeError(f'RBAC G57A: se esperaba exactamente 1 {descripcion}.')


def _validar() -> None:
    for rol in (_INGENIERO, _VETERINARIO):
        _exigir(f"SELECT 1 FROM modulo1.roles WHERE nombre_rol = '{rol}'", f"rol '{rol}'")
    _exigir(f"SELECT 1 FROM modulo1.recursos WHERE nombre_recurso = '{_RECURSO}'", f"recurso '{_RECURSO}'")
    for codigo in _ACCIONES:
        _exigir(f"SELECT 1 FROM modulo1.acciones WHERE codigo = '{codigo}'", f"acción '{codigo}'")


def _activar(rol: str, codigo: str) -> None:
    nombre = f'{_PREFIJO[rol]}_{_ACCIONES[codigo]}_umbral_ambiental'
    op.execute(sa.text(f"""
        INSERT INTO modulo1.permisos (nombre, descripcion, es_activo, id_recurso, id_accion, id_rol)
        SELECT '{nombre}', 'RF-57 R3/CA-14: {_ACCIONES[codigo]} umbrales ambientales', TRUE,
               rec.id_recurso, a.id_accion, r.id_rol
        FROM modulo1.roles r, modulo1.recursos rec, modulo1.acciones a
        WHERE r.nombre_rol = '{rol}' AND rec.nombre_recurso = '{_RECURSO}' AND a.codigo = '{codigo}'
        ON CONFLICT (id_rol, id_recurso, id_accion)
        DO UPDATE SET es_activo = TRUE, fecha_actualizacion = now()
    """))


def _desactivar(rol: str, codigo: str) -> None:
    op.execute(sa.text(f"""
        UPDATE modulo1.permisos p SET es_activo = FALSE, fecha_actualizacion = now()
        FROM modulo1.roles r, modulo1.recursos rec, modulo1.acciones a
        WHERE p.id_rol = r.id_rol AND p.id_recurso = rec.id_recurso AND p.id_accion = a.id_accion
          AND r.nombre_rol = '{rol}' AND rec.nombre_recurso = '{_RECURSO}' AND a.codigo = '{codigo}'
    """))


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
        _validar()
        _sincronizar_secuencia()
        for codigo in _ACCIONES:
            _activar(_INGENIERO, codigo)
        _activar(_VETERINARIO, 'R')
        for codigo in ('C', 'U', 'D'):
            _desactivar(_VETERINARIO, codigo)
    finally:
        _rls(True)


def downgrade() -> None:
    _rls(False)
    try:
        _validar()
        for codigo in ('C', 'U', 'D'):
            _activar(_VETERINARIO, codigo)
        for codigo in _ACCIONES:
            _desactivar(_INGENIERO, codigo)
    finally:
        _rls(True)
