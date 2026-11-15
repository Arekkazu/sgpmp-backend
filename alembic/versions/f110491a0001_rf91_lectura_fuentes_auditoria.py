# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-11-13 | Leandro | TC-M06-G52 RF-91: habilitar las lecturas acotadas de las fuentes bajo RLS. |
"""RF-91: permisos de lectura de las columnas usadas en la verificación."""

from alembic import op

revision = "f110491a0001"
down_revision = "0884ba08a944"
branch_labels = None
depends_on = None

_COLUMNAS = {
    "modulo2.bitacora_auditoria_m02": "id_evento, id_bitacora, id_activo_biologico, resultado, "
    "registro_incompleto, detalle_tecnico, timestamp_registro",
    "modulo2.asociaciones_activos_sensores": "id_activo_biologico, id_sensor, dispositivo_iot_id, fecha_inicio, fecha_fin",
    "modulo3.telemetrias": "id_telemetria, id_sensor, id_dispositivo_iot, timestamp_captura",
    "modulo3.telemetria_calidad": "id_telemetria, id_sensor, estado_evaluacion, apto_para_nic41",
    "modulo3.vinculaciones_lecturas": "id_telemetria, id_activo_biologico, fecha_fin_vinculacion, estado_vinculacion",
    "modulo3.bitacora_auditoria_iot": "id_evento, entidad_afectada_id, entidad_afectada_tipo, "
    "tipo_evento, resultado, registro_incompleto, fecha_hora",
    "modulo4.eventos_auditoria_m04": "id_evento, tipo_evento, resultado_operacion, entidad_referencia, "
    "es_payload_truncado, hash_evento, payload_evento, fecha_evento",
    "modulo6.variaciones_valor_razonable": "id_variacion_valor_razonable, id_periodo_contable, id_evento, "
    "id_precio_mercado, id_cierre",
}


def upgrade() -> None:
    op.execute("GRANT USAGE ON SCHEMA modulo2, modulo3, modulo4 TO sgpmp_app")
    for tabla, columnas in _COLUMNAS.items():
        op.execute(f"GRANT SELECT ({columnas}) ON {tabla} TO sgpmp_app")
    # La línea base instala las políticas de RF-91 pero no todos los privilegios
    # sobre la cadena que necesitan los endpoints que las usan.
    op.execute("GRANT SELECT, INSERT ON modulo6.cadenas_trazabilidad_contable TO sgpmp_app")
    op.execute("GRANT USAGE ON SEQUENCE modulo6.cadenas_trazabilidad_contable_id_asiento_seq TO sgpmp_app")


def downgrade() -> None:
    # Igual que RF-82, preservar los privilegios que el entorno podía tener antes de esta revisión.
    pass
