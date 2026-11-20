# | Fecha      | Nombre   | Que se hizo                                                                     |
# |------------|----------|---------------------------------------------------------------------------------|
# | 2026-11-19 | Arekkazu | M8-02/M8-03 RF-103/RF-105: nivel de avisos anteriores y panel del Productor      |
"""m08 usabilidad: nivel de los avisos anteriores a RF-105 y panel predeterminado en las cuentas del Productor

Revision ID: a0701b636a92
Revises: a7c3e91f5b20
Create Date: 2026-11-19

Solo datos, sin objetos nuevos.

- M8-03: la columna ``nivel`` de ``modulo1.notificaciones`` llegó con ``DEFAULT 'INFORMATIVA'`` y las notificaciones
  que ya existían quedaron así: una alerta ambiental crítica sin etiqueta, después de los avisos de cuenta y con
  «Descartar». Se les pone el nivel de su tipo (el mismo mapa de ``nivel_notificacion._NIVEL_POR_TIPO``) y las
  alertas de telemetría cuyo texto dice «(crítica)» pasan a CRÍTICA. Solo las aún sin atender (NUEVA o LEÍDA): las
  restricciones no dejan una CRÍTICA descartada.
- M8-02: el predeterminado del Productor ya trae el semáforo y sus indicadores, pero los Productores que guardaron
  su panel antes siguen con los widgets técnicos de IoT. Por decisión del equipo se aplica a todas sus cuentas lo
  mismo que hace «Restaurar predeterminado», conservando la frecuencia de actualización que cada uno eligió.

``downgrade()`` no deshace los datos: los paneles personales anteriores y el nivel original no se guardaron.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'a0701b636a92'
down_revision: Union[str, Sequence[str], None] = 'a7c3e91f5b20'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLAS_FORCE = ('modulo1.notificaciones', 'modulo9.dashboard_layouts', 'modulo1.usuarios', 'modulo1.roles')

# Copia de nivel_notificacion._NIVEL_POR_TIPO (una migración no importa código de la app).
_NIVEL_POR_TIPO = {
    'LOGIN_FALLIDO': 'ADVERTENCIA', 'CAMBIO_ESTADO_CUENTA': 'ADVERTENCIA',
    'REUSO_TOKEN_REFRESCO_DETECTADO': 'ADVERTENCIA', 'FALLO_ARCHIVADO_AUDITORIA': 'ADVERTENCIA',
    'INCONSISTENCIA_AUDITORIA_M02': 'ADVERTENCIA', 'NOTIFICACION_ALERTA': 'ADVERTENCIA',
    'REPORTE_GASTOS_FALLIDO': 'ADVERTENCIA', 'PROVISION_M06_PENDIENTE': 'ADVERTENCIA',
    'ALERTA_CONVERSION_ALIMENTICIA': 'ADVERTENCIA', 'BATCH_ICA_INTERRUMPIDO': 'ADVERTENCIA',
    'ALERTA_FINANCIERA_NIC41': 'ADVERTENCIA', 'FIN_PERIODO_RETIRO': 'ADVERTENCIA',
    'ALERTA_INTEGRACION_CONTABLE': 'CRITICA', 'REPORTE_FALLIDO': 'ADVERTENCIA',
    'DEGRADACION_MODELO_PREDICTIVO': 'ADVERTENCIA',
}


def _rls(force: bool) -> None:
    for tabla in _TABLAS_FORCE:
        op.execute(sa.text(f"ALTER TABLE {tabla} {'FORCE' if force else 'NO FORCE'} ROW LEVEL SECURITY"))


def upgrade() -> None:
    _rls(False)
    try:
        # Los triggers de auditoría DML piden un actor en la sesión.
        op.execute(sa.text("SELECT set_config('app.current_role', 'Administrador', true), "
                           "set_config('app.current_user_id', '1', true)"))
        for tipo, nivel in _NIVEL_POR_TIPO.items():
            op.execute(sa.text("""
                UPDATE modulo1.notificaciones n
                   SET nivel = CAST(CASE WHEN t.nombre = 'NOTIFICACION_ALERTA' AND n.mensaje LIKE '%(crítica)%'
                                         THEN 'CRITICA' ELSE :nivel END AS modulo1.enum_notificacion_nivel)
                  FROM modulo1.eventos e
                  JOIN modulo1.tipos_eventos t ON t.id_tipo_evento = e.tipo_evento
                 WHERE e.id_evento = n.id_evento AND t.nombre = :tipo
                   AND n.nivel = 'INFORMATIVA' AND n.estado IN ('NUEVA', 'LEIDA')
            """).bindparams(tipo=tipo, nivel=nivel))
        op.execute(sa.text("""
            UPDATE modulo9.dashboard_layouts dl
               SET config = d.config || CASE WHEN dl.config ? 'frecuencia_actualizacion'
                                             THEN jsonb_build_object('frecuencia_actualizacion',
                                                                     dl.config->'frecuencia_actualizacion')
                                             ELSE '{}'::jsonb END,
                   active_widget = d.active_widget,
                   fecha_actualizacion = now()
              FROM modulo1.usuarios u
              JOIN modulo1.roles r ON r.id_rol = u.id_rol AND r.nombre_rol = 'Productor'
              JOIN modulo9.dashboard_layouts_default d ON d.id_rol = r.id_rol
             WHERE dl.id_usuario = u.id_usuario
        """))
    finally:
        _rls(True)


def downgrade() -> None:
    pass
