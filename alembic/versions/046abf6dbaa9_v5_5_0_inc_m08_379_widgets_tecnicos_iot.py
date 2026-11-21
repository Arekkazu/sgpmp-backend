# | Fecha      | Nombre       | Que se hizo                                                                  |
# |------------|--------------|------------------------------------------------------------------------------|
# | 2026-11-21 | destroyerban | INC-M08-379-G001 RF-103: widgets técnicos de IoT solo para Ingeniero y Admin |
"""v5.5.0_inc_m08_379_widgets_tecnicos_iot

Revision ID: 046abf6dbaa9
Revises: e84904d795fd
Create Date: 2026-11-21

INC-M08-379-G001 (RF-103, #1195). Los cuatro widgets técnicos de IoT (``estado_iot``, ``cal_sensores``,
``cfg_pendiente`` y ``dispositivos_sin_senal``) colgaban de ``infraestructura_iot`` y ``dispositivos_iot``,
que el Productor lee para otras pantallas. Como el catálogo, el PATCH y los datos del widget filtran por
el permiso Leer del recurso de cada widget, el Productor los veía y podía guardarlos.

RF-103: «las alertas técnicas de dispositivos IoT (SIN_SEÑAL, EN_MANTENIMIENTO) son de competencia del
Ingeniero de Campo / Administrador (RF-60). El dashboard del Productor NO muestra estas alertas».

- Recurso nuevo ``widgets_tecnicos_iot`` con Leer para Administrador e Ingeniero de Campo. No se usa
  ``datos_tecnicos_dashboard``: ese recurso también lo lee el Veterinario (batería y RSSI de RF-58).
- Los cuatro widgets pasan a ese recurso. El código no cambia: el filtro por RBAC hace el resto.
- Los layouts guardados de usuarios cuyo rol ya no lee el recurso pierden esas celdas (y su clave en
  ``active_widget``); sin esto, su siguiente PATCH respondería 403 por un widget que ya tenían. Lo mismo
  para los predeterminados de rol (solo afecta a roles creados después del seed; los del seed no los
  traen salvo el del Ingeniero de Campo).

Roles y recursos se resuelven por nombre (los ids no coinciden entre bases). ``modulo1.recursos``,
``permisos``, ``roles``, ``acciones``, ``usuarios`` y ``modulo9.dashboard_layouts`` tienen FORCE RLS: se
suspende durante la migración (si no, el UPDATE de layouts solo vería los del actor declarado).

``downgrade()`` devuelve los widgets a su recurso anterior y retira el permiso del Ingeniero; conserva
el recurso y el permiso del Administrador (``trg_proteger_permisos_admin_delete``). Las celdas quitadas
de los layouts no se restauran: el usuario las vuelve a agregar desde el catálogo.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '046abf6dbaa9'
down_revision: Union[str, Sequence[str], None] = 'e84904d795fd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLAS_FORCE = ('modulo1.recursos', 'modulo1.permisos', 'modulo1.roles', 'modulo1.acciones',
                 'modulo1.usuarios', 'modulo9.dashboard_layouts')
_RECURSO = 'widgets_tecnicos_iot'

# clave → recurso anterior (para downgrade)
_WIDGETS = {
    'estado_iot': 'infraestructura_iot',
    'cal_sensores': 'dispositivos_iot',
    'cfg_pendiente': 'dispositivos_iot',
    'dispositivos_sin_senal': 'infraestructura_iot',
}

# rol → prefijo del permiso ({rol}_{accion}_{recurso_singular})
_ROLES = {'Administrador': 'admin', 'Ingeniero de Campo': 'ing'}

_CLAVES = sa.bindparam('claves', value=tuple(_WIDGETS), expanding=True)


def _rls(force: bool) -> None:
    for tabla in _TABLAS_FORCE:
        op.execute(sa.text(f"ALTER TABLE {tabla} {'FORCE' if force else 'NO FORCE'} ROW LEVEL SECURITY"))


def _actor() -> None:
    # Los triggers de M01 (auditoría DML, protección de permisos) piden un actor en la sesión.
    op.execute(sa.text("SELECT set_config('app.current_role', 'Administrador', true), "
                       "set_config('app.current_user_id', '1', true)"))


def _exigir_existentes() -> None:
    """Falla temprano si falta un rol o un widget: un UPDATE sin filas pasaría en silencio."""
    op.execute(sa.text("""
        DO $$
        DECLARE faltan int;
        BEGIN
            SELECT count(*) INTO faltan
              FROM unnest(ARRAY['Administrador', 'Ingeniero de Campo']) AS n(nombre)
             WHERE NOT EXISTS (SELECT 1 FROM modulo1.roles r WHERE r.nombre_rol = n.nombre);
            IF faltan > 0 THEN
                RAISE EXCEPTION 'INC-M08-379: falta el rol Administrador o Ingeniero de Campo';
            END IF;
            SELECT 4 - count(*) INTO faltan FROM modulo9.widgets
             WHERE clave IN ('estado_iot', 'cal_sensores', 'cfg_pendiente', 'dispositivos_sin_senal');
            IF faltan > 0 THEN
                RAISE EXCEPTION 'INC-M08-379: faltan % widgets técnicos de IoT en el catálogo', faltan;
            END IF;
        END $$
    """))


def _sembrar_recurso() -> None:
    op.execute(sa.text(f"""
        INSERT INTO modulo1.recursos (id_recurso, nombre_recurso, descripcion)
        SELECT (SELECT max(id_recurso) + 1 FROM modulo1.recursos), '{_RECURSO}',
               'Widgets técnicos de IoT del dashboard (RF-103): estado, calibraciones, configuración '
               'pendiente y dispositivos sin comunicación. Competencia del Ingeniero de Campo (RF-60).'
        WHERE NOT EXISTS (SELECT 1 FROM modulo1.recursos WHERE nombre_recurso = '{_RECURSO}')
    """))
    for rol, prefijo in _ROLES.items():
        op.execute(sa.text(f"""
            INSERT INTO modulo1.permisos (nombre, descripcion, es_activo, id_recurso, id_accion, id_rol)
            SELECT '{prefijo}_leer_widget_tecnico_iot',
                   '{rol} ve los widgets técnicos de IoT en su dashboard (RF-103).', TRUE,
                   rec.id_recurso, a.id_accion, r.id_rol
            FROM modulo1.roles r, modulo1.recursos rec, modulo1.acciones a
            WHERE r.nombre_rol = '{rol}' AND rec.nombre_recurso = '{_RECURSO}' AND a.codigo = 'R'
            ON CONFLICT (id_rol, id_recurso, id_accion) DO UPDATE SET es_activo = TRUE, fecha_actualizacion = now()
        """))


def _reasignar_widgets() -> None:
    op.execute(sa.text(f"""
        UPDATE modulo9.widgets
           SET id_recurso = (SELECT id_recurso FROM modulo1.recursos WHERE nombre_recurso = '{_RECURSO}')
         WHERE clave IN :claves
    """).bindparams(_CLAVES))


# Roles que leen el recurso: el resto pierde las celdas técnicas de sus layouts.
_ROLES_CON_LECTURA = f"""
    SELECT p.id_rol FROM modulo1.permisos p
      JOIN modulo1.recursos rec ON rec.id_recurso = p.id_recurso
      JOIN modulo1.acciones a ON a.id_accion = p.id_accion
     WHERE rec.nombre_recurso = '{_RECURSO}' AND a.codigo = 'R' AND p.es_activo
"""


def _config_sin_tecnicos(alias: str) -> str:
    """``config`` con el ``grid`` sin las celdas de los widgets técnicos; el resto del JSON se conserva."""
    return f"""
        jsonb_set({alias}.config, '{{grid}}', COALESCE((
            SELECT jsonb_agg(celda ORDER BY ord)
              FROM jsonb_array_elements({alias}.config -> 'grid') WITH ORDINALITY AS g(celda, ord)
             WHERE COALESCE((celda ->> 'id_widget')::int, -1) NOT IN (SELECT id_widget FROM tecnicos)
        ), '[]'::jsonb))
    """


def _tiene_tecnicos(alias: str) -> str:
    return f"""(
        EXISTS (SELECT 1 FROM jsonb_array_elements({alias}.config -> 'grid') AS g(celda)
                 WHERE (celda ->> 'id_widget')::int IN (SELECT id_widget FROM tecnicos))
        OR {alias}.active_widget::text[] && ARRAY(SELECT clave::text FROM tecnicos)
    )"""


def _limpiar_layouts() -> None:
    tecnicos = "WITH tecnicos AS (SELECT id_widget, clave FROM modulo9.widgets WHERE clave IN :claves)"
    op.execute(sa.text(f"""
        {tecnicos}
        UPDATE modulo9.dashboard_layouts d
           SET config = {_config_sin_tecnicos('d')},
               active_widget = ARRAY(SELECT x FROM unnest(d.active_widget) AS x
                                      WHERE x NOT IN (SELECT clave FROM tecnicos)),
               fecha_actualizacion = now()
          FROM modulo1.usuarios u
         WHERE u.id_usuario = d.id_usuario
           AND u.id_rol NOT IN ({_ROLES_CON_LECTURA})
           AND {_tiene_tecnicos('d')}
    """).bindparams(_CLAVES))
    op.execute(sa.text(f"""
        {tecnicos}
        UPDATE modulo9.dashboard_layouts_default d
           SET config = {_config_sin_tecnicos('d')},
               active_widget = ARRAY(SELECT x FROM unnest(d.active_widget) AS x
                                      WHERE x NOT IN (SELECT clave FROM tecnicos))
         WHERE d.id_rol NOT IN ({_ROLES_CON_LECTURA})
           AND {_tiene_tecnicos('d')}
    """).bindparams(_CLAVES))


def upgrade() -> None:
    _rls(False)
    try:
        _actor()
        _exigir_existentes()
        _sembrar_recurso()
        _reasignar_widgets()
        _limpiar_layouts()
    finally:
        _rls(True)


def downgrade() -> None:
    _rls(False)
    try:
        _actor()
        for clave, recurso in _WIDGETS.items():
            op.execute(sa.text("""
                UPDATE modulo9.widgets
                   SET id_recurso = (SELECT id_recurso FROM modulo1.recursos WHERE nombre_recurso = :recurso)
                 WHERE clave = :clave
            """).bindparams(clave=clave, recurso=recurso))
        op.execute(sa.text(f"""
            DELETE FROM modulo1.permisos p
             USING modulo1.roles r, modulo1.recursos rec
             WHERE p.id_rol = r.id_rol AND p.id_recurso = rec.id_recurso
               AND r.nombre_rol = 'Ingeniero de Campo' AND rec.nombre_recurso = '{_RECURSO}'
        """))
    finally:
        _rls(True)
