"""RLS MODULO1

Revision ID: 8d80fb56a30b
Revises: 1147428cd8fb
Create Date: 2026-09-18 17:06:50.868277

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8d80fb56a30b'
down_revision: Union[str, Sequence[str], None] = '1147428cd8fb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # =========================================================
    # 1. Funciones de contexto de sesion (compartidas entre modulos)
    # =========================================================
    op.execute("""
        CREATE SCHEMA IF NOT EXISTS app_ctx;
    """)

    op.execute("""
        CREATE OR REPLACE FUNCTION app_ctx.current_user_id()
        RETURNS bigint
        LANGUAGE sql
        STABLE
        AS $$
          SELECT NULLIF(current_setting('app.current_user_id', true), '')::bigint;
        $$;
    """)

    op.execute("""
        CREATE OR REPLACE FUNCTION app_ctx.current_role()
        RETURNS text
        LANGUAGE sql
        STABLE
        AS $$
          SELECT NULLIF(current_setting('app.current_role', true), '');
        $$;
    """)

    # =========================================================
    # 2. Trigger de proteccion: un usuario no puede cambiar su propio id_rol
    #    (RF-05). No es expresable como RLS puro porque requiere comparar
    #    OLD.id_rol vs NEW.id_rol sobre la misma fila.
    # =========================================================
    op.execute("""
        CREATE OR REPLACE FUNCTION modulo1.fn_prevenir_autocambio_rol()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
          IF OLD.id_usuario = app_ctx.current_user_id()
             AND NEW.id_rol IS DISTINCT FROM OLD.id_rol THEN
            RAISE EXCEPTION 'Un usuario no puede modificar su propio rol (RF-05)';
          END IF;
          RETURN NEW;
        END;
        $$;
    """)

    op.execute("""
        CREATE TRIGGER trg_prevenir_autocambio_rol
        BEFORE UPDATE ON modulo1.usuarios
        FOR EACH ROW
        EXECUTE FUNCTION modulo1.fn_prevenir_autocambio_rol();
    """)

    # =========================================================
    # 3. Activar RLS en todas las tablas de modulo1 (sin politicas aun)
    # =========================================================
    tablas_modulo1 = [
        "acciones", "cola_exportaciones_auditoria",
        "configuracion_batch_exportacion_auditoria", "credenciales_servicio",
        "cuentas_usuarios", "dispositivos_fcm",
        "ejecuciones_exportaciones_auditoria", "estados_cuentas",
        "eventos", "eventos_archivados", "gestiones_cuenta",
        "integridad_baseline", "intentos_anonimos_ip", "notificaciones",
        "notificaciones_canal", "permisos", "recursos", "roles",
        "sesiones", "tipos_eventos", "tokens", "usuarios",
    ]
    for tabla in tablas_modulo1:
        op.execute(f"ALTER TABLE modulo1.{tabla} ENABLE ROW LEVEL SECURITY;")

    # =========================================================
    # 4. Politicas RLS
    # =========================================================

    # ---- usuarios (RF-01, RF-05, RF-11, RF-13) ----
    op.execute("""
        CREATE POLICY pol_usuarios_select ON modulo1.usuarios
          FOR SELECT
          USING (
            id_usuario = app_ctx.current_user_id()
            OR app_ctx.current_role() = 'Administrador'
          );
    """)
    op.execute("""
        CREATE POLICY pol_usuarios_insert ON modulo1.usuarios
          FOR INSERT
          WITH CHECK (true);
    """)
    op.execute("""
        CREATE POLICY pol_usuarios_update ON modulo1.usuarios
          FOR UPDATE
          USING (
            id_usuario = app_ctx.current_user_id()
            OR app_ctx.current_role() = 'Administrador'
          )
          WITH CHECK (
            id_usuario = app_ctx.current_user_id()
            OR app_ctx.current_role() = 'Administrador'
          );
    """)

    # ---- cuentas_usuarios (RF-06) ----
    op.execute("""
        CREATE POLICY pol_cuentas_usuarios_select ON modulo1.cuentas_usuarios
          FOR SELECT
          USING (
            id_usuario = app_ctx.current_user_id()
            OR app_ctx.current_role() = 'Administrador'
          );
    """)
    op.execute("""
        CREATE POLICY pol_cuentas_usuarios_insert ON modulo1.cuentas_usuarios
          FOR INSERT
          WITH CHECK (true);
    """)
    op.execute("""
        CREATE POLICY pol_cuentas_usuarios_update ON modulo1.cuentas_usuarios
          FOR UPDATE
          USING (
            app_ctx.current_role() = 'Administrador'
            AND id_usuario <> app_ctx.current_user_id()
          )
          WITH CHECK (
            app_ctx.current_role() = 'Administrador'
            AND id_usuario <> app_ctx.current_user_id()
          );
    """)

    # ---- sesiones / tokens / dispositivos_fcm (RF-02) ----
    op.execute("""
        CREATE POLICY pol_sesiones_select ON modulo1.sesiones
          FOR SELECT
          USING (
            app_ctx.current_role() = 'Administrador'
            OR id_cuenta_usuario IN (
              SELECT id_cuenta_usuario FROM modulo1.cuentas_usuarios
              WHERE id_usuario = app_ctx.current_user_id()
            )
          );
    """)
    op.execute("""
        CREATE POLICY pol_sesiones_insert ON modulo1.sesiones
          FOR INSERT
          WITH CHECK (
            id_cuenta_usuario IN (
              SELECT id_cuenta_usuario FROM modulo1.cuentas_usuarios
              WHERE id_usuario = app_ctx.current_user_id()
            )
          );
    """)
    op.execute("""
        CREATE POLICY pol_sesiones_update_delete ON modulo1.sesiones
          FOR UPDATE
          USING (
            app_ctx.current_role() = 'Administrador'
            OR id_cuenta_usuario IN (
              SELECT id_cuenta_usuario FROM modulo1.cuentas_usuarios
              WHERE id_usuario = app_ctx.current_user_id()
            )
          )
          WITH CHECK (
            app_ctx.current_role() = 'Administrador'
            OR id_cuenta_usuario IN (
              SELECT id_cuenta_usuario FROM modulo1.cuentas_usuarios
              WHERE id_usuario = app_ctx.current_user_id()
            )
          );
    """)
    op.execute("""
        CREATE POLICY pol_sesiones_delete ON modulo1.sesiones
          FOR DELETE
          USING (
            app_ctx.current_role() = 'Administrador'
            OR id_cuenta_usuario IN (
              SELECT id_cuenta_usuario FROM modulo1.cuentas_usuarios
              WHERE id_usuario = app_ctx.current_user_id()
            )
          );
    """)

    op.execute("""
        CREATE POLICY pol_tokens_select ON modulo1.tokens
          FOR SELECT
          USING (
            app_ctx.current_role() = 'Administrador'
            OR id_sesion IN (
              SELECT s.id_sesion FROM modulo1.sesiones s
              JOIN modulo1.cuentas_usuarios c ON c.id_cuenta_usuario = s.id_cuenta_usuario
              WHERE c.id_usuario = app_ctx.current_user_id()
            )
          );
    """)
    op.execute("""
        CREATE POLICY pol_tokens_insert ON modulo1.tokens
          FOR INSERT
          WITH CHECK (true);
    """)
    op.execute("""
        CREATE POLICY pol_tokens_update ON modulo1.tokens
          FOR UPDATE
          USING (
            app_ctx.current_role() = 'Administrador'
            OR id_sesion IN (
              SELECT s.id_sesion FROM modulo1.sesiones s
              JOIN modulo1.cuentas_usuarios c ON c.id_cuenta_usuario = s.id_cuenta_usuario
              WHERE c.id_usuario = app_ctx.current_user_id()
            )
          )
          WITH CHECK (true);
    """)

    op.execute("""
        CREATE POLICY pol_dispositivos_fcm_all ON modulo1.dispositivos_fcm
          FOR ALL
          USING (
            id_usuario = app_ctx.current_user_id()
            OR app_ctx.current_role() = 'Administrador'
          )
          WITH CHECK (id_usuario = app_ctx.current_user_id());
    """)

    # ---- eventos / eventos_archivados / integridad_baseline (RF-10, inmutables) ----
    op.execute("""
        CREATE POLICY pol_eventos_select ON modulo1.eventos
          FOR SELECT
          USING (app_ctx.current_role() = 'Administrador');
    """)
    op.execute("""
        CREATE POLICY pol_eventos_insert ON modulo1.eventos
          FOR INSERT
          WITH CHECK (true);
    """)
    # Sin politica de UPDATE/DELETE en eventos: bloqueado para todos.

    op.execute("""
        CREATE POLICY pol_eventos_archivados_select ON modulo1.eventos_archivados
          FOR SELECT
          USING (app_ctx.current_role() = 'Administrador');
    """)
    # Sin politica de INSERT/UPDATE/DELETE: el archivado no lo hace rol_app.

    op.execute("""
        CREATE POLICY pol_integridad_baseline_select ON modulo1.integridad_baseline
          FOR SELECT
          USING (app_ctx.current_role() = 'Administrador');
    """)
    # Sin politica de escritura: la genera un proceso interno, no rol_app.

    # ---- gestiones_cuenta (RF-06) ----
    op.execute("""
        CREATE POLICY pol_gestiones_cuenta_select ON modulo1.gestiones_cuenta
          FOR SELECT
          USING (app_ctx.current_role() = 'Administrador');
    """)
    op.execute("""
        CREATE POLICY pol_gestiones_cuenta_insert ON modulo1.gestiones_cuenta
          FOR INSERT
          WITH CHECK (
            app_ctx.current_role() = 'Administrador'
            AND id_usuario_responsable = app_ctx.current_user_id()
          );
    """)

    # ---- notificaciones (RF-14) ----
    op.execute("""
        CREATE POLICY pol_notificaciones_select ON modulo1.notificaciones
          FOR SELECT
          USING (
            id_usuario = app_ctx.current_user_id()
            OR app_ctx.current_role() = 'Administrador'
          );
    """)
    op.execute("""
        CREATE POLICY pol_notificaciones_insert ON modulo1.notificaciones
          FOR INSERT
          WITH CHECK (true);
    """)
    op.execute("""
        CREATE POLICY pol_notificaciones_update ON modulo1.notificaciones
          FOR UPDATE
          USING (id_usuario = app_ctx.current_user_id())
          WITH CHECK (id_usuario = app_ctx.current_user_id());
    """)

    # ---- catalogos de lectura abierta ----
    op.execute("""
        CREATE POLICY pol_notificaciones_canal_select ON modulo1.notificaciones_canal
          FOR SELECT USING (true);
    """)
    op.execute("""
        CREATE POLICY pol_estados_cuentas_select ON modulo1.estados_cuentas
          FOR SELECT USING (true);
    """)
    op.execute("""
        CREATE POLICY pol_tipos_eventos_select ON modulo1.tipos_eventos
          FOR SELECT USING (true);
    """)
    op.execute("""
        CREATE POLICY pol_acciones_select ON modulo1.acciones
          FOR SELECT USING (true);
    """)
    op.execute("""
        CREATE POLICY pol_acciones_insert ON modulo1.acciones
          FOR INSERT
          WITH CHECK (app_ctx.current_role() = 'Administrador');
    """)

    # ---- roles / recursos / permisos (RF-03, RF-04) ----
    op.execute("""
        CREATE POLICY pol_roles_select ON modulo1.roles
          FOR SELECT
          USING (app_ctx.current_role() = 'Administrador');
    """)
    op.execute("""
        CREATE POLICY pol_roles_insert ON modulo1.roles
          FOR INSERT
          WITH CHECK (app_ctx.current_role() = 'Administrador');
    """)
    op.execute("""
        CREATE POLICY pol_roles_update ON modulo1.roles
          FOR UPDATE
          USING (app_ctx.current_role() = 'Administrador')
          WITH CHECK (app_ctx.current_role() = 'Administrador');
    """)
    op.execute("""
        CREATE POLICY pol_roles_delete ON modulo1.roles
          FOR DELETE
          USING (
            app_ctx.current_role() = 'Administrador'
            AND es_protegido = false
          );
    """)

    op.execute("""
        CREATE POLICY pol_recursos_all ON modulo1.recursos
          FOR ALL
          USING (app_ctx.current_role() = 'Administrador')
          WITH CHECK (app_ctx.current_role() = 'Administrador');
    """)

    op.execute("""
        CREATE POLICY pol_permisos_all ON modulo1.permisos
          FOR ALL
          USING (app_ctx.current_role() = 'Administrador')
          WITH CHECK (app_ctx.current_role() = 'Administrador');
    """)

    # ---- procesos de exportacion de auditoria ----
    op.execute("""
        CREATE POLICY pol_cola_export_select ON modulo1.cola_exportaciones_auditoria
          FOR SELECT
          USING (app_ctx.current_role() = 'Administrador');
    """)
    op.execute("""
        CREATE POLICY pol_cola_export_insert ON modulo1.cola_exportaciones_auditoria
          FOR INSERT
          WITH CHECK (
            app_ctx.current_role() = 'Administrador'
            AND id_usuario_solicitante = app_ctx.current_user_id()
          );
    """)

    op.execute("""
        CREATE POLICY pol_ejecuciones_export_select ON modulo1.ejecuciones_exportaciones_auditoria
          FOR SELECT
          USING (app_ctx.current_role() = 'Administrador');
    """)

    op.execute("""
        CREATE POLICY pol_config_batch_export_all ON modulo1.configuracion_batch_exportacion_auditoria
          FOR ALL
          USING (app_ctx.current_role() = 'Administrador')
          WITH CHECK (app_ctx.current_role() = 'Administrador');
    """)

    # ---- credenciales_servicio / intentos_anonimos_ip ----
    # Sin ninguna politica: con RLS activo y cero politicas, rol_app queda
    # bloqueado por defecto (deny-by-default) hasta que se defina su caso de uso.


def downgrade():
    # ---- eliminar politicas ----
    politicas_por_tabla = {
        "usuarios": ["pol_usuarios_select", "pol_usuarios_insert", "pol_usuarios_update"],
        "cuentas_usuarios": ["pol_cuentas_usuarios_select", "pol_cuentas_usuarios_insert", "pol_cuentas_usuarios_update"],
        "sesiones": ["pol_sesiones_select", "pol_sesiones_insert", "pol_sesiones_update_delete", "pol_sesiones_delete"],
        "tokens": ["pol_tokens_select", "pol_tokens_insert", "pol_tokens_update"],
        "dispositivos_fcm": ["pol_dispositivos_fcm_all"],
        "eventos": ["pol_eventos_select", "pol_eventos_insert"],
        "eventos_archivados": ["pol_eventos_archivados_select"],
        "integridad_baseline": ["pol_integridad_baseline_select"],
        "gestiones_cuenta": ["pol_gestiones_cuenta_select", "pol_gestiones_cuenta_insert"],
        "notificaciones": ["pol_notificaciones_select", "pol_notificaciones_insert", "pol_notificaciones_update"],
        "notificaciones_canal": ["pol_notificaciones_canal_select"],
        "estados_cuentas": ["pol_estados_cuentas_select"],
        "tipos_eventos": ["pol_tipos_eventos_select"],
        "acciones": ["pol_acciones_select", "pol_acciones_insert"],
        "roles": ["pol_roles_select", "pol_roles_insert", "pol_roles_update", "pol_roles_delete"],
        "recursos": ["pol_recursos_all"],
        "permisos": ["pol_permisos_all"],
        "cola_exportaciones_auditoria": ["pol_cola_export_select", "pol_cola_export_insert"],
        "ejecuciones_exportaciones_auditoria": ["pol_ejecuciones_export_select"],
        "configuracion_batch_exportacion_auditoria": ["pol_config_batch_export_all"],
    }
    for tabla, politicas in politicas_por_tabla.items():
        for politica in politicas:
            op.execute(f"DROP POLICY IF EXISTS {politica} ON modulo1.{tabla};")

    # ---- desactivar RLS ----
    tablas_modulo1 = [
        "acciones", "cola_exportaciones_auditoria",
        "configuracion_batch_exportacion_auditoria", "credenciales_servicio",
        "cuentas_usuarios", "dispositivos_fcm",
        "ejecuciones_exportaciones_auditoria", "estados_cuentas",
        "eventos", "eventos_archivados", "gestiones_cuenta",
        "integridad_baseline", "intentos_anonimos_ip", "notificaciones",
        "notificaciones_canal", "permisos", "recursos", "roles",
        "sesiones", "tipos_eventos", "tokens", "usuarios",
    ]
    for tabla in tablas_modulo1:
        op.execute(f"ALTER TABLE modulo1.{tabla} DISABLE ROW LEVEL SECURITY;")

    # ---- eliminar trigger y su funcion ----
    op.execute("DROP TRIGGER IF EXISTS trg_prevenir_autocambio_rol ON modulo1.usuarios;")
    op.execute("DROP FUNCTION IF EXISTS modulo1.fn_prevenir_autocambio_rol();")

    # ---- eliminar funciones de contexto ----
    # Nota: si otros modulos ya dependen de app_ctx.*, no ejecutar este downgrade
    # de forma aislada sin antes revertir esas dependencias.
    op.execute("DROP FUNCTION IF EXISTS app_ctx.current_role();")
    op.execute("DROP FUNCTION IF EXISTS app_ctx.current_user_id();")
    op.execute("DROP SCHEMA IF EXISTS app_ctx;")