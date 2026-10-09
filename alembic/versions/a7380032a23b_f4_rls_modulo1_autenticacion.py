"""F4 control de acceso: RLS de modulo1 compatible con la autenticación

Revision ID: a7380032a23b
Revises: 5c3e9b1d7a20
Create Date: 2026-10-07 00:00:00.000000

Con la API conectada como `sgpmp_app`, las políticas de `8d80fb56a30b` no
dejaban autenticar a nadie: `get_current_user` respondía 401 a todos, el
Administrador incluido. Diagnóstico y propuesta en el PR #485; el DBA autorizó
incluirlo en ese mismo PR.

1. `roles`, `permisos` y `recursos` quedan legibles para todos: la app los lee
   en cada request para autorizar a cualquier usuario. La escritura sigue
   siendo solo del Administrador.
2. `pol_tokens_select` / `pol_tokens_update` enlazaban por `tokens.id_sesion`,
   que solo existe en los tokens de refresco; el de acceso se enlaza por
   `sesiones.id_token`. Ahora aceptan los tres enlaces.
3. `pol_cuentas_usuarios_update`: el usuario actualiza su propia cuenta
   (último acceso, intentos fallidos, bloqueo, activación). Y
   `pol_eventos_select`: cada usuario lee sus propios eventos. Las
   notificaciones de RF-14 se enlazan con el evento del destinatario, así que
   sin esto la bandeja quedaba vacía y no se creaba ninguna notificación.
4. Funciones `SECURITY DEFINER` para los flujos sin identidad todavía (login,
   SSO, refresh, activación, recuperación). Solo responden "¿quién es?"; con
   ese id la app declara la identidad y el resto del flujo pasa por las
   políticas de fila propia. Nadie usa BYPASSRLS.
5. `credenciales_servicio` (RLS sin políticas) se puede leer con el rol
   Administrador: la verificación del token del broker corre como el usuario
   de servicio de D1. `intentos_anonimos_ip` es anónima por naturaleza (solo
   guarda contadores por IP), así que queda abierta a la app.
"""
from typing import Sequence, Union

from alembic import op

revision: str = 'a7380032a23b'
down_revision: Union[str, Sequence[str], None] = '5c3e9b1d7a20'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TOKEN_PROPIO = """
    modulo1.fn_rol_actual() = 'Administrador' OR EXISTS (
      SELECT 1 FROM modulo1.sesiones s
      JOIN modulo1.cuentas_usuarios c ON c.id_cuenta_usuario = s.id_cuenta_usuario
      WHERE c.id_usuario = modulo1.fn_id_usuario_actual()
        AND (s.id_sesion = tokens.id_sesion
             OR s.id_token = tokens.id_token
             OR s.id_token_refresco = tokens.id_token))
"""

_TOKEN_PROPIO_ANTERIOR = """
    modulo1.fn_rol_actual() = 'Administrador'
    OR id_sesion IN (
      SELECT s.id_sesion FROM modulo1.sesiones s
      JOIN modulo1.cuentas_usuarios c ON c.id_cuenta_usuario = s.id_cuenta_usuario
      WHERE c.id_usuario = modulo1.fn_id_usuario_actual())
"""

_FUNCIONES = {
    # Login, SSO, recuperación de contraseña y reenvío de activación.
    "fn_id_usuario_por_correo(p_correo text)": """
        SELECT id_usuario FROM modulo1.usuarios
        WHERE correo_electronico = p_correo
    """,
    # Activación de cuenta y restablecimiento de contraseña.
    "fn_id_usuario_por_hash_token_cuenta(p_hash text)": """
        SELECT id_usuario FROM modulo1.cuentas_usuarios
        WHERE token_activacion_actual = p_hash
    """,
    # Refresh: el token de refresco cuelga de su sesión por cualquiera de los dos lados.
    "fn_id_usuario_por_hash_token_refresco(p_hash text)": """
        SELECT c.id_usuario
        FROM modulo1.tokens t
        JOIN modulo1.sesiones s ON s.id_sesion = t.id_sesion OR s.id_token_refresco = t.id_token
        JOIN modulo1.cuentas_usuarios c ON c.id_cuenta_usuario = s.id_cuenta_usuario
        WHERE t.hash_valor = p_hash
        LIMIT 1
    """,
}


def upgrade() -> None:
    # 1. Catálogos de RBAC.
    op.execute("ALTER POLICY pol_roles_select ON modulo1.roles USING (true);")
    op.execute("CREATE POLICY pol_permisos_select ON modulo1.permisos FOR SELECT USING (true);")
    op.execute("CREATE POLICY pol_recursos_select ON modulo1.recursos FOR SELECT USING (true);")

    # 2. Tokens.
    op.execute(f"ALTER POLICY pol_tokens_select ON modulo1.tokens USING ({_TOKEN_PROPIO});")
    op.execute(f"ALTER POLICY pol_tokens_update ON modulo1.tokens USING ({_TOKEN_PROPIO});")

    # 3. Cuenta propia.
    op.execute(
        """
        ALTER POLICY pol_cuentas_usuarios_update ON modulo1.cuentas_usuarios
          USING (id_usuario = modulo1.fn_id_usuario_actual() OR modulo1.fn_rol_actual() = 'Administrador')
          WITH CHECK (id_usuario = modulo1.fn_id_usuario_actual() OR modulo1.fn_rol_actual() = 'Administrador');
        """
    )

    op.execute(
        "ALTER POLICY pol_eventos_select ON modulo1.eventos "
        "USING (modulo1.fn_rol_actual() = 'Administrador' OR id_usuario = modulo1.fn_id_usuario_actual());"
    )

    # 4. Flujos sin identidad.
    for firma, cuerpo in _FUNCIONES.items():
        op.execute(
            f"""
            CREATE OR REPLACE FUNCTION modulo1.{firma} RETURNS integer
              LANGUAGE sql STABLE SECURITY DEFINER
              SET search_path = pg_catalog, modulo1
            AS $$ {cuerpo} $$;
            """
        )
        op.execute(f"REVOKE ALL ON FUNCTION modulo1.{firma} FROM PUBLIC;")
        op.execute(f"GRANT EXECUTE ON FUNCTION modulo1.{firma} TO sgpmp_app;")
    # Límite por IP del reenvío de activación (RF-08): cuenta solicitudes ajenas.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION modulo1.fn_solicitudes_recuperacion_por_ip(p_ip text, p_desde timestamptz)
        RETURNS TABLE (total bigint, primera timestamptz)
          LANGUAGE sql STABLE SECURITY DEFINER
          SET search_path = pg_catalog, modulo1
        AS $$
            SELECT count(*), min(fecha_evento) FROM modulo1.eventos
            WHERE tipo_evento = 7 AND fecha_evento >= p_desde AND detalle ->> 'ip' = p_ip
        $$;
        """
    )
    op.execute("REVOKE ALL ON FUNCTION modulo1.fn_solicitudes_recuperacion_por_ip(text, timestamptz) FROM PUBLIC;")
    op.execute("GRANT EXECUTE ON FUNCTION modulo1.fn_solicitudes_recuperacion_por_ip(text, timestamptz) TO sgpmp_app;")

    # 5. Tablas con RLS y sin políticas.
    op.execute(
        "CREATE POLICY pol_credenciales_servicio_select ON modulo1.credenciales_servicio "
        "FOR SELECT USING (modulo1.fn_rol_actual() = 'Administrador');"
    )
    op.execute(
        "CREATE POLICY pol_intentos_anonimos_ip_all ON modulo1.intentos_anonimos_ip "
        "FOR ALL USING (true) WITH CHECK (true);"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS pol_intentos_anonimos_ip_all ON modulo1.intentos_anonimos_ip;")
    op.execute("DROP POLICY IF EXISTS pol_credenciales_servicio_select ON modulo1.credenciales_servicio;")
    op.execute("DROP FUNCTION IF EXISTS modulo1.fn_solicitudes_recuperacion_por_ip(text, timestamptz);")
    for firma in _FUNCIONES:
        nombre, argumentos = firma.split("(", 1)
        tipos = ", ".join(arg.split()[1] for arg in argumentos.rstrip(")").split(","))
        op.execute(f"DROP FUNCTION IF EXISTS modulo1.{nombre}({tipos});")
    op.execute(
        """
        ALTER POLICY pol_cuentas_usuarios_update ON modulo1.cuentas_usuarios
          USING (modulo1.fn_rol_actual() = 'Administrador' AND id_usuario <> modulo1.fn_id_usuario_actual())
          WITH CHECK (modulo1.fn_rol_actual() = 'Administrador' AND id_usuario <> modulo1.fn_id_usuario_actual());
        """
    )
    op.execute("ALTER POLICY pol_eventos_select ON modulo1.eventos USING (modulo1.fn_rol_actual() = 'Administrador');")
    op.execute(f"ALTER POLICY pol_tokens_update ON modulo1.tokens USING ({_TOKEN_PROPIO_ANTERIOR});")
    op.execute(f"ALTER POLICY pol_tokens_select ON modulo1.tokens USING ({_TOKEN_PROPIO_ANTERIOR});")
    op.execute("DROP POLICY IF EXISTS pol_recursos_select ON modulo1.recursos;")
    op.execute("DROP POLICY IF EXISTS pol_permisos_select ON modulo1.permisos;")
    op.execute("ALTER POLICY pol_roles_select ON modulo1.roles USING (modulo1.fn_rol_actual() = 'Administrador');")
