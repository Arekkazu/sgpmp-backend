"""F5: RLS de modulo1 por permisos RBAC

Revision ID: 98389cebef99
Revises: 00c60ae92735
Create Date: 2026-10-09 09:05:30.982488

Reemplaza las políticas de modulo1 (F1 + F4) por permisos RBAC: en lugar de
comparar el texto 'Administrador', cada política pregunta a
`modulo1.fn_tiene_permiso(recurso, accion)` lo mismo que `require_permission`
pregunta en la app (`modulo1.permisos` del rol del usuario). Cambiar un permiso
en la tabla cambia también lo que la BD deja ver, sin redesplegar.

Contrato con la app (anotaciones/convencion_nomenclatura_bd.md):
  - Identidad: `app.current_user_id`, leída por `modulo1.fn_id_usuario_actual()`.
    No se crean variables de sesión nuevas.
  - Procesos sin usuario: el usuario de servicio `servicio.sistema@sgpmp.local`
    (D1, PR #485), identificado por `modulo1.fn_es_usuario_servicio()`. No hay
    bandera de "contexto sistema" que se salte las políticas.
  - El rol se lee de la BD, no de la sesión: un cambio de rol aplica en el
    siguiente request (RF-04) sin volver a iniciar sesión.

Las funciones de apoyo son SECURITY DEFINER y leen tablas con RLS y FORCE: su
dueño tiene que saltarse RLS o cada consulta entra en recursión infinita. Por
eso la migración exige correr como superusuario o BYPASSRLS.

En las políticas, cada función va dentro de `(SELECT ...)`: así se evalúa una
vez por sentencia y no una vez por fila (100k eventos: 17,8 s -> 10 ms).
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '98389cebef99'
down_revision: Union[str, Sequence[str], None] = '00c60ae92735'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UID = "(SELECT modulo1.fn_id_usuario_actual())"
CUENTA = "(SELECT modulo1.fn_id_cuenta_actual())"
ROL = "(SELECT modulo1.fn_id_rol_actual())"
SERVICIO = "(SELECT modulo1.fn_es_usuario_servicio())"


def permiso(recurso: str, accion: str) -> str:
    """Nombres reales de `modulo1.recursos` (los mismos ids que usan los routers)."""
    return f"(SELECT modulo1.fn_tiene_permiso('{recurso}', '{accion}'))"


_FUNCIONES = {
    "fn_id_rol_actual() RETURNS integer": """
        SELECT id_rol FROM modulo1.usuarios
        WHERE id_usuario = modulo1.fn_id_usuario_actual()
    """,
    "fn_id_cuenta_actual() RETURNS integer": """
        SELECT id_cuenta_usuario FROM modulo1.cuentas_usuarios
        WHERE id_usuario = modulo1.fn_id_usuario_actual()
    """,
    # Sin chequeo de estado de cuenta: el usuario de servicio tiene la cuenta
    # Inactiva a propósito (no puede iniciar sesión), y el estado ya lo valida
    # `get_current_user` en cada request.
    "fn_tiene_permiso(p_recurso text, p_accion text) RETURNS boolean": """
        SELECT EXISTS (
          SELECT 1 FROM modulo1.permisos p
          JOIN modulo1.recursos r ON r.id_recurso = p.id_recurso
          JOIN modulo1.acciones a ON a.id_accion = p.id_accion
          WHERE p.id_rol = modulo1.fn_id_rol_actual() AND p.es_activo
            AND r.nombre_recurso = p_recurso AND a.codigo = p_accion)
    """,
    "fn_es_usuario_servicio() RETURNS boolean": """
        SELECT EXISTS (
          SELECT 1 FROM modulo1.usuarios
          WHERE id_usuario = modulo1.fn_id_usuario_actual()
            AND correo_electronico = 'servicio.sistema@sgpmp.local')
    """,
    "fn_rol_protegido(p_id_rol integer) RETURNS boolean": """
        SELECT coalesce((SELECT es_protegido FROM modulo1.roles WHERE id_rol = p_id_rol), false)
    """,
}

_CATALOGOS = ["acciones", "recursos", "estados_cuentas", "tipos_eventos", "notificaciones_canal"]

_TOKEN_PROPIO = f"""
    EXISTS (SELECT 1 FROM modulo1.sesiones s
            WHERE s.id_cuenta_usuario = {CUENTA}
              AND (s.id_sesion = tokens.id_sesion
                   OR s.id_token = tokens.id_token
                   OR s.id_token_refresco = tokens.id_token))
"""

# (nombre, tabla, comando, USING, WITH CHECK)
_POLITICAS = [
    # roles: legibles para todos (la app los lee antes de autorizar);
    # los protegidos (Administrador) no se crean, editan ni borran.
    ("pol_roles_select", "roles", "SELECT", "true", None),
    ("pol_roles_insert", "roles", "INSERT", None, f"{permiso('roles', 'C')} AND NOT es_protegido"),
    ("pol_roles_update", "roles", "UPDATE",
     f"{permiso('roles', 'U')} AND NOT es_protegido", f"{permiso('roles', 'U')} AND NOT es_protegido"),
    ("pol_roles_delete", "roles", "DELETE", f"{permiso('roles', 'D')} AND NOT es_protegido", None),

    # permisos: cada uno lee los de su rol (require_permission); gestión por RBAC.
    ("pol_permisos_select", "permisos", "SELECT",
     f"id_rol = {ROL} OR {permiso('permisos', 'R')} OR {permiso('roles', 'R')}", None),
    ("pol_permisos_insert", "permisos", "INSERT", None,
     f"{permiso('permisos', 'C')} AND NOT modulo1.fn_rol_protegido(id_rol)"),
    ("pol_permisos_update", "permisos", "UPDATE",
     f"{permiso('permisos', 'U')} AND NOT modulo1.fn_rol_protegido(id_rol)",
     f"{permiso('permisos', 'U')} AND NOT modulo1.fn_rol_protegido(id_rol)"),
    ("pol_permisos_delete", "permisos", "DELETE",
     f"{permiso('permisos', 'D')} AND NOT modulo1.fn_rol_protegido(id_rol)", None),

    # Configuración del batch de exportación y credenciales de servicio.
    ("pol_config_batch_export_select", "configuracion_batch_exportacion_auditoria", "SELECT",
     f"{permiso('eventos', 'R')} OR {SERVICIO}", None),
    ("pol_config_batch_export_servicio", "configuracion_batch_exportacion_auditoria", "ALL",
     SERVICIO, SERVICIO),
    ("pol_credenciales_servicio_select", "credenciales_servicio", "SELECT", SERVICIO, None),

    # eventos: append-only (los triggers bloquean UPDATE/DELETE). El INSERT queda
    # abierto como en F4: login fallido, registro y activación auditan antes de
    # que exista identidad; la integridad la dan el hash y los triggers.
    ("pol_eventos_select", "eventos", "SELECT", f"{permiso('eventos', 'R')} OR id_usuario = {UID}", None),
    ("pol_eventos_insert", "eventos", "INSERT", None, "true"),
    ("pol_eventos_archivados_select", "eventos_archivados", "SELECT", permiso("eventos", "R"), None),
    ("pol_eventos_archivados_insert", "eventos_archivados", "INSERT", None, SERVICIO),
    ("pol_integridad_baseline_select", "integridad_baseline", "SELECT", permiso("eventos", "R"), None),

    ("pol_gestiones_cuenta_select", "gestiones_cuenta", "SELECT", permiso("cuentas", "R"), None),
    ("pol_gestiones_cuenta_insert", "gestiones_cuenta", "INSERT", None,
     f"{permiso('cuentas', 'U')} AND id_usuario_responsable = {UID}"),

    # Anónima por naturaleza: el límite por IP tiene que poder contar sus filas.
    ("pol_intentos_anonimos_ip_all", "intentos_anonimos_ip", "ALL", "true", "true"),

    # Exportación de auditoría: la solicita quien lee auditoría; la procesa el worker.
    ("pol_cola_export_select", "cola_exportaciones_auditoria", "SELECT",
     f"id_usuario_solicitante = {UID} OR {SERVICIO}", None),
    ("pol_cola_export_insert", "cola_exportaciones_auditoria", "INSERT", None,
     f"{permiso('eventos', 'R')} AND id_usuario_solicitante = {UID}"),
    ("pol_cola_export_update", "cola_exportaciones_auditoria", "UPDATE", SERVICIO, SERVICIO),
    ("pol_cola_export_delete", "cola_exportaciones_auditoria", "DELETE", SERVICIO, None),
    ("pol_ejecuciones_export_select", "ejecuciones_exportaciones_auditoria", "SELECT",
     "EXISTS (SELECT 1 FROM modulo1.cola_exportaciones_auditoria c"
     " WHERE c.id_cola = ejecuciones_exportaciones_auditoria.id_cola)", None),
    ("pol_ejecuciones_export_servicio", "ejecuciones_exportaciones_auditoria", "ALL", SERVICIO, SERVICIO),

    # usuarios: sin DELETE (borrado lógico, RF-06). El registro es anónimo, pero
    # nadie sin permiso crea un usuario con rol protegido. El cambio del propio
    # rol ya lo bloquea el trigger `fn_prevenir_autocambio_rol` (RF-05).
    ("pol_usuarios_select", "usuarios", "SELECT", f"id_usuario = {UID} OR {permiso('usuarios', 'R')}", None),
    ("pol_usuarios_insert", "usuarios", "INSERT", None,
     f"{permiso('usuarios', 'C')} OR NOT modulo1.fn_rol_protegido(id_rol)"),
    ("pol_usuarios_update", "usuarios", "UPDATE",
     f"id_usuario = {UID} OR {permiso('usuarios', 'U')}", f"id_usuario = {UID} OR {permiso('usuarios', 'U')}"),

    # cuentas: el login actualiza la propia (último acceso, intentos, bloqueo,
    # activación); la gestión es sobre cuentas ajenas.
    ("pol_cuentas_usuarios_select", "cuentas_usuarios", "SELECT",
     f"id_usuario = {UID} OR {permiso('cuentas', 'R')}", None),
    ("pol_cuentas_usuarios_insert", "cuentas_usuarios", "INSERT", None, "true"),
    ("pol_cuentas_usuarios_update_propia", "cuentas_usuarios", "UPDATE",
     f"id_usuario = {UID}", f"id_usuario = {UID}"),
    ("pol_cuentas_usuarios_update_gestion", "cuentas_usuarios", "UPDATE",
     f"{permiso('cuentas', 'U')} AND id_usuario <> {UID}", f"{permiso('cuentas', 'U')} AND id_usuario <> {UID}"),

    # sesiones: el login crea la propia; RF-06 invalida las ajenas con cuentas U.
    ("pol_sesiones_select", "sesiones", "SELECT",
     f"id_cuenta_usuario = {CUENTA} OR {permiso('sesiones', 'R')}", None),
    ("pol_sesiones_insert", "sesiones", "INSERT", None, f"id_cuenta_usuario = {CUENTA}"),
    ("pol_sesiones_update", "sesiones", "UPDATE",
     f"id_cuenta_usuario = {CUENTA} OR {permiso('cuentas', 'U')}",
     f"id_cuenta_usuario = {CUENTA} OR {permiso('cuentas', 'U')}"),

    # tokens: los de activación y recuperación se emiten sin sesión ni identidad.
    # El de acceso cuelga de sesiones.id_token y el de refresco de los dos lados.
    ("pol_tokens_insert", "tokens", "INSERT", None, "true"),
    ("pol_tokens_select", "tokens", "SELECT", f"{permiso('sesiones', 'R')} OR {_TOKEN_PROPIO}", None),
    ("pol_tokens_update", "tokens", "UPDATE", f"{permiso('cuentas', 'U')} OR {_TOKEN_PROPIO}", "true"),

    ("pol_dispositivos_fcm_all", "dispositivos_fcm", "ALL",
     f"id_usuario = {UID} OR {SERVICIO}", f"id_usuario = {UID} OR {SERVICIO}"),

    # notificaciones (RF-14): cualquier módulo notifica a otros usuarios desde
    # su request; cada uno lee y marca las suyas; el envío lo hace el servicio.
    ("pol_notificaciones_select", "notificaciones", "SELECT", f"id_usuario = {UID} OR {SERVICIO}", None),
    ("pol_notificaciones_insert", "notificaciones", "INSERT", None, "true"),
    ("pol_notificaciones_update", "notificaciones", "UPDATE",
     f"id_usuario = {UID} OR {SERVICIO}", f"id_usuario = {UID} OR {SERVICIO}"),
]

# Estado de modulo1 en 00c60ae92735 (F1 + F4), para el downgrade.
_POLITICAS_ANTERIORES = """
CREATE POLICY pol_acciones_insert ON modulo1.acciones AS PERMISSIVE FOR INSERT WITH CHECK ((modulo1.fn_rol_actual() = 'Administrador'::text));
CREATE POLICY pol_acciones_select ON modulo1.acciones AS PERMISSIVE FOR SELECT USING (true);
CREATE POLICY pol_cola_export_insert ON modulo1.cola_exportaciones_auditoria AS PERMISSIVE FOR INSERT WITH CHECK (((modulo1.fn_rol_actual() = 'Administrador'::text) AND (id_usuario_solicitante = modulo1.fn_id_usuario_actual())));
CREATE POLICY pol_cola_export_select ON modulo1.cola_exportaciones_auditoria AS PERMISSIVE FOR SELECT USING ((modulo1.fn_rol_actual() = 'Administrador'::text));
CREATE POLICY pol_cola_export_update ON modulo1.cola_exportaciones_auditoria AS PERMISSIVE FOR UPDATE USING ((modulo1.fn_rol_actual() = 'Administrador'::text)) WITH CHECK ((modulo1.fn_rol_actual() = 'Administrador'::text));
CREATE POLICY pol_config_batch_export_all ON modulo1.configuracion_batch_exportacion_auditoria AS PERMISSIVE FOR ALL USING ((modulo1.fn_rol_actual() = 'Administrador'::text)) WITH CHECK ((modulo1.fn_rol_actual() = 'Administrador'::text));
CREATE POLICY pol_credenciales_servicio_select ON modulo1.credenciales_servicio AS PERMISSIVE FOR SELECT USING ((modulo1.fn_rol_actual() = 'Administrador'::text));
CREATE POLICY pol_cuentas_usuarios_insert ON modulo1.cuentas_usuarios AS PERMISSIVE FOR INSERT WITH CHECK (true);
CREATE POLICY pol_cuentas_usuarios_select ON modulo1.cuentas_usuarios AS PERMISSIVE FOR SELECT USING (((id_usuario = modulo1.fn_id_usuario_actual()) OR (modulo1.fn_rol_actual() = 'Administrador'::text)));
CREATE POLICY pol_cuentas_usuarios_update ON modulo1.cuentas_usuarios AS PERMISSIVE FOR UPDATE USING (((id_usuario = modulo1.fn_id_usuario_actual()) OR (modulo1.fn_rol_actual() = 'Administrador'::text))) WITH CHECK (((id_usuario = modulo1.fn_id_usuario_actual()) OR (modulo1.fn_rol_actual() = 'Administrador'::text)));
CREATE POLICY pol_dispositivos_fcm_all ON modulo1.dispositivos_fcm AS PERMISSIVE FOR ALL USING (((id_usuario = modulo1.fn_id_usuario_actual()) OR (modulo1.fn_rol_actual() = 'Administrador'::text))) WITH CHECK ((id_usuario = modulo1.fn_id_usuario_actual()));
CREATE POLICY pol_ejecuciones_export_insert ON modulo1.ejecuciones_exportaciones_auditoria AS PERMISSIVE FOR INSERT WITH CHECK ((modulo1.fn_rol_actual() = 'Administrador'::text));
CREATE POLICY pol_ejecuciones_export_select ON modulo1.ejecuciones_exportaciones_auditoria AS PERMISSIVE FOR SELECT USING ((modulo1.fn_rol_actual() = 'Administrador'::text));
CREATE POLICY pol_estados_cuentas_select ON modulo1.estados_cuentas AS PERMISSIVE FOR SELECT USING (true);
CREATE POLICY pol_eventos_insert ON modulo1.eventos AS PERMISSIVE FOR INSERT WITH CHECK (true);
CREATE POLICY pol_eventos_select ON modulo1.eventos AS PERMISSIVE FOR SELECT USING (((modulo1.fn_rol_actual() = 'Administrador'::text) OR (id_usuario = modulo1.fn_id_usuario_actual())));
CREATE POLICY pol_eventos_archivados_insert ON modulo1.eventos_archivados AS PERMISSIVE FOR INSERT WITH CHECK (true);
CREATE POLICY pol_eventos_archivados_select ON modulo1.eventos_archivados AS PERMISSIVE FOR SELECT USING ((modulo1.fn_rol_actual() = 'Administrador'::text));
CREATE POLICY pol_gestiones_cuenta_insert ON modulo1.gestiones_cuenta AS PERMISSIVE FOR INSERT WITH CHECK (((modulo1.fn_rol_actual() = 'Administrador'::text) AND (id_usuario_responsable = modulo1.fn_id_usuario_actual())));
CREATE POLICY pol_gestiones_cuenta_select ON modulo1.gestiones_cuenta AS PERMISSIVE FOR SELECT USING ((modulo1.fn_rol_actual() = 'Administrador'::text));
CREATE POLICY pol_integridad_baseline_select ON modulo1.integridad_baseline AS PERMISSIVE FOR SELECT USING ((modulo1.fn_rol_actual() = 'Administrador'::text));
CREATE POLICY pol_intentos_anonimos_ip_all ON modulo1.intentos_anonimos_ip AS PERMISSIVE FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY pol_notificaciones_insert ON modulo1.notificaciones AS PERMISSIVE FOR INSERT WITH CHECK (true);
CREATE POLICY pol_notificaciones_select ON modulo1.notificaciones AS PERMISSIVE FOR SELECT USING (((id_usuario = modulo1.fn_id_usuario_actual()) OR (modulo1.fn_rol_actual() = 'Administrador'::text)));
CREATE POLICY pol_notificaciones_update ON modulo1.notificaciones AS PERMISSIVE FOR UPDATE USING ((id_usuario = modulo1.fn_id_usuario_actual())) WITH CHECK ((id_usuario = modulo1.fn_id_usuario_actual()));
CREATE POLICY pol_notificaciones_canal_select ON modulo1.notificaciones_canal AS PERMISSIVE FOR SELECT USING (true);
CREATE POLICY pol_permisos_all ON modulo1.permisos AS PERMISSIVE FOR ALL USING ((modulo1.fn_rol_actual() = 'Administrador'::text)) WITH CHECK ((modulo1.fn_rol_actual() = 'Administrador'::text));
CREATE POLICY pol_permisos_select ON modulo1.permisos AS PERMISSIVE FOR SELECT USING (true);
CREATE POLICY pol_recursos_all ON modulo1.recursos AS PERMISSIVE FOR ALL USING ((modulo1.fn_rol_actual() = 'Administrador'::text)) WITH CHECK ((modulo1.fn_rol_actual() = 'Administrador'::text));
CREATE POLICY pol_recursos_select ON modulo1.recursos AS PERMISSIVE FOR SELECT USING (true);
CREATE POLICY pol_roles_delete ON modulo1.roles AS PERMISSIVE FOR DELETE USING (((modulo1.fn_rol_actual() = 'Administrador'::text) AND (es_protegido = false)));
CREATE POLICY pol_roles_insert ON modulo1.roles AS PERMISSIVE FOR INSERT WITH CHECK ((modulo1.fn_rol_actual() = 'Administrador'::text));
CREATE POLICY pol_roles_select ON modulo1.roles AS PERMISSIVE FOR SELECT USING (true);
CREATE POLICY pol_roles_update ON modulo1.roles AS PERMISSIVE FOR UPDATE USING ((modulo1.fn_rol_actual() = 'Administrador'::text)) WITH CHECK ((modulo1.fn_rol_actual() = 'Administrador'::text));
CREATE POLICY pol_sesiones_delete ON modulo1.sesiones AS PERMISSIVE FOR DELETE USING (((modulo1.fn_rol_actual() = 'Administrador'::text) OR (id_cuenta_usuario IN ( SELECT cuentas_usuarios.id_cuenta_usuario
   FROM modulo1.cuentas_usuarios
  WHERE (cuentas_usuarios.id_usuario = modulo1.fn_id_usuario_actual())))));
CREATE POLICY pol_sesiones_insert ON modulo1.sesiones AS PERMISSIVE FOR INSERT WITH CHECK ((id_cuenta_usuario IN ( SELECT cuentas_usuarios.id_cuenta_usuario
   FROM modulo1.cuentas_usuarios
  WHERE (cuentas_usuarios.id_usuario = modulo1.fn_id_usuario_actual()))));
CREATE POLICY pol_sesiones_select ON modulo1.sesiones AS PERMISSIVE FOR SELECT USING (((modulo1.fn_rol_actual() = 'Administrador'::text) OR (id_cuenta_usuario IN ( SELECT cuentas_usuarios.id_cuenta_usuario
   FROM modulo1.cuentas_usuarios
  WHERE (cuentas_usuarios.id_usuario = modulo1.fn_id_usuario_actual())))));
CREATE POLICY pol_sesiones_update_delete ON modulo1.sesiones AS PERMISSIVE FOR UPDATE USING (((modulo1.fn_rol_actual() = 'Administrador'::text) OR (id_cuenta_usuario IN ( SELECT cuentas_usuarios.id_cuenta_usuario
   FROM modulo1.cuentas_usuarios
  WHERE (cuentas_usuarios.id_usuario = modulo1.fn_id_usuario_actual()))))) WITH CHECK (((modulo1.fn_rol_actual() = 'Administrador'::text) OR (id_cuenta_usuario IN ( SELECT cuentas_usuarios.id_cuenta_usuario
   FROM modulo1.cuentas_usuarios
  WHERE (cuentas_usuarios.id_usuario = modulo1.fn_id_usuario_actual())))));
CREATE POLICY pol_tipos_eventos_select ON modulo1.tipos_eventos AS PERMISSIVE FOR SELECT USING (true);
CREATE POLICY pol_tokens_insert ON modulo1.tokens AS PERMISSIVE FOR INSERT WITH CHECK (true);
CREATE POLICY pol_tokens_select ON modulo1.tokens AS PERMISSIVE FOR SELECT USING (((modulo1.fn_rol_actual() = 'Administrador'::text) OR (EXISTS ( SELECT 1
   FROM (modulo1.sesiones s
     JOIN modulo1.cuentas_usuarios c ON ((c.id_cuenta_usuario = s.id_cuenta_usuario)))
  WHERE ((c.id_usuario = modulo1.fn_id_usuario_actual()) AND ((s.id_sesion = tokens.id_sesion) OR (s.id_token = tokens.id_token) OR (s.id_token_refresco = tokens.id_token)))))));
CREATE POLICY pol_tokens_update ON modulo1.tokens AS PERMISSIVE FOR UPDATE USING (((modulo1.fn_rol_actual() = 'Administrador'::text) OR (EXISTS ( SELECT 1
   FROM (modulo1.sesiones s
     JOIN modulo1.cuentas_usuarios c ON ((c.id_cuenta_usuario = s.id_cuenta_usuario)))
  WHERE ((c.id_usuario = modulo1.fn_id_usuario_actual()) AND ((s.id_sesion = tokens.id_sesion) OR (s.id_token = tokens.id_token) OR (s.id_token_refresco = tokens.id_token))))))) WITH CHECK (true);
CREATE POLICY pol_usuarios_insert ON modulo1.usuarios AS PERMISSIVE FOR INSERT WITH CHECK (true);
CREATE POLICY pol_usuarios_select ON modulo1.usuarios AS PERMISSIVE FOR SELECT USING (((id_usuario = modulo1.fn_id_usuario_actual()) OR (modulo1.fn_rol_actual() = 'Administrador'::text)));
CREATE POLICY pol_usuarios_update ON modulo1.usuarios AS PERMISSIVE FOR UPDATE USING (((id_usuario = modulo1.fn_id_usuario_actual()) OR (modulo1.fn_rol_actual() = 'Administrador'::text))) WITH CHECK (((id_usuario = modulo1.fn_id_usuario_actual()) OR (modulo1.fn_rol_actual() = 'Administrador'::text)));
"""


def _borrar_politicas() -> None:
    op.execute("""
        DO $$ DECLARE r record; BEGIN
          FOR r IN SELECT policyname, tablename FROM pg_policies WHERE schemaname = 'modulo1' LOOP
            EXECUTE format('DROP POLICY %I ON modulo1.%I', r.policyname, r.tablename);
          END LOOP; END $$;
    """)


def upgrade() -> None:
    # Guarda: si no corre como superusuario/BYPASSRLS, las funciones SECURITY
    # DEFINER + FORCE causan recursión infinita. Mejor fallar aquí que en prod.
    op.execute("""
        DO $$ BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_roles
                         WHERE rolname = current_user AND (rolsuper OR rolbypassrls)) THEN
            RAISE EXCEPTION 'F5 debe correr como superusuario o con BYPASSRLS: las funciones de '
              'apoyo quedan a nombre de este rol y, con FORCE, otro dueño entra en recursión infinita';
          END IF;
        END $$;
    """)

    _borrar_politicas()

    for firma, cuerpo in _FUNCIONES.items():
        op.execute(f"""
            CREATE OR REPLACE FUNCTION modulo1.{firma}
            LANGUAGE sql STABLE SECURITY DEFINER
            SET search_path = pg_catalog, modulo1 AS $${cuerpo}$$;
        """)
        nombre = firma.split(" RETURNS")[0]
        op.execute(f"REVOKE ALL ON FUNCTION modulo1.{nombre} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION modulo1.{nombre} TO sgpmp_app")

    for tabla in _CATALOGOS:
        op.execute(f"CREATE POLICY pol_{tabla}_select ON modulo1.{tabla} FOR SELECT USING (true)")

    for nombre, tabla, comando, using, check in _POLITICAS:
        sql = f"CREATE POLICY {nombre} ON modulo1.{tabla} FOR {comando}"
        if using:
            sql += f" USING ({using})"
        if check:
            sql += f" WITH CHECK ({check})"
        op.execute(sql)

    op.execute("""
        DO $$ DECLARE t text; BEGIN
          FOR t IN SELECT tablename FROM pg_tables WHERE schemaname = 'modulo1' LOOP
            EXECUTE format('ALTER TABLE modulo1.%I FORCE ROW LEVEL SECURITY', t);
          END LOOP; END $$;
    """)


def downgrade() -> None:
    op.execute("""
        DO $$ DECLARE t text; BEGIN
          FOR t IN SELECT tablename FROM pg_tables WHERE schemaname = 'modulo1' LOOP
            EXECUTE format('ALTER TABLE modulo1.%I NO FORCE ROW LEVEL SECURITY', t);
          END LOOP; END $$;
    """)
    _borrar_politicas()
    op.execute(_POLITICAS_ANTERIORES)
    for firma in reversed(list(_FUNCIONES)):
        op.execute(f"DROP FUNCTION modulo1.{firma.split(' RETURNS')[0]}")