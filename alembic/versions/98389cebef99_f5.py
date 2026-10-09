"""F5

Revision ID: 98389cebef99
Revises: 00c60ae92735
Create Date: 2026-10-09 09:05:30.982488


Reemplaza la totalidad de las políticas de modulo1 por un esquema
basado en funciones helper (f_uid, f_sistema, f_auth, f_permiso) que
resuelven identidad, contexto de sistema y permisos RBAC.

Patrones aplicados:
  - Catálogo:      SELECT para autenticados, escritura solo sistema.
  - Roles/Permisos: RBAC con protección de roles inmutables.
  - Auditoría:     INSERT-only, archivado con retención 12 meses.
  - Usuarios/Cuentas: gestión propia + admin, sin DELETE físico.
  - Sesiones/Tokens: propias o sistema.
  - Notificaciones: propias del usuario, creación por sistema.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '98389cebef99'
down_revision: Union[str, Sequence[str], None] = '00c60ae92735'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

    # ==========================================================
    # 0. Limpiar: borrar todas las políticas existentes en modulo1
    # ==========================================================
    op.execute("""
        DO $$ DECLARE r record; BEGIN
          FOR r IN SELECT policyname, tablename
                   FROM pg_policies WHERE schemaname = 'modulo1' LOOP
            EXECUTE format('DROP POLICY %I ON modulo1.%I', r.policyname, r.tablename);
          END LOOP; END $$;
    """)

    # ==========================================================
    # 1. Funciones helper de identidad y permisos
    # ==========================================================

    # Identidad del usuario autenticado (la pone la API en cada request)
    op.execute("""
        CREATE OR REPLACE FUNCTION modulo1.f_uid() RETURNS int
        LANGUAGE sql STABLE AS
        $$ SELECT nullif(current_setting('app.user_id', true), '')::int $$;
    """)

    # Contexto de sistema (tareas de fondo, ingesta IoT, batch)
    op.execute("""
        CREATE OR REPLACE FUNCTION modulo1.f_sistema() RETURNS boolean
        LANGUAGE sql STABLE AS
        $$ SELECT coalesce(current_setting('app.contexto', true), '') = 'sistema' $$;
    """)

    # Rol vigente del usuario (SECURITY DEFINER para evitar RLS circular)
    op.execute("""
        CREATE OR REPLACE FUNCTION modulo1.f_rol_id() RETURNS int
        LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = pg_catalog, modulo1 AS
        $$ SELECT id_rol FROM usuarios WHERE id_usuario = modulo1.f_uid() $$;
    """)

    # Cuenta vigente del usuario
    op.execute("""
        CREATE OR REPLACE FUNCTION modulo1.f_cuenta_id() RETURNS int
        LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = pg_catalog, modulo1 AS
        $$ SELECT id_cuenta_usuario FROM cuentas_usuarios
           WHERE id_usuario = modulo1.f_uid() $$;
    """)

    # ¿Está autenticado Y tiene cuenta ACTIVA? (RF-02, RF-03)
    op.execute("""
        CREATE OR REPLACE FUNCTION modulo1.f_auth() RETURNS boolean
        LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = pg_catalog, modulo1 AS
        $$ SELECT EXISTS (
             SELECT 1 FROM cuentas_usuarios c
             JOIN estados_cuentas e USING (id_estado_cuenta)
             WHERE c.id_usuario = modulo1.f_uid()
               AND upper(e.nombre) IN ('ACTIVO', 'ACTIVA')) $$;
    """)

    # ¿Tiene el permiso rol+recurso+acción? (RF-04), solo cuentas activas
    op.execute("""
        CREATE OR REPLACE FUNCTION modulo1.f_permiso(p_recurso text, p_accion text)
        RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = pg_catalog, modulo1 AS
        $$ SELECT modulo1.f_auth() AND EXISTS (
             SELECT 1 FROM permisos p
             JOIN recursos  r USING (id_recurso)
             JOIN acciones  a USING (id_accion)
             WHERE p.id_rol = modulo1.f_rol_id() AND p.es_activo
               AND r.nombre_recurso = p_recurso AND a.codigo = p_accion) $$;
    """)

    # ¿El rol es protegido (inmutable)?
    op.execute("""
        CREATE OR REPLACE FUNCTION modulo1.f_rol_protegido(p_id int)
        RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = pg_catalog, modulo1 AS
        $$ SELECT coalesce((SELECT es_protegido FROM roles WHERE id_rol = p_id), false) $$;
    """)

    # Permisos de ejecución: solo la app, nada para PUBLIC
    op.execute("""
        DO $$ BEGIN
          PERFORM 1; -- placeholder para que el bloque no esté vacío
        END $$;
    """)
    for fn in [
        "f_uid()",
        "f_sistema()",
        "f_rol_id()",
        "f_cuenta_id()",
        "f_auth()",
        "f_permiso(text,text)",
        "f_rol_protegido(int)",
    ]:
        op.execute(f"REVOKE ALL ON FUNCTION modulo1.{fn} FROM PUBLIC;")
        op.execute(f"GRANT EXECUTE ON FUNCTION modulo1.{fn} TO sgpmp_app;")

    # ==========================================================
    # 2. Catálogos: SELECT para autenticados, escritura solo sistema
    # ==========================================================
    op.execute("""
        DO $$ DECLARE t text; BEGIN
          FOREACH t IN ARRAY ARRAY[
            'acciones','recursos','estados_cuentas',
            'tipos_eventos','notificaciones_canal'
          ] LOOP
            EXECUTE format(
              'CREATE POLICY %I ON modulo1.%I FOR SELECT
                 USING (modulo1.f_sistema() OR modulo1.f_auth())',
              t || '_sel', t);
            EXECUTE format(
              'CREATE POLICY %I ON modulo1.%I FOR ALL
                 USING (modulo1.f_sistema()) WITH CHECK (modulo1.f_sistema())',
              t || '_sis', t);
          END LOOP; END $$;
    """)

    # --- roles (RF-03): protegido inmutable; FK impide borrar roles con usuarios
    op.execute("""
        CREATE POLICY roles_sel ON modulo1.roles FOR SELECT
          USING (modulo1.f_sistema() OR modulo1.f_auth());
    """)
    op.execute("""
        CREATE POLICY roles_ins ON modulo1.roles FOR INSERT
          WITH CHECK (modulo1.f_permiso('GESTION_ROLES','C') AND NOT es_protegido);
    """)
    op.execute("""
        CREATE POLICY roles_upd ON modulo1.roles FOR UPDATE
          USING (modulo1.f_permiso('GESTION_ROLES','U') AND NOT es_protegido)
          WITH CHECK (modulo1.f_permiso('GESTION_ROLES','U') AND NOT es_protegido);
    """)
    op.execute("""
        CREATE POLICY roles_del ON modulo1.roles FOR DELETE
          USING (modulo1.f_permiso('GESTION_ROLES','D') AND NOT es_protegido);
    """)
    op.execute("""
        CREATE POLICY roles_sis ON modulo1.roles FOR ALL
          USING (modulo1.f_sistema()) WITH CHECK (modulo1.f_sistema());
    """)

    # --- permisos (RF-04): cada usuario ve los de su rol
    op.execute("""
        CREATE POLICY permisos_sel ON modulo1.permisos FOR SELECT
          USING (modulo1.f_sistema()
                 OR id_rol = modulo1.f_rol_id()
                 OR modulo1.f_permiso('GESTION_PERMISOS','R')
                 OR modulo1.f_permiso('GESTION_ROLES','R'));
    """)
    op.execute("""
        CREATE POLICY permisos_w ON modulo1.permisos FOR ALL
          USING ((modulo1.f_permiso('GESTION_PERMISOS','U')
                  OR modulo1.f_permiso('GESTION_ROLES','U'))
                 AND NOT modulo1.f_rol_protegido(id_rol))
          WITH CHECK ((modulo1.f_permiso('GESTION_PERMISOS','U')
                       OR modulo1.f_permiso('GESTION_ROLES','U'))
                 AND NOT modulo1.f_rol_protegido(id_rol));
    """)
    op.execute("""
        CREATE POLICY permisos_sis ON modulo1.permisos FOR ALL
          USING (modulo1.f_sistema()) WITH CHECK (modulo1.f_sistema());
    """)

    # --- configuración batch y credenciales de servicio
    op.execute("""
        CREATE POLICY cfgbatch_sel ON modulo1.configuracion_batch_exportacion_auditoria
          FOR SELECT USING (modulo1.f_sistema() OR modulo1.f_permiso('AUDITORIA','R'));
    """)
    op.execute("""
        CREATE POLICY cfgbatch_sis ON modulo1.configuracion_batch_exportacion_auditoria
          FOR ALL USING (modulo1.f_sistema()) WITH CHECK (modulo1.f_sistema());
    """)
    op.execute("""
        CREATE POLICY cred_sis ON modulo1.credenciales_servicio FOR ALL
          USING (modulo1.f_sistema()) WITH CHECK (modulo1.f_sistema());
    """)

    # ==========================================================
    # 3. Auditoría y eventos
    # ==========================================================

    # eventos: INSERT-only; archivado puede borrar solo lo copiado y >12 meses
    op.execute("""
        CREATE POLICY eventos_sel ON modulo1.eventos FOR SELECT
          USING (modulo1.f_sistema() OR modulo1.f_permiso('AUDITORIA','R'));
    """)
    op.execute("""
        CREATE POLICY eventos_ins ON modulo1.eventos FOR INSERT
          WITH CHECK (modulo1.f_sistema()
                      OR (modulo1.f_auth() AND id_usuario = modulo1.f_uid()));
    """)
    op.execute("""
        CREATE POLICY eventos_del_arch ON modulo1.eventos FOR DELETE
          USING (modulo1.f_sistema()
                 AND fecha_evento < now() - interval '12 months'
                 AND EXISTS (SELECT 1 FROM modulo1.eventos_archivados a
                             WHERE a.id_evento = eventos.id_evento));
    """)

    # eventos archivados
    op.execute("""
        CREATE POLICY evarch_sel ON modulo1.eventos_archivados FOR SELECT
          USING (modulo1.f_sistema() OR modulo1.f_permiso('AUDITORIA','R'));
    """)
    op.execute("""
        CREATE POLICY evarch_ins ON modulo1.eventos_archivados FOR INSERT
          WITH CHECK (modulo1.f_sistema());
    """)

    # integridad baseline
    op.execute("""
        CREATE POLICY integ_sel ON modulo1.integridad_baseline FOR SELECT
          USING (modulo1.f_sistema() OR modulo1.f_permiso('AUDITORIA','R'));
    """)
    op.execute("""
        CREATE POLICY integ_ins ON modulo1.integridad_baseline FOR INSERT
          WITH CHECK (modulo1.f_sistema());
    """)

    # gestiones de cuenta
    op.execute("""
        CREATE POLICY gest_sel ON modulo1.gestiones_cuenta FOR SELECT
          USING (modulo1.f_sistema() OR modulo1.f_permiso('GESTION_CUENTAS','R'));
    """)
    op.execute("""
        CREATE POLICY gest_ins ON modulo1.gestiones_cuenta FOR INSERT
          WITH CHECK (modulo1.f_sistema()
                      OR (modulo1.f_permiso('GESTION_CUENTAS','U')
                          AND id_usuario_responsable = modulo1.f_uid()));
    """)

    # intentos anónimos por IP
    op.execute("""
        CREATE POLICY ipint_ins ON modulo1.intentos_anonimos_ip
          FOR INSERT WITH CHECK (true);
    """)
    op.execute("""
        CREATE POLICY ipint_sel ON modulo1.intentos_anonimos_ip
          FOR SELECT USING (modulo1.f_sistema());
    """)
    op.execute("""
        CREATE POLICY ipint_del ON modulo1.intentos_anonimos_ip
          FOR DELETE USING (modulo1.f_sistema());
    """)

    # exportaciones de auditoría
    op.execute("""
        CREATE POLICY cola_sel ON modulo1.cola_exportaciones_auditoria FOR SELECT
          USING (modulo1.f_sistema() OR id_usuario_solicitante = modulo1.f_uid());
    """)
    op.execute("""
        CREATE POLICY cola_ins ON modulo1.cola_exportaciones_auditoria FOR INSERT
          WITH CHECK (modulo1.f_permiso('AUDITORIA','E')
                      AND id_usuario_solicitante = modulo1.f_uid());
    """)
    op.execute("""
        CREATE POLICY cola_upd ON modulo1.cola_exportaciones_auditoria FOR UPDATE
          USING (modulo1.f_sistema()) WITH CHECK (modulo1.f_sistema());
    """)
    op.execute("""
        CREATE POLICY cola_del ON modulo1.cola_exportaciones_auditoria FOR DELETE
          USING (modulo1.f_sistema());
    """)
    op.execute("""
        CREATE POLICY ejec_sel ON modulo1.ejecuciones_exportaciones_auditoria FOR SELECT
          USING (modulo1.f_sistema()
                 OR EXISTS (SELECT 1 FROM modulo1.cola_exportaciones_auditoria c
                            WHERE c.id_cola = ejecuciones_exportaciones_auditoria.id_cola));
    """)
    op.execute("""
        CREATE POLICY ejec_sis ON modulo1.ejecuciones_exportaciones_auditoria FOR ALL
          USING (modulo1.f_sistema()) WITH CHECK (modulo1.f_sistema());
    """)

    # ==========================================================
    # 4. Usuarios, cuentas, sesiones, tokens, dispositivos
    # ==========================================================

    # usuarios (RF-05/11/12/13): sin DELETE (borrado lógico, RF-06)
    op.execute("""
        CREATE POLICY usr_sel ON modulo1.usuarios FOR SELECT
          USING (modulo1.f_sistema()
                 OR id_usuario = modulo1.f_uid()
                 OR modulo1.f_permiso('GESTION_USUARIOS','R'));
    """)
    op.execute("""
        CREATE POLICY usr_ins ON modulo1.usuarios FOR INSERT
          WITH CHECK (modulo1.f_sistema());
    """)
    op.execute("""
        CREATE POLICY usr_upd_self ON modulo1.usuarios FOR UPDATE
          USING (id_usuario = modulo1.f_uid() AND modulo1.f_auth())
          WITH CHECK (id_usuario = modulo1.f_uid()
                      AND id_rol = modulo1.f_rol_id());
    """)
    op.execute("""
        CREATE POLICY usr_upd_adm ON modulo1.usuarios FOR UPDATE
          USING (modulo1.f_permiso('GESTION_USUARIOS','U'))
          WITH CHECK (id_usuario <> modulo1.f_uid()
                      OR id_rol = modulo1.f_rol_id());
    """)
    op.execute("""
        CREATE POLICY usr_upd_sis ON modulo1.usuarios FOR UPDATE
          USING (modulo1.f_sistema()) WITH CHECK (modulo1.f_sistema());
    """)

    # cuentas_usuarios (RF-02/06): admin no se gestiona a sí mismo
    op.execute("""
        CREATE POLICY cta_sel ON modulo1.cuentas_usuarios FOR SELECT
          USING (modulo1.f_sistema()
                 OR id_usuario = modulo1.f_uid()
                 OR modulo1.f_permiso('GESTION_CUENTAS','R'));
    """)
    op.execute("""
        CREATE POLICY cta_ins ON modulo1.cuentas_usuarios FOR INSERT
          WITH CHECK (modulo1.f_sistema());
    """)
    op.execute("""
        CREATE POLICY cta_upd_sis ON modulo1.cuentas_usuarios FOR UPDATE
          USING (modulo1.f_sistema()) WITH CHECK (modulo1.f_sistema());
    """)
    op.execute("""
        CREATE POLICY cta_upd_adm ON modulo1.cuentas_usuarios FOR UPDATE
          USING (modulo1.f_permiso('GESTION_CUENTAS','U')
                 AND id_usuario <> modulo1.f_uid())
          WITH CHECK (modulo1.f_permiso('GESTION_CUENTAS','U')
                      AND id_usuario <> modulo1.f_uid());
    """)

    # sesiones: propias o admin que invalida por cambio de estado (RF-06)
    op.execute("""
        CREATE POLICY ses_sel ON modulo1.sesiones FOR SELECT
          USING (modulo1.f_sistema()
                 OR id_cuenta_usuario = modulo1.f_cuenta_id()
                 OR modulo1.f_permiso('GESTION_CUENTAS','R'));
    """)
    op.execute("""
        CREATE POLICY ses_ins ON modulo1.sesiones FOR INSERT
          WITH CHECK (modulo1.f_sistema());
    """)
    op.execute("""
        CREATE POLICY ses_upd ON modulo1.sesiones FOR UPDATE
          USING (modulo1.f_sistema()
                 OR id_cuenta_usuario = modulo1.f_cuenta_id()
                 OR modulo1.f_permiso('GESTION_CUENTAS','U'))
          WITH CHECK (modulo1.f_sistema()
                      OR id_cuenta_usuario = modulo1.f_cuenta_id()
                      OR modulo1.f_permiso('GESTION_CUENTAS','U'));
    """)
    op.execute("""
        CREATE POLICY ses_del ON modulo1.sesiones FOR DELETE
          USING (modulo1.f_sistema());
    """)

    # tokens: pre-sesión solo sistema; el usuario ve los de sus sesiones
    op.execute("""
        CREATE POLICY tok_sis ON modulo1.tokens FOR ALL
          USING (modulo1.f_sistema()) WITH CHECK (modulo1.f_sistema());
    """)
    op.execute("""
        CREATE POLICY tok_sel ON modulo1.tokens FOR SELECT
          USING (id_sesion IN (
            SELECT s.id_sesion FROM modulo1.sesiones s
            WHERE s.id_cuenta_usuario = modulo1.f_cuenta_id()));
    """)

    # dispositivos FCM
    op.execute("""
        CREATE POLICY fcm_own ON modulo1.dispositivos_fcm FOR ALL
          USING (id_usuario = modulo1.f_uid())
          WITH CHECK (id_usuario = modulo1.f_uid());
    """)
    op.execute("""
        CREATE POLICY fcm_sis ON modulo1.dispositivos_fcm FOR ALL
          USING (modulo1.f_sistema()) WITH CHECK (modulo1.f_sistema());
    """)

    # notificaciones (RF-14): usuario lee y marca leídas; crea/borra sistema
    op.execute("""
        CREATE POLICY not_sel ON modulo1.notificaciones FOR SELECT
          USING (id_usuario = modulo1.f_uid());
    """)
    op.execute("""
        CREATE POLICY not_upd ON modulo1.notificaciones FOR UPDATE
          USING (id_usuario = modulo1.f_uid())
          WITH CHECK (id_usuario = modulo1.f_uid());
    """)
    op.execute("""
        CREATE POLICY not_sis ON modulo1.notificaciones FOR ALL
          USING (modulo1.f_sistema()) WITH CHECK (modulo1.f_sistema());
    """)

    # ==========================================================
    # 5. FORCE RLS en todas las tablas de modulo1
    # ==========================================================
    op.execute("""
        DO $$ DECLARE t text; BEGIN
          FOR t IN SELECT tablename FROM pg_tables WHERE schemaname = 'modulo1' LOOP
            EXECUTE format('ALTER TABLE modulo1.%I FORCE ROW LEVEL SECURITY', t);
          END LOOP; END $$;
    """)


def downgrade() -> None:

    # 1. Quitar FORCE RLS de todas las tablas
    op.execute("""
        DO $$ DECLARE t text; BEGIN
          FOR t IN SELECT tablename FROM pg_tables WHERE schemaname = 'modulo1' LOOP
            EXECUTE format('ALTER TABLE modulo1.%I NO FORCE ROW LEVEL SECURITY', t);
            EXECUTE format('ALTER TABLE modulo1.%I DISABLE ROW LEVEL SECURITY', t);
          END LOOP; END $$;
    """)

    # 2. Borrar todas las políticas creadas
    op.execute("""
        DO $$ DECLARE r record; BEGIN
          FOR r IN SELECT policyname, tablename
                   FROM pg_policies WHERE schemaname = 'modulo1' LOOP
            EXECUTE format('DROP POLICY %I ON modulo1.%I', r.policyname, r.tablename);
          END LOOP; END $$;
    """)

    # 3. Borrar funciones helper
    op.execute("DROP FUNCTION IF EXISTS modulo1.f_rol_protegido(int);")
    op.execute("DROP FUNCTION IF EXISTS modulo1.f_permiso(text,text);")
    op.execute("DROP FUNCTION IF EXISTS modulo1.f_auth();")
    op.execute("DROP FUNCTION IF EXISTS modulo1.f_cuenta_id();")
    op.execute("DROP FUNCTION IF EXISTS modulo1.f_rol_id();")
    op.execute("DROP FUNCTION IF EXISTS modulo1.f_sistema();")
    op.execute("DROP FUNCTION IF EXISTS modulo1.f_uid();")

    # NOTA: Este downgrade NO restaura las políticas previas de F3/F4.
    # Si se necesita volver a ese estado, re-aplicar las migraciones
    # 8d80fb56a30b, bc82ffbdf797 y a7380032a23b.