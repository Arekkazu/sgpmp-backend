"""rf28 catalogo de widgets, layouts base por rol y unicidad de layout

Revision ID: a7f3c92e4d18
Revises: c4a19e7d2b63
Create Date: 2026-09-02 10:00:00.000000

RF-28 — personalizacion del dashboard. El RF describe cuatro reglas que la BD
no podia sostener:

1. "widget no disponible para su rol" (403) y "tipo de widget inexistente":
   ``dashboard_layouts.config`` guarda ``id_widget`` como un entero libre, sin
   catalogo contra el cual validarlo ni forma de saber que modulo gobierna cada
   widget. Se crea ``modulo9.widgets``, donde cada widget declara el
   ``id_recurso`` cuyo permiso R lo habilita. La autorizacion sigue siendo
   dinamica y leida de ``modulo1.permisos``: cambiar una fila cambia que ve
   cada rol, sin tocar codigo.

2. "Restaurar configuracion predeterminada": el layout base por rol vivia en un
   diccionario vacio quemado en la entidad de dominio (``_DEFAULT_GRID_POR_ROL``
   con llaves 1-5), asi que restaurar era un no-op silencioso y los roles 6-9 ni
   siquiera existian ahi. Se crea ``modulo9.dashboard_layouts_default``, una fila
   por rol. Cada default solo contiene widgets cuyo recurso ese rol lee de
   verdad, verificado contra ``modulo1.permisos`` al escribir este seed; los
   roles 6-9 no tienen R sobre ningun recurso de widget, asi que su grid base es
   vacio a proposito.

3. Un layout por usuario: ``dashboard_layouts`` no tenia ``UNIQUE(id_usuario)``,
   asi que dos PATCH concurrentes de un usuario sin fila previa insertaban dos
   filas y el repositorio desempataba por ``fecha_actualizacion DESC``. El dedup
   previo conserva la fila mas reciente por usuario; hoy es un no-op (0
   duplicados en dev), va por seguridad ante cualquier otro entorno.

4. La FK ``dashboard_layouts.id_usuario`` estaba ``NOT VALID``: nunca se
   comprobo contra las filas existentes. Se valida.

Los ids, claves y spans del catalogo son exactamente los que el frontend tenia
quemados en ``DashboardLayoutSection.tsx``, para que los layouts ya guardados
sigan resolviendo. ``fuente_datos`` apunta a las vistas ``vw_rf28_widget_*`` que
ya existian en el esquema y que ningun codigo consumia; un widget con
``fuente_datos`` NULL responde "Sin datos disponibles", que es el fallback que
el propio RF prescribe.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "a7f3c92e4d18"
down_revision: Union[str, Sequence[str], None] = "c4a19e7d2b63"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# id, clave, nombre, grupo, span, id_recurso, fuente_datos
_WIDGETS = [
    (1, "temp_galpon", "Temperatura Galpon", "Ambiental", 1, 33, None),
    (2, "hum_galpon", "Humedad Galpon", "Ambiental", 1, 33, None),
    (3, "ph_estanque", "pH Estanque", "Ambiental", 1, 33, None),
    (4, "co2_galpon", "CO2 Ambiente", "Ambiental", 1, 33, None),
    (5, "temp_corral", "Temperatura Corral", "Ambiental", 1, 33, None),
    (6, "estado_iot", "Estado Dispositivos IoT", "IoT", 2, 35, "vw_rf28_widget_estado_dispositivos"),
    (7, "cal_sensores", "Calibraciones Recientes", "IoT", 1, 11, "vw_rf28_widget_estado_dispositivos"),
    (8, "alertas", "Alertas Ambientales", "Alertas", 1, 32, None),
    (9, "alertas_crit", "Alertas Criticas", "Alertas", 1, 32, None),
    (10, "hist_temp", "Historico Temperatura", "Historico", 2, 34, None),
    (11, "hist_hum", "Historico Humedad", "Historico", 2, 34, None),
    (12, "prod_aves", "Indicadores Avicultura", "Produccion", 1, 19, None),
    (13, "prod_bovinos", "Indicadores Bovinos", "Produccion", 1, 19, None),
    (14, "fincas_estado", "Estado de Fincas", "Infraestructura", 2, 9, "vw_rf28_widget_estado_fincas"),
    (15, "cfg_pendiente", "Config. IoT Pendientes", "Infraestructura", 1, 11, "vw_rf28_widget_dispositivos_sin_configuracion"),
]


def _celda(id_widget: int, fila: int, columna: int, span: int, orden: int) -> dict:
    return {
        "id_widget": id_widget,
        "posicion_fila": fila,
        "posicion_columna": columna,
        "span_columnas": span,
        "visible": True,
        "orden": orden,
    }


# Un default solo puede contener widgets cuyo recurso el rol lee. Matriz real de
# modulo1.permisos (id_accion=2, es_activo) al momento de escribir esta revision:
#   recurso  9 fincas               -> roles 1,2,3,4
#   recurso 11 dispositivos_iot     -> roles 1,2,4
#   recurso 19 metricas_produccion  -> roles 1,3
#   recurso 32 alertas_operativas   -> roles 1,2,3,4
#   recurso 33 monitoreo_telemetria -> roles 1,2,3,4
#   recurso 34 historial_telemetria -> roles 1,2,3,4,5
#   recurso 35 infraestructura_iot  -> roles 1,2,3,4
# Los roles 6-9 (Supervisor, Gestor de Granja, Revisor Fiscal, Externo
# AgroFusion) no tienen R sobre ninguno de esos recursos: su default es vacio.
_DEFAULTS = {
    # Administrador: infraestructura y estado del sistema.
    1: [
        _celda(6, 1, 1, 2, 0),
        _celda(9, 1, 3, 1, 1),
        _celda(15, 1, 4, 1, 2),
        _celda(14, 2, 1, 2, 3),
        _celda(7, 2, 3, 1, 4),
    ],
    # Productor: ambiente general y alertas (no lee metricas_produccion).
    2: [
        _celda(1, 1, 1, 1, 0),
        _celda(2, 1, 2, 1, 1),
        _celda(8, 1, 3, 1, 2),
        _celda(9, 1, 4, 1, 3),
        _celda(14, 2, 1, 2, 4),
    ],
    # Veterinario: ambiente, alertas criticas y produccion (no lee dispositivos_iot).
    3: [
        _celda(1, 1, 1, 1, 0),
        _celda(3, 1, 2, 1, 1),
        _celda(9, 1, 3, 1, 2),
        _celda(12, 1, 4, 1, 3),
        _celda(10, 2, 1, 2, 4),
    ],
    # Ingeniero de Campo: dispositivos e historicos (no lee metricas_produccion).
    4: [
        _celda(6, 1, 1, 2, 0),
        _celda(7, 1, 3, 1, 1),
        _celda(15, 1, 4, 1, 2),
        _celda(10, 2, 1, 2, 3),
        _celda(11, 2, 3, 2, 4),
    ],
    # Contador: solo lee historial_telemetria.
    5: [
        _celda(10, 1, 1, 2, 0),
        _celda(11, 1, 3, 2, 1),
    ],
    6: [],
    7: [],
    8: [],
    9: [],
}

_CLAVE_POR_ID = {w[0]: w[1] for w in _WIDGETS}


def upgrade() -> None:
    op.create_table(
        "widgets",
        sa.Column("id_widget", sa.Integer, primary_key=True, autoincrement=False),
        sa.Column("clave", sa.String(40), nullable=False, unique=True),
        sa.Column("nombre", sa.String(80), nullable=False),
        sa.Column("grupo", sa.String(40), nullable=False),
        sa.Column("span_predeterminado", sa.SmallInteger, nullable=False),
        sa.Column("id_recurso", sa.Integer, nullable=False),
        sa.Column("fuente_datos", sa.String(60), nullable=True),
        sa.Column("es_activo", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.CheckConstraint(
            "span_predeterminado IN (1, 2)",
            name="widgets_span_predeterminado_check",
        ),
        sa.ForeignKeyConstraint(
            ["id_recurso"],
            ["modulo1.recursos.id_recurso"],
            name="fk_widgets_recurso",
        ),
        schema="modulo9",
    )

    op.bulk_insert(
        sa.table(
            "widgets",
            sa.column("id_widget", sa.Integer),
            sa.column("clave", sa.String),
            sa.column("nombre", sa.String),
            sa.column("grupo", sa.String),
            sa.column("span_predeterminado", sa.SmallInteger),
            sa.column("id_recurso", sa.Integer),
            sa.column("fuente_datos", sa.String),
            schema="modulo9",
        ),
        [
            {
                "id_widget": w[0],
                "clave": w[1],
                "nombre": w[2],
                "grupo": w[3],
                "span_predeterminado": w[4],
                "id_recurso": w[5],
                "fuente_datos": w[6],
            }
            for w in _WIDGETS
        ],
    )

    op.create_table(
        "dashboard_layouts_default",
        sa.Column("id_rol", sa.Integer, primary_key=True, autoincrement=False),
        sa.Column("config", postgresql.JSONB, nullable=False),
        sa.Column(
            "active_widget",
            postgresql.ARRAY(sa.String),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["id_rol"],
            ["modulo1.roles.id_rol"],
            name="fk_dashboard_layouts_default_rol",
            ondelete="CASCADE",
        ),
        schema="modulo9",
    )

    op.bulk_insert(
        sa.table(
            "dashboard_layouts_default",
            sa.column("id_rol", sa.Integer),
            sa.column("config", postgresql.JSONB),
            sa.column("active_widget", postgresql.ARRAY(sa.String)),
            schema="modulo9",
        ),
        [
            {
                "id_rol": id_rol,
                "config": {"grid": grid},
                "active_widget": [_CLAVE_POR_ID[c["id_widget"]] for c in grid],
            }
            for id_rol, grid in sorted(_DEFAULTS.items())
        ],
    )

    # Dedup defensivo antes del UNIQUE: conserva la fila mas reciente por usuario,
    # el mismo criterio de desempate que usaba el repositorio.
    op.execute(
        """
        DELETE FROM modulo9.dashboard_layouts a
        USING modulo9.dashboard_layouts b
        WHERE a.id_usuario = b.id_usuario
          AND (
                a.fecha_actualizacion IS NULL AND b.fecha_actualizacion IS NOT NULL
             OR a.fecha_actualizacion < b.fecha_actualizacion
             OR (a.fecha_actualizacion IS NOT DISTINCT FROM b.fecha_actualizacion
                 AND a.id_dashboard_layout < b.id_dashboard_layout)
          )
        """
    )
    op.create_unique_constraint(
        "uq_dashboard_layouts_usuario",
        "dashboard_layouts",
        ["id_usuario"],
        schema="modulo9",
    )
    op.execute(
        "ALTER TABLE modulo9.dashboard_layouts "
        "VALIDATE CONSTRAINT dashboard_layouts_id_usuario_fkey"
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_dashboard_layouts_usuario",
        "dashboard_layouts",
        schema="modulo9",
        type_="unique",
    )
    op.drop_table("dashboard_layouts_default", schema="modulo9")
    op.drop_table("widgets", schema="modulo9")
    # La FK vuelve a quedar NOT VALID: es el estado exacto previo a esta revision.
    op.drop_constraint(
        "dashboard_layouts_id_usuario_fkey",
        "dashboard_layouts",
        schema="modulo9",
        type_="foreignkey",
    )
    op.execute(
        "ALTER TABLE modulo9.dashboard_layouts "
        "ADD CONSTRAINT dashboard_layouts_id_usuario_fkey "
        "FOREIGN KEY (id_usuario) REFERENCES modulo1.usuarios(id_usuario) NOT VALID"
    )
