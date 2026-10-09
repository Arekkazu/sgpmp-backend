"""F5 para el modulo9

Revision ID: bd9cea80dea6
Revises: 00c60ae92735
Create Date: 2026-10-09 09:54:44.791321

Clasifica la totalidad de las tablas de modulo9 en patrones de acceso:

  1. CATALOGO (sin RLS):    tablas de referencia, escritura via API/RBAC.
  2. PROPIA DEL USUARIO:    id_usuario = dueno (dashboard, temas, idiomas).
  3. FINCA DIRECTA:         id_finca directo (identidad_visuales, auditorias_fincas).
  4. FINCA POR CADENA:      via infraestructuras (dispositivos, sensores, calibraciones).
  5. AUDITORIA POR CADENA:  read-only, visibilidad via finca. id_usuario = quien opero.
  6. AUDITORIA DE CATALOGO: audit de tablas catalogo, sin finca.
  7. AUDITORIA PROPIA:      id_usuario = dueno del registro.
  8. CONFIG GLOBAL:         lectura autenticada, escritura restringida.

NO SE TOCAN: fincas, infraestructuras (F4 vigente), usuarios_fincas (acceso).

NOTA downgrade: restaura al estado post-F4. No reconstruye politicas intermedias.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bd9cea80dea6'
down_revision: Union[str, Sequence[str], None] = '00c60ae92735'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None



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
    'dashboard_layouts', 'temas_visuales', 'preferencias_idiomas',
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


def upgrade() -> None:

    # ================================================================
    # 0. FUNCIONES HELPER para cadenas de 2 y 3 saltos
    # ================================================================

    # Dispositivos IoT del usuario (dispositivo → infraestructura → finca)
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

    # Sensores del usuario (sensor → dispositivo → infraestructura → finca)
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
    # 1. CATÁLOGOS: desactivar RLS (sin datos sensibles por finca)
    # ================================================================
    for t in _CATALOGOS:
        op.execute(f"ALTER TABLE modulo9.{t} DISABLE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE modulo9.{t} NO FORCE ROW LEVEL SECURITY;")

    # usuarios_fincas: tabla de acceso, NUNCA llevar RLS (dependencia circular)
    op.execute("ALTER TABLE modulo9.usuarios_fincas DISABLE ROW LEVEL SECURITY;")

    # ================================================================
    # 2. PROPIA DEL USUARIO: id_usuario = dueño
    # ================================================================
    for t in _PROPIAS_USUARIO:
        op.execute(f"""
            CREATE POLICY {t}_own_sel ON modulo9.{t}
              FOR SELECT USING (id_usuario = modulo1.f_uid());
        """)
        op.execute(f"""
            CREATE POLICY {t}_own_ins ON modulo9.{t}
              FOR INSERT WITH CHECK (id_usuario = modulo1.f_uid());
        """)
        op.execute(f"""
            CREATE POLICY {t}_own_upd ON modulo9.{t}
              FOR UPDATE USING (id_usuario = modulo1.f_uid())
              WITH CHECK (id_usuario = modulo1.f_uid());
        """)
        op.execute(f"""
            CREATE POLICY {t}_sis ON modulo9.{t}
              FOR ALL USING (modulo1.f_sistema())
              WITH CHECK (modulo1.f_sistema());
        """)
        op.execute(f"ALTER TABLE modulo9.{t} FORCE ROW LEVEL SECURITY;")

    # ================================================================
    # 3. FINCA DIRECTA (excepto fincas — F4 vigente)
    # ================================================================

    # identidad_visuales: configuración visual por finca
    op.execute("""
        CREATE POLICY identidad_vis_sel ON modulo9.identidad_visuales
          FOR SELECT USING (
            id_finca IN (SELECT f.id_finca
                         FROM modulo9.fn_fincas_del_usuario(modulo1.f_uid()) f));
    """)
    op.execute("""
        CREATE POLICY identidad_vis_ins ON modulo9.identidad_visuales
          FOR INSERT WITH CHECK (
            id_finca IN (SELECT f.id_finca
                         FROM modulo9.fn_fincas_del_usuario(modulo1.f_uid()) f));
    """)
    op.execute("""
        CREATE POLICY identidad_vis_upd ON modulo9.identidad_visuales
          FOR UPDATE USING (
            id_finca IN (SELECT f.id_finca
                         FROM modulo9.fn_fincas_del_usuario(modulo1.f_uid()) f))
          WITH CHECK (
            id_finca IN (SELECT f.id_finca
                         FROM modulo9.fn_fincas_del_usuario(modulo1.f_uid()) f));
    """)
    op.execute("""
        CREATE POLICY identidad_vis_sis ON modulo9.identidad_visuales
          FOR ALL USING (modulo1.f_sistema()) WITH CHECK (modulo1.f_sistema());
    """)
    op.execute("ALTER TABLE modulo9.identidad_visuales FORCE ROW LEVEL SECURITY;")

    # auditorias_fincas: auditoría por finca (read + insert, sin update/delete)
    op.execute("""
        CREATE POLICY audit_fincas_sel ON modulo9.auditorias_fincas
          FOR SELECT USING (
            id_finca IN (SELECT f.id_finca
                         FROM modulo9.fn_fincas_del_usuario(modulo1.f_uid()) f));
    """)
    op.execute("""
        CREATE POLICY audit_fincas_ins ON modulo9.auditorias_fincas
          FOR INSERT WITH CHECK (
            id_finca IN (SELECT f.id_finca
                         FROM modulo9.fn_fincas_del_usuario(modulo1.f_uid()) f));
    """)
    op.execute("""
        CREATE POLICY audit_fincas_sis ON modulo9.auditorias_fincas
          FOR ALL USING (modulo1.f_sistema()) WITH CHECK (modulo1.f_sistema());
    """)
    op.execute("ALTER TABLE modulo9.auditorias_fincas FORCE ROW LEVEL SECURITY;")

    # ================================================================
    # 4. FINCA POR CADENA (excepto infraestructuras — F4 vigente)
    # ================================================================

    # ── dispositivos_iot (2 saltos: dispositivo → infra → finca)
    op.execute("""
        CREATE POLICY disp_iot_sel ON modulo9.dispositivos_iot
          FOR SELECT USING (
            id_infraestructura IN (
              SELECT i.id_infraestructura
              FROM modulo9.fn_infraestructuras_del_usuario(modulo1.f_uid()) i));
    """)
    op.execute("""
        CREATE POLICY disp_iot_ins ON modulo9.dispositivos_iot
          FOR INSERT WITH CHECK (
            id_infraestructura IN (
              SELECT i.id_infraestructura
              FROM modulo9.fn_infraestructuras_del_usuario(modulo1.f_uid()) i));
    """)
    op.execute("""
        CREATE POLICY disp_iot_upd ON modulo9.dispositivos_iot
          FOR UPDATE USING (
            id_infraestructura IN (
              SELECT i.id_infraestructura
              FROM modulo9.fn_infraestructuras_del_usuario(modulo1.f_uid()) i))
          WITH CHECK (
            id_infraestructura IN (
              SELECT i.id_infraestructura
              FROM modulo9.fn_infraestructuras_del_usuario(modulo1.f_uid()) i));
    """)
    op.execute("""
        CREATE POLICY disp_iot_sis ON modulo9.dispositivos_iot
          FOR ALL USING (modulo1.f_sistema()) WITH CHECK (modulo1.f_sistema());
    """)
    op.execute("ALTER TABLE modulo9.dispositivos_iot FORCE ROW LEVEL SECURITY;")

    # ── sensores (3 saltos: sensor → dispositivo → infra → finca)
    op.execute("""
        CREATE POLICY sensores_sel ON modulo9.sensores
          FOR SELECT USING (
            id_dispositivo_iot IN (
              SELECT d.id_dispositivo_iot
              FROM modulo9.fn_dispositivos_del_usuario(modulo1.f_uid()) d));
    """)
    op.execute("""
        CREATE POLICY sensores_ins ON modulo9.sensores
          FOR INSERT WITH CHECK (
            id_dispositivo_iot IN (
              SELECT d.id_dispositivo_iot
              FROM modulo9.fn_dispositivos_del_usuario(modulo1.f_uid()) d));
    """)
    op.execute("""
        CREATE POLICY sensores_upd ON modulo9.sensores
          FOR UPDATE USING (
            id_dispositivo_iot IN (
              SELECT d.id_dispositivo_iot
              FROM modulo9.fn_dispositivos_del_usuario(modulo1.f_uid()) d))
          WITH CHECK (
            id_dispositivo_iot IN (
              SELECT d.id_dispositivo_iot
              FROM modulo9.fn_dispositivos_del_usuario(modulo1.f_uid()) d));
    """)
    op.execute("""
        CREATE POLICY sensores_sis ON modulo9.sensores
          FOR ALL USING (modulo1.f_sistema()) WITH CHECK (modulo1.f_sistema());
    """)
    op.execute("ALTER TABLE modulo9.sensores FORCE ROW LEVEL SECURITY;")

    # ── sensores_areas_asociadas (2 saltos: tiene id_infraestructura directo)
    op.execute("""
        CREATE POLICY sens_area_sel ON modulo9.sensores_areas_asociadas
          FOR SELECT USING (
            id_infraestructura IN (
              SELECT i.id_infraestructura
              FROM modulo9.fn_infraestructuras_del_usuario(modulo1.f_uid()) i));
    """)
    op.execute("""
        CREATE POLICY sens_area_ins ON modulo9.sensores_areas_asociadas
          FOR INSERT WITH CHECK (
            id_infraestructura IN (
              SELECT i.id_infraestructura
              FROM modulo9.fn_infraestructuras_del_usuario(modulo1.f_uid()) i));
    """)
    op.execute("""
        CREATE POLICY sens_area_upd ON modulo9.sensores_areas_asociadas
          FOR UPDATE USING (
            id_infraestructura IN (
              SELECT i.id_infraestructura
              FROM modulo9.fn_infraestructuras_del_usuario(modulo1.f_uid()) i))
          WITH CHECK (
            id_infraestructura IN (
              SELECT i.id_infraestructura
              FROM modulo9.fn_infraestructuras_del_usuario(modulo1.f_uid()) i));
    """)
    op.execute("""
        CREATE POLICY sens_area_sis ON modulo9.sensores_areas_asociadas
          FOR ALL USING (modulo1.f_sistema()) WITH CHECK (modulo1.f_sistema());
    """)
    op.execute("ALTER TABLE modulo9.sensores_areas_asociadas FORCE ROW LEVEL SECURITY;")

    # ── calibraciones (3 saltos: calibración → dispositivo → infra → finca)
    op.execute("""
        CREATE POLICY calib_sel ON modulo9.calibraciones
          FOR SELECT USING (
            id_dispositivo_iot IN (
              SELECT d.id_dispositivo_iot
              FROM modulo9.fn_dispositivos_del_usuario(modulo1.f_uid()) d));
    """)
    op.execute("""
        CREATE POLICY calib_ins ON modulo9.calibraciones
          FOR INSERT WITH CHECK (
            id_dispositivo_iot IN (
              SELECT d.id_dispositivo_iot
              FROM modulo9.fn_dispositivos_del_usuario(modulo1.f_uid()) d));
    """)
    op.execute("""
        CREATE POLICY calib_sis ON modulo9.calibraciones
          FOR ALL USING (modulo1.f_sistema()) WITH CHECK (modulo1.f_sistema());
    """)
    op.execute("ALTER TABLE modulo9.calibraciones FORCE ROW LEVEL SECURITY;")

    # ── calibraciones_vision (2 saltos: tiene id_infraestructura directo)
    op.execute("""
        CREATE POLICY calib_vis_sel ON modulo9.calibraciones_vision
          FOR SELECT USING (
            id_infraestructura IN (
              SELECT i.id_infraestructura
              FROM modulo9.fn_infraestructuras_del_usuario(modulo1.f_uid()) i));
    """)
    op.execute("""
        CREATE POLICY calib_vis_ins ON modulo9.calibraciones_vision
          FOR INSERT WITH CHECK (
            id_infraestructura IN (
              SELECT i.id_infraestructura
              FROM modulo9.fn_infraestructuras_del_usuario(modulo1.f_uid()) i));
    """)
    op.execute("""
        CREATE POLICY calib_vis_sis ON modulo9.calibraciones_vision
          FOR ALL USING (modulo1.f_sistema()) WITH CHECK (modulo1.f_sistema());
    """)
    op.execute("ALTER TABLE modulo9.calibraciones_vision FORCE ROW LEVEL SECURITY;")

    # ── lineas_base_vision (2 saltos: tiene id_infraestructura directo)
    op.execute("""
        CREATE POLICY lineas_base_sel ON modulo9.lineas_base_vision
          FOR SELECT USING (
            id_infraestructura IN (
              SELECT i.id_infraestructura
              FROM modulo9.fn_infraestructuras_del_usuario(modulo1.f_uid()) i));
    """)
    op.execute("""
        CREATE POLICY lineas_base_ins ON modulo9.lineas_base_vision
          FOR INSERT WITH CHECK (
            id_infraestructura IN (
              SELECT i.id_infraestructura
              FROM modulo9.fn_infraestructuras_del_usuario(modulo1.f_uid()) i));
    """)
    op.execute("""
        CREATE POLICY lineas_base_sis ON modulo9.lineas_base_vision
          FOR ALL USING (modulo1.f_sistema()) WITH CHECK (modulo1.f_sistema());
    """)
    op.execute("ALTER TABLE modulo9.lineas_base_vision FORCE ROW LEVEL SECURITY;")

    # ── configuraciones_remotas (3 saltos: config → dispositivo → infra → finca)
    op.execute("""
        CREATE POLICY config_rem_sel ON modulo9.configuraciones_remotas
          FOR SELECT USING (
            id_dispositivo_iot IN (
              SELECT d.id_dispositivo_iot
              FROM modulo9.fn_dispositivos_del_usuario(modulo1.f_uid()) d));
    """)
    op.execute("""
        CREATE POLICY config_rem_ins ON modulo9.configuraciones_remotas
          FOR INSERT WITH CHECK (
            id_dispositivo_iot IN (
              SELECT d.id_dispositivo_iot
              FROM modulo9.fn_dispositivos_del_usuario(modulo1.f_uid()) d));
    """)
    op.execute("""
        CREATE POLICY config_rem_upd ON modulo9.configuraciones_remotas
          FOR UPDATE USING (
            id_dispositivo_iot IN (
              SELECT d.id_dispositivo_iot
              FROM modulo9.fn_dispositivos_del_usuario(modulo1.f_uid()) d))
          WITH CHECK (
            id_dispositivo_iot IN (
              SELECT d.id_dispositivo_iot
              FROM modulo9.fn_dispositivos_del_usuario(modulo1.f_uid()) d));
    """)
    op.execute("""
        CREATE POLICY config_rem_sis ON modulo9.configuraciones_remotas
          FOR ALL USING (modulo1.f_sistema()) WITH CHECK (modulo1.f_sistema());
    """)
    op.execute("ALTER TABLE modulo9.configuraciones_remotas FORCE ROW LEVEL SECURITY;")

    # ================================================================
    # 5. AUDITORÍA POR CADENA (read + insert, sin update/delete)
    # ================================================================

    # auditorias_infraestructuras (2 saltos)
    op.execute("""
        CREATE POLICY audit_infra_sel ON modulo9.auditorias_infraestructuras
          FOR SELECT USING (
            id_infraestructura IN (
              SELECT i.id_infraestructura
              FROM modulo9.fn_infraestructuras_del_usuario(modulo1.f_uid()) i));
    """)
    op.execute("""
        CREATE POLICY audit_infra_ins ON modulo9.auditorias_infraestructuras
          FOR INSERT WITH CHECK (
            id_infraestructura IN (
              SELECT i.id_infraestructura
              FROM modulo9.fn_infraestructuras_del_usuario(modulo1.f_uid()) i));
    """)
    op.execute("""
        CREATE POLICY audit_infra_sis ON modulo9.auditorias_infraestructuras
          FOR ALL USING (modulo1.f_sistema()) WITH CHECK (modulo1.f_sistema());
    """)
    op.execute("ALTER TABLE modulo9.auditorias_infraestructuras FORCE ROW LEVEL SECURITY;")

    # auditorias_dispositivos_iot (3 saltos)
    op.execute("""
        CREATE POLICY audit_disp_sel ON modulo9.auditorias_dispositivos_iot
          FOR SELECT USING (
            id_dispositivo_iot IN (
              SELECT d.id_dispositivo_iot
              FROM modulo9.fn_dispositivos_del_usuario(modulo1.f_uid()) d));
    """)
    op.execute("""
        CREATE POLICY audit_disp_ins ON modulo9.auditorias_dispositivos_iot
          FOR INSERT WITH CHECK (
            id_dispositivo_iot IN (
              SELECT d.id_dispositivo_iot
              FROM modulo9.fn_dispositivos_del_usuario(modulo1.f_uid()) d));
    """)
    op.execute("""
        CREATE POLICY audit_disp_sis ON modulo9.auditorias_dispositivos_iot
          FOR ALL USING (modulo1.f_sistema()) WITH CHECK (modulo1.f_sistema());
    """)
    op.execute("ALTER TABLE modulo9.auditorias_dispositivos_iot FORCE ROW LEVEL SECURITY;")

    # auditorias_sensores_areas (3 saltos via sensores_areas_asociadas)
    op.execute("""
        CREATE POLICY audit_sens_area_sel ON modulo9.auditorias_sensores_areas
          FOR SELECT USING (
            id_sensores_area_asociada IN (
              SELECT sa.id_sensores_area_asociada
              FROM modulo9.sensores_areas_asociadas sa
              WHERE sa.id_infraestructura IN (
                SELECT i.id_infraestructura
                FROM modulo9.fn_infraestructuras_del_usuario(modulo1.f_uid()) i)));
    """)
    op.execute("""
        CREATE POLICY audit_sens_area_ins ON modulo9.auditorias_sensores_areas
          FOR INSERT WITH CHECK (
            id_sensores_area_asociada IN (
              SELECT sa.id_sensores_area_asociada
              FROM modulo9.sensores_areas_asociadas sa
              WHERE sa.id_infraestructura IN (
                SELECT i.id_infraestructura
                FROM modulo9.fn_infraestructuras_del_usuario(modulo1.f_uid()) i)));
    """)
    op.execute("""
        CREATE POLICY audit_sens_area_sis ON modulo9.auditorias_sensores_areas
          FOR ALL USING (modulo1.f_sistema()) WITH CHECK (modulo1.f_sistema());
    """)
    op.execute("ALTER TABLE modulo9.auditorias_sensores_areas FORCE ROW LEVEL SECURITY;")

    # auditorias_calibraciones (4 saltos via calibraciones)
    op.execute("""
        CREATE POLICY audit_calib_sel ON modulo9.auditorias_calibraciones
          FOR SELECT USING (
            id_calibracion IN (
              SELECT c.id_calibracion FROM modulo9.calibraciones c
              WHERE c.id_dispositivo_iot IN (
                SELECT d.id_dispositivo_iot
                FROM modulo9.fn_dispositivos_del_usuario(modulo1.f_uid()) d)));
    """)
    op.execute("""
        CREATE POLICY audit_calib_ins ON modulo9.auditorias_calibraciones
          FOR INSERT WITH CHECK (
            id_calibracion IN (
              SELECT c.id_calibracion FROM modulo9.calibraciones c
              WHERE c.id_dispositivo_iot IN (
                SELECT d.id_dispositivo_iot
                FROM modulo9.fn_dispositivos_del_usuario(modulo1.f_uid()) d)));
    """)
    op.execute("""
        CREATE POLICY audit_calib_sis ON modulo9.auditorias_calibraciones
          FOR ALL USING (modulo1.f_sistema()) WITH CHECK (modulo1.f_sistema());
    """)
    op.execute("ALTER TABLE modulo9.auditorias_calibraciones FORCE ROW LEVEL SECURITY;")

    # ================================================================
    # 6. AUDITORÍA DE CATÁLOGO (sin finca; lectura autenticada)
    # ================================================================
    for t in _AUDIT_CATALOGO:
        op.execute(f"""
            CREATE POLICY {t}_sel ON modulo9.{t}
              FOR SELECT USING (modulo1.f_auth() OR modulo1.f_sistema());
        """)
        op.execute(f"""
            CREATE POLICY {t}_ins ON modulo9.{t}
              FOR INSERT WITH CHECK (modulo1.f_auth() OR modulo1.f_sistema());
        """)
        op.execute(f"""
            CREATE POLICY {t}_sis ON modulo9.{t}
              FOR ALL USING (modulo1.f_sistema()) WITH CHECK (modulo1.f_sistema());
        """)
        op.execute(f"ALTER TABLE modulo9.{t} FORCE ROW LEVEL SECURITY;")

    # ================================================================
    # 7. AUDITORÍA PROPIA DEL USUARIO
    # ================================================================
    for t in _AUDIT_PROPIA:
        op.execute(f"""
            CREATE POLICY {t}_own_sel ON modulo9.{t}
              FOR SELECT USING (id_usuario = modulo1.f_uid() OR modulo1.f_sistema());
        """)
        op.execute(f"""
            CREATE POLICY {t}_own_ins ON modulo9.{t}
              FOR INSERT WITH CHECK (id_usuario = modulo1.f_uid() OR modulo1.f_sistema());
        """)
        op.execute(f"""
            CREATE POLICY {t}_sis ON modulo9.{t}
              FOR ALL USING (modulo1.f_sistema()) WITH CHECK (modulo1.f_sistema());
        """)
        op.execute(f"ALTER TABLE modulo9.{t} FORCE ROW LEVEL SECURITY;")

    # ================================================================
    # 8. CONFIG GLOBAL (lectura autenticada, escritura restringida)
    # ================================================================

    # configuraciones_globales: solo Admin escribe
    op.execute("""
        CREATE POLICY cfg_global_sel ON modulo9.configuraciones_globales
          FOR SELECT USING (modulo1.f_auth() OR modulo1.f_sistema());
    """)
    op.execute("""
        CREATE POLICY cfg_global_w ON modulo9.configuraciones_globales
          FOR ALL USING (modulo1.f_sistema()) WITH CHECK (modulo1.f_sistema());
    """)
    op.execute("ALTER TABLE modulo9.configuraciones_globales FORCE ROW LEVEL SECURITY;")

    # umbrales_ambientales: lectura autenticada, escritura Admin/Vet
    op.execute("""
        CREATE POLICY umbrales_sel ON modulo9.umbrales_ambientales
          FOR SELECT USING (modulo1.f_auth() OR modulo1.f_sistema());
    """)
    op.execute("""
        CREATE POLICY umbrales_ins ON modulo9.umbrales_ambientales
          FOR INSERT WITH CHECK (modulo1.f_auth() OR modulo1.f_sistema());
    """)
    op.execute("""
        CREATE POLICY umbrales_upd ON modulo9.umbrales_ambientales
          FOR UPDATE USING (modulo1.f_auth() OR modulo1.f_sistema())
          WITH CHECK (modulo1.f_auth() OR modulo1.f_sistema());
    """)
    op.execute("""
        CREATE POLICY umbrales_sis ON modulo9.umbrales_ambientales
          FOR ALL USING (modulo1.f_sistema()) WITH CHECK (modulo1.f_sistema());
    """)
    op.execute("ALTER TABLE modulo9.umbrales_ambientales FORCE ROW LEVEL SECURITY;")

    # niveles_alerta_ambientales: hijo de umbrales, mismo patrón
    op.execute("""
        CREATE POLICY niveles_sel ON modulo9.niveles_alerta_ambientales
          FOR SELECT USING (modulo1.f_auth() OR modulo1.f_sistema());
    """)
    op.execute("""
        CREATE POLICY niveles_ins ON modulo9.niveles_alerta_ambientales
          FOR INSERT WITH CHECK (modulo1.f_auth() OR modulo1.f_sistema());
    """)
    op.execute("""
        CREATE POLICY niveles_upd ON modulo9.niveles_alerta_ambientales
          FOR UPDATE USING (modulo1.f_auth() OR modulo1.f_sistema())
          WITH CHECK (modulo1.f_auth() OR modulo1.f_sistema());
    """)
    op.execute("""
        CREATE POLICY niveles_sis ON modulo9.niveles_alerta_ambientales
          FOR ALL USING (modulo1.f_sistema()) WITH CHECK (modulo1.f_sistema());
    """)
    op.execute("ALTER TABLE modulo9.niveles_alerta_ambientales FORCE ROW LEVEL SECURITY;")

    # plantillas: lectura autenticada, escritura por creador
    op.execute("""
        CREATE POLICY plant_sel ON modulo9.plantillas
          FOR SELECT USING (modulo1.f_auth() OR modulo1.f_sistema());
    """)
    op.execute("""
        CREATE POLICY plant_ins ON modulo9.plantillas
          FOR INSERT WITH CHECK (id_usuario = modulo1.f_uid() OR modulo1.f_sistema());
    """)
    op.execute("""
        CREATE POLICY plant_upd ON modulo9.plantillas
          FOR UPDATE USING (id_usuario = modulo1.f_uid() OR modulo1.f_sistema())
          WITH CHECK (id_usuario = modulo1.f_uid() OR modulo1.f_sistema());
    """)
    op.execute("""
        CREATE POLICY plant_sis ON modulo9.plantillas
          FOR ALL USING (modulo1.f_sistema()) WITH CHECK (modulo1.f_sistema());
    """)
    op.execute("ALTER TABLE modulo9.plantillas FORCE ROW LEVEL SECURITY;")

    # ================================================================
    # 9. ESTADÍSTICAS
    # ================================================================
    op.execute("ANALYZE modulo9.fincas;")
    op.execute("ANALYZE modulo9.infraestructuras;")
    op.execute("ANALYZE modulo9.dispositivos_iot;")
    op.execute("ANALYZE modulo9.sensores;")
    op.execute("ANALYZE modulo9.usuarios_fincas;")


def downgrade() -> None:

    # 1. Borrar funciones helper
    op.execute("DROP FUNCTION IF EXISTS modulo9.fn_sensores_del_usuario(bigint);")
    op.execute("DROP FUNCTION IF EXISTS modulo9.fn_dispositivos_del_usuario(bigint);")

    # 2. Borrar todas las políticas creadas en modulo9
    #    (excepto las de fincas e infraestructuras que son de F4)
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

    # 3. Quitar FORCE RLS de las tablas que lo recibieron
    op.execute("""
        DO $$ DECLARE t text; BEGIN
          FOR t IN
            SELECT tablename FROM pg_tables WHERE schemaname = 'modulo9'
              AND tablename NOT IN ('fincas', 'infraestructuras')
          LOOP
            EXECUTE format('ALTER TABLE modulo9.%I NO FORCE ROW LEVEL SECURITY', t);
          END LOOP; END $$;
    """)

    # 4. Restaurar RLS habilitado en catálogos (estado original del DDL)
    for t in _CATALOGOS:
        op.execute(f"ALTER TABLE modulo9.{t} ENABLE ROW LEVEL SECURITY;")

    # 5. Restaurar RLS en las demás tablas (estado original del DDL)
    for grupo in [_PROPIAS_USUARIO, _AUDIT_CATALOGO, _AUDIT_PROPIA]:
        for t in grupo:
            op.execute(f"ALTER TABLE modulo9.{t} ENABLE ROW LEVEL SECURITY;")

    for t in [
        'identidad_visuales', 'auditorias_fincas', 'dispositivos_iot',
        'sensores', 'sensores_areas_asociadas', 'calibraciones',
        'calibraciones_vision', 'lineas_base_vision', 'configuraciones_remotas',
        'auditorias_infraestructuras', 'auditorias_dispositivos_iot',
        'auditorias_sensores_areas', 'auditorias_calibraciones',
        'configuraciones_globales', 'umbrales_ambientales',
        'niveles_alerta_ambientales', 'plantillas',
    ]:
        op.execute(f"ALTER TABLE modulo9.{t} ENABLE ROW LEVEL SECURITY;")