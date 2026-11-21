# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-12 | Arekkazu | Lote M05/M06 11-12 RF-82 v1.1 (INC-M06-304-G05): Administrador con todo el módulo financiero; Auditor ve el reconocimiento; unión de los heads del lote |
"""rbac m06: el Administrador opera todo el módulo financiero y el Auditor ve el reconocimiento

Revision ID: 810b1e4eb4f9
Revises: a107980ae001, d1f3a5c7e902, f108174bc001
Create Date: 2026-11-12

Une los tres heads del lote del 12-11 (#1094 d1f3a5c7e902, #1096 a107980ae001, #1097 f108174bc001,
los tres sobre 603631775892) y ajusta permisos (CLAUDE.md, RBAC: son datos; router, menú y RLS
los leen en cada request).

- RF-82 v1.1 propuesto (INC-M06-304-G05): el Administrador confirmaba la propuesta de
  reconocimiento y recibía 403. Se le dan las mismas acciones que el Contador sobre los 12
  recursos de M06: 14 permisos nuevos (cierre, reconocimiento, costos, cotizaciones, estado de
  resultados, revelaciones, trazabilidad, valoración y valoración por costo).
- RF-82 postcondición 6 b): el Auditor no veía el reconocimiento confirmado. GET
  /finanzas/activos/{id} pide Leer de `valoracion_activos` y la RLS de
  `reconocimientos_iniciales` pide Leer de `reconocimiento_inicial`; se le dan los dos.
  El rol es dinámico (lo crea el Administrador, no una migración): si no existe, no se hace
  nada; si lo renombran, el permiso sigue con el rol por su id.

Rol, recurso y acción se resuelven por nombre (los ids difieren entre bases).

Un permiso del Administrador ya existente no se puede tocar (`trg_proteger_permisos_admin_update`):
si alguno de los 31 quedó inactivo en una base, la migración aborta y lo nombra en vez de
seguir sin él. Downgrade: retira los del Auditor; los del Administrador no se pueden retirar
(`trg_proteger_permisos_admin_delete`), igual que en 603631775892.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '810b1e4eb4f9'
down_revision: Union[str, Sequence[str], None] = ('a107980ae001', 'd1f3a5c7e902', 'f108174bc001')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_VERBO = {'C': 'crear', 'R': 'leer', 'U': 'actualizar', 'D': 'desactivar', 'E': 'ejecutar'}
_ADMIN = {  # recurso -> acciones; las del Contador en M06
    'precios_mercado': 'CR',
    'configuracion_contable': 'CRU',
    'reconocimiento_inicial': 'CRD',
    'valoracion_activos': 'RE',
    'costos_activos': 'CRU',
    'cierre_periodo': 'RE',
    'valoracion_por_costo': 'CRU',
    'cotizaciones': 'CRUD',
    'trazabilidad_contable': 'RE',
    'revelaciones_nic41': 'CRU',
    'estado_resultados': 'CRU',
    'auditoria_financiera': 'R',
}
_AUDITOR = 'Auditor'
_AUDITOR_LECTURA = ('valoracion_activos', 'reconocimiento_inicial')


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


def _pares_admin() -> list[tuple[str, str]]:
    return [(recurso, codigo) for recurso, acciones in _ADMIN.items() for codigo in acciones]


def _validar_catalogo() -> None:
    bind = op.get_bind()
    faltan = [r for r in _ADMIN if not bind.execute(
        sa.text("SELECT 1 FROM modulo1.recursos WHERE nombre_recurso = :r"), {'r': r}).first()]
    if faltan or not bind.execute(sa.text("SELECT 1 FROM modulo1.roles WHERE nombre_rol = 'Administrador'")).first():
        raise RuntimeError(f"RBAC M06: falta el rol Administrador o los recursos {faltan}.")


def _insertar(rol: str, prefijo: str, recurso: str, codigo: str, descripcion: str) -> None:
    op.execute(sa.text("""
        INSERT INTO modulo1.permisos (nombre, descripcion, es_activo, id_recurso, id_accion, id_rol)
        SELECT :nombre, :descripcion, TRUE, rec.id_recurso, a.id_accion, r.id_rol
        FROM modulo1.roles r, modulo1.recursos rec, modulo1.acciones a
        WHERE r.nombre_rol = :rol AND rec.nombre_recurso = :recurso AND a.codigo = :codigo
        ON CONFLICT (id_rol, id_recurso, id_accion) DO NOTHING
    """).bindparams(nombre=f'{prefijo}_{_VERBO[codigo]}_{recurso}', descripcion=descripcion,
                    rol=rol, recurso=recurso, codigo=codigo))


def _exigir_admin_activo() -> None:
    inactivos = [f'{recurso} {codigo}' for recurso, codigo in _pares_admin() if not op.get_bind().execute(sa.text("""
        SELECT 1 FROM modulo1.permisos p
        JOIN modulo1.roles r ON r.id_rol = p.id_rol
        JOIN modulo1.recursos rec ON rec.id_recurso = p.id_recurso
        JOIN modulo1.acciones a ON a.id_accion = p.id_accion
        WHERE r.nombre_rol = 'Administrador' AND rec.nombre_recurso = :recurso AND a.codigo = :codigo AND p.es_activo
    """), {'recurso': recurso, 'codigo': codigo}).first()]
    if inactivos:
        raise RuntimeError(f"RBAC M06: el Administrador tiene inactivos {inactivos} y el trigger no deja reactivarlos.")


def upgrade() -> None:
    _rls(False)
    try:
        _validar_catalogo()
        _actor()
        _sincronizar_secuencia()
        for recurso, codigo in _pares_admin():
            _insertar('Administrador', 'admin', recurso, codigo,
                      'RF-82 v1.1: el Administrador opera todo el módulo financiero')
        _exigir_admin_activo()
        for recurso in _AUDITOR_LECTURA:
            _insertar(_AUDITOR, 'audit', recurso, 'R', 'RF-82 postcondición 6: el Auditor ve el reconocimiento inicial')
    finally:
        _rls(True)


def downgrade() -> None:
    _rls(False)
    try:
        _actor()
        op.execute(sa.text("""
            DELETE FROM modulo1.permisos p USING modulo1.roles r
            WHERE p.id_rol = r.id_rol AND r.nombre_rol = :rol AND p.nombre = ANY(:nombres)
        """).bindparams(rol=_AUDITOR, nombres=[f'audit_leer_{r}' for r in _AUDITOR_LECTURA]))
    finally:
        _rls(True)
