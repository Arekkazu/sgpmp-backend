# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-02 | Arekkazu | AJF-04/AJF-07 RF-53/RF-60: RLS e índice para leer ingesta y parámetros de heartbeat con el permiso de operación IoT |
"""ajf04/ajf07: lectura de ingesta y de parámetros de heartbeat para quien opera los equipos

Revision ID: bb5526687aae
Revises: 21fe51f2aea1
Create Date: 2026-11-02

Requiere la autorización de SamuelPR21 (DBA) antes de desplegar.

Gaps encontrados al exponer los datos reales de Flujo IoT y Dispositivos (detalle en
``anotaciones/ajustes_m02_m03_m04_gaps_bd.md``):

1. AJF-07 · ``modulo3.bitacora_ingest``: la RLS solo deja leer con ``bitacora_auditoria_iot`` R
   (recurso 39), pero la pestaña Ingesta y ``GET /iot/ingesta`` usan el permiso de operación de
   equipos, ``alertas_tecnicas_iot`` R (recurso 36). Un Ingeniero con 36 y sin 39 recibía la
   lista vacía sin error. La política de lectura acepta cualquiera de los dos; el alcance por
   dispositivos del usuario no cambia.
2. AJF-07 · índice ``idx_bitacora_ingest_fecha_evento``: el monitor consulta por rango de fechas
   sin dispositivo ni tipo de evento, y los dos índices existentes empiezan por esas columnas.
3. AJF-04 · ``modulo4.parametros_mlops``: solo se leía con ``version_modelo`` R (recurso 43). El
   Ingeniero ve los parámetros de heartbeat y de ventanas de visión (con 36 R) y no los modelos:
   le salían todos "Sin configurar". Política nueva de lectura limitada a esas siete claves.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'bb5526687aae'
down_revision: Union[str, Sequence[str], None] = '21fe51f2aea1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_UID = "(SELECT modulo1.fn_id_usuario_actual())"
_DISP_SUBQ = f"SELECT d.id_dispositivo_iot FROM modulo9.fn_dispositivos_del_usuario({_UID}) d"
# Las de configuration/domain/entities/parametros_heartbeat.py que muestra la pantalla de dispositivos.
_PARAMETROS_IOT = (
    "'intervalo_heartbeat_camara', 'intervalos_heartbeat_por_tipo', 'margen_tolerancia', "
    "'tiempo_inactividad_extendida', 'ventanas_consecutivas_sin_deteccion', "
    "'cobertura_minima_deteccion_valida', 'duracion_ventana_observacion'"
)


def upgrade() -> None:
    op.execute(f"""
        DROP POLICY pol_bitacora_ingest_select ON modulo3.bitacora_ingest;
        CREATE POLICY pol_bitacora_ingest_select ON modulo3.bitacora_ingest
          FOR SELECT USING (
            ((SELECT modulo1.fn_tiene_permiso('bitacora_auditoria_iot', 'R'))
              OR (SELECT modulo1.fn_tiene_permiso('alertas_tecnicas_iot', 'R')))
            AND id_dispositivo_iot IN ({_DISP_SUBQ}));

        CREATE INDEX IF NOT EXISTS idx_bitacora_ingest_fecha_evento
            ON modulo3.bitacora_ingest (fecha_evento DESC);

        CREATE POLICY pol_parametro_mlops_select_operacion_iot ON modulo4.parametros_mlops
          FOR SELECT USING (
            (SELECT modulo1.fn_tiene_permiso('alertas_tecnicas_iot', 'R'))
            AND nombre_parametro IN ({_PARAMETROS_IOT}));
    """)


def downgrade() -> None:
    op.execute(f"""
        DROP POLICY pol_parametro_mlops_select_operacion_iot ON modulo4.parametros_mlops;
        DROP INDEX IF EXISTS modulo3.idx_bitacora_ingest_fecha_evento;
        DROP POLICY pol_bitacora_ingest_select ON modulo3.bitacora_ingest;
        CREATE POLICY pol_bitacora_ingest_select ON modulo3.bitacora_ingest
          FOR SELECT USING (
            (SELECT modulo1.fn_tiene_permiso('bitacora_auditoria_iot', 'R'))
            AND id_dispositivo_iot IN ({_DISP_SUBQ}));
    """)
