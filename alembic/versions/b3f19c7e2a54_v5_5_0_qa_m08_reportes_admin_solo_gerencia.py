# | Fecha      | Nombre   | Que se hizo                                                                      |
# |------------|----------|----------------------------------------------------------------------------------|
# | 2026-11-23 | Arekkazu | QA-M08 CU02 H-01/H-06 RF-104: el Administrador solo genera los reportes de Gerencia |
"""v5.5.0_qa_m08_reportes_admin_solo_gerencia

Revision ID: b3f19c7e2a54
Revises: 046abf6dbaa9
Create Date: 2026-11-23

QA M08 ronda 3, CU02 H-01 (CP61) y H-06 (CP82). RF-104 v1.1 y RFC-032: el Administrador hace las veces de la
Gerencia y genera solo sus reportes. Los demás son exclusivos de otro rol: Valoración NIC 41, Estado de las
exportaciones y Variación de períodos del Contador (CA-6); los cuatro sanitarios del Veterinario y el Productor
(CA-7; la Gerencia no ve datos clínicos individuales); los cuatro de IoT del Ingeniero de Campo (CA-8).

Los permisos del Administrador no se pueden borrar ni desactivar (``trg_proteger_permisos_admin_update/delete``,
como en 046abf6dbaa9 y 810b1e4eb4f9). Por eso cada uno de esos 11 recursos se renombra con el sufijo
``_retirado`` (se queda con el permiso del Administrador, que ya nada consulta) y se crea un recurso nuevo con el
nombre original al que pasan los permisos de los demás roles. El código no cambia: el catálogo de reportes
busca el permiso por el nombre ``reporte_<tipo>``.

Roles y recursos se resuelven por nombre (los ids no coinciden entre bases). ``modulo1.recursos``, ``permisos``
y ``roles`` tienen FORCE RLS: se suspende durante la migración. Reejecutar ``upgrade()`` no hace nada: solo
actúa si el recurso original todavía tiene un permiso del Administrador.

``downgrade()`` devuelve los permisos al recurso original, borra el nuevo y le quita el sufijo al retirado.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'b3f19c7e2a54'
down_revision: Union[str, Sequence[str], None] = '046abf6dbaa9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLAS_FORCE = ('modulo1.recursos', 'modulo1.permisos', 'modulo1.roles')
_SUFIJO = '_retirado'
_DESCRIPCION_RETIRADO = ('Recurso retirado: el Administrador ya no genera este reporte. Los demás roles usan el '
                         'recurso con el mismo nombre sin el sufijo.')

# Reportes que el Administrador deja de generar (todos menos los siete en los que RF-104 nombra a la Gerencia).
_RECURSOS = (
    'reporte_valoracion_nic41', 'reporte_estado_exportaciones', 'reporte_variacion_periodos',
    'reporte_historico_sanitario', 'reporte_ficha_animal', 'reporte_vacunacion_medicamentos',
    'reporte_riesgo_sanitario',
    'reporte_telemetria', 'reporte_estado_dispositivos', 'reporte_calibracion_sensores', 'reporte_alertas_sensores',
)

_ADMIN = "(SELECT id_rol FROM modulo1.roles WHERE nombre_rol = 'Administrador')"
_ID = "(SELECT id_recurso FROM modulo1.recursos WHERE nombre_recurso = :{})"


def _rls(force: bool) -> None:
    for tabla in _TABLAS_FORCE:
        op.execute(sa.text(f"ALTER TABLE {tabla} {'FORCE' if force else 'NO FORCE'} ROW LEVEL SECURITY"))


def _actor() -> None:
    # Los triggers de M01 (auditoría DML, protección de permisos) piden un actor en la sesión.
    op.execute(sa.text("SELECT set_config('app.current_role', 'Administrador', true), "
                       "set_config('app.current_user_id', '1', true)"))


def _retirar(recurso: str) -> None:
    params = {"recurso": recurso, "retirado": recurso + _SUFIJO}
    # 1. El recurso con el permiso del Administrador pasa a llamarse «…_retirado».
    op.execute(sa.text(f"""
        UPDATE modulo1.recursos rec SET nombre_recurso = :retirado
         WHERE rec.nombre_recurso = :recurso
           AND EXISTS (SELECT 1 FROM modulo1.permisos p WHERE p.id_recurso = rec.id_recurso AND p.id_rol = {_ADMIN})
    """).bindparams(**params))
    # 2. El nombre original vuelve como recurso nuevo, con la misma descripción.
    op.execute(sa.text("""
        INSERT INTO modulo1.recursos (id_recurso, nombre_recurso, descripcion)
        SELECT (SELECT max(id_recurso) + 1 FROM modulo1.recursos), :recurso, viejo.descripcion
          FROM modulo1.recursos viejo
         WHERE viejo.nombre_recurso = :retirado
           AND NOT EXISTS (SELECT 1 FROM modulo1.recursos WHERE nombre_recurso = :recurso)
    """).bindparams(**params))
    op.execute(sa.text("UPDATE modulo1.recursos SET descripcion = :descripcion WHERE nombre_recurso = :retirado")
               .bindparams(retirado=recurso + _SUFIJO, descripcion=_DESCRIPCION_RETIRADO))
    # 3. Los permisos de los demás roles pasan al recurso nuevo; el del Administrador se queda en el retirado.
    op.execute(sa.text(f"""
        UPDATE modulo1.permisos
           SET id_recurso = {_ID.format('recurso')}, fecha_actualizacion = now()
         WHERE id_recurso = {_ID.format('retirado')} AND id_rol <> {_ADMIN}
    """).bindparams(**params))


def _restaurar(recurso: str) -> None:
    params = {"recurso": recurso, "retirado": recurso + _SUFIJO}
    op.execute(sa.text(f"""
        UPDATE modulo1.permisos
           SET id_recurso = {_ID.format('retirado')}, fecha_actualizacion = now()
         WHERE id_recurso = {_ID.format('recurso')} AND {_ID.format('retirado')} IS NOT NULL
    """).bindparams(**params))
    op.execute(sa.text("""
        UPDATE modulo1.recursos retirado
           SET descripcion = nuevo.descripcion
          FROM modulo1.recursos nuevo
         WHERE retirado.nombre_recurso = :retirado AND nuevo.nombre_recurso = :recurso
    """).bindparams(**params))
    op.execute(sa.text("""
        DELETE FROM modulo1.recursos
         WHERE nombre_recurso = :recurso
           AND EXISTS (SELECT 1 FROM modulo1.recursos WHERE nombre_recurso = :retirado)
    """).bindparams(**params))
    op.execute(sa.text("UPDATE modulo1.recursos SET nombre_recurso = :recurso WHERE nombre_recurso = :retirado")
               .bindparams(**params))


def upgrade() -> None:
    _rls(False)
    try:
        _actor()
        for recurso in _RECURSOS:
            _retirar(recurso)
    finally:
        _rls(True)


def downgrade() -> None:
    _rls(False)
    try:
        _actor()
        for recurso in _RECURSOS:
            _restaurar(recurso)
    finally:
        _rls(True)
