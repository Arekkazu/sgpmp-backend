# | Fecha      | Nombre   | Que se hizo                                                                  |
# |------------|----------|------------------------------------------------------------------------------|
# | 2026-11-14 | Arekkazu | M08 RF-103/RF-105: catálogo de widgets, dashboard por rol y ciclo de notificaciones |
"""m08: widgets del dashboard (RF-103) y ciclo de vida de notificaciones (RF-105)

Revision ID: d2e201924d1b
Revises: f0d5920d51b6
Create Date: 2026-11-14

RF-103 (solo datos):
- 15 widgets nuevos en ``modulo9.widgets`` (inventario, valor, semáforo, sanidad, finanzas…). El id se
  asigna después del mayor existente, porque la columna no tiene secuencia y el catálogo puede no ser
  igual en todas las bases; un widget que ya existe por su clave se actualiza.
- Nombres visibles de los widgets existentes; se retiran ``temp_corral`` (igual a Temperatura con el
  área configurable), ``prod_aves`` y ``prod_bovinos`` (sin contraparte en RF-103).
- Recurso ``indicadores_valor_inventario``: el Productor ve el valor del inventario en su dashboard
  sin abrirle la valoración de Finanzas. Lectura para Administrador, Productor y Contador.
- Dashboard predeterminado de Productor, Veterinario, Contador e Ingeniero de Campo con lo que pide
  RF-103 (el del Contador eran dos históricos de telemetría que su rol no puede leer).

RF-105 (estructura):
- ``nivel`` y ``estado`` del ciclo NUEVA → LEÍDA → ATENDIDA/DESCARTADA, acción documentada, fechas,
  animal (para agrupar), contexto del origen, ocurrencias e intentos del push.
- CHECK: una crítica no se descarta y no se atiende sin una acción de 20+ caracteres.
- Índice para el entregador de push y política RLS de DELETE para la purga del usuario de servicio.

Roles y recursos se resuelven por nombre (los ids no coinciden entre bases). ``modulo1.recursos``,
``permisos``, ``roles`` y ``notificaciones`` tienen FORCE RLS: se suspende durante la migración.

``downgrade()`` revierte la estructura y el catálogo, y deja el recurso y sus permisos: el permiso del
Administrador no se puede borrar (``trg_proteger_permisos_admin_delete``) y sin uso no afecta nada.
"""
import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'd2e201924d1b'
down_revision: Union[str, Sequence[str], None] = 'f0d5920d51b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLAS_FORCE = ('modulo1.recursos', 'modulo1.permisos', 'modulo1.roles', 'modulo1.notificaciones')
_RECURSO = 'indicadores_valor_inventario'

# (clave, nombre visible, grupo, span, recurso que lo habilita)
_WIDGETS_NUEVOS = (
    ('semaforo_areas', 'Estado de las áreas', 'Alertas', 2, 'monitoreo_telemetria'),
    ('inventario_especies', 'Animales por especie', 'Produccion', 2, 'activos_biologicos'),
    ('valor_inventario', 'Valor del inventario', 'Finanzas', 2, _RECURSO),
    ('ultimos_eventos', 'Últimos eventos', 'Produccion', 2, 'activos_biologicos'),
    ('conversion_alimenticia', 'Conversión alimenticia', 'Produccion', 1, 'eficiencia_alimenticia'),
    ('riesgo_sanitario_alto', 'Animales con riesgo alto', 'Sanidad', 2, 'retroalimentacion_clinica'),
    ('distribucion_riesgo', 'Riesgo de enfermedad por especie', 'Sanidad', 2, 'retroalimentacion_clinica'),
    ('retroalimentacion_pendiente', 'Diagnósticos por confirmar', 'Sanidad', 2, 'retroalimentacion_clinica'),
    ('alertas_sanitarias', 'Alertas sanitarias activas', 'Sanidad', 2, 'retroalimentacion_clinica'),
    ('periodos_abiertos', 'Períodos contables abiertos', 'Finanzas', 2, 'cierre_periodo'),
    ('reconocimientos_pendientes', 'Animales por reconocer', 'Finanzas', 2, 'reconocimiento_inicial'),
    ('integraciones_fallidas', 'Consultas contables con error', 'Finanzas', 2, 'exportacion_contable'),
    ('precios_por_vencer', 'Precios que vencen pronto', 'Finanzas', 2, 'precios_mercado'),
    ('dispositivos_sin_senal', 'Dispositivos sin comunicación', 'IoT', 2, 'infraestructura_iot'),
    ('lecturas_area', 'Lecturas en tiempo real', 'Ambiental', 2, 'monitoreo_telemetria'),
)

# clave → (nombre nuevo, nombre anterior)
_RENOMBRES = {
    'temp_galpon': ('Temperatura', 'Temperatura Galpon'),
    'hum_galpon': ('Humedad', 'Humedad Galpon'),
    'ph_estanque': ('pH del agua', 'pH Estanque'),
    'co2_galpon': ('CO₂ del ambiente', 'CO2 Ambiente'),
    'estado_iot': ('Estado de los dispositivos', 'Estado Dispositivos IoT'),
    'cal_sensores': ('Calibraciones recientes', 'Calibraciones Recientes'),
    'alertas': ('Alertas activas', 'Alertas Ambientales'),
    'alertas_crit': ('Alertas críticas', 'Alertas Criticas'),
    'hist_temp': ('Histórico de temperatura', 'Historico Temperatura'),
    'hist_hum': ('Histórico de humedad', 'Historico Humedad'),
    'fincas_estado': ('Estado de las fincas', 'Estado de Fincas'),
    'cfg_pendiente': ('Dispositivos sin configurar', 'Config. IoT Pendientes'),
}
_RETIRADOS = ('temp_corral', 'prod_aves', 'prod_bovinos')

# rol → celdas (clave, fila, columna, span, parámetros)
_LAYOUTS = {
    'Productor': (
        ('semaforo_areas', 1, 1, 2, {}), ('temp_galpon', 1, 3, 1, {}), ('hum_galpon', 1, 4, 1, {}),
        ('valor_inventario', 2, 1, 2, {}), ('conversion_alimenticia', 2, 3, 1, {}),
        ('inventario_especies', 3, 1, 2, {}), ('ultimos_eventos', 3, 3, 2, {}),
    ),
    'Veterinario': (
        ('riesgo_sanitario_alto', 1, 1, 2, {}), ('distribucion_riesgo', 1, 3, 2, {}),
        ('retroalimentacion_pendiente', 2, 1, 2, {}), ('alertas_sanitarias', 2, 3, 2, {}),
        ('semaforo_areas', 3, 1, 2, {}),
    ),
    'Contador': (
        ('periodos_abiertos', 1, 1, 2, {}), ('valor_inventario', 1, 3, 2, {'vista': 'POR_METODO'}),
        ('reconocimientos_pendientes', 2, 1, 2, {}), ('precios_por_vencer', 2, 3, 2, {}),
        ('integraciones_fallidas', 3, 1, 2, {}),
    ),
    'Ingeniero de Campo': (
        ('estado_iot', 1, 1, 2, {}), ('dispositivos_sin_senal', 1, 3, 2, {}),
        ('lecturas_area', 2, 1, 2, {}), ('cfg_pendiente', 2, 3, 2, {}),
        ('cal_sensores', 3, 1, 2, {}), ('hist_temp', 3, 3, 2, {}),
    ),
}

# Predeterminados anteriores (para downgrade), tal como estaban en el seed de RF-28.
_LAYOUTS_ANTERIORES = {
    'Productor': ((1, 1, 1, 1), (2, 1, 2, 1), (8, 1, 3, 1), (9, 1, 4, 1), (14, 2, 1, 2)),
    'Veterinario': ((1, 1, 1, 1), (3, 1, 2, 1), (9, 1, 3, 1), (12, 1, 4, 1), (10, 2, 1, 2)),
    'Ingeniero de Campo': ((6, 1, 1, 2), (7, 1, 3, 1), (15, 1, 4, 1), (10, 2, 1, 2), (11, 2, 3, 2)),
    'Contador': ((10, 1, 1, 2), (11, 1, 3, 2)),
}


def _rls(force: bool) -> None:
    for tabla in _TABLAS_FORCE:
        op.execute(sa.text(f"ALTER TABLE {tabla} {'FORCE' if force else 'NO FORCE'} ROW LEVEL SECURITY"))


def _actor() -> None:
    # Los triggers de M01 (auditoría DML, protección de permisos) piden un actor en la sesión.
    op.execute(sa.text("SELECT set_config('app.current_role', 'Administrador', true), "
                       "set_config('app.current_user_id', '1', true)"))


def _id_widget(clave: str) -> str:
    return f"(SELECT id_widget FROM modulo9.widgets WHERE clave = '{clave}')"


def _config_layout(celdas) -> str:
    """JSON del layout armado en SQL: los ids de widget se buscan por clave en esta base."""
    grid = ", ".join(
        "jsonb_build_object('id_widget', {id}, 'posicion_fila', {f}, 'posicion_columna', {c}, "
        "'span_columnas', {s}, 'visible', true, 'orden', {o}{p})".format(
            id=_id_widget(clave), f=fila, c=col, s=span, o=orden,
            p=f", 'parametros', '{json.dumps(params)}'::jsonb" if params else "")
        for orden, (clave, fila, col, span, params) in enumerate(celdas)
    )
    return f"jsonb_build_object('grid', jsonb_build_array({grid}), 'frecuencia_actualizacion', 30)"


def _sembrar_recurso() -> None:
    op.execute(sa.text(f"""
        INSERT INTO modulo1.recursos (id_recurso, nombre_recurso, descripcion)
        SELECT (SELECT max(id_recurso) + 1 FROM modulo1.recursos), '{_RECURSO}',
               'Valor del inventario biológico en el dashboard (RF-103), sin acceso a la valoración de Finanzas'
        WHERE NOT EXISTS (SELECT 1 FROM modulo1.recursos WHERE nombre_recurso = '{_RECURSO}')
    """))
    for prefijo, rol in (('admin', 'Administrador'), ('prod', 'Productor'), ('cont', 'Contador')):
        op.execute(sa.text(f"""
            INSERT INTO modulo1.permisos (nombre, descripcion, es_activo, id_recurso, id_accion, id_rol)
            SELECT '{prefijo}_leer_indicador_valor_inventario',
                   '{rol} ve el valor del inventario biológico en su dashboard (RF-103).', TRUE,
                   rec.id_recurso, a.id_accion, r.id_rol
            FROM modulo1.roles r, modulo1.recursos rec, modulo1.acciones a
            WHERE r.nombre_rol = '{rol}' AND rec.nombre_recurso = '{_RECURSO}' AND a.codigo = 'R'
            ON CONFLICT (id_rol, id_recurso, id_accion) DO UPDATE SET es_activo = TRUE, fecha_actualizacion = now()
        """))


def _sembrar_widgets() -> None:
    for clave, nombre, grupo, span, recurso in _WIDGETS_NUEVOS:
        params = {'clave': clave, 'nombre': nombre, 'grupo': grupo, 'span': span, 'recurso': recurso}
        op.execute(sa.text("""
            UPDATE modulo9.widgets w
               SET nombre = :nombre, grupo = :grupo, span_predeterminado = :span, es_activo = TRUE,
                   id_recurso = (SELECT id_recurso FROM modulo1.recursos WHERE nombre_recurso = :recurso)
             WHERE w.clave = :clave
        """).bindparams(**params))
        op.execute(sa.text("""
            INSERT INTO modulo9.widgets (id_widget, clave, nombre, grupo, span_predeterminado, id_recurso, es_activo)
            SELECT COALESCE((SELECT max(id_widget) FROM modulo9.widgets), 0) + 1, :clave, :nombre, :grupo, :span,
                   (SELECT id_recurso FROM modulo1.recursos WHERE nombre_recurso = :recurso), TRUE
            WHERE NOT EXISTS (SELECT 1 FROM modulo9.widgets WHERE clave = :clave)
        """).bindparams(**params))
    for clave, (nombre, _anterior) in _RENOMBRES.items():
        op.execute(sa.text("UPDATE modulo9.widgets SET nombre = :n WHERE clave = :c").bindparams(n=nombre, c=clave))
    op.execute(sa.text("UPDATE modulo9.widgets SET es_activo = FALSE WHERE clave IN :claves")
               .bindparams(sa.bindparam('claves', value=_RETIRADOS, expanding=True)))


def _layouts_por_rol(layouts, a_config) -> None:
    for rol, celdas in layouts.items():
        op.execute(sa.text(f"""
            UPDATE modulo9.dashboard_layouts_default d
               SET config = {a_config(celdas)},
                   active_widget = :activos
              FROM modulo1.roles r
             WHERE r.id_rol = d.id_rol AND r.nombre_rol = :rol
        """).bindparams(rol=rol, activos=[c[0] for c in celdas]))


def _ddl_notificaciones() -> None:
    op.execute("CREATE TYPE modulo1.enum_notificacion_nivel AS ENUM ('CRITICA', 'ADVERTENCIA', 'INFORMATIVA')")
    op.execute("CREATE TYPE modulo1.enum_notificacion_estado AS ENUM ('NUEVA', 'LEIDA', 'ATENDIDA', 'DESCARTADA')")
    op.execute("""
        ALTER TABLE modulo1.notificaciones
          ADD COLUMN nivel modulo1.enum_notificacion_nivel NOT NULL DEFAULT 'INFORMATIVA',
          ADD COLUMN estado modulo1.enum_notificacion_estado NOT NULL DEFAULT 'NUEVA',
          ADD COLUMN accion_documentada text,
          ADD COLUMN fecha_lectura timestamptz,
          ADD COLUMN fecha_atencion timestamptz,
          ADD COLUMN fecha_descarte timestamptz,
          ADD COLUMN id_activo_biologico integer
              CONSTRAINT notificaciones_id_activo_biologico_fkey
              REFERENCES modulo2.activos_biologicos (id_activo_biologico) ON DELETE SET NULL ON UPDATE CASCADE,
          ADD COLUMN json_contexto jsonb,
          ADD COLUMN ocurrencias integer NOT NULL DEFAULT 1,
          ADD COLUMN fecha_ultima_ocurrencia timestamptz,
          ADD COLUMN intentos_push smallint NOT NULL DEFAULT 0,
          ADD COLUMN fecha_proximo_intento timestamptz
    """)
    op.execute("UPDATE modulo1.notificaciones SET estado = 'LEIDA' WHERE es_leido")
    op.execute("""
        ALTER TABLE modulo1.notificaciones
          ADD CONSTRAINT ck_notificacion_critica_no_descartada
              CHECK (NOT (nivel = 'CRITICA' AND estado = 'DESCARTADA')),
          ADD CONSTRAINT ck_notificacion_critica_atendida_con_accion
              CHECK (NOT (nivel = 'CRITICA' AND estado = 'ATENDIDA')
                     OR char_length(btrim(COALESCE(accion_documentada, ''))) >= 20),
          ADD CONSTRAINT ck_notificacion_atendida_con_fecha
              CHECK (estado <> 'ATENDIDA' OR fecha_atencion IS NOT NULL),
          ADD CONSTRAINT ck_notificacion_ocurrencias CHECK (ocurrencias >= 1)
    """)
    op.execute("""
        CREATE INDEX idx_notificacion_entrega_pendiente ON modulo1.notificaciones (fecha_proximo_intento)
        WHERE id_notificacion_canal = 2 AND nivel <> 'INFORMATIVA' AND estado_envio IN ('en_cola', 'fallido')
    """)
    op.execute("""
        CREATE POLICY pol_notificaciones_delete ON modulo1.notificaciones FOR DELETE
        USING ((SELECT modulo1.fn_es_usuario_servicio()))
    """)
    op.execute("COMMENT ON COLUMN modulo1.notificaciones.estado IS "
               "'Ciclo de vida RF-105: NUEVA, LEIDA, ATENDIDA (con accion_documentada en las críticas) o DESCARTADA.'")
    op.execute("COMMENT ON COLUMN modulo1.notificaciones.json_contexto IS "
               "'Origen de la notificación: url de destino en el front, finca, área, alerta.'")


def upgrade() -> None:
    _rls(False)
    try:
        _actor()
        _sembrar_recurso()
        _sembrar_widgets()
        _layouts_por_rol(_LAYOUTS, _config_layout)
        _ddl_notificaciones()
    finally:
        _rls(True)


def _config_anterior(celdas) -> str:
    grid = ", ".join(
        f"jsonb_build_object('id_widget', {w}, 'posicion_fila', {f}, 'posicion_columna', {c}, "
        f"'span_columnas', {s}, 'visible', true, 'orden', {o})"
        for o, (w, f, c, s) in enumerate(celdas)
    )
    return f"jsonb_build_object('grid', jsonb_build_array({grid}))"


def downgrade() -> None:
    _rls(False)
    try:
        _actor()
        op.execute("DROP POLICY IF EXISTS pol_notificaciones_delete ON modulo1.notificaciones")
        op.execute("DROP INDEX IF EXISTS modulo1.idx_notificacion_entrega_pendiente")
        op.execute("""
            ALTER TABLE modulo1.notificaciones
              DROP CONSTRAINT IF EXISTS ck_notificacion_critica_no_descartada,
              DROP CONSTRAINT IF EXISTS ck_notificacion_critica_atendida_con_accion,
              DROP CONSTRAINT IF EXISTS ck_notificacion_atendida_con_fecha,
              DROP CONSTRAINT IF EXISTS ck_notificacion_ocurrencias,
              DROP COLUMN IF EXISTS nivel, DROP COLUMN IF EXISTS estado,
              DROP COLUMN IF EXISTS accion_documentada, DROP COLUMN IF EXISTS fecha_lectura,
              DROP COLUMN IF EXISTS fecha_atencion, DROP COLUMN IF EXISTS fecha_descarte,
              DROP COLUMN IF EXISTS id_activo_biologico, DROP COLUMN IF EXISTS json_contexto,
              DROP COLUMN IF EXISTS ocurrencias, DROP COLUMN IF EXISTS fecha_ultima_ocurrencia,
              DROP COLUMN IF EXISTS intentos_push, DROP COLUMN IF EXISTS fecha_proximo_intento
        """)
        op.execute("DROP TYPE IF EXISTS modulo1.enum_notificacion_estado")
        op.execute("DROP TYPE IF EXISTS modulo1.enum_notificacion_nivel")

        for rol, celdas in _LAYOUTS_ANTERIORES.items():
            op.execute(sa.text(f"""
                UPDATE modulo9.dashboard_layouts_default d
                   SET config = {_config_anterior(celdas)},
                       active_widget = ARRAY(SELECT clave FROM modulo9.widgets WHERE id_widget = ANY(:ids))
                  FROM modulo1.roles r
                 WHERE r.id_rol = d.id_rol AND r.nombre_rol = :rol
            """).bindparams(rol=rol, ids=[c[0] for c in celdas]))
        op.execute(sa.text("UPDATE modulo9.widgets SET es_activo = TRUE WHERE clave IN :claves")
                   .bindparams(sa.bindparam('claves', value=_RETIRADOS, expanding=True)))
        for clave, (_nombre, anterior) in _RENOMBRES.items():
            op.execute(sa.text("UPDATE modulo9.widgets SET nombre = :n WHERE clave = :c").bindparams(n=anterior, c=clave))
        op.execute(sa.text("DELETE FROM modulo9.widgets WHERE clave IN :claves")
                   .bindparams(sa.bindparam('claves', value=tuple(w[0] for w in _WIDGETS_NUEVOS), expanding=True)))
    finally:
        _rls(True)
