"""rls_modulo_03

Revision ID: 0784d8c03206
Revises: ebbb160365e5
Create Date: 2026-10-27 10:10:59.058781

Clasifica la totalidad de las 18 tablas de modulo3 en patrones de acceso:

  1. FINCA DIRECTA + GLOBAL: reglas_alertas (id_finca nullable)
  2. VIA INFRAESTRUCTURA:    alertas, observaciones_vision, vinculaciones_lecturas
  3. VIA DISPOSITIVO:        eventos_edge, estados_dispositivos, heartbeats,
                             historico_transiciones, paquetes_inferencia,
                             periodos_inactividad, bitacora_ingest,
                             transmisiones_mqtt, sincronizaciones_reglas_edge
  4. VIA SENSOR:             telemetrias, estados_actuales_sensores
  5. EXISTS SOBRE PADRE:     historico_estados_alertas, telemetria_calidad
  6. SIN FINCA (AUDITORIA):  bitacora_auditoria_iot (RF-63)

Recursos RBAC utilizados (modulo1.recursos):
  - alertas_operativas (32): alertas y reglas
  - monitoreo_telemetria (33): dashboard tiempo real
  - historial_telemetria (34): historial y exportacion
  - infraestructura_iot (35): estados de dispositivos
  - alertas_tecnicas_iot (36): alertas tecnicas
  - vinculaciones_lecturas (37): vinculacion telemetria-activo
  - calidad_telemetria (38): evaluacion de calidad
  - bitacora_auditoria_iot (39): bitacora RF-63
  - sincronizacion_reglas_edge (65): propagacion Edge
  - datos_tecnicos_dashboard (85): datos tecnicos

Reutiliza funciones de modulo9 (F5):
  - fn_infraestructuras_del_usuario()
  - fn_dispositivos_del_usuario()
  - fn_sensores_del_usuario()

Contrato con la app:
  - Identidad: modulo1.fn_id_usuario_actual() lee app.current_user_id
  - Servicio: modulo1.fn_es_usuario_servicio() identifica servicio.sistema@sgpmp.local
  - Todas las funciones van dentro de (SELECT ...) para evaluarse por sentencia

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0784d8c03206'
down_revision: Union[str, Sequence[str], None] = 'ebbb160365e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None



UID = "(SELECT modulo1.fn_id_usuario_actual())"
SERVICIO = "(SELECT modulo1.fn_es_usuario_servicio())"


def permiso(recurso: str, accion: str) -> str:
    """Nombres reales de modulo1.recursos."""
    return f"(SELECT modulo1.fn_tiene_permiso('{recurso}', '{accion}'))"


# ── Subconsultas reutilizables ────────────────────────────────────────
_INFRA_SUBQ = (
    "SELECT i.id_infraestructura"
    f" FROM modulo9.fn_infraestructuras_del_usuario({UID}) i"
)
_DISP_SUBQ = (
    "SELECT d.id_dispositivo_iot"
    f" FROM modulo9.fn_dispositivos_del_usuario({UID}) d"
)
_SENSOR_SUBQ = (
    "SELECT s.id_sensores"
    f" FROM modulo9.fn_sensores_del_usuario({UID}) s"
)
_FINCA_SUBQ = (
    "SELECT f.id_finca"
    f" FROM modulo9.fn_fincas_del_usuario({UID}) f"
)


def _enable_force(tabla: str) -> None:
    op.execute(f"ALTER TABLE modulo3.{tabla} ENABLE ROW LEVEL SECURITY;")
    op.execute(f"ALTER TABLE modulo3.{tabla} FORCE ROW LEVEL SECURITY;")


def upgrade() -> None:

    # ================================================================
    # 1. REGLAS_ALERTAS: finca directa + global (id_finca nullable)
    #    NULL = regla global del sistema, visible para todos
    # ================================================================
    op.execute(f"""
        CREATE POLICY pol_reglas_alertas_select ON modulo3.reglas_alertas
          FOR SELECT USING (
            id_finca IS NULL
            OR id_finca IN ({_FINCA_SUBQ}));
    """)
    op.execute(f"""
        CREATE POLICY pol_reglas_alertas_insert ON modulo3.reglas_alertas
          FOR INSERT WITH CHECK (
            {permiso('alertas_operativas', 'U')}
            AND (id_finca IS NULL OR id_finca IN ({_FINCA_SUBQ})));
    """)
    op.execute(f"""
        CREATE POLICY pol_reglas_alertas_update ON modulo3.reglas_alertas
          FOR UPDATE USING (
            {permiso('alertas_operativas', 'U')}
            AND (id_finca IS NULL OR id_finca IN ({_FINCA_SUBQ})))
          WITH CHECK (
            {permiso('alertas_operativas', 'U')}
            AND (id_finca IS NULL OR id_finca IN ({_FINCA_SUBQ})));
    """)
    op.execute(f"""
        CREATE POLICY pol_reglas_alertas_servicio ON modulo3.reglas_alertas
          FOR ALL USING ({SERVICIO}) WITH CHECK ({SERVICIO});
    """)
    _enable_force('reglas_alertas')

    # ================================================================
    # 2. ALERTAS: via infraestructura (2 saltos)
    #    RF-57: ciclo de vida de alertas operativas
    # ================================================================
    op.execute(f"""
        CREATE POLICY pol_alertas_select ON modulo3.alertas
          FOR SELECT USING (
            id_infraestructura IN ({_INFRA_SUBQ})
            OR {permiso('alertas_tecnicas_iot', 'R')});
    """)
    op.execute(f"""
        CREATE POLICY pol_alertas_insert ON modulo3.alertas
          FOR INSERT WITH CHECK (
            id_infraestructura IN ({_INFRA_SUBQ}));
    """)
    # UPDATE: atender/resolver alertas (RF-57)
    op.execute(f"""
        CREATE POLICY pol_alertas_update ON modulo3.alertas
          FOR UPDATE USING (
            {permiso('alertas_operativas', 'U')}
            AND id_infraestructura IN ({_INFRA_SUBQ}))
          WITH CHECK (
            {permiso('alertas_operativas', 'U')}
            AND id_infraestructura IN ({_INFRA_SUBQ}));
    """)
    op.execute(f"""
        CREATE POLICY pol_alertas_servicio ON modulo3.alertas
          FOR ALL USING ({SERVICIO}) WITH CHECK ({SERVICIO});
    """)
    _enable_force('alertas')

    # ================================================================
    # 3. OBSERVACIONES_VISION: via infraestructura (2 saltos)
    #    RF-56/RF-62: vision Edge, calidad de observacion
    # ================================================================
    op.execute(f"""
        CREATE POLICY pol_observaciones_vision_select ON modulo3.observaciones_vision
          FOR SELECT USING (
            id_infraestructura IN ({_INFRA_SUBQ}));
    """)
    op.execute(f"""
        CREATE POLICY pol_observaciones_vision_insert ON modulo3.observaciones_vision
          FOR INSERT WITH CHECK (
            id_infraestructura IN ({_INFRA_SUBQ}));
    """)
    # UPDATE: solo campos de calidad (GRANT UPDATE ya existe en DDL)
    op.execute(f"""
        CREATE POLICY pol_observaciones_vision_update ON modulo3.observaciones_vision
          FOR UPDATE USING (
            id_infraestructura IN ({_INFRA_SUBQ}))
          WITH CHECK (
            id_infraestructura IN ({_INFRA_SUBQ}));
    """)
    op.execute(f"""
        CREATE POLICY pol_observaciones_vision_servicio ON modulo3.observaciones_vision
          FOR ALL USING ({SERVICIO}) WITH CHECK ({SERVICIO});
    """)
    _enable_force('observaciones_vision')

    # ================================================================
    # 4. VINCULACIONES_LECTURAS: via infraestructura (2 saltos)
    #    RF-61: vinculacion telemetria-activo para NIC41
    # ================================================================
    op.execute(f"""
        CREATE POLICY pol_vinculaciones_select ON modulo3.vinculaciones_lecturas
          FOR SELECT USING (
            id_infraestructura IN ({_INFRA_SUBQ}));
    """)
    op.execute(f"""
        CREATE POLICY pol_vinculaciones_insert ON modulo3.vinculaciones_lecturas
          FOR INSERT WITH CHECK (
            id_infraestructura IN ({_INFRA_SUBQ}));
    """)
    op.execute(f"""
        CREATE POLICY pol_vinculaciones_update ON modulo3.vinculaciones_lecturas
          FOR UPDATE USING (
            {permiso('vinculaciones_lecturas', 'U')}
            AND id_infraestructura IN ({_INFRA_SUBQ}))
          WITH CHECK (
            {permiso('vinculaciones_lecturas', 'U')}
            AND id_infraestructura IN ({_INFRA_SUBQ}));
    """)
    op.execute(f"""
        CREATE POLICY pol_vinculaciones_servicio ON modulo3.vinculaciones_lecturas
          FOR ALL USING ({SERVICIO}) WITH CHECK ({SERVICIO});
    """)
    _enable_force('vinculaciones_lecturas')

    # ================================================================
    # 5. TABLAS VIA DISPOSITIVO (3 saltos)
    #    Reutilizan modulo9.fn_dispositivos_del_usuario()
    # ================================================================

    # --- eventos_edge_computing (RF-55): append-only, sistema escribe
    op.execute(f"""
        CREATE POLICY pol_eventos_edge_select ON modulo3.eventos_edge_computing
          FOR SELECT USING (
            id_dispositivo_iot IN ({_DISP_SUBQ}));
    """)
    op.execute(f"""
        CREATE POLICY pol_eventos_edge_insert ON modulo3.eventos_edge_computing
          FOR INSERT WITH CHECK (
            id_dispositivo_iot IN ({_DISP_SUBQ}));
    """)
    op.execute(f"""
        CREATE POLICY pol_eventos_edge_servicio ON modulo3.eventos_edge_computing
          FOR ALL USING ({SERVICIO}) WITH CHECK ({SERVICIO});
    """)
    _enable_force('eventos_edge_computing')

    # --- estados_dispositivos_iot (RF-60): cache de estado, sistema actualiza
    op.execute(f"""
        CREATE POLICY pol_estados_disp_select ON modulo3.estados_dispositivos_iot
          FOR SELECT USING (
            id_dispositivo_iot IN ({_DISP_SUBQ}));
    """)
    op.execute(f"""
        CREATE POLICY pol_estados_disp_insert ON modulo3.estados_dispositivos_iot
          FOR INSERT WITH CHECK (
            id_dispositivo_iot IN ({_DISP_SUBQ}));
    """)
    op.execute(f"""
        CREATE POLICY pol_estados_disp_update ON modulo3.estados_dispositivos_iot
          FOR UPDATE USING (
            ({permiso('infraestructura_iot', 'U')} OR {SERVICIO})
            AND id_dispositivo_iot IN ({_DISP_SUBQ}))
          WITH CHECK (
            ({permiso('infraestructura_iot', 'U')} OR {SERVICIO})
            AND id_dispositivo_iot IN ({_DISP_SUBQ}));
    """)
    op.execute(f"""
        CREATE POLICY pol_estados_disp_servicio ON modulo3.estados_dispositivos_iot
          FOR ALL USING ({SERVICIO}) WITH CHECK ({SERVICIO});
    """)
    _enable_force('estados_dispositivos_iot')

    # --- heartbeats (RF-60): append-only, solo tecnico + sistema
    op.execute(f"""
        CREATE POLICY pol_heartbeats_select ON modulo3.heartbeats
          FOR SELECT USING (
            {permiso('infraestructura_iot', 'R')}
            AND id_dispositivo_iot IN ({_DISP_SUBQ}));
    """)
    op.execute(f"""
        CREATE POLICY pol_heartbeats_insert ON modulo3.heartbeats
          FOR INSERT WITH CHECK (
            id_dispositivo_iot IN ({_DISP_SUBQ}));
    """)
    op.execute(f"""
        CREATE POLICY pol_heartbeats_servicio ON modulo3.heartbeats
          FOR ALL USING ({SERVICIO}) WITH CHECK ({SERVICIO});
    """)
    _enable_force('heartbeats')

    # --- historico_transiciones_dispositivos (RF-60): append-only
    op.execute(f"""
        CREATE POLICY pol_hist_transiciones_select ON modulo3.historico_transiciones_dispositivos
          FOR SELECT USING (
            {permiso('infraestructura_iot', 'R')}
            AND id_dispositivo_iot IN ({_DISP_SUBQ}));
    """)
    op.execute(f"""
        CREATE POLICY pol_hist_transiciones_insert ON modulo3.historico_transiciones_dispositivos
          FOR INSERT WITH CHECK (
            id_dispositivo_iot IN ({_DISP_SUBQ}));
    """)
    op.execute(f"""
        CREATE POLICY pol_hist_transiciones_servicio ON modulo3.historico_transiciones_dispositivos
          FOR ALL USING ({SERVICIO}) WITH CHECK ({SERVICIO});
    """)
    _enable_force('historico_transiciones_dispositivos')

    # --- paquetes_inferencia (RF-56): alimentan M04
    op.execute(f"""
        CREATE POLICY pol_paquetes_inferencia_select ON modulo3.paquetes_inferencia
          FOR SELECT USING (
            id_dispositivo_iot IN ({_DISP_SUBQ}));
    """)
    op.execute(f"""
        CREATE POLICY pol_paquetes_inferencia_insert ON modulo3.paquetes_inferencia
          FOR INSERT WITH CHECK (
            id_dispositivo_iot IN ({_DISP_SUBQ}));
    """)
    op.execute(f"""
        CREATE POLICY pol_paquetes_inferencia_update ON modulo3.paquetes_inferencia
          FOR UPDATE USING (
            id_dispositivo_iot IN ({_DISP_SUBQ}))
          WITH CHECK (
            id_dispositivo_iot IN ({_DISP_SUBQ}));
    """)
    op.execute(f"""
        CREATE POLICY pol_paquetes_inferencia_servicio ON modulo3.paquetes_inferencia
          FOR ALL USING ({SERVICIO}) WITH CHECK ({SERVICIO});
    """)
    _enable_force('paquetes_inferencia')

    # --- periodos_inactividad (RF-60/RF-59): solo tecnico
    op.execute(f"""
        CREATE POLICY pol_periodos_inactividad_select ON modulo3.periodos_inactividad
          FOR SELECT USING (
            {permiso('alertas_tecnicas_iot', 'R')}
            AND id_dispositivo_iot IN ({_DISP_SUBQ}));
    """)
    op.execute(f"""
        CREATE POLICY pol_periodos_inactividad_insert ON modulo3.periodos_inactividad
          FOR INSERT WITH CHECK (
            id_dispositivo_iot IN ({_DISP_SUBQ}));
    """)
    op.execute(f"""
        CREATE POLICY pol_periodos_inactividad_servicio ON modulo3.periodos_inactividad
          FOR ALL USING ({SERVICIO}) WITH CHECK ({SERVICIO});
    """)
    _enable_force('periodos_inactividad')

    # --- bitacora_ingest (RF-53 Fase 12): append-only, solo tecnico
    op.execute(f"""
        CREATE POLICY pol_bitacora_ingest_select ON modulo3.bitacora_ingest
          FOR SELECT USING (
            {permiso('bitacora_auditoria_iot', 'R')}
            AND id_dispositivo_iot IN ({_DISP_SUBQ}));
    """)
    op.execute(f"""
        CREATE POLICY pol_bitacora_ingest_insert ON modulo3.bitacora_ingest
          FOR INSERT WITH CHECK (
            id_dispositivo_iot IN ({_DISP_SUBQ}));
    """)
    op.execute(f"""
        CREATE POLICY pol_bitacora_ingest_servicio ON modulo3.bitacora_ingest
          FOR ALL USING ({SERVICIO}) WITH CHECK ({SERVICIO});
    """)
    _enable_force('bitacora_ingest')

    # --- transmisiones_mqtt: append-only, solo tecnico
    op.execute(f"""
        CREATE POLICY pol_transmisiones_mqtt_select ON modulo3.transmisiones_mqtt
          FOR SELECT USING (
            {permiso('infraestructura_iot', 'R')}
            AND id_dispositivo_iot IN ({_DISP_SUBQ}));
    """)
    op.execute(f"""
        CREATE POLICY pol_transmisiones_mqtt_insert ON modulo3.transmisiones_mqtt
          FOR INSERT WITH CHECK (
            id_dispositivo_iot IN ({_DISP_SUBQ}));
    """)
    op.execute(f"""
        CREATE POLICY pol_transmisiones_mqtt_servicio ON modulo3.transmisiones_mqtt
          FOR ALL USING ({SERVICIO}) WITH CHECK ({SERVICIO});
    """)
    _enable_force('transmisiones_mqtt')

    # --- sincronizaciones_reglas_edge (RF-55/RF-57): propagacion Edge
    op.execute(f"""
        CREATE POLICY pol_sincronizaciones_select ON modulo3.sincronizaciones_reglas_edge
          FOR SELECT USING (
            {permiso('sincronizacion_reglas_edge', 'R')}
            AND id_dispositivo_iot IN ({_DISP_SUBQ}));
    """)
    op.execute(f"""
        CREATE POLICY pol_sincronizaciones_insert ON modulo3.sincronizaciones_reglas_edge
          FOR INSERT WITH CHECK (
            id_dispositivo_iot IN ({_DISP_SUBQ}));
    """)
    op.execute(f"""
        CREATE POLICY pol_sincronizaciones_update ON modulo3.sincronizaciones_reglas_edge
          FOR UPDATE USING (
            ({permiso('sincronizacion_reglas_edge', 'E')} OR {SERVICIO})
            AND id_dispositivo_iot IN ({_DISP_SUBQ}))
          WITH CHECK (
            ({permiso('sincronizacion_reglas_edge', 'E')} OR {SERVICIO})
            AND id_dispositivo_iot IN ({_DISP_SUBQ}));
    """)
    op.execute(f"""
        CREATE POLICY pol_sincronizaciones_servicio ON modulo3.sincronizaciones_reglas_edge
          FOR ALL USING ({SERVICIO}) WITH CHECK ({SERVICIO});
    """)
    _enable_force('sincronizaciones_reglas_edge')

    # ================================================================
    # 6. TABLAS VIA SENSOR (4 saltos)
    #    Reutilizan modulo9.fn_sensores_del_usuario()
    # ================================================================

    # --- telemetrias (RF-53): TABLA DE MAYOR VOLUMEN
    #     SELECT: monitoreo tiempo real (33) o historial (34)
    #     INSERT: solo sistema (ingesta IoT)
    #     UPDATE: solo sistema (flags apto_para_ia, apto_para_nic41)
    op.execute(f"""
        CREATE POLICY pol_telemetrias_select ON modulo3.telemetrias
          FOR SELECT USING (
            ({permiso('monitoreo_telemetria', 'R')} OR {permiso('historial_telemetria', 'R')})
            AND id_sensor IN ({_SENSOR_SUBQ}));
    """)
    op.execute(f"""
        CREATE POLICY pol_telemetrias_insert ON modulo3.telemetrias
          FOR INSERT WITH CHECK (
            id_sensor IN ({_SENSOR_SUBQ}));
    """)
    op.execute(f"""
        CREATE POLICY pol_telemetrias_update ON modulo3.telemetrias
          FOR UPDATE USING (
            id_sensor IN ({_SENSOR_SUBQ}))
          WITH CHECK (
            id_sensor IN ({_SENSOR_SUBQ}));
    """)
    op.execute(f"""
        CREATE POLICY pol_telemetrias_servicio ON modulo3.telemetrias
          FOR ALL USING ({SERVICIO}) WITH CHECK ({SERVICIO});
    """)
    _enable_force('telemetrias')

    # --- estados_actuales_sensores (RF-58): cache dashboard tiempo real
    op.execute(f"""
        CREATE POLICY pol_estados_sensores_select ON modulo3.estados_actuales_sensores
          FOR SELECT USING (
            {permiso('monitoreo_telemetria', 'R')}
            AND id_sensor IN ({_SENSOR_SUBQ}));
    """)
    op.execute(f"""
        CREATE POLICY pol_estados_sensores_insert ON modulo3.estados_actuales_sensores
          FOR INSERT WITH CHECK (
            id_sensor IN ({_SENSOR_SUBQ}));
    """)
    op.execute(f"""
        CREATE POLICY pol_estados_sensores_update ON modulo3.estados_actuales_sensores
          FOR UPDATE USING (
            id_sensor IN ({_SENSOR_SUBQ}))
          WITH CHECK (
            id_sensor IN ({_SENSOR_SUBQ}));
    """)
    op.execute(f"""
        CREATE POLICY pol_estados_sensores_servicio ON modulo3.estados_actuales_sensores
          FOR ALL USING ({SERVICIO}) WITH CHECK ({SERVICIO});
    """)
    _enable_force('estados_actuales_sensores')

    # ================================================================
    # 7. EXISTS SOBRE PADRE (append-only, heredan visibilidad)
    # ================================================================

    # --- historico_estados_alertas (RF-57): EXISTS sobre alertas
    op.execute("""
        CREATE POLICY pol_hist_estados_alertas_select ON modulo3.historico_estados_alertas
          FOR SELECT USING (
            EXISTS (SELECT 1 FROM modulo3.alertas a
                    WHERE a.id_alerta = historico_estados_alertas.id_alerta));
    """)
    op.execute("""
        CREATE POLICY pol_hist_estados_alertas_insert ON modulo3.historico_estados_alertas
          FOR INSERT WITH CHECK (
            EXISTS (SELECT 1 FROM modulo3.alertas a
                    WHERE a.id_alerta = historico_estados_alertas.id_alerta));
    """)
    op.execute(f"""
        CREATE POLICY pol_hist_estados_alertas_servicio ON modulo3.historico_estados_alertas
          FOR ALL USING ({SERVICIO}) WITH CHECK ({SERVICIO});
    """)
    _enable_force('historico_estados_alertas')

    # --- telemetria_calidad (RF-62): EXISTS sobre telemetrias
    op.execute("""
        CREATE POLICY pol_telemetria_calidad_select ON modulo3.telemetria_calidad
          FOR SELECT USING (
            EXISTS (SELECT 1 FROM modulo3.telemetrias t
                    WHERE t.id_telemetria = telemetria_calidad.id_telemetria));
    """)
    op.execute("""
        CREATE POLICY pol_telemetria_calidad_insert ON modulo3.telemetria_calidad
          FOR INSERT WITH CHECK (
            EXISTS (SELECT 1 FROM modulo3.telemetrias t
                    WHERE t.id_telemetria = telemetria_calidad.id_telemetria));
    """)
    op.execute(f"""
        CREATE POLICY pol_telemetria_calidad_servicio ON modulo3.telemetria_calidad
          FOR ALL USING ({SERVICIO}) WITH CHECK ({SERVICIO});
    """)
    _enable_force('telemetria_calidad')

    # ================================================================
    # 8. BITACORA_AUDITORIA_IOT (RF-63): sin finca, append-only
    #    clasificacion_registro: NIC41 (ADM, CON, RF) | TECNICO (ADM, ING)
    #    Permiso R sobre bitacora_auditoria_iot (39) cubre ADM, ING, CON
    # ================================================================
    op.execute(f"""
        CREATE POLICY pol_bitacora_iot_select ON modulo3.bitacora_auditoria_iot
          FOR SELECT USING (
            {permiso('bitacora_auditoria_iot', 'R')}
            OR {SERVICIO});
    """)
    op.execute(f"""
        CREATE POLICY pol_bitacora_iot_insert ON modulo3.bitacora_iot
          FOR INSERT WITH CHECK (
            {SERVICIO}
            OR {UID} IS NOT NULL);
    """)
    op.execute(f"""
        CREATE POLICY pol_bitacora_iot_servicio ON modulo3.bitacora_auditoria_iot
          FOR ALL USING ({SERVICIO}) WITH CHECK ({SERVICIO});
    """)
    _enable_force('bitacora_auditoria_iot')

    # ================================================================
    # 9. ESTADISTICAS
    # ================================================================
    op.execute("ANALYZE modulo3.telemetrias;")
    op.execute("ANALYZE modulo3.alertas;")
    op.execute("ANALYZE modulo3.eventos_edge_computing;")
    op.execute("ANALYZE modulo3.heartbeats;")
    op.execute("ANALYZE modulo3.reglas_alertas;")


def downgrade() -> None:

    # 1. Borrar politicas PRIMERO
    op.execute("""
        DO $$ DECLARE r record; BEGIN
          FOR r IN
            SELECT policyname, tablename FROM pg_policies
            WHERE schemaname = 'modulo3'
          LOOP
            EXECUTE format('DROP POLICY %I ON modulo3.%I', r.policyname, r.tablename);
          END LOOP; END $$;
    """)

    # 2. Quitar FORCE RLS
    op.execute("""
        DO $$ DECLARE t text; BEGIN
          FOR t IN
            SELECT tablename FROM pg_tables WHERE schemaname = 'modulo3'
          LOOP
            EXECUTE format('ALTER TABLE modulo3.%I NO FORCE ROW LEVEL SECURITY', t);
          END LOOP; END $$;
    """)

    # 3. DISABLE RLS (estado original: ninguna tabla tenia RLS)
    op.execute("""
        DO $$ DECLARE t text; BEGIN
          FOR t IN
            SELECT tablename FROM pg_tables WHERE schemaname = 'modulo3'
          LOOP
            EXECUTE format('ALTER TABLE modulo3.%I DISABLE ROW LEVEL SECURITY', t);
          END LOOP; END $$;
    """)