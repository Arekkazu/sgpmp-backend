"""RLS MODULO9

Revision ID: 5243bbbb28de
Revises: 1147428cd8fb
Create Date: 2026-09-18 18:03:09.482238

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5243bbbb28de'
down_revision: Union[str, Sequence[str], None] = '1147428cd8fb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # =========================================================
    # 1. Activar RLS en todas las tablas de modulo9 (sin politicas aun)
    # =========================================================
    tablas_modulo9 = [
        "aplicaciones_plantillas", "auditorias_calibraciones",
        "auditorias_ciclos_biologicos", "auditorias_configuraciones_globales",
        "auditorias_dispositivos_iot", "auditorias_especies",
        "auditorias_fincas", "auditorias_infraestructuras",
        "auditorias_metricas_produccion", "auditorias_patologias",
        "auditorias_plantillas", "auditorias_sensores_areas",
        "auditorias_umbrales_ambientales", "auditorias_visuales",
        "calibraciones", "ciclos_biologicos", "ciclos_productivos",
        "ciclos_productivos_biologicos", "compatibilidad_sensores_especies",
        "compatibilidades_tipo_area_especie", "configuraciones_globales",
        "configuraciones_remotas", "dashboard_layouts",
        "dashboard_layouts_default", "dispositivos_iot", "especies",
        "especies_patologias", "fincas", "gestion_especies",
        "identidad_visuales", "infraestructuras", "intentos_fallidos",
        "metricas_ciclo_productivo", "metricas_produccion",
        "niveles_alerta_ambientales", "patologias", "plantillas",
        "preferencias_idiomas", "rangos_calibracion", "sensores",
        "sensores_areas_asociadas", "temas_visuales", "tipos_area",
        "tipos_dispositivo_iot", "umbrales_ambientales",
        "variables_ambientales", "widgets",
    ]
    for tabla in tablas_modulo9:
        op.execute(f"ALTER TABLE modulo9.{tabla} ENABLE ROW LEVEL SECURITY;")

    # =========================================================
    # 2. Tablas de auditoria (patron uniforme): SELECT solo Administrador,
    #    INSERT abierto (el sistema genera el registro), sin UPDATE/DELETE.
    # =========================================================
    tablas_auditoria = [
        "auditorias_calibraciones", "auditorias_ciclos_biologicos",
        "auditorias_configuraciones_globales", "auditorias_dispositivos_iot",
        "auditorias_especies", "auditorias_fincas",
        "auditorias_infraestructuras", "auditorias_metricas_produccion",
        "auditorias_patologias", "auditorias_plantillas",
        "auditorias_sensores_areas", "auditorias_umbrales_ambientales",
        "auditorias_visuales", "gestion_especies",
    ]
    for tabla in tablas_auditoria:
        op.execute(f"""
            CREATE POLICY pol_{tabla}_select ON modulo9.{tabla}
              FOR SELECT
              USING (app_ctx.current_role() = 'Administrador');
        """)
        op.execute(f"""
            CREATE POLICY pol_{tabla}_insert ON modulo9.{tabla}
              FOR INSERT
              WITH CHECK (true);
        """)
    # Sin politica de UPDATE/DELETE en ninguna de estas: bloqueado para todos.

    # =========================================================
    # 3. especies (RF-15)
    # =========================================================
    op.execute("""
        CREATE POLICY pol_especies_select ON modulo9.especies
          FOR SELECT USING (true);
    """)
    op.execute("""
        CREATE POLICY pol_especies_insert ON modulo9.especies
          FOR INSERT
          WITH CHECK (app_ctx.current_role() = 'Administrador');
    """)
    op.execute("""
        CREATE POLICY pol_especies_update ON modulo9.especies
          FOR UPDATE
          USING (app_ctx.current_role() IN ('Administrador', 'Ingeniero de Campo'))
          WITH CHECK (app_ctx.current_role() IN ('Administrador', 'Ingeniero de Campo'));
    """)
    # Trigger: solo Administrador puede desactivar/reactivar (cambiar es_activo).
    op.execute("""
        CREATE OR REPLACE FUNCTION modulo9.fn_proteger_activo_especie()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
          IF NEW.es_activo IS DISTINCT FROM OLD.es_activo
             AND app_ctx.current_role() <> 'Administrador' THEN
            RAISE EXCEPTION 'Solo Administrador puede activar/desactivar especies (RF-15)';
          END IF;
          RETURN NEW;
        END;
        $$;
    """)
    op.execute("""
        CREATE TRIGGER trg_proteger_activo_especie
        BEFORE UPDATE ON modulo9.especies
        FOR EACH ROW
        EXECUTE FUNCTION modulo9.fn_proteger_activo_especie();
    """)

    # =========================================================
    # 4. ciclos_biologicos / especies_patologias / metricas_produccion (RF-16)
    # =========================================================
    for tabla in ["ciclos_biologicos", "especies_patologias", "metricas_produccion"]:
        op.execute(f"""
            CREATE POLICY pol_{tabla}_select ON modulo9.{tabla}
              FOR SELECT USING (true);
        """)
        op.execute(f"""
            CREATE POLICY pol_{tabla}_insert ON modulo9.{tabla}
              FOR INSERT
              WITH CHECK (app_ctx.current_role() IN ('Administrador', 'Veterinario'));
        """)
        op.execute(f"""
            CREATE POLICY pol_{tabla}_update ON modulo9.{tabla}
              FOR UPDATE
              USING (app_ctx.current_role() IN ('Administrador', 'Veterinario'))
              WITH CHECK (app_ctx.current_role() IN ('Administrador', 'Veterinario'));
        """)

    # =========================================================
    # 5. patologias (catalogo, RF-16 / RF-64: es_base inmutable)
    # =========================================================
    op.execute("""
        CREATE POLICY pol_patologias_select ON modulo9.patologias
          FOR SELECT USING (true);
    """)
    op.execute("""
        CREATE POLICY pol_patologias_insert ON modulo9.patologias
          FOR INSERT
          WITH CHECK (app_ctx.current_role() IN ('Administrador', 'Veterinario'));
    """)
    op.execute("""
        CREATE POLICY pol_patologias_update ON modulo9.patologias
          FOR UPDATE
          USING (
            app_ctx.current_role() IN ('Administrador', 'Veterinario')
            AND es_base = false
          )
          WITH CHECK (
            app_ctx.current_role() IN ('Administrador', 'Veterinario')
            AND es_base = false
          );
    """)
    # Sin politica de DELETE: no se permite eliminacion fisica (RF-16).

    # =========================================================
    # 6. umbrales_ambientales / niveles_alerta_ambientales (RF-17)
    # =========================================================
    for tabla in ["umbrales_ambientales", "niveles_alerta_ambientales"]:
        op.execute(f"""
            CREATE POLICY pol_{tabla}_select ON modulo9.{tabla}
              FOR SELECT USING (true);
        """)
        op.execute(f"""
            CREATE POLICY pol_{tabla}_insert ON modulo9.{tabla}
              FOR INSERT
              WITH CHECK (app_ctx.current_role() IN ('Administrador', 'Veterinario'));
        """)
        op.execute(f"""
            CREATE POLICY pol_{tabla}_update ON modulo9.{tabla}
              FOR UPDATE
              USING (app_ctx.current_role() IN ('Administrador', 'Veterinario'))
              WITH CHECK (app_ctx.current_role() IN ('Administrador', 'Veterinario'));
        """)

    # =========================================================
    # 7. variables_ambientales (RF-17: catalogo exclusivo del sistema)
    # =========================================================
    op.execute("""
        CREATE POLICY pol_variables_ambientales_select ON modulo9.variables_ambientales
          FOR SELECT USING (true);
    """)
    # Sin politica de INSERT/UPDATE/DELETE para rol_app: gestionado solo por
    # migracion/DBA, ningun usuario final puede modificarlo (RF-17).

    # =========================================================
    # 8. configuraciones_globales (RF-18)
    # =========================================================
    op.execute("""
        CREATE POLICY pol_config_globales_select ON modulo9.configuraciones_globales
          FOR SELECT USING (true);
    """)
    op.execute("""
        CREATE POLICY pol_config_globales_insert ON modulo9.configuraciones_globales
          FOR INSERT
          WITH CHECK (
            app_ctx.current_role() = 'Administrador'
            AND id_usuario = app_ctx.current_user_id()
          );
    """)
    op.execute("""
        CREATE POLICY pol_config_globales_update ON modulo9.configuraciones_globales
          FOR UPDATE
          USING (app_ctx.current_role() = 'Administrador')
          WITH CHECK (app_ctx.current_role() = 'Administrador');
    """)

    # =========================================================
    # 9. fincas (RF-19)
    # =========================================================
    op.execute("""
        CREATE POLICY pol_fincas_select ON modulo9.fincas
          FOR SELECT
          USING (
            app_ctx.current_role() = 'Administrador'
            OR id_usuario = app_ctx.current_user_id()
          );
    """)
    op.execute("""
        CREATE POLICY pol_fincas_insert ON modulo9.fincas
          FOR INSERT
          WITH CHECK (app_ctx.current_role() = 'Administrador');
    """)
    op.execute("""
        CREATE POLICY pol_fincas_update ON modulo9.fincas
          FOR UPDATE
          USING (app_ctx.current_role() = 'Administrador')
          WITH CHECK (app_ctx.current_role() = 'Administrador');
    """)

    # =========================================================
    # 10. infraestructuras (RF-20)
    # =========================================================
    op.execute("""
        CREATE POLICY pol_infraestructuras_select ON modulo9.infraestructuras
          FOR SELECT
          USING (
            app_ctx.current_role() = 'Administrador'
            OR id_finca IN (
              SELECT id_finca FROM modulo9.fincas WHERE id_usuario = app_ctx.current_user_id()
            )
          );
    """)
    op.execute("""
        CREATE POLICY pol_infraestructuras_insert ON modulo9.infraestructuras
          FOR INSERT
          WITH CHECK (app_ctx.current_role() = 'Administrador');
    """)
    op.execute("""
        CREATE POLICY pol_infraestructuras_update ON modulo9.infraestructuras
          FOR UPDATE
          USING (app_ctx.current_role() = 'Administrador')
          WITH CHECK (app_ctx.current_role() = 'Administrador');
    """)

    # =========================================================
    # 11. tipos_area (catalogo RF-20)
    # =========================================================
    op.execute("""
        CREATE POLICY pol_tipos_area_select ON modulo9.tipos_area
          FOR SELECT USING (true);
    """)
    op.execute("""
        CREATE POLICY pol_tipos_area_insert ON modulo9.tipos_area
          FOR INSERT
          WITH CHECK (app_ctx.current_role() = 'Administrador');
    """)
    op.execute("""
        CREATE POLICY pol_tipos_area_update ON modulo9.tipos_area
          FOR UPDATE
          USING (app_ctx.current_role() = 'Administrador')
          WITH CHECK (app_ctx.current_role() = 'Administrador');
    """)

    # =========================================================
    # 12. dispositivos_iot (RF-21) / sensores / sensores_areas_asociadas (RF-22)
    #     / configuraciones_remotas (RF-23)
    # =========================================================
    for tabla in ["dispositivos_iot", "sensores", "sensores_areas_asociadas", "configuraciones_remotas"]:
        op.execute(f"""
            CREATE POLICY pol_{tabla}_select ON modulo9.{tabla}
              FOR SELECT
              USING (app_ctx.current_role() IN ('Administrador', 'Ingeniero de Campo'));
        """)
        op.execute(f"""
            CREATE POLICY pol_{tabla}_insert ON modulo9.{tabla}
              FOR INSERT
              WITH CHECK (app_ctx.current_role() IN ('Administrador', 'Ingeniero de Campo'));
        """)
        op.execute(f"""
            CREATE POLICY pol_{tabla}_update ON modulo9.{tabla}
              FOR UPDATE
              USING (app_ctx.current_role() IN ('Administrador', 'Ingeniero de Campo'))
              WITH CHECK (app_ctx.current_role() IN ('Administrador', 'Ingeniero de Campo'));
        """)

    # =========================================================
    # 13. tipos_dispositivo_iot (catalogo, sin RF explicito)
    # =========================================================
    op.execute("""
        CREATE POLICY pol_tipos_dispositivo_iot_select ON modulo9.tipos_dispositivo_iot
          FOR SELECT USING (true);
    """)
    op.execute("""
        CREATE POLICY pol_tipos_dispositivo_iot_insert ON modulo9.tipos_dispositivo_iot
          FOR INSERT
          WITH CHECK (app_ctx.current_role() = 'Administrador');
    """)
    op.execute("""
        CREATE POLICY pol_tipos_dispositivo_iot_update ON modulo9.tipos_dispositivo_iot
          FOR UPDATE
          USING (app_ctx.current_role() = 'Administrador')
          WITH CHECK (app_ctx.current_role() = 'Administrador');
    """)

    # =========================================================
    # 14. calibraciones (RF-24) / rangos_calibracion (catalogo)
    # =========================================================
    op.execute("""
        CREATE POLICY pol_calibraciones_select ON modulo9.calibraciones
          FOR SELECT
          USING (app_ctx.current_role() IN ('Administrador', 'Ingeniero de Campo'));
    """)
    op.execute("""
        CREATE POLICY pol_calibraciones_insert ON modulo9.calibraciones
          FOR INSERT
          WITH CHECK (
            app_ctx.current_role() IN ('Administrador', 'Ingeniero de Campo')
            AND id_usuario = app_ctx.current_user_id()
          );
    """)
    # Sin politica de UPDATE: la calibracion es un registro historico, no se edita.

    op.execute("""
        CREATE POLICY pol_rangos_calibracion_select ON modulo9.rangos_calibracion
          FOR SELECT USING (true);
    """)
    op.execute("""
        CREATE POLICY pol_rangos_calibracion_insert ON modulo9.rangos_calibracion
          FOR INSERT
          WITH CHECK (app_ctx.current_role() = 'Administrador');
    """)
    op.execute("""
        CREATE POLICY pol_rangos_calibracion_update ON modulo9.rangos_calibracion
          FOR UPDATE
          USING (app_ctx.current_role() = 'Administrador')
          WITH CHECK (app_ctx.current_role() = 'Administrador');
    """)

    # =========================================================
    # 15. identidad_visuales (RF-26)
    # =========================================================
    op.execute("""
        CREATE POLICY pol_identidad_visuales_select ON modulo9.identidad_visuales
          FOR SELECT USING (true);
    """)
    op.execute("""
        CREATE POLICY pol_identidad_visuales_insert ON modulo9.identidad_visuales
          FOR INSERT
          WITH CHECK (
            app_ctx.current_role() = 'Administrador'
            AND id_usuario = app_ctx.current_user_id()
          );
    """)
    op.execute("""
        CREATE POLICY pol_identidad_visuales_update ON modulo9.identidad_visuales
          FOR UPDATE
          USING (app_ctx.current_role() = 'Administrador')
          WITH CHECK (app_ctx.current_role() = 'Administrador');
    """)

    # =========================================================
    # 16. temas_visuales (RF-27)
    # =========================================================
    op.execute("""
        CREATE POLICY pol_temas_visuales_select ON modulo9.temas_visuales
          FOR SELECT
          USING (
            id_usuario = app_ctx.current_user_id()
            OR es_global = true
            OR app_ctx.current_role() = 'Administrador'
          );
    """)
    op.execute("""
        CREATE POLICY pol_temas_visuales_insert ON modulo9.temas_visuales
          FOR INSERT
          WITH CHECK (
            (id_usuario = app_ctx.current_user_id() AND es_global = false)
            OR (app_ctx.current_role() = 'Administrador' AND es_global = true)
          );
    """)
    op.execute("""
        CREATE POLICY pol_temas_visuales_update ON modulo9.temas_visuales
          FOR UPDATE
          USING (
            (id_usuario = app_ctx.current_user_id() AND es_global = false)
            OR (app_ctx.current_role() = 'Administrador' AND es_global = true)
          )
          WITH CHECK (
            (id_usuario = app_ctx.current_user_id() AND es_global = false)
            OR (app_ctx.current_role() = 'Administrador' AND es_global = true)
          );
    """)

    # =========================================================
    # 17. preferencias_idiomas (RF-29) - estrictamente personal
    # =========================================================
    op.execute("""
        CREATE POLICY pol_preferencias_idiomas_all ON modulo9.preferencias_idiomas
          FOR ALL
          USING (id_usuario = app_ctx.current_user_id())
          WITH CHECK (id_usuario = app_ctx.current_user_id());
    """)

    # =========================================================
    # 18. dashboard_layouts (RF-28) - estrictamente personal
    # =========================================================
    op.execute("""
        CREATE POLICY pol_dashboard_layouts_all ON modulo9.dashboard_layouts
          FOR ALL
          USING (id_usuario = app_ctx.current_user_id())
          WITH CHECK (id_usuario = app_ctx.current_user_id());
    """)

    # =========================================================
    # 19. dashboard_layouts_default (defaults por rol) / widgets (catalogo)
    # =========================================================
    op.execute("""
        CREATE POLICY pol_dashboard_layouts_default_select ON modulo9.dashboard_layouts_default
          FOR SELECT USING (true);
    """)
    op.execute("""
        CREATE POLICY pol_dashboard_layouts_default_insert ON modulo9.dashboard_layouts_default
          FOR INSERT
          WITH CHECK (app_ctx.current_role() = 'Administrador');
    """)
    op.execute("""
        CREATE POLICY pol_dashboard_layouts_default_update ON modulo9.dashboard_layouts_default
          FOR UPDATE
          USING (app_ctx.current_role() = 'Administrador')
          WITH CHECK (app_ctx.current_role() = 'Administrador');
    """)

    op.execute("""
        CREATE POLICY pol_widgets_select ON modulo9.widgets
          FOR SELECT USING (true);
    """)
    op.execute("""
        CREATE POLICY pol_widgets_insert ON modulo9.widgets
          FOR INSERT
          WITH CHECK (app_ctx.current_role() = 'Administrador');
    """)
    op.execute("""
        CREATE POLICY pol_widgets_update ON modulo9.widgets
          FOR UPDATE
          USING (app_ctx.current_role() = 'Administrador')
          WITH CHECK (app_ctx.current_role() = 'Administrador');
    """)

    # =========================================================
    # 20. plantillas (RF-30/31) / aplicaciones_plantillas (RF-32)
    # =========================================================
    op.execute("""
        CREATE POLICY pol_plantillas_select ON modulo9.plantillas
          FOR SELECT
          USING (app_ctx.current_role() IN ('Administrador', 'Ingeniero de Campo'));
    """)
    op.execute("""
        CREATE POLICY pol_plantillas_insert ON modulo9.plantillas
          FOR INSERT
          WITH CHECK (
            app_ctx.current_role() IN ('Administrador', 'Ingeniero de Campo')
            AND id_usuario = app_ctx.current_user_id()
          );
    """)
    # Sin politica de UPDATE: las plantillas son inmutables (RF-31), toda
    # modificacion genera una fila nueva con version incrementada.

    op.execute("""
        CREATE POLICY pol_aplicaciones_plantillas_select ON modulo9.aplicaciones_plantillas
          FOR SELECT
          USING (app_ctx.current_role() IN ('Administrador', 'Ingeniero de Campo'));
    """)
    op.execute("""
        CREATE POLICY pol_aplicaciones_plantillas_insert ON modulo9.aplicaciones_plantillas
          FOR INSERT
          WITH CHECK (
            app_ctx.current_role() IN ('Administrador', 'Ingeniero de Campo')
            AND id_usuario = app_ctx.current_user_id()
          );
    """)
    # Sin politica de UPDATE/DELETE: registro de intento, inmutable.

    # =========================================================
    # 21. ciclos_productivos / ciclos_productivos_biologicos /
    #     metricas_ciclo_productivo - sin RF explicito en este lote,
    #     politica inferida por analogia a ciclos_biologicos (RF-16)
    # =========================================================
    for tabla in ["ciclos_productivos", "ciclos_productivos_biologicos", "metricas_ciclo_productivo"]:
        op.execute(f"""
            CREATE POLICY pol_{tabla}_select ON modulo9.{tabla}
              FOR SELECT USING (true);
        """)
        op.execute(f"""
            CREATE POLICY pol_{tabla}_insert ON modulo9.{tabla}
              FOR INSERT
              WITH CHECK (app_ctx.current_role() IN ('Administrador', 'Veterinario'));
        """)
        op.execute(f"""
            CREATE POLICY pol_{tabla}_update ON modulo9.{tabla}
              FOR UPDATE
              USING (app_ctx.current_role() IN ('Administrador', 'Veterinario'))
              WITH CHECK (app_ctx.current_role() IN ('Administrador', 'Veterinario'));
        """)

    # =========================================================
    # 22. compatibilidad_sensores_especies / compatibilidades_tipo_area_especie
    #     (RF-49, no incluido en este lote) / intentos_fallidos (pendiente)
    # =========================================================
    # Sin ninguna politica: con RLS activo y cero politicas, rol_app queda
    # bloqueado por defecto hasta que se defina su caso de uso.


def downgrade():
    politicas_por_tabla = {
        "auditorias_calibraciones": ["select", "insert"],
        "auditorias_ciclos_biologicos": ["select", "insert"],
        "auditorias_configuraciones_globales": ["select", "insert"],
        "auditorias_dispositivos_iot": ["select", "insert"],
        "auditorias_especies": ["select", "insert"],
        "auditorias_fincas": ["select", "insert"],
        "auditorias_infraestructuras": ["select", "insert"],
        "auditorias_metricas_produccion": ["select", "insert"],
        "auditorias_patologias": ["select", "insert"],
        "auditorias_plantillas": ["select", "insert"],
        "auditorias_sensores_areas": ["select", "insert"],
        "auditorias_umbrales_ambientales": ["select", "insert"],
        "auditorias_visuales": ["select", "insert"],
        "gestion_especies": ["select", "insert"],
        "especies": ["select", "insert", "update"],
        "ciclos_biologicos": ["select", "insert", "update"],
        "especies_patologias": ["select", "insert", "update"],
        "metricas_produccion": ["select", "insert", "update"],
        "patologias": ["select", "insert", "update"],
        "umbrales_ambientales": ["select", "insert", "update"],
        "niveles_alerta_ambientales": ["select", "insert", "update"],
        "variables_ambientales": ["select"],
        "configuraciones_globales": ["select", "insert", "update"],
        "fincas": ["select", "insert", "update"],
        "infraestructuras": ["select", "insert", "update"],
        "tipos_area": ["select", "insert", "update"],
        "dispositivos_iot": ["select", "insert", "update"],
        "sensores": ["select", "insert", "update"],
        "sensores_areas_asociadas": ["select", "insert", "update"],
        "configuraciones_remotas": ["select", "insert", "update"],
        "tipos_dispositivo_iot": ["select", "insert", "update"],
        "calibraciones": ["select", "insert"],
        "rangos_calibracion": ["select", "insert", "update"],
        "identidad_visuales": ["select", "insert", "update"],
        "temas_visuales": ["select", "insert", "update"],
        "preferencias_idiomas": ["all"],
        "dashboard_layouts": ["all"],
        "dashboard_layouts_default": ["select", "insert", "update"],
        "widgets": ["select", "insert", "update"],
        "plantillas": ["select", "insert"],
        "aplicaciones_plantillas": ["select", "insert"],
        "ciclos_productivos": ["select", "insert", "update"],
        "ciclos_productivos_biologicos": ["select", "insert", "update"],
        "metricas_ciclo_productivo": ["select", "insert", "update"],
    }
    for tabla, ops_list in politicas_por_tabla.items():
        for op_nombre in ops_list:
            op.execute(f"DROP POLICY IF EXISTS pol_{tabla}_{op_nombre} ON modulo9.{tabla};")

    op.execute("DROP TRIGGER IF EXISTS trg_proteger_activo_especie ON modulo9.especies;")
    op.execute("DROP FUNCTION IF EXISTS modulo9.fn_proteger_activo_especie();")

    tablas_modulo9 = [
        "aplicaciones_plantillas", "auditorias_calibraciones",
        "auditorias_ciclos_biologicos", "auditorias_configuraciones_globales",
        "auditorias_dispositivos_iot", "auditorias_especies",
        "auditorias_fincas", "auditorias_infraestructuras",
        "auditorias_metricas_produccion", "auditorias_patologias",
        "auditorias_plantillas", "auditorias_sensores_areas",
        "auditorias_umbrales_ambientales", "auditorias_visuales",
        "calibraciones", "ciclos_biologicos", "ciclos_productivos",
        "ciclos_productivos_biologicos", "compatibilidad_sensores_especies",
        "compatibilidades_tipo_area_especie", "configuraciones_globales",
        "configuraciones_remotas", "dashboard_layouts",
        "dashboard_layouts_default", "dispositivos_iot", "especies",
        "especies_patologias", "fincas", "gestion_especies",
        "identidad_visuales", "infraestructuras", "intentos_fallidos",
        "metricas_ciclo_productivo", "metricas_produccion",
        "niveles_alerta_ambientales", "patologias", "plantillas",
        "preferencias_idiomas", "rangos_calibracion", "sensores",
        "sensores_areas_asociadas", "temas_visuales", "tipos_area",
        "tipos_dispositivo_iot", "umbrales_ambientales",
        "variables_ambientales", "widgets",
    ]
    for tabla in tablas_modulo9:
        op.execute(f"ALTER TABLE modulo9.{tabla} DISABLE ROW LEVEL SECURITY;")