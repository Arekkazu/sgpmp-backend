"""rls_modulo8

Revision ID: e84904d795fd
Revises: 3076315fb9c7
Create Date: 2026-11-18 18:56:37.633113

Clasifica la totalidad de las 13 tablas de modulo8 en patrones de acceso:

  1. CATALOGO (sin RLS):              indicadores_kpi
  2. PROPIA DEL USUARIO:              dashboards, widgets_dashboard,
                                      preferencias_visualizacion
  3. VIA ACTIVO BIOLOGICO:            historiales_clinicos,
                                      retroalimentacion_feedback
  4. VIA ACTIVO + INFRA:              snapshots_kpi, configuraciones_semaforo
  5. VIA FINCA DIRECTA:               reportes_regulatorios
  6. REPORTE FINANCIERO (por rol):    reportes_financieros
  7. AUDITORIA (append-only):         acciones_critica_log, auditorias_reportes,
                                      consultas_auditoria_externas

Recursos RBAC utilizados (modulo1.recursos):
  - activos_biologicos (29): Productor, Vet, Admin, Ing
  - datos_analiticos_metricas (63): lectura de KPIs
  - auditoria_m04 (46): auditores (Admin, Contador, Revisor Fiscal)
  - historial_diagnostico (42): Vet + Admin para historiales clinicos

Reutiliza funciones de modulo1/modulo2/modulo9 (F5):
  - modulo1.fn_id_usuario_actual()
  - modulo1.fn_es_usuario_servicio()
  - modulo1.fn_tiene_permiso()
  - modulo9.fn_fincas_del_usuario()
  - modulo9.fn_infraestructuras_del_usuario()
  - modulo2.fn_activos_del_usuario()

Tabla de Seguimiento (Obligatoria CLAUDE.md):
+------------+--------------+----------------------------------------------+
| Fecha      | Autor        | Descripcion                                  | 
+------------+--------------+----------------------------------------------+
| 2026-11-19 | SamuelPR21   | Creacion inicial politicas RLS modulo8       |     
+------------+--------------+----------------------------------------------+
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e84904d795fd'
down_revision: Union[str, Sequence[str], None] = '3076315fb9c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UID = "(SELECT modulo1.fn_id_usuario_actual())"
SERVICIO = "(SELECT modulo1.fn_es_usuario_servicio())"

# Subconsultas de cadena (reutilizan helpers de F5)
_FINCA_SUBQ = (
    "SELECT f.id_finca"
    f" FROM modulo9.fn_fincas_del_usuario({UID}) f"
)
_INFRA_SUBQ = (
    "SELECT i.id_infraestructura"
    f" FROM modulo9.fn_infraestructuras_del_usuario({UID}) i"
)
_ACTIVO_SUBQ = (
    "SELECT a.id_activo_biologico"
    f" FROM modulo2.fn_activos_del_usuario({UID}) a"
)


def permiso(recurso: str, accion: str) -> str:
    return f"(SELECT modulo1.fn_tiene_permiso('{recurso}', '{accion}'))"


def _enable_force(tabla: str) -> None:
    op.execute(f"ALTER TABLE modulo8.{tabla} ENABLE ROW LEVEL SECURITY;")
    op.execute(f"ALTER TABLE modulo8.{tabla} FORCE ROW LEVEL SECURITY;")


def upgrade() -> None:

    # ================================================================
    # 1. CATALOGO (sin RLS)
    # ================================================================
    op.execute("ALTER TABLE modulo8.indicadores_kpi DISABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE modulo8.indicadores_kpi NO FORCE ROW LEVEL SECURITY;")

    # ================================================================
    # 2. PROPIA DEL USUARIO (id_usuario = usuario actual)
    #    RF-103: dashboards personalizados y preferencias de visualizacion
    # ================================================================
    for t in ('dashboards', 'preferencias_visualizacion'):
        op.execute(f"""
            CREATE POLICY pol_{t}_select ON modulo8.{t}
              FOR SELECT USING (id_usuario = {UID});
        """)
        op.execute(f"""
            CREATE POLICY pol_{t}_insert ON modulo8.{t}
              FOR INSERT WITH CHECK (id_usuario = {UID});
        """)
        op.execute(f"""
            CREATE POLICY pol_{t}_update ON modulo8.{t}
              FOR UPDATE USING (id_usuario = {UID})
              WITH CHECK (id_usuario = {UID});
        """)
        op.execute(f"""
            CREATE POLICY pol_{t}_servicio ON modulo8.{t}
              FOR ALL USING ({SERVICIO}) WITH CHECK ({SERVICIO});
        """)
        _enable_force(t)

    # widgets_dashboard: hereda del dashboard padre via EXISTS
    op.execute("""
        CREATE POLICY pol_widgets_dashboard_select ON modulo8.widgets_dashboard
          FOR SELECT USING (
            EXISTS (SELECT 1 FROM modulo8.dashboards d
                    WHERE d.id_dashboard = widgets_dashboard.id_dashboard
                      AND d.id_usuario = (SELECT modulo1.fn_id_usuario_actual())));
    """)
    op.execute("""
        CREATE POLICY pol_widgets_dashboard_insert ON modulo8.widgets_dashboard
          FOR INSERT WITH CHECK (
            EXISTS (SELECT 1 FROM modulo8.dashboards d
                    WHERE d.id_dashboard = widgets_dashboard.id_dashboard
                      AND d.id_usuario = (SELECT modulo1.fn_id_usuario_actual())));
    """)
    op.execute("""
        CREATE POLICY pol_widgets_dashboard_update ON modulo8.widgets_dashboard
          FOR UPDATE USING (
            EXISTS (SELECT 1 FROM modulo8.dashboards d
                    WHERE d.id_dashboard = widgets_dashboard.id_dashboard
                      AND d.id_usuario = (SELECT modulo1.fn_id_usuario_actual())))
          WITH CHECK (
            EXISTS (SELECT 1 FROM modulo8.dashboards d
                    WHERE d.id_dashboard = widgets_dashboard.id_dashboard
                      AND d.id_usuario = (SELECT modulo1.fn_id_usuario_actual())));
    """)
    op.execute(f"""
        CREATE POLICY pol_widgets_dashboard_servicio ON modulo8.widgets_dashboard
          FOR ALL USING ({SERVICIO}) WITH CHECK ({SERVICIO});
    """)
    _enable_force('widgets_dashboard')

    # ================================================================
    # 3. VIA ACTIVO BIOLOGICO (3 saltos a finca)
    #    RF-103 / RF-67: historial clinico predictivo y retroalimentacion
    # ================================================================

    # --- historiales_clinicos: SELECT/INSERT para Vet y Admin
    op.execute(f"""
        CREATE POLICY pol_historiales_clinicos_select ON modulo8.historiales_clinicos
          FOR SELECT USING (id_activo_biologico IN ({_ACTIVO_SUBQ}));
    """)
    op.execute(f"""
        CREATE POLICY pol_historiales_clinicos_insert ON modulo8.historiales_clinicos
          FOR INSERT WITH CHECK (
            id_activo_biologico IN ({_ACTIVO_SUBQ})
            AND ({permiso('historial_diagnostico', 'R')} OR {SERVICIO}));
    """)
    op.execute(f"""
        CREATE POLICY pol_historiales_clinicos_servicio ON modulo8.historiales_clinicos
          FOR ALL USING ({SERVICIO}) WITH CHECK ({SERVICIO});
    """)
    _enable_force('historiales_clinicos')

    # --- retroalimentacion_feedback (RF-72): append-only por veterinario
    op.execute(f"""
        CREATE POLICY pol_retroalimentacion_select ON modulo8.retroalimentacion_feedback
          FOR SELECT USING (
            EXISTS (SELECT 1 FROM modulo8.historiales_clinicos hc
                    WHERE hc.id_historial_clinicos
                        = retroalimentacion_feedback.id_historial_clinico
                      AND hc.id_activo_biologico IN ({_ACTIVO_SUBQ})));
    """)
    op.execute(f"""
        CREATE POLICY pol_retroalimentacion_insert ON modulo8.retroalimentacion_feedback
          FOR INSERT WITH CHECK (
            id_usuario = {UID}
            AND EXISTS (SELECT 1 FROM modulo8.historiales_clinicos hc
                        WHERE hc.id_historial_clinicos
                            = retroalimentacion_feedback.id_historial_clinico
                          AND hc.id_activo_biologico IN ({_ACTIVO_SUBQ})));
    """)
    op.execute(f"""
        CREATE POLICY pol_retroalimentacion_servicio ON modulo8.retroalimentacion_feedback
          FOR ALL USING ({SERVICIO}) WITH CHECK ({SERVICIO});
    """)
    _enable_force('retroalimentacion_feedback')

    # ================================================================
    # 4. VIA ACTIVO + INFRA (snapshots y semaforos)
    # ================================================================

    # --- snapshots_kpi (RF-103): lectura amplia por rol, escritura solo sistema
    op.execute(f"""
        CREATE POLICY pol_snapshots_kpi_select ON modulo8.snapshots_kpi
          FOR SELECT USING (
            id_activo_biologico IN ({_ACTIVO_SUBQ})
            AND id_infraestructura IN ({_INFRA_SUBQ}));
    """)
    op.execute(f"""
        CREATE POLICY pol_snapshots_kpi_insert ON modulo8.snapshots_kpi
          FOR INSERT WITH CHECK ({SERVICIO});
    """)
    op.execute(f"""
        CREATE POLICY pol_snapshots_kpi_servicio ON modulo8.snapshots_kpi
          FOR ALL USING ({SERVICIO}) WITH CHECK ({SERVICIO});
    """)
    _enable_force('snapshots_kpi')

    # --- configuraciones_semaforo: lectura activa, escritura admin/vet
    op.execute(f"""
        CREATE POLICY pol_semaforo_select ON modulo8.configuraciones_semaforo
          FOR SELECT USING (
            (id_activo_biologico IS NULL
             AND id_infraestructura IS NULL)
            OR id_activo_biologico IN ({_ACTIVO_SUBQ})
            OR id_infraestructura IN ({_INFRA_SUBQ}));
    """)
    op.execute(f"""
        CREATE POLICY pol_semaforo_insert ON modulo8.configuraciones_semaforo
          FOR INSERT WITH CHECK (
            {permiso('datos_analiticos_metricas', 'U')}
            AND (id_activo_biologico IS NULL
                 OR id_activo_biologico IN ({_ACTIVO_SUBQ}))
            AND (id_infraestructura IS NULL
                 OR id_infraestructura IN ({_INFRA_SUBQ})));
    """)
    op.execute(f"""
        CREATE POLICY pol_semaforo_update ON modulo8.configuraciones_semaforo
          FOR UPDATE USING (
            {permiso('datos_analiticos_metricas', 'U')}
            AND (id_activo_biologico IS NULL
                 OR id_activo_biologico IN ({_ACTIVO_SUBQ}))
            AND (id_infraestructura IS NULL
                 OR id_infraestructura IN ({_INFRA_SUBQ})))
          WITH CHECK (
            {permiso('datos_analiticos_metricas', 'U')}
            AND (id_activo_biologico IS NULL
                 OR id_activo_biologico IN ({_ACTIVO_SUBQ}))
            AND (id_infraestructura IS NULL
                 OR id_infraestructura IN ({_INFRA_SUBQ})));
    """)
    op.execute(f"""
        CREATE POLICY pol_semaforo_servicio ON modulo8.configuraciones_semaforo
          FOR ALL USING ({SERVICIO}) WITH CHECK ({SERVICIO});
    """)
    _enable_force('configuraciones_semaforo')

    # ================================================================
    # 5. VIA FINCA DIRECTA (reportes_regulatorios)
    #    RF-103: el sistema valida id_finca antes de consultar modulos fuente
    # ================================================================
    op.execute(f"""
        CREATE POLICY pol_reportes_regulatorios_select ON modulo8.reportes_regulatorios
          FOR SELECT USING (id_finca IN ({_FINCA_SUBQ}));
    """)
    op.execute(f"""
        CREATE POLICY pol_reportes_regulatorios_insert ON modulo8.reportes_regulatorios
          FOR INSERT WITH CHECK (
            id_finca IN ({_FINCA_SUBQ})
            AND id_usuario = {UID});
    """)
    op.execute(f"""
        CREATE POLICY pol_reportes_regulatorios_update ON modulo8.reportes_regulatorios
          FOR UPDATE USING (
            id_finca IN ({_FINCA_SUBQ})
            AND id_usuario = {UID})
          WITH CHECK (
            id_finca IN ({_FINCA_SUBQ})
            AND id_usuario = {UID});
    """)
    op.execute(f"""
        CREATE POLICY pol_reportes_regulatorios_servicio ON modulo8.reportes_regulatorios
          FOR ALL USING ({SERVICIO}) WITH CHECK ({SERVICIO});
    """)
    _enable_force('reportes_regulatorios')

    # ================================================================
    # 6. REPORTES FINANCIEROS (por rol, sin filtro de finca)
    #    RF-103 CA-6: solo Contador accede a NIC41/exportaciones/variacion.
    #    Gestor de Granja (rol 7 = Gerencia) ve ejecutivos consolidados.
    #    Admin ve todo.
    # ================================================================
    op.execute("""
        CREATE POLICY pol_reportes_financieros_select ON modulo8.reportes_financieros
          FOR SELECT USING (
            (SELECT modulo1.fn_tiene_permiso('datos_analiticos_metricas', 'R'))
            OR (SELECT modulo1.fn_es_usuario_servicio()));
    """)
    op.execute("""
        CREATE POLICY pol_reportes_financieros_insert ON modulo8.reportes_financieros
          FOR INSERT WITH CHECK (
            (SELECT modulo1.fn_tiene_permiso('datos_analiticos_metricas', 'C'))
            AND id_usuario = (SELECT modulo1.fn_id_usuario_actual()));
    """)
    op.execute("""
        CREATE POLICY pol_reportes_financieros_servicio ON modulo8.reportes_financieros
          FOR ALL USING ((SELECT modulo1.fn_es_usuario_servicio()))
          WITH CHECK ((SELECT modulo1.fn_es_usuario_servicio()));
    """)
    _enable_force('reportes_financieros')

    # ================================================================
    # 7. AUDITORIA (append-only)
    #    acciones_critica_log, auditorias_reportes, consultas_auditoria_externas
    # ================================================================
    _AUDITORIA = (
        'acciones_critica_log',
        'auditorias_reportes',
        'consultas_auditoria_externas',
    )
    for t in _AUDITORIA:
        op.execute(f"""
            CREATE POLICY pol_{t}_select ON modulo8.{t}
              FOR SELECT USING ({permiso('auditoria_m04', 'R')});
        """)
        op.execute(f"""
            CREATE POLICY pol_{t}_insert ON modulo8.{t}
              FOR INSERT WITH CHECK (
                {SERVICIO}
                OR (id_usuario = {UID} AND {UID} IS NOT NULL));
        """)
        _enable_force(t)

    # ================================================================
    # 8. ESTADISTICAS
    # ================================================================
    op.execute("ANALYZE modulo8.reportes_regulatorios;")
    op.execute("ANALYZE modulo8.snapshots_kpi;")
    op.execute("ANALYZE modulo8.historiales_clinicos;")
    op.execute("ANALYZE modulo8.reportes_financieros;")


def downgrade() -> None:

    # 1. Borrar politicas PRIMERO
    op.execute("""
        DO $$ DECLARE r record; BEGIN
          FOR r IN
            SELECT policyname, tablename FROM pg_policies
            WHERE schemaname = 'modulo8'
          LOOP
            EXECUTE format('DROP POLICY %I ON modulo8.%I', r.policyname, r.tablename);
          END LOOP; END $$;
    """)

    # 2. Quitar FORCE + DISABLE RLS
    op.execute("""
        DO $$ DECLARE t text; BEGIN
          FOR t IN
            SELECT tablename FROM pg_tables WHERE schemaname = 'modulo8'
          LOOP
            EXECUTE format('ALTER TABLE modulo8.%I NO FORCE ROW LEVEL SECURITY', t);
            EXECUTE format('ALTER TABLE modulo8.%I DISABLE ROW LEVEL SECURITY', t);
          END LOOP; END $$;
    """)