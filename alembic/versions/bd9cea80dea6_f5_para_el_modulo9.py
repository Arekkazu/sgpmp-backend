"""F5 para el modulo9: RLS por permisos RBAC

Revision ID: bd9cea80dea6
Revises: 98389cebef99
Create Date: 2026-10-09 09:54:44.791321

Clasifica la totalidad de las tablas de modulo9 en patrones de acceso:

  1. CATALOGO (sin RLS):    tablas de referencia, escritura via API/RBAC.
  2. PROPIA DEL USUARIO:    id_usuario = dueno (dashboard, temas, idiomas).
  3. FINCA DIRECTA:         id_finca directo (identidad_visuales, auditorias_fincas).
  4. FINCA POR CADENA:      via infraestructuras (dispositivos, sensores, calibraciones).
  5. AUDITORIA POR CADENA:  read-only, visibilidad via finca. id_usuario = quien opero.
  6. AUDITORIA DE CATALOGO: audit de tablas catalogo, sin finca.
  7. AUDITORIA PROPIA:      id_usuario = dueno del registro.
  8. CONFIG GLOBAL:         lectura autenticada, escritura por permiso RBAC.

Contrato con la app (anotaciones/convencion_nomenclatura_bd.md):
  - Identidad: modulo1.fn_id_usuario_actual() lee app.current_user_id.
  - Servicio: modulo1.fn_es_usuario_servicio() identifica servicio.sistema@sgpmp.local.
  - Permisos: modulo1.fn_tiene_permiso(recurso, accion) consulta modulo1.permisos.
  - Todas las funciones van dentro de (SELECT ...) para evaluarse por sentencia.

NO SE TOCAN: fincas, infraestructuras (F4 vigente).
usuarios_fincas: RLS con lectura propia y escritura con permiso sobre fincas.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'bd9cea80dea6'
down_revision: Union[str, Sequence[str], None] = '98389cebef99'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UID = "(SELECT modulo1.fn_id_usuario_actual())"
SERVICIO = "(SELECT modulo1.fn_es_usuario_servicio())"


def permiso(recurso: str, accion: str) -> str:
    """Nombres reales de modulo1.recursos para M09."""
    return f"(SELECT modulo1.fn_tiene_permiso('{recurso}', '{accion}'))"


# RF-27: cada uno escribe su tema; el global solo con configuracion_ui_global (recurso 27,
# solo Administrador). tema_visual U lo tienen todos los roles para su propio tema.
_TEMA_ESCRIBIBLE = (f"(id_usuario = {UID} AND NOT es_global)"
                    f" OR (es_global AND {permiso('configuracion_ui_global', 'U')})")

# ── Tablas catálogo: sin RLS ──────────────────────────────────────────
_CATALOGOS = [
    'especies', 'ciclos_biologicos', 'ciclos_productivos',
    'ciclos_productivos_biologicos', 'metricas_produccion',
    'metricas_ciclo_productivo', 'variables_ambientales',
    'tipos_area', 'tipos_dispositivo_iot', 'patologias',
    'especies_patologias', 'compatibilidad_sensores_especies',
    'compatibilidades_tipo_area_especie', 'widgets',
    'dashboard_layouts_default', 'rangos_calibracion',
]

# ── Tablas propia del usuario ─────────────────────────────────────────
_PROPIAS_USUARIO = [
    'dashboard_layouts', 'preferencias_idiomas',
]

# ── Auditoría de catálogo (sin finca) ─────────────────────────────────
_AUDIT_CATALOGO = [
    'auditorias_ciclos_biologicos', 'auditorias_configuraciones_globales',
    'auditorias_especies', 'auditorias_metricas_produccion',
    'auditorias_patologias', 'auditorias_plantillas',
    'auditorias_umbrales_ambientales', 'gestion_especies',
]

# ── Auditoría propia del usuario ──────────────────────────────────────
_AUDIT_PROPIA = [
    'auditorias_visuales', 'aplicaciones_plantillas', 'intentos_fallidos',
]

# Recurso que exige el endpoint que lista cada historial (hoy lo leen esos roles).
_LECTURA_AUDIT_PROPIA = {
    'auditorias_visuales': 'identidad_visual',
    'aplicaciones_plantillas': 'plantillas',
}

# ── Tablas finca por cadena ───────────────────────────────────────────
_FINCA_CADENA = [
    'dispositivos_iot', 'sensores', 'sensores_areas_asociadas',
    'calibraciones', 'calibraciones_vision', 'lineas_base_vision',
    'configuraciones_remotas',
]

# ── Auditoría por cadena ──────────────────────────────────────────────
_AUDIT_CADENA = [
    'auditorias_infraestructuras', 'auditorias_dispositivos_iot',
    'auditorias_sensores_areas', 'auditorias_calibraciones',
]

# ── Config global ─────────────────────────────────────────────────────
_CONFIG_GLOBAL = [
    'configuraciones_globales', 'umbrales_ambientales',
    'niveles_alerta_ambientales', 'plantillas',
]


def _borrar_politicas_modulo9() -> None:
    """Borra todas las políticas de modulo9 excepto fincas e infraestructuras."""
    op.execute("""
        DO $$ DECLARE r record; BEGIN
          FOR r IN
            SELECT policyname, tablename FROM pg_policies
            WHERE schemaname = 'modulo9'
              AND tablename NOT IN ('fincas', 'infraestructuras')
          LOOP
            EXECUTE format('DROP POLICY %I ON modulo9.%I', r.policyname, r.tablename);
          END LOOP; END $$;
    """)


def upgrade() -> None:

    # ================================================================
    # 0. BORRAR POLÍTICAS EXISTENTES (crítico: sin esto las viejas
    #    políticas permisivas se combinan con OR y no aíslan nada)
    # ================================================================
    _borrar_politicas_modulo9()

    # ================================================================
    # 1. FUNCIONES HELPER para cadenas de 2 y 3 saltos
    # ================================================================
    op.execute("""
        CREATE OR REPLACE FUNCTION modulo9.fn_dispositivos_del_usuario(p_usuario_id bigint)
        RETURNS TABLE (id_dispositivo_iot int)
        LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = pg_catalog, modulo9 AS
        $$ SELECT d.id_dispositivo_iot
           FROM modulo9.dispositivos_iot d
           WHERE d.id_infraestructura IN (
               SELECT i.id_infraestructura
               FROM modulo9.fn_infraestructuras_del_usuario(p_usuario_id) i); $$;
    """)
    op.execute("REVOKE ALL ON FUNCTION modulo9.fn_dispositivos_del_usuario(bigint) FROM PUBLIC;")
    op.execute("GRANT EXECUTE ON FUNCTION modulo9.fn_dispositivos_del_usuario(bigint) TO sgpmp_app;")

    op.execute("""
        CREATE OR REPLACE FUNCTION modulo9.fn_sensores_del_usuario(p_usuario_id bigint)
        RETURNS TABLE (id_sensores int)
        LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = pg_catalog, modulo9 AS
        $$ SELECT s.id_sensores
           FROM modulo9.sensores s
           WHERE s.id_dispositivo_iot IN (
               SELECT d.id_dispositivo_iot
               FROM modulo9.fn_dispositivos_del_usuario(p_usuario_id) d); $$;
    """)
    op.execute("REVOKE ALL ON FUNCTION modulo9.fn_sensores_del_usuario(bigint) FROM PUBLIC;")
    op.execute("GRANT EXECUTE ON FUNCTION modulo9.fn_sensores_del_usuario(bigint) TO sgpmp_app;")

    # ================================================================
    # 2. CATÁLOGOS: desactivar RLS
    # ================================================================
    for t in _CATALOGOS:
        op.execute(f"ALTER TABLE modulo9.{t} DISABLE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE modulo9.{t} NO FORCE ROW LEVEL SECURITY;")

    # ================================================================
    # 3. usuarios_fincas: RLS con lectura propia + escritura por permiso
    #    (Arekkazu: dejarla abierta permite que un request se asigne
    #     cualquier finca)
    # ================================================================
    op.execute(f"""
        CREATE POLICY pol_usuarios_fincas_select ON modulo9.usuarios_fincas
          FOR SELECT USING (id_usuario = {UID}
                            OR id_finca IN (SELECT f.id_finca FROM modulo9.fn_fincas_del_usuario({UID}) f)
                            OR {permiso('fincas', 'U')});
    """)
    op.execute(f"""
        CREATE POLICY pol_usuarios_fincas_insert ON modulo9.usuarios_fincas
          FOR INSERT WITH CHECK ({permiso('fincas', 'U')});
    """)
    op.execute(f"""
        CREATE POLICY pol_usuarios_fincas_update ON modulo9.usuarios_fincas
          FOR UPDATE USING ({permiso('fincas', 'U')})
          WITH CHECK ({permiso('fincas', 'U')});
    """)
    op.execute(f"""
        CREATE POLICY pol_usuarios_fincas_delete ON modulo9.usuarios_fincas
          FOR DELETE USING ({permiso('fincas', 'U')});
    """)
    op.execute(f"""
        CREATE POLICY pol_usuarios_fincas_servicio ON modulo9.usuarios_fincas
          FOR ALL USING ({SERVICIO}) WITH CHECK ({SERVICIO});
    """)
    op.execute("ALTER TABLE modulo9.usuarios_fincas ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE modulo9.usuarios_fincas FORCE ROW LEVEL SECURITY;")

    # ================================================================
    # 4. PROPIA DEL USUARIO: id_usuario = dueño
    # ================================================================

    # dashboard_layouts
    op.execute(f"""
        CREATE POLICY pol_dashboard_layouts_select ON modulo9.dashboard_layouts
          FOR SELECT USING (id_usuario = {UID});
    """)
    op.execute(f"""
        CREATE POLICY pol_dashboard_layouts_insert ON modulo9.dashboard_layouts
          FOR INSERT WITH CHECK (id_usuario = {UID});
    """)
    op.execute(f"""
        CREATE POLICY pol_dashboard_layouts_update ON modulo9.dashboard_layouts
          FOR UPDATE USING (id_usuario = {UID}) WITH CHECK (id_usuario = {UID});
    """)
    op.execute(f"""
        CREATE POLICY pol_dashboard_layouts_servicio ON modulo9.dashboard_layouts
          FOR ALL USING ({SERVICIO}) WITH CHECK ({SERVICIO});
    """)
    op.execute("ALTER TABLE modulo9.dashboard_layouts FORCE ROW LEVEL SECURITY;")

    # temas_visuales (RF-27: es_global = true visible para todos)
    op.execute(f"""
        CREATE POLICY pol_temas_visuales_select ON modulo9.temas_visuales
          FOR SELECT USING (id_usuario = {UID} OR es_global);
    """)
    op.execute(f"""
        CREATE POLICY pol_temas_visuales_insert ON modulo9.temas_visuales
          FOR INSERT WITH CHECK ({_TEMA_ESCRIBIBLE});
    """)
    op.execute(f"""
        CREATE POLICY pol_temas_visuales_update ON modulo9.temas_visuales
          FOR UPDATE USING ({_TEMA_ESCRIBIBLE}) WITH CHECK ({_TEMA_ESCRIBIBLE});
    """)
    op.execute(f"""
        CREATE POLICY pol_temas_visuales_servicio ON modulo9.temas_visuales
          FOR ALL USING ({SERVICIO}) WITH CHECK ({SERVICIO});
    """)
    op.execute("ALTER TABLE modulo9.temas_visuales FORCE ROW LEVEL SECURITY;")

    # preferencias_idiomas
    op.execute(f"""
        CREATE POLICY pol_preferencias_idiomas_select ON modulo9.preferencias_idiomas
          FOR SELECT USING (id_usuario = {UID});
    """)
    op.execute(f"""
        CREATE POLICY pol_preferencias_idiomas_insert ON modulo9.preferencias_idiomas
          FOR INSERT WITH CHECK (id_usuario = {UID});
    """)
    op.execute(f"""
        CREATE POLICY pol_preferencias_idiomas_update ON modulo9.preferencias_idiomas
          FOR UPDATE USING (id_usuario = {UID}) WITH CHECK (id_usuario = {UID});
    """)
    op.execute(f"""
        CREATE POLICY pol_preferencias_idiomas_servicio ON modulo9.preferencias_idiomas
          FOR ALL USING ({SERVICIO}) WITH CHECK ({SERVICIO});
    """)
    op.execute("ALTER TABLE modulo9.preferencias_idiomas FORCE ROW LEVEL SECURITY;")

    # ================================================================
    # 5. FINCA DIRECTA (excepto fincas — F4 vigente)
    # ================================================================

    # identidad_visuales
    for cmd, clause in [
        ("SELECT", f"USING (id_finca IN (SELECT f.id_finca FROM modulo9.fn_fincas_del_usuario({UID}) f))"),
        ("INSERT", f"WITH CHECK (id_finca IN (SELECT f.id_finca FROM modulo9.fn_fincas_del_usuario({UID}) f))"),
        ("UPDATE", f"USING (id_finca IN (SELECT f.id_finca FROM modulo9.fn_fincas_del_usuario({UID}) f)) WITH CHECK (id_finca IN (SELECT f.id_finca FROM modulo9.fn_fincas_del_usuario({UID}) f))"),
    ]:
        op.execute(f"""
            CREATE POLICY pol_identidad_visuales_{cmd.lower()} ON modulo9.identidad_visuales
              FOR {cmd} {clause};
        """)
    op.execute(f"""
        CREATE POLICY pol_identidad_visuales_servicio ON modulo9.identidad_visuales
          FOR ALL USING ({SERVICIO}) WITH CHECK ({SERVICIO});
    """)
    op.execute("ALTER TABLE modulo9.identidad_visuales FORCE ROW LEVEL SECURITY;")

    # auditorias_fincas (read + insert, sin update/delete)
    op.execute(f"""
        CREATE POLICY pol_auditorias_fincas_select ON modulo9.auditorias_fincas
          FOR SELECT USING (id_finca IN (SELECT f.id_finca FROM modulo9.fn_fincas_del_usuario({UID}) f));
    """)
    op.execute(f"""
        CREATE POLICY pol_auditorias_fincas_insert ON modulo9.auditorias_fincas
          FOR INSERT WITH CHECK (id_finca IN (SELECT f.id_finca FROM modulo9.fn_fincas_del_usuario({UID}) f));
    """)
    op.execute(f"""
        CREATE POLICY pol_auditorias_fincas_servicio ON modulo9.auditorias_fincas
          FOR ALL USING ({SERVICIO}) WITH CHECK ({SERVICIO});
    """)
    op.execute("ALTER TABLE modulo9.auditorias_fincas FORCE ROW LEVEL SECURITY;")

    # ================================================================
    # 6. FINCA POR CADENA (excepto infraestructuras — F4 vigente)
    # ================================================================

    # dispositivos_iot (2 saltos: dispositivo → infra → finca)
    _infra_subq = f"SELECT i.id_infraestructura FROM modulo9.fn_infraestructuras_del_usuario({UID}) i"
    for cmd, clause in [
        ("SELECT", f"USING (id_infraestructura IN ({_infra_subq}))"),
        ("INSERT", f"WITH CHECK (id_infraestructura IN ({_infra_subq}))"),
        ("UPDATE", f"USING (id_infraestructura IN ({_infra_subq})) WITH CHECK (id_infraestructura IN ({_infra_subq}))"),
    ]:
        op.execute(f"""
            CREATE POLICY pol_dispositivos_iot_{cmd.lower()} ON modulo9.dispositivos_iot
              FOR {cmd} {clause};
        """)
    op.execute(f"""
        CREATE POLICY pol_dispositivos_iot_servicio ON modulo9.dispositivos_iot
          FOR ALL USING ({SERVICIO}) WITH CHECK ({SERVICIO});
    """)
    op.execute("ALTER TABLE modulo9.dispositivos_iot FORCE ROW LEVEL SECURITY;")

    # sensores (3 saltos: sensor → dispositivo → infra → finca)
    _sensor_subq = f"SELECT s.id_sensores FROM modulo9.fn_sensores_del_usuario({UID}) s"
    for cmd, clause in [
        ("SELECT", f"USING (id_sensores IN ({_sensor_subq}))"),
        ("INSERT", f"WITH CHECK (id_dispositivo_iot IN (SELECT d.id_dispositivo_iot FROM modulo9.fn_dispositivos_del_usuario({UID}) d))"),
        ("UPDATE", f"USING (id_sensores IN ({_sensor_subq})) WITH CHECK (id_sensores IN ({_sensor_subq}))"),
    ]:
        op.execute(f"""
            CREATE POLICY pol_sensores_{cmd.lower()} ON modulo9.sensores
              FOR {cmd} {clause};
        """)
    op.execute(f"""
        CREATE POLICY pol_sensores_servicio ON modulo9.sensores
          FOR ALL USING ({SERVICIO}) WITH CHECK ({SERVICIO});
    """)
    op.execute("ALTER TABLE modulo9.sensores FORCE ROW LEVEL SECURITY;")

    # sensores_areas_asociadas (2 saltos: id_infraestructura directo)
    for cmd, clause in [
        ("SELECT", f"USING (id_infraestructura IN ({_infra_subq}))"),
        ("INSERT", f"WITH CHECK (id_infraestructura IN ({_infra_subq}))"),
        ("UPDATE", f"USING (id_infraestructura IN ({_infra_subq})) WITH CHECK (id_infraestructura IN ({_infra_subq}))"),
    ]:
        op.execute(f"""
            CREATE POLICY pol_sensores_areas_{cmd.lower()} ON modulo9.sensores_areas_asociadas
              FOR {cmd} {clause};
        """)
    op.execute(f"""
        CREATE POLICY pol_sensores_areas_servicio ON modulo9.sensores_areas_asociadas
          FOR ALL USING ({SERVICIO}) WITH CHECK ({SERVICIO});
    """)
    op.execute("ALTER TABLE modulo9.sensores_areas_asociadas FORCE ROW LEVEL SECURITY;")

    # calibraciones (3 saltos: calibración → dispositivo → infra → finca)
    _disp_subq = f"SELECT d.id_dispositivo_iot FROM modulo9.fn_dispositivos_del_usuario({UID}) d"
    op.execute(f"""
        CREATE POLICY pol_calibraciones_select ON modulo9.calibraciones
          FOR SELECT USING (id_dispositivo_iot IN ({_disp_subq}));
    """)
    op.execute(f"""
        CREATE POLICY pol_calibraciones_insert ON modulo9.calibraciones
          FOR INSERT WITH CHECK (id_dispositivo_iot IN ({_disp_subq}));
    """)
    op.execute(f"""
        CREATE POLICY pol_calibraciones_servicio ON modulo9.calibraciones
          FOR ALL USING ({SERVICIO}) WITH CHECK ({SERVICIO});
    """)
    op.execute("ALTER TABLE modulo9.calibraciones FORCE ROW LEVEL SECURITY;")

    # calibraciones_vision (2 saltos: id_infraestructura directo)
    op.execute(f"""
        CREATE POLICY pol_calibraciones_vision_select ON modulo9.calibraciones_vision
          FOR SELECT USING (id_infraestructura IN ({_infra_subq}));
    """)
    op.execute(f"""
        CREATE POLICY pol_calibraciones_vision_insert ON modulo9.calibraciones_vision
          FOR INSERT WITH CHECK (id_infraestructura IN ({_infra_subq}));
    """)
    op.execute(f"""
        CREATE POLICY pol_calibraciones_vision_servicio ON modulo9.calibraciones_vision
          FOR ALL USING ({SERVICIO}) WITH CHECK ({SERVICIO});
    """)
    op.execute("ALTER TABLE modulo9.calibraciones_vision FORCE ROW LEVEL SECURITY;")

    # lineas_base_vision (2 saltos: id_infraestructura directo)
    op.execute(f"""
        CREATE POLICY pol_lineas_base_vision_select ON modulo9.lineas_base_vision
          FOR SELECT USING (id_infraestructura IN ({_infra_subq}));
    """)
    op.execute(f"""
        CREATE POLICY pol_lineas_base_vision_insert ON modulo9.lineas_base_vision
          FOR INSERT WITH CHECK (id_infraestructura IN ({_infra_subq}));
    """)
    op.execute(f"""
        CREATE POLICY pol_lineas_base_vision_servicio ON modulo9.lineas_base_vision
          FOR ALL USING ({SERVICIO}) WITH CHECK ({SERVICIO});
    """)
    op.execute("ALTER TABLE modulo9.lineas_base_vision FORCE ROW LEVEL SECURITY;")

    # configuraciones_remotas (3 saltos: config → dispositivo → infra → finca)
    for cmd, clause in [
        ("SELECT", f"USING (id_dispositivo_iot IN ({_disp_subq}))"),
        ("INSERT", f"WITH CHECK (id_dispositivo_iot IN ({_disp_subq}))"),
        ("UPDATE", f"USING (id_dispositivo_iot IN ({_disp_subq})) WITH CHECK (id_dispositivo_iot IN ({_disp_subq}))"),
    ]:
        op.execute(f"""
            CREATE POLICY pol_configuraciones_remotas_{cmd.lower()} ON modulo9.configuraciones_remotas
              FOR {cmd} {clause};
        """)
    op.execute(f"""
        CREATE POLICY pol_configuraciones_remotas_servicio ON modulo9.configuraciones_remotas
          FOR ALL USING ({SERVICIO}) WITH CHECK ({SERVICIO});
    """)
    op.execute("ALTER TABLE modulo9.configuraciones_remotas FORCE ROW LEVEL SECURITY;")

    # ================================================================
    # 7. AUDITORÍA POR CADENA (read + insert, sin update/delete)
    # ================================================================

    # auditorias_infraestructuras
    op.execute(f"""
        CREATE POLICY pol_auditorias_infraestructuras_select ON modulo9.auditorias_infraestructuras
          FOR SELECT USING (id_infraestructura IN ({_infra_subq}));
    """)
    op.execute(f"""
        CREATE POLICY pol_auditorias_infraestructuras_insert ON modulo9.auditorias_infraestructuras
          FOR INSERT WITH CHECK (id_infraestructura IN ({_infra_subq}));
    """)
    op.execute(f"""
        CREATE POLICY pol_auditorias_infraestructuras_servicio ON modulo9.auditorias_infraestructuras
          FOR ALL USING ({SERVICIO}) WITH CHECK ({SERVICIO});
    """)
    op.execute("ALTER TABLE modulo9.auditorias_infraestructuras FORCE ROW LEVEL SECURITY;")

    # auditorias_dispositivos_iot
    op.execute(f"""
        CREATE POLICY pol_auditorias_dispositivos_select ON modulo9.auditorias_dispositivos_iot
          FOR SELECT USING (id_dispositivo_iot IN ({_disp_subq}));
    """)
    op.execute(f"""
        CREATE POLICY pol_auditorias_dispositivos_insert ON modulo9.auditorias_dispositivos_iot
          FOR INSERT WITH CHECK (id_dispositivo_iot IN ({_disp_subq}));
    """)
    op.execute(f"""
        CREATE POLICY pol_auditorias_dispositivos_servicio ON modulo9.auditorias_dispositivos_iot
          FOR ALL USING ({SERVICIO}) WITH CHECK ({SERVICIO});
    """)
    op.execute("ALTER TABLE modulo9.auditorias_dispositivos_iot FORCE ROW LEVEL SECURITY;")

    # auditorias_sensores_areas
    _sens_area_subq = f"""SELECT sa.id_sensores_area_asociada
              FROM modulo9.sensores_areas_asociadas sa
              WHERE sa.id_infraestructura IN ({_infra_subq})"""
    op.execute(f"""
        CREATE POLICY pol_auditorias_sensores_areas_select ON modulo9.auditorias_sensores_areas
          FOR SELECT USING (id_sensores_area_asociada IN ({_sens_area_subq}));
    """)
    op.execute(f"""
        CREATE POLICY pol_auditorias_sensores_areas_insert ON modulo9.auditorias_sensores_areas
          FOR INSERT WITH CHECK (id_sensores_area_asociada IN ({_sens_area_subq}));
    """)
    op.execute(f"""
        CREATE POLICY pol_auditorias_sensores_areas_servicio ON modulo9.auditorias_sensores_areas
          FOR ALL USING ({SERVICIO}) WITH CHECK ({SERVICIO});
    """)
    op.execute("ALTER TABLE modulo9.auditorias_sensores_areas FORCE ROW LEVEL SECURITY;")

    # auditorias_calibraciones
    _calib_subq = f"""SELECT c.id_calibracion FROM modulo9.calibraciones c
              WHERE c.id_dispositivo_iot IN ({_disp_subq})"""
    op.execute(f"""
        CREATE POLICY pol_auditorias_calibraciones_select ON modulo9.auditorias_calibraciones
          FOR SELECT USING (id_calibracion IN ({_calib_subq}));
    """)
    op.execute(f"""
        CREATE POLICY pol_auditorias_calibraciones_insert ON modulo9.auditorias_calibraciones
          FOR INSERT WITH CHECK (id_calibracion IN ({_calib_subq}));
    """)
    op.execute(f"""
        CREATE POLICY pol_auditorias_calibraciones_servicio ON modulo9.auditorias_calibraciones
          FOR ALL USING ({SERVICIO}) WITH CHECK ({SERVICIO});
    """)
    op.execute("ALTER TABLE modulo9.auditorias_calibraciones FORCE ROW LEVEL SECURITY;")

    # ================================================================
    # 8. AUDITORÍA DE CATÁLOGO (sin finca; lectura por permiso)
    # ================================================================
    for t in _AUDIT_CATALOGO:
        op.execute(f"""
            CREATE POLICY pol_{t}_select ON modulo9.{t}
              FOR SELECT USING ({permiso('especies', 'R')} OR {SERVICIO});
        """)
        op.execute(f"""
            CREATE POLICY pol_{t}_insert ON modulo9.{t}
              FOR INSERT WITH CHECK ({UID} IS NOT NULL);
        """)
        op.execute(f"""
            CREATE POLICY pol_{t}_servicio ON modulo9.{t}
              FOR ALL USING ({SERVICIO}) WITH CHECK ({SERVICIO});
        """)
        op.execute(f"ALTER TABLE modulo9.{t} FORCE ROW LEVEL SECURITY;")

    # ================================================================
    # 9. AUDITORÍA PROPIA DEL USUARIO
    # ================================================================
    for t in _AUDIT_PROPIA:
        lectura = _LECTURA_AUDIT_PROPIA.get(t)
        extra = f" OR {permiso(lectura, 'R')}" if lectura else ""
        op.execute(f"""
            CREATE POLICY pol_{t}_select ON modulo9.{t}
              FOR SELECT USING (id_usuario = {UID} OR {SERVICIO}{extra});
        """)
        op.execute(f"""
            CREATE POLICY pol_{t}_insert ON modulo9.{t}
              FOR INSERT WITH CHECK (id_usuario = {UID} OR {SERVICIO});
        """)
        op.execute(f"""
            CREATE POLICY pol_{t}_servicio ON modulo9.{t}
              FOR ALL USING ({SERVICIO}) WITH CHECK ({SERVICIO});
        """)
        op.execute(f"ALTER TABLE modulo9.{t} FORCE ROW LEVEL SECURITY;")

    # ================================================================
    # 10. CONFIG GLOBAL (lectura amplia, escritura por permiso RBAC)
    # ================================================================

    # configuraciones_globales (RF-18): Admin escribe, servicio lee
    op.execute(f"""
        CREATE POLICY pol_configuraciones_globales_select ON modulo9.configuraciones_globales
          FOR SELECT USING (true);
    """)
    op.execute(f"""
        CREATE POLICY pol_configuraciones_globales_insert ON modulo9.configuraciones_globales
          FOR INSERT WITH CHECK ({permiso('configuraciones_globales', 'C')});
    """)
    op.execute(f"""
        CREATE POLICY pol_configuraciones_globales_update ON modulo9.configuraciones_globales
          FOR UPDATE USING ({permiso('configuraciones_globales', 'U')})
          WITH CHECK ({permiso('configuraciones_globales', 'U')});
    """)
    op.execute(f"""
        CREATE POLICY pol_configuraciones_globales_servicio ON modulo9.configuraciones_globales
          FOR ALL USING ({SERVICIO}) WITH CHECK ({SERVICIO});
    """)
    op.execute("ALTER TABLE modulo9.configuraciones_globales FORCE ROW LEVEL SECURITY;")

    # umbrales_ambientales (RF-17): Admin/Vet escribe, servicio lee
    op.execute(f"""
        CREATE POLICY pol_umbrales_ambientales_select ON modulo9.umbrales_ambientales
          FOR SELECT USING (true);
    """)
    op.execute(f"""
        CREATE POLICY pol_umbrales_ambientales_insert ON modulo9.umbrales_ambientales
          FOR INSERT WITH CHECK ({permiso('umbrales_ambientales', 'C')});
    """)
    op.execute(f"""
        CREATE POLICY pol_umbrales_ambientales_update ON modulo9.umbrales_ambientales
          FOR UPDATE USING ({permiso('umbrales_ambientales', 'U')})
          WITH CHECK ({permiso('umbrales_ambientales', 'U')});
    """)
    op.execute(f"""
        CREATE POLICY pol_umbrales_ambientales_servicio ON modulo9.umbrales_ambientales
          FOR ALL USING ({SERVICIO}) WITH CHECK ({SERVICIO});
    """)
    op.execute("ALTER TABLE modulo9.umbrales_ambientales FORCE ROW LEVEL SECURITY;")

    # niveles_alerta_ambientales: hijo de umbrales, mismo patrón
    op.execute(f"""
        CREATE POLICY pol_niveles_alerta_select ON modulo9.niveles_alerta_ambientales
          FOR SELECT USING (true);
    """)
    op.execute(f"""
        CREATE POLICY pol_niveles_alerta_insert ON modulo9.niveles_alerta_ambientales
          FOR INSERT WITH CHECK ({permiso('umbrales_ambientales', 'C')});
    """)
    op.execute(f"""
        CREATE POLICY pol_niveles_alerta_update ON modulo9.niveles_alerta_ambientales
          FOR UPDATE USING ({permiso('umbrales_ambientales', 'U')})
          WITH CHECK ({permiso('umbrales_ambientales', 'U')});
    """)
    op.execute(f"""
        CREATE POLICY pol_niveles_alerta_servicio ON modulo9.niveles_alerta_ambientales
          FOR ALL USING ({SERVICIO}) WITH CHECK ({SERVICIO});
    """)
    op.execute("ALTER TABLE modulo9.niveles_alerta_ambientales FORCE ROW LEVEL SECURITY;")

    # plantillas: lectura autenticada, escritura por creador o Admin
    op.execute(f"""
        CREATE POLICY pol_plantillas_select ON modulo9.plantillas
          FOR SELECT USING (true);
    """)
    op.execute(f"""
        CREATE POLICY pol_plantillas_insert ON modulo9.plantillas
          FOR INSERT WITH CHECK (id_usuario = {UID});
    """)
    op.execute(f"""
        CREATE POLICY pol_plantillas_update ON modulo9.plantillas
          FOR UPDATE USING (id_usuario = {UID} OR {permiso('plantillas', 'U')})
          WITH CHECK (id_usuario = {UID} OR {permiso('plantillas', 'U')});
    """)
    op.execute(f"""
        CREATE POLICY pol_plantillas_servicio ON modulo9.plantillas
          FOR ALL USING ({SERVICIO}) WITH CHECK ({SERVICIO});
    """)
    op.execute("ALTER TABLE modulo9.plantillas FORCE ROW LEVEL SECURITY;")

    # ================================================================
    # 11. ESTADÍSTICAS
    # ================================================================
    op.execute("ANALYZE modulo9.fincas;")
    op.execute("ANALYZE modulo9.infraestructuras;")
    op.execute("ANALYZE modulo9.dispositivos_iot;")
    op.execute("ANALYZE modulo9.sensores;")
    op.execute("ANALYZE modulo9.usuarios_fincas;")


def downgrade() -> None:

    # 1. Borrar políticas nuevas PRIMERO (antes que las funciones)
    _borrar_politicas_modulo9()

    # 2. Quitar FORCE RLS
    op.execute("""
        DO $$ DECLARE t text; BEGIN
          FOR t IN
            SELECT tablename FROM pg_tables WHERE schemaname = 'modulo9'
              AND tablename NOT IN ('fincas', 'infraestructuras')
          LOOP
            EXECUTE format('ALTER TABLE modulo9.%I NO FORCE ROW LEVEL SECURITY', t);
          END LOOP; END $$;
    """)

    # 3. Restaurar RLS habilitado en todas las tablas (estado del DDL)
    op.execute("""
        DO $$ DECLARE t text; BEGIN
          FOR t IN
            SELECT tablename FROM pg_tables WHERE schemaname = 'modulo9'
              AND tablename NOT IN ('fincas', 'infraestructuras', 'usuarios_fincas')
          LOOP
            EXECUTE format('ALTER TABLE modulo9.%I ENABLE ROW LEVEL SECURITY', t);
          END LOOP; END $$;
    """)

    # 4. usuarios_fincas: restaurar estado original (sin RLS en DDL)
    op.execute("ALTER TABLE modulo9.usuarios_fincas DISABLE ROW LEVEL SECURITY;")

    # 5. Recrear las políticas de 00c60ae92735 (las de fincas e infraestructuras no se tocaron)
    op.execute(_POLITICAS_ANTERIORES)

    # 6. Borrar funciones helper AL FINAL (después de las políticas)
    op.execute("DROP FUNCTION IF EXISTS modulo9.fn_sensores_del_usuario(bigint);")
    op.execute("DROP FUNCTION IF EXISTS modulo9.fn_dispositivos_del_usuario(bigint);")


# Estado de modulo9 en 00c60ae92735, sacado de pg_policy, para el downgrade.
_POLITICAS_ANTERIORES = """
CREATE POLICY pol_aplicaciones_plantillas_insert ON modulo9.aplicaciones_plantillas AS PERMISSIVE FOR INSERT WITH CHECK (((modulo1.fn_rol_actual() = ANY (ARRAY['Administrador'::text, 'Ingeniero de Campo'::text])) AND (id_usuario = modulo1.fn_id_usuario_actual())));
CREATE POLICY pol_aplicaciones_plantillas_select ON modulo9.aplicaciones_plantillas AS PERMISSIVE FOR SELECT USING ((modulo1.fn_rol_actual() = ANY (ARRAY['Administrador'::text, 'Ingeniero de Campo'::text])));
CREATE POLICY pol_auditorias_calibraciones_insert ON modulo9.auditorias_calibraciones AS PERMISSIVE FOR INSERT WITH CHECK (true);
CREATE POLICY pol_auditorias_calibraciones_select ON modulo9.auditorias_calibraciones AS PERMISSIVE FOR SELECT USING ((modulo1.fn_rol_actual() = 'Administrador'::text));
CREATE POLICY pol_auditorias_ciclos_biologicos_insert ON modulo9.auditorias_ciclos_biologicos AS PERMISSIVE FOR INSERT WITH CHECK (true);
CREATE POLICY pol_auditorias_ciclos_biologicos_select ON modulo9.auditorias_ciclos_biologicos AS PERMISSIVE FOR SELECT USING ((modulo1.fn_rol_actual() = 'Administrador'::text));
CREATE POLICY pol_auditorias_configuraciones_globales_insert ON modulo9.auditorias_configuraciones_globales AS PERMISSIVE FOR INSERT WITH CHECK (true);
CREATE POLICY pol_auditorias_configuraciones_globales_select ON modulo9.auditorias_configuraciones_globales AS PERMISSIVE FOR SELECT USING ((modulo1.fn_rol_actual() = 'Administrador'::text));
CREATE POLICY pol_auditorias_dispositivos_iot_insert ON modulo9.auditorias_dispositivos_iot AS PERMISSIVE FOR INSERT WITH CHECK (true);
CREATE POLICY pol_auditorias_dispositivos_iot_select ON modulo9.auditorias_dispositivos_iot AS PERMISSIVE FOR SELECT USING ((modulo1.fn_rol_actual() = 'Administrador'::text));
CREATE POLICY pol_auditorias_especies_insert ON modulo9.auditorias_especies AS PERMISSIVE FOR INSERT WITH CHECK (true);
CREATE POLICY pol_auditorias_especies_select ON modulo9.auditorias_especies AS PERMISSIVE FOR SELECT USING ((modulo1.fn_rol_actual() = 'Administrador'::text));
CREATE POLICY pol_auditorias_fincas_insert ON modulo9.auditorias_fincas AS PERMISSIVE FOR INSERT WITH CHECK (true);
CREATE POLICY pol_auditorias_fincas_select ON modulo9.auditorias_fincas AS PERMISSIVE FOR SELECT USING ((modulo1.fn_rol_actual() = 'Administrador'::text));
CREATE POLICY pol_auditorias_infraestructuras_insert ON modulo9.auditorias_infraestructuras AS PERMISSIVE FOR INSERT WITH CHECK (true);
CREATE POLICY pol_auditorias_infraestructuras_select ON modulo9.auditorias_infraestructuras AS PERMISSIVE FOR SELECT USING ((modulo1.fn_rol_actual() = 'Administrador'::text));
CREATE POLICY pol_auditorias_metricas_produccion_insert ON modulo9.auditorias_metricas_produccion AS PERMISSIVE FOR INSERT WITH CHECK (true);
CREATE POLICY pol_auditorias_metricas_produccion_select ON modulo9.auditorias_metricas_produccion AS PERMISSIVE FOR SELECT USING ((modulo1.fn_rol_actual() = 'Administrador'::text));
CREATE POLICY pol_auditorias_patologias_insert ON modulo9.auditorias_patologias AS PERMISSIVE FOR INSERT WITH CHECK (true);
CREATE POLICY pol_auditorias_patologias_select ON modulo9.auditorias_patologias AS PERMISSIVE FOR SELECT USING ((modulo1.fn_rol_actual() = 'Administrador'::text));
CREATE POLICY pol_auditorias_plantillas_insert ON modulo9.auditorias_plantillas AS PERMISSIVE FOR INSERT WITH CHECK (true);
CREATE POLICY pol_auditorias_plantillas_select ON modulo9.auditorias_plantillas AS PERMISSIVE FOR SELECT USING ((modulo1.fn_rol_actual() = 'Administrador'::text));
CREATE POLICY pol_auditorias_sensores_areas_insert ON modulo9.auditorias_sensores_areas AS PERMISSIVE FOR INSERT WITH CHECK (true);
CREATE POLICY pol_auditorias_sensores_areas_select ON modulo9.auditorias_sensores_areas AS PERMISSIVE FOR SELECT USING ((modulo1.fn_rol_actual() = 'Administrador'::text));
CREATE POLICY pol_auditorias_umbrales_ambientales_insert ON modulo9.auditorias_umbrales_ambientales AS PERMISSIVE FOR INSERT WITH CHECK (true);
CREATE POLICY pol_auditorias_umbrales_ambientales_select ON modulo9.auditorias_umbrales_ambientales AS PERMISSIVE FOR SELECT USING ((modulo1.fn_rol_actual() = 'Administrador'::text));
CREATE POLICY pol_auditorias_visuales_insert ON modulo9.auditorias_visuales AS PERMISSIVE FOR INSERT WITH CHECK (true);
CREATE POLICY pol_auditorias_visuales_select ON modulo9.auditorias_visuales AS PERMISSIVE FOR SELECT USING ((modulo1.fn_rol_actual() = 'Administrador'::text));
CREATE POLICY pol_calibraciones_insert ON modulo9.calibraciones AS PERMISSIVE FOR INSERT WITH CHECK (((modulo1.fn_rol_actual() = ANY (ARRAY['Administrador'::text, 'Ingeniero de Campo'::text])) AND (id_usuario = modulo1.fn_id_usuario_actual())));
CREATE POLICY pol_calibraciones_select ON modulo9.calibraciones AS PERMISSIVE FOR SELECT USING ((modulo1.fn_rol_actual() = ANY (ARRAY['Administrador'::text, 'Ingeniero de Campo'::text])));
CREATE POLICY pol_calibraciones_vision_insert ON modulo9.calibraciones_vision AS PERMISSIVE FOR INSERT WITH CHECK (((modulo1.fn_rol_actual() = ANY (ARRAY['Administrador'::text, 'Ingeniero de Campo'::text])) AND (id_usuario = modulo1.fn_id_usuario_actual())));
CREATE POLICY pol_calibraciones_vision_select ON modulo9.calibraciones_vision AS PERMISSIVE FOR SELECT USING ((modulo1.fn_rol_actual() = ANY (ARRAY['Administrador'::text, 'Ingeniero de Campo'::text])));
CREATE POLICY pol_ciclos_biologicos_insert ON modulo9.ciclos_biologicos AS PERMISSIVE FOR INSERT WITH CHECK ((modulo1.fn_rol_actual() = ANY (ARRAY['Administrador'::text, 'Veterinario'::text])));
CREATE POLICY pol_ciclos_biologicos_select ON modulo9.ciclos_biologicos AS PERMISSIVE FOR SELECT USING (true);
CREATE POLICY pol_ciclos_biologicos_update ON modulo9.ciclos_biologicos AS PERMISSIVE FOR UPDATE USING ((modulo1.fn_rol_actual() = ANY (ARRAY['Administrador'::text, 'Veterinario'::text]))) WITH CHECK ((modulo1.fn_rol_actual() = ANY (ARRAY['Administrador'::text, 'Veterinario'::text])));
CREATE POLICY pol_ciclos_productivos_insert ON modulo9.ciclos_productivos AS PERMISSIVE FOR INSERT WITH CHECK ((modulo1.fn_rol_actual() = ANY (ARRAY['Administrador'::text, 'Veterinario'::text])));
CREATE POLICY pol_ciclos_productivos_select ON modulo9.ciclos_productivos AS PERMISSIVE FOR SELECT USING (true);
CREATE POLICY pol_ciclos_productivos_update ON modulo9.ciclos_productivos AS PERMISSIVE FOR UPDATE USING ((modulo1.fn_rol_actual() = ANY (ARRAY['Administrador'::text, 'Veterinario'::text]))) WITH CHECK ((modulo1.fn_rol_actual() = ANY (ARRAY['Administrador'::text, 'Veterinario'::text])));
CREATE POLICY pol_ciclos_productivos_biologicos_insert ON modulo9.ciclos_productivos_biologicos AS PERMISSIVE FOR INSERT WITH CHECK ((modulo1.fn_rol_actual() = ANY (ARRAY['Administrador'::text, 'Veterinario'::text])));
CREATE POLICY pol_ciclos_productivos_biologicos_select ON modulo9.ciclos_productivos_biologicos AS PERMISSIVE FOR SELECT USING (true);
CREATE POLICY pol_ciclos_productivos_biologicos_update ON modulo9.ciclos_productivos_biologicos AS PERMISSIVE FOR UPDATE USING ((modulo1.fn_rol_actual() = ANY (ARRAY['Administrador'::text, 'Veterinario'::text]))) WITH CHECK ((modulo1.fn_rol_actual() = ANY (ARRAY['Administrador'::text, 'Veterinario'::text])));
CREATE POLICY pol_config_globales_insert ON modulo9.configuraciones_globales AS PERMISSIVE FOR INSERT WITH CHECK (((modulo1.fn_rol_actual() = 'Administrador'::text) AND (id_usuario = modulo1.fn_id_usuario_actual())));
CREATE POLICY pol_config_globales_select ON modulo9.configuraciones_globales AS PERMISSIVE FOR SELECT USING (true);
CREATE POLICY pol_config_globales_update ON modulo9.configuraciones_globales AS PERMISSIVE FOR UPDATE USING ((modulo1.fn_rol_actual() = 'Administrador'::text)) WITH CHECK ((modulo1.fn_rol_actual() = 'Administrador'::text));
CREATE POLICY pol_configuraciones_remotas_insert ON modulo9.configuraciones_remotas AS PERMISSIVE FOR INSERT WITH CHECK ((modulo1.fn_rol_actual() = ANY (ARRAY['Administrador'::text, 'Ingeniero de Campo'::text])));
CREATE POLICY pol_configuraciones_remotas_select ON modulo9.configuraciones_remotas AS PERMISSIVE FOR SELECT USING ((modulo1.fn_rol_actual() = ANY (ARRAY['Administrador'::text, 'Ingeniero de Campo'::text])));
CREATE POLICY pol_configuraciones_remotas_update ON modulo9.configuraciones_remotas AS PERMISSIVE FOR UPDATE USING ((modulo1.fn_rol_actual() = ANY (ARRAY['Administrador'::text, 'Ingeniero de Campo'::text]))) WITH CHECK ((modulo1.fn_rol_actual() = ANY (ARRAY['Administrador'::text, 'Ingeniero de Campo'::text])));
CREATE POLICY pol_dashboard_layouts_all ON modulo9.dashboard_layouts AS PERMISSIVE FOR ALL USING ((id_usuario = modulo1.fn_id_usuario_actual())) WITH CHECK ((id_usuario = modulo1.fn_id_usuario_actual()));
CREATE POLICY pol_dashboard_layouts_default_insert ON modulo9.dashboard_layouts_default AS PERMISSIVE FOR INSERT WITH CHECK ((modulo1.fn_rol_actual() = 'Administrador'::text));
CREATE POLICY pol_dashboard_layouts_default_select ON modulo9.dashboard_layouts_default AS PERMISSIVE FOR SELECT USING (true);
CREATE POLICY pol_dashboard_layouts_default_update ON modulo9.dashboard_layouts_default AS PERMISSIVE FOR UPDATE USING ((modulo1.fn_rol_actual() = 'Administrador'::text)) WITH CHECK ((modulo1.fn_rol_actual() = 'Administrador'::text));
CREATE POLICY pol_dispositivos_iot_insert ON modulo9.dispositivos_iot AS PERMISSIVE FOR INSERT WITH CHECK ((modulo1.fn_rol_actual() = ANY (ARRAY['Administrador'::text, 'Ingeniero de Campo'::text])));
CREATE POLICY pol_dispositivos_iot_select ON modulo9.dispositivos_iot AS PERMISSIVE FOR SELECT USING ((modulo1.fn_rol_actual() = ANY (ARRAY['Administrador'::text, 'Ingeniero de Campo'::text])));
CREATE POLICY pol_dispositivos_iot_update ON modulo9.dispositivos_iot AS PERMISSIVE FOR UPDATE USING ((modulo1.fn_rol_actual() = ANY (ARRAY['Administrador'::text, 'Ingeniero de Campo'::text]))) WITH CHECK ((modulo1.fn_rol_actual() = ANY (ARRAY['Administrador'::text, 'Ingeniero de Campo'::text])));
CREATE POLICY pol_especies_insert ON modulo9.especies AS PERMISSIVE FOR INSERT WITH CHECK ((modulo1.fn_rol_actual() = 'Administrador'::text));
CREATE POLICY pol_especies_select ON modulo9.especies AS PERMISSIVE FOR SELECT USING (true);
CREATE POLICY pol_especies_update ON modulo9.especies AS PERMISSIVE FOR UPDATE USING ((modulo1.fn_rol_actual() = ANY (ARRAY['Administrador'::text, 'Ingeniero de Campo'::text, 'Veterinario'::text]))) WITH CHECK ((modulo1.fn_rol_actual() = ANY (ARRAY['Administrador'::text, 'Ingeniero de Campo'::text, 'Veterinario'::text])));
CREATE POLICY pol_especies_patologias_insert ON modulo9.especies_patologias AS PERMISSIVE FOR INSERT WITH CHECK ((modulo1.fn_rol_actual() = ANY (ARRAY['Administrador'::text, 'Veterinario'::text])));
CREATE POLICY pol_especies_patologias_select ON modulo9.especies_patologias AS PERMISSIVE FOR SELECT USING (true);
CREATE POLICY pol_especies_patologias_update ON modulo9.especies_patologias AS PERMISSIVE FOR UPDATE USING ((modulo1.fn_rol_actual() = ANY (ARRAY['Administrador'::text, 'Veterinario'::text]))) WITH CHECK ((modulo1.fn_rol_actual() = ANY (ARRAY['Administrador'::text, 'Veterinario'::text])));
CREATE POLICY pol_gestion_especies_insert ON modulo9.gestion_especies AS PERMISSIVE FOR INSERT WITH CHECK (true);
CREATE POLICY pol_gestion_especies_select ON modulo9.gestion_especies AS PERMISSIVE FOR SELECT USING ((modulo1.fn_rol_actual() = 'Administrador'::text));
CREATE POLICY pol_identidad_visuales_insert ON modulo9.identidad_visuales AS PERMISSIVE FOR INSERT WITH CHECK (((modulo1.fn_rol_actual() = 'Administrador'::text) AND (id_usuario = modulo1.fn_id_usuario_actual())));
CREATE POLICY pol_identidad_visuales_select ON modulo9.identidad_visuales AS PERMISSIVE FOR SELECT USING (true);
CREATE POLICY pol_identidad_visuales_update ON modulo9.identidad_visuales AS PERMISSIVE FOR UPDATE USING ((modulo1.fn_rol_actual() = 'Administrador'::text)) WITH CHECK ((modulo1.fn_rol_actual() = 'Administrador'::text));
CREATE POLICY pol_lineas_base_vision_insert ON modulo9.lineas_base_vision AS PERMISSIVE FOR INSERT WITH CHECK ((modulo1.fn_rol_actual() = ANY (ARRAY['Administrador'::text, 'Ingeniero de Campo'::text])));
CREATE POLICY pol_lineas_base_vision_select ON modulo9.lineas_base_vision AS PERMISSIVE FOR SELECT USING ((modulo1.fn_rol_actual() = ANY (ARRAY['Administrador'::text, 'Ingeniero de Campo'::text])));
CREATE POLICY pol_lineas_base_vision_update ON modulo9.lineas_base_vision AS PERMISSIVE FOR UPDATE USING ((modulo1.fn_rol_actual() = ANY (ARRAY['Administrador'::text, 'Ingeniero de Campo'::text]))) WITH CHECK ((modulo1.fn_rol_actual() = ANY (ARRAY['Administrador'::text, 'Ingeniero de Campo'::text])));
CREATE POLICY pol_metricas_ciclo_productivo_insert ON modulo9.metricas_ciclo_productivo AS PERMISSIVE FOR INSERT WITH CHECK ((modulo1.fn_rol_actual() = ANY (ARRAY['Administrador'::text, 'Veterinario'::text])));
CREATE POLICY pol_metricas_ciclo_productivo_select ON modulo9.metricas_ciclo_productivo AS PERMISSIVE FOR SELECT USING (true);
CREATE POLICY pol_metricas_ciclo_productivo_update ON modulo9.metricas_ciclo_productivo AS PERMISSIVE FOR UPDATE USING ((modulo1.fn_rol_actual() = ANY (ARRAY['Administrador'::text, 'Veterinario'::text]))) WITH CHECK ((modulo1.fn_rol_actual() = ANY (ARRAY['Administrador'::text, 'Veterinario'::text])));
CREATE POLICY pol_metricas_produccion_insert ON modulo9.metricas_produccion AS PERMISSIVE FOR INSERT WITH CHECK ((modulo1.fn_rol_actual() = ANY (ARRAY['Administrador'::text, 'Veterinario'::text])));
CREATE POLICY pol_metricas_produccion_select ON modulo9.metricas_produccion AS PERMISSIVE FOR SELECT USING (true);
CREATE POLICY pol_metricas_produccion_update ON modulo9.metricas_produccion AS PERMISSIVE FOR UPDATE USING ((modulo1.fn_rol_actual() = ANY (ARRAY['Administrador'::text, 'Veterinario'::text]))) WITH CHECK ((modulo1.fn_rol_actual() = ANY (ARRAY['Administrador'::text, 'Veterinario'::text])));
CREATE POLICY pol_niveles_alerta_ambientales_insert ON modulo9.niveles_alerta_ambientales AS PERMISSIVE FOR INSERT WITH CHECK ((modulo1.fn_rol_actual() = ANY (ARRAY['Administrador'::text, 'Veterinario'::text])));
CREATE POLICY pol_niveles_alerta_ambientales_select ON modulo9.niveles_alerta_ambientales AS PERMISSIVE FOR SELECT USING (true);
CREATE POLICY pol_niveles_alerta_ambientales_update ON modulo9.niveles_alerta_ambientales AS PERMISSIVE FOR UPDATE USING ((modulo1.fn_rol_actual() = ANY (ARRAY['Administrador'::text, 'Veterinario'::text]))) WITH CHECK ((modulo1.fn_rol_actual() = ANY (ARRAY['Administrador'::text, 'Veterinario'::text])));
CREATE POLICY pol_patologias_insert ON modulo9.patologias AS PERMISSIVE FOR INSERT WITH CHECK ((modulo1.fn_rol_actual() = ANY (ARRAY['Administrador'::text, 'Veterinario'::text])));
CREATE POLICY pol_patologias_select ON modulo9.patologias AS PERMISSIVE FOR SELECT USING (true);
CREATE POLICY pol_patologias_update ON modulo9.patologias AS PERMISSIVE FOR UPDATE USING (((modulo1.fn_rol_actual() = ANY (ARRAY['Administrador'::text, 'Veterinario'::text])) AND (es_base = false))) WITH CHECK (((modulo1.fn_rol_actual() = ANY (ARRAY['Administrador'::text, 'Veterinario'::text])) AND (es_base = false)));
CREATE POLICY pol_plantillas_insert ON modulo9.plantillas AS PERMISSIVE FOR INSERT WITH CHECK (((modulo1.fn_rol_actual() = ANY (ARRAY['Administrador'::text, 'Ingeniero de Campo'::text])) AND (id_usuario = modulo1.fn_id_usuario_actual())));
CREATE POLICY pol_plantillas_select ON modulo9.plantillas AS PERMISSIVE FOR SELECT USING ((modulo1.fn_rol_actual() = ANY (ARRAY['Administrador'::text, 'Ingeniero de Campo'::text])));
CREATE POLICY pol_preferencias_idiomas_all ON modulo9.preferencias_idiomas AS PERMISSIVE FOR ALL USING ((id_usuario = modulo1.fn_id_usuario_actual())) WITH CHECK ((id_usuario = modulo1.fn_id_usuario_actual()));
CREATE POLICY pol_rangos_calibracion_insert ON modulo9.rangos_calibracion AS PERMISSIVE FOR INSERT WITH CHECK ((modulo1.fn_rol_actual() = 'Administrador'::text));
CREATE POLICY pol_rangos_calibracion_select ON modulo9.rangos_calibracion AS PERMISSIVE FOR SELECT USING (true);
CREATE POLICY pol_rangos_calibracion_update ON modulo9.rangos_calibracion AS PERMISSIVE FOR UPDATE USING ((modulo1.fn_rol_actual() = 'Administrador'::text)) WITH CHECK ((modulo1.fn_rol_actual() = 'Administrador'::text));
CREATE POLICY pol_sensores_insert ON modulo9.sensores AS PERMISSIVE FOR INSERT WITH CHECK ((modulo1.fn_rol_actual() = ANY (ARRAY['Administrador'::text, 'Ingeniero de Campo'::text])));
CREATE POLICY pol_sensores_select ON modulo9.sensores AS PERMISSIVE FOR SELECT USING ((modulo1.fn_rol_actual() = ANY (ARRAY['Administrador'::text, 'Ingeniero de Campo'::text])));
CREATE POLICY pol_sensores_update ON modulo9.sensores AS PERMISSIVE FOR UPDATE USING ((modulo1.fn_rol_actual() = ANY (ARRAY['Administrador'::text, 'Ingeniero de Campo'::text]))) WITH CHECK ((modulo1.fn_rol_actual() = ANY (ARRAY['Administrador'::text, 'Ingeniero de Campo'::text])));
CREATE POLICY pol_sensores_areas_asociadas_insert ON modulo9.sensores_areas_asociadas AS PERMISSIVE FOR INSERT WITH CHECK ((modulo1.fn_rol_actual() = ANY (ARRAY['Administrador'::text, 'Ingeniero de Campo'::text])));
CREATE POLICY pol_sensores_areas_asociadas_select ON modulo9.sensores_areas_asociadas AS PERMISSIVE FOR SELECT USING ((modulo1.fn_rol_actual() = ANY (ARRAY['Administrador'::text, 'Ingeniero de Campo'::text])));
CREATE POLICY pol_sensores_areas_asociadas_update ON modulo9.sensores_areas_asociadas AS PERMISSIVE FOR UPDATE USING ((modulo1.fn_rol_actual() = ANY (ARRAY['Administrador'::text, 'Ingeniero de Campo'::text]))) WITH CHECK ((modulo1.fn_rol_actual() = ANY (ARRAY['Administrador'::text, 'Ingeniero de Campo'::text])));
CREATE POLICY pol_temas_visuales_insert ON modulo9.temas_visuales AS PERMISSIVE FOR INSERT WITH CHECK ((((id_usuario = modulo1.fn_id_usuario_actual()) AND (es_global = false)) OR ((modulo1.fn_rol_actual() = 'Administrador'::text) AND (es_global = true))));
CREATE POLICY pol_temas_visuales_select ON modulo9.temas_visuales AS PERMISSIVE FOR SELECT USING (((id_usuario = modulo1.fn_id_usuario_actual()) OR (es_global = true) OR (modulo1.fn_rol_actual() = 'Administrador'::text)));
CREATE POLICY pol_temas_visuales_update ON modulo9.temas_visuales AS PERMISSIVE FOR UPDATE USING ((((id_usuario = modulo1.fn_id_usuario_actual()) AND (es_global = false)) OR ((modulo1.fn_rol_actual() = 'Administrador'::text) AND (es_global = true)))) WITH CHECK ((((id_usuario = modulo1.fn_id_usuario_actual()) AND (es_global = false)) OR ((modulo1.fn_rol_actual() = 'Administrador'::text) AND (es_global = true))));
CREATE POLICY pol_tipos_area_insert ON modulo9.tipos_area AS PERMISSIVE FOR INSERT WITH CHECK ((modulo1.fn_rol_actual() = 'Administrador'::text));
CREATE POLICY pol_tipos_area_select ON modulo9.tipos_area AS PERMISSIVE FOR SELECT USING (true);
CREATE POLICY pol_tipos_area_update ON modulo9.tipos_area AS PERMISSIVE FOR UPDATE USING ((modulo1.fn_rol_actual() = 'Administrador'::text)) WITH CHECK ((modulo1.fn_rol_actual() = 'Administrador'::text));
CREATE POLICY pol_tipos_dispositivo_iot_insert ON modulo9.tipos_dispositivo_iot AS PERMISSIVE FOR INSERT WITH CHECK ((modulo1.fn_rol_actual() = 'Administrador'::text));
CREATE POLICY pol_tipos_dispositivo_iot_select ON modulo9.tipos_dispositivo_iot AS PERMISSIVE FOR SELECT USING (true);
CREATE POLICY pol_tipos_dispositivo_iot_update ON modulo9.tipos_dispositivo_iot AS PERMISSIVE FOR UPDATE USING ((modulo1.fn_rol_actual() = 'Administrador'::text)) WITH CHECK ((modulo1.fn_rol_actual() = 'Administrador'::text));
CREATE POLICY pol_umbrales_ambientales_insert ON modulo9.umbrales_ambientales AS PERMISSIVE FOR INSERT WITH CHECK ((modulo1.fn_rol_actual() = ANY (ARRAY['Administrador'::text, 'Veterinario'::text])));
CREATE POLICY pol_umbrales_ambientales_select ON modulo9.umbrales_ambientales AS PERMISSIVE FOR SELECT USING (true);
CREATE POLICY pol_umbrales_ambientales_update ON modulo9.umbrales_ambientales AS PERMISSIVE FOR UPDATE USING ((modulo1.fn_rol_actual() = ANY (ARRAY['Administrador'::text, 'Veterinario'::text]))) WITH CHECK ((modulo1.fn_rol_actual() = ANY (ARRAY['Administrador'::text, 'Veterinario'::text])));
CREATE POLICY pol_variables_ambientales_select ON modulo9.variables_ambientales AS PERMISSIVE FOR SELECT USING (true);
CREATE POLICY pol_widgets_insert ON modulo9.widgets AS PERMISSIVE FOR INSERT WITH CHECK ((modulo1.fn_rol_actual() = 'Administrador'::text));
CREATE POLICY pol_widgets_select ON modulo9.widgets AS PERMISSIVE FOR SELECT USING (true);
CREATE POLICY pol_widgets_update ON modulo9.widgets AS PERMISSIVE FOR UPDATE USING ((modulo1.fn_rol_actual() = 'Administrador'::text)) WITH CHECK ((modulo1.fn_rol_actual() = 'Administrador'::text));
"""
