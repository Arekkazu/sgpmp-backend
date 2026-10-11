"""Vistas modulo1

Revision ID: 58c0b8b18f74
Revises: f68851f9a433
Create Date: 2026-10-11 07:35:50.641236

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '58c0b8b18f74'
down_revision: Union[str, Sequence[str], None] = 'f68851f9a433'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # =====================================================================
    # 1. CORRECCIONES / AJUSTES A VISTAS EXISTENTES
    # =====================================================================
    op.execute("""
    -- RF-01: la ventana de 24h se contaba desde fecha_registro; tras un cambio de
    -- correo (RF-05) la cuenta vuelve a PENDIENTE con token nuevo, asi que la
    -- referencia correcta es fecha_cambio_estado. Se excluye ELIMINADO.
    CREATE OR REPLACE VIEW modulo1.vw_registros_pendientes_activacion AS
     SELECT u.id_usuario,
        u.nombre,
        u.apellidos,
        u.correo_electronico,
        u.fecha_registro,
        r.id_rol,
        r.nombre_rol,
        cu.id_cuenta_usuario,
        ec.id_estado_cuenta,
        ec.nombre AS estado_cuenta,
        cu.tiene_correo_verificado,
        cu.fecha_verificacion,
        (cu.token_activacion_actual IS NOT NULL) AS tiene_token_activacion,
        cu.fecha_cambio_estado,
        ((now())::timestamp without time zone - u.fecha_registro) AS antiguedad_registro,
        ((now() - COALESCE(cu.fecha_cambio_estado, u.fecha_registro::timestamptz)) > interval '24 hours') AS supera_ventana_activacion,
        cu.es_token_usado,
        (COALESCE(cu.fecha_cambio_estado, u.fecha_registro::timestamptz) + interval '24 hours') AS fecha_limite_activacion
       FROM modulo1.usuarios u
         JOIN modulo1.roles r ON r.id_rol = u.id_rol
         JOIN modulo1.cuentas_usuarios cu ON cu.id_usuario = u.id_usuario
         JOIN modulo1.estados_cuentas ec ON ec.id_estado_cuenta = cu.id_estado_cuenta
      WHERE (cu.tiene_correo_verificado IS FALSE OR upper(ec.nombre::text) LIKE 'PENDIENTE%')
        AND upper(ec.nombre::text) <> 'ELIMINADO';

    -- RF-01/RF-08/RF-09: se agrega el usuario dueno del token (join por hash contra
    -- cuentas_usuarios, porque tokens no tiene FK a usuarios) y conformidad con 24h.
    -- Nunca se expone hash_valor.
    CREATE OR REPLACE VIEW modulo1.vw_tokens_seguridad_estado AS
     SELECT t.id_token,
        t.token_tipo,
        t.fecha_creacion,
        t.fecha_expiracion,
        t.fecha_uso,
        t.id_sesion,
        (t.hash_valor IS NOT NULL) AS tiene_hash_almacenado,
        (t.fecha_expiracion - t.fecha_creacion) AS vigencia_configurada,
            CASE
                WHEN t.fecha_uso IS NOT NULL THEN 'UTILIZADO'::text
                WHEN t.fecha_expiracion IS NULL THEN 'SIN_EXPIRACION'::text
                WHEN t.fecha_expiracion <= now() THEN 'EXPIRADO'::text
                ELSE 'VIGENTE'::text
            END AS estado_token,
        cu.id_usuario,
        (t.token_tipo = 'verificacion_correo'::modulo1.enum_token_tipo
           AND (t.fecha_expiracion - t.fecha_creacion) <= interval '24 hours') AS vigencia_conforme_rf01
       FROM modulo1.tokens t
         LEFT JOIN modulo1.cuentas_usuarios cu ON cu.token_activacion_actual::text = t.hash_valor::text
      WHERE t.token_tipo = ANY (ARRAY['verificacion_correo'::modulo1.enum_token_tipo, 'recuperacion'::modulo1.enum_token_tipo]);

    -- RF-02: intentos_restantes podia quedar negativo (>5 intentos registrados).
    CREATE OR REPLACE VIEW modulo1.vw_control_acceso_cuenta AS
     SELECT u.id_usuario,
        u.nombre,
        u.apellidos,
        u.correo_electronico,
        r.id_rol,
        r.nombre_rol,
        cu.id_cuenta_usuario,
        ec.id_estado_cuenta,
        ec.nombre AS estado_cuenta,
        cu.tiene_correo_verificado,
        cu.intentos_fallidos,
        GREATEST(5 - cu.intentos_fallidos, 0) AS intentos_restantes,
        cu.ultimo_intento_fallido,
        cu.bloqueado_hasta,
        ((cu.bloqueado_hasta IS NOT NULL) AND (cu.bloqueado_hasta > now())) AS esta_bloqueado_temporalmente,
        GREATEST((cu.bloqueado_hasta - now()), '00:00:00'::interval) AS tiempo_restante_bloqueo,
        cu.ultimo_acceso,
        cu.fecha_cambio_estado,
        cu.motivo_ultimo_cambio,
        ((upper(ec.nombre::text) = 'ACTIVO'::text) AND (cu.tiene_correo_verificado IS TRUE) AND ((cu.bloqueado_hasta IS NULL) OR (cu.bloqueado_hasta <= now()))) AS puede_autenticar
       FROM modulo1.usuarios u
         JOIN modulo1.roles r ON r.id_rol = u.id_rol
         JOIN modulo1.cuentas_usuarios cu ON cu.id_usuario = u.id_usuario
         JOIN modulo1.estados_cuentas ec ON ec.id_estado_cuenta = cu.id_estado_cuenta;

    -- RF-11: el refresco/deteccion de cambios concurrentes necesita marcas de cambio
    -- (estado, edicion y version). Se agregan al final.
    CREATE OR REPLACE VIEW modulo1.vw_usuarios_listado_admin AS
     SELECT u.id_usuario,
        (((u.nombre)::text || ' '::text) || (u.apellidos)::text) AS nombre_usuario,
        u.nombre,
        u.apellidos,
        u.correo_electronico,
        r.id_rol,
        r.nombre_rol AS rol,
        ec.id_estado_cuenta,
        ec.nombre AS estado_cuenta,
        u.fecha_registro,
        cu.fecha_cambio_estado,
        u.fecha_actualizacion,
        u.version
       FROM modulo1.usuarios u
         JOIN modulo1.roles r ON r.id_rol = u.id_rol
         JOIN modulo1.cuentas_usuarios cu ON cu.id_usuario = u.id_usuario
         JOIN modulo1.estados_cuentas ec ON ec.id_estado_cuenta = cu.id_estado_cuenta
      WHERE upper(ec.nombre::text) <> 'ELIMINADO'::text;

    -- RF-12/RF-13: (a) con <=4 caracteres ya no se devuelve una mascara (revelaba la
    -- longitud y RF-13 pide ocultar el campo ante formato inesperado) -> NULL;
    -- (b) ELIMINADO queda fuera (RF-12 responde 404 para eliminados logicos).
    CREATE OR REPLACE VIEW modulo1.vw_usuario_ficha_datos AS
     SELECT u.id_usuario,
        u.nombre,
        u.apellidos,
        u.correo_electronico,
        u.tipo_identificacion,
            CASE
                WHEN u.numero_identificacion IS NULL THEN NULL::text
                WHEN length(u.numero_identificacion::text) <= 4 THEN NULL::text
                ELSE left(u.numero_identificacion::text, 4) || repeat('*'::text, length(u.numero_identificacion::text) - 4)
            END AS numero_identificacion_enmascarado,
        u.fecha_nacimiento,
        u.fecha_registro,
        r.id_rol,
        r.nombre_rol AS rol,
        ec.id_estado_cuenta,
        ec.nombre AS estado_cuenta
       FROM modulo1.usuarios u
         JOIN modulo1.roles r ON r.id_rol = u.id_rol
         JOIN modulo1.cuentas_usuarios cu ON cu.id_usuario = u.id_usuario
         JOIN modulo1.estados_cuentas ec ON ec.id_estado_cuenta = cu.id_estado_cuenta
      WHERE upper(ec.nombre::text) <> 'ELIMINADO'::text;

    -- RF-10: se agregan categoria, descripcion e id_sesion para no tener que saltar
    -- a la vista completa en consultas livianas.
    CREATE OR REPLACE VIEW modulo1.vw_eventos_usuario_detalle AS
     SELECT e.id_evento,
        u.id_usuario,
        u.nombre,
        u.apellidos,
        te.id_tipo_evento,
        te.nombre AS nombre_evento,
        te.accion AS accion_evento,
        e.modulo,
        e.resultado,
        e.estado,
        e.fecha_evento,
        e.categoria,
        e.descripcion,
        e.id_sesion
       FROM modulo1.eventos e
         JOIN modulo1.usuarios u ON u.id_usuario = e.id_usuario
         JOIN modulo1.tipos_eventos te ON te.id_tipo_evento = e.tipo_evento;

    -- RF-02/RF-10: el LATERAL original pegaba a CADA evento historico la sesion activa
    -- mas reciente del usuario (sesion que no necesariamente generó el evento).
    -- Ahora se une por eventos.id_sesion = sesiones.id_sesion y se filtra es_activa.
    CREATE OR REPLACE VIEW modulo1.vw_eventos_usuario_sesion_activa AS
     SELECT e.id_evento,
        u.id_usuario,
        u.nombre,
        u.apellidos,
        te.nombre AS nombre_evento,
        e.estado,
        e.modulo,
        s.id_sesion,
        s.direccion_ip,
        e.fecha_evento,
        s.fecha_inicio AS fecha_inicio_sesion,
        s.agente_usuario
       FROM modulo1.eventos e
         JOIN modulo1.usuarios u ON u.id_usuario = e.id_usuario
         JOIN modulo1.tipos_eventos te ON te.id_tipo_evento = e.tipo_evento
         JOIN modulo1.sesiones s ON s.id_sesion = e.id_sesion AND s.es_activa IS TRUE;

    -- RF-14: se agregan estado_envio y canal para poder distinguir QUEUED/SENT/FAILED.
    CREATE OR REPLACE VIEW modulo1.vw_notificaciones_eventos AS
     SELECT n.id_notificacion,
        n.id_evento,
        n.mensaje,
        n.fecha_envio,
        n.es_leido,
        u.id_usuario,
        u.nombre,
        u.apellidos,
        e.descripcion AS evento,
        e.modulo,
        e.fecha_evento,
        n.estado_envio,
        n.id_notificacion_canal
       FROM modulo1.notificaciones n
         JOIN modulo1.eventos e ON e.id_evento = n.id_evento
         JOIN modulo1.usuarios u ON u.id_usuario = n.id_usuario;

    -- RF-04: se agregan es_proceso_especial (valida accion E) y es_protegido del rol.
    CREATE OR REPLACE VIEW modulo1.vw_permisos_roles AS
     SELECT r.id_rol,
        r.nombre_rol,
        p.id_permiso,
        p.nombre AS permiso,
        p.descripcion AS descripcion_permiso,
        a.id_accion,
        a.codigo AS codigo_accion,
        a.descripcion AS accion,
        rec.id_recurso,
        rec.nombre_recurso AS recurso,
        rec.descripcion AS descripcion_recurso,
        p.fecha_creacion AS fecha_asignacion,
        p.fecha_actualizacion,
        p.es_activo,
        rec.es_proceso_especial,
        r.es_protegido
       FROM modulo1.roles r
         JOIN modulo1.permisos p ON p.id_rol = r.id_rol
         JOIN modulo1.acciones a ON a.id_accion = p.id_accion
         JOIN modulo1.recursos rec ON rec.id_recurso = p.id_recurso;

    -- RF-06: la pantalla de gestion necesita motivo/fecha del ultimo cambio y saber si
    -- la cuenta es el ULTIMO administrador activo (flujo alterno "ultimo administrador").
    CREATE OR REPLACE VIEW modulo1.vw_resumen_cuentas_usuarios AS
     SELECT u.id_usuario,
        u.nombre,
        u.apellidos,
        u.correo_electronico,
        u.telefono,
        r.id_rol,
        r.nombre_rol AS rol,
        cu.id_cuenta_usuario,
        ec.id_estado_cuenta,
        ec.nombre AS estado_cuenta,
        cu.ultimo_acceso,
        cu.fecha_cambio_estado,
        cu.motivo_ultimo_cambio,
        cu.tiene_correo_verificado,
        (upper(r.nombre_rol::text) = 'ADMINISTRADOR') AS es_administrador,
        ((upper(r.nombre_rol::text) = 'ADMINISTRADOR')
           AND (upper(ec.nombre::text) = 'ACTIVO')
           AND (( SELECT count(*)
                   FROM modulo1.usuarios ua
                     JOIN modulo1.roles ra ON ra.id_rol = ua.id_rol
                     JOIN modulo1.cuentas_usuarios cua ON cua.id_usuario = ua.id_usuario
                     JOIN modulo1.estados_cuentas eca ON eca.id_estado_cuenta = cua.id_estado_cuenta
                  WHERE upper(ra.nombre_rol::text) = 'ADMINISTRADOR'
                    AND upper(eca.nombre::text) = 'ACTIVO') = 1)) AS es_ultimo_administrador_activo
       FROM modulo1.usuarios u
         JOIN modulo1.roles r ON r.id_rol = u.id_rol
         JOIN modulo1.cuentas_usuarios cu ON cu.id_usuario = u.id_usuario
         JOIN modulo1.estados_cuentas ec ON ec.id_estado_cuenta = cu.id_estado_cuenta;

    -- RF-02: se agregan expiracion esperada, agente y bandera de sesion vencida pero
    -- aun marcada activa (limpieza pendiente).
    CREATE OR REPLACE VIEW modulo1.vw_sesiones_activas_usuario AS
     SELECT u.id_usuario,
        u.nombre,
        u.apellidos,
        r.id_rol,
        r.nombre_rol,
        cu.id_cuenta_usuario,
        cu.ultimo_acceso,
        ec.nombre AS estado_cuenta,
        s.id_sesion,
        s.es_activa,
        s.direccion_ip,
        s.fecha_inicio,
        s.fecha_finalizacion,
        s.agente_usuario,
        (s.fecha_finalizacion <= now()) AS sesion_vencida
       FROM modulo1.sesiones s
         JOIN modulo1.cuentas_usuarios cu ON cu.id_cuenta_usuario = s.id_cuenta_usuario
         JOIN modulo1.usuarios u ON u.id_usuario = cu.id_usuario
         JOIN modulo1.roles r ON r.id_rol = u.id_rol
         JOIN modulo1.estados_cuentas ec ON ec.id_estado_cuenta = cu.id_estado_cuenta
      WHERE s.es_activa IS TRUE;

    -- RF-14: total_enviadas para completar el control anti-spam (QUEUED/SENT/FAILED).
    CREATE OR REPLACE VIEW modulo1.vw_notificaciones_control_frecuencia AS
     SELECT n.id_usuario,
        te.id_tipo_evento,
        te.nombre AS tipo_evento,
        nc.id_notificacion_canal,
        nc.nombre AS canal_envio,
        max(n.fecha_envio) AS ultimo_envio,
        (now() - max(n.fecha_envio)) AS tiempo_desde_ultimo_envio,
        ((now() - max(n.fecha_envio)) < '00:05:00'::interval) AS en_ventana_antispam,
        count(*) AS total_notificaciones,
        count(*) FILTER (WHERE n.estado_envio = 'fallido'::modulo1.enum_estado_envio) AS total_fallidas,
        count(*) FILTER (WHERE n.estado_envio = 'enviado'::modulo1.enum_estado_envio) AS total_enviadas
       FROM modulo1.notificaciones n
         JOIN modulo1.eventos e ON e.id_evento = n.id_evento
         JOIN modulo1.tipos_eventos te ON te.id_tipo_evento = e.tipo_evento
         JOIN modulo1.notificaciones_canal nc ON nc.id_notificacion_canal = n.id_notificacion_canal
      GROUP BY n.id_usuario, te.id_tipo_evento, te.nombre, nc.id_notificacion_canal, nc.nombre;

    -- RF-03: puede_modificarse (rol protegido es inmutable).
    CREATE OR REPLACE VIEW modulo1.vw_roles_resumen_permisos AS
     SELECT r.id_rol,
        r.nombre_rol,
        r.descripcion,
        r.es_protegido,
        r.fecha_creacion,
        r.fecha_actualizacion,
        count(p.id_permiso) FILTER (WHERE p.es_activo IS TRUE) AS total_permisos_activos,
        count(p.id_permiso) AS total_permisos,
        count(DISTINCT p.id_recurso) FILTER (WHERE p.es_activo IS TRUE) AS total_recursos_cubiertos,
        ( SELECT count(*) AS count
               FROM modulo1.usuarios u
              WHERE u.id_rol = r.id_rol) AS total_usuarios_asignados,
        (count(p.id_permiso) FILTER (WHERE p.es_activo IS TRUE) > 0) AS cumple_permiso_minimo,
        ((r.es_protegido IS FALSE) AND (NOT (EXISTS ( SELECT 1
               FROM modulo1.usuarios u2
              WHERE u2.id_rol = r.id_rol)))) AS puede_eliminarse,
        (r.es_protegido IS FALSE) AS puede_modificarse
       FROM modulo1.roles r
         LEFT JOIN modulo1.permisos p ON p.id_rol = r.id_rol
      GROUP BY r.id_rol, r.nombre_rol, r.descripcion, r.es_protegido, r.fecha_creacion, r.fecha_actualizacion;

    -- RF-05: se elimina el id_rol = 1 hardcodeado (fragil ante re-seed) y se agrega la
    -- bandera de ultimo administrador activo (restriccion de autogestion).
    CREATE OR REPLACE VIEW modulo1.vw_usuarios_edicion_datos AS
     SELECT u.id_usuario,
        u.nombre,
        u.apellidos,
        u.correo_electronico,
        u.telefono,
        u.direccion,
        u.id_rol,
        r.nombre_rol,
        cu.id_cuenta_usuario,
        cu.id_estado_cuenta,
        ec.nombre AS estado_cuenta,
        cu.tiene_correo_verificado,
        u.version,
        u.fecha_actualizacion,
        u.fecha_registro,
        (upper(r.nombre_rol::text) = 'ADMINISTRADOR') AS es_administrador,
        ((upper(r.nombre_rol::text) = 'ADMINISTRADOR')
           AND (upper(ec.nombre::text) = 'ACTIVO')
           AND (( SELECT count(*)
                   FROM modulo1.usuarios ua
                     JOIN modulo1.roles ra ON ra.id_rol = ua.id_rol
                     JOIN modulo1.cuentas_usuarios cua ON cua.id_usuario = ua.id_usuario
                     JOIN modulo1.estados_cuentas eca ON eca.id_estado_cuenta = cua.id_estado_cuenta
                  WHERE upper(ra.nombre_rol::text) = 'ADMINISTRADOR'
                    AND upper(eca.nombre::text) = 'ACTIVO') = 1)) AS es_ultimo_administrador_activo
       FROM modulo1.usuarios u
         JOIN modulo1.roles r ON r.id_rol = u.id_rol
         JOIN modulo1.cuentas_usuarios cu ON cu.id_usuario = u.id_usuario
         JOIN modulo1.estados_cuentas ec ON ec.id_estado_cuenta = cu.id_estado_cuenta;
    """)

    # =====================================================================
    # 2. VISTAS NUEVAS
    # =====================================================================
    op.execute("""
    -- Reemplazo seguro de usuarios_admin (que expone contrasena_cifrada).
    CREATE OR REPLACE VIEW modulo1.vw_administradores_sistema AS
     SELECT u.id_usuario,
        u.nombre,
        u.apellidos,
        u.correo_electronico,
        r.id_rol,
        r.nombre_rol,
        cu.id_cuenta_usuario,
        ec.id_estado_cuenta,
        ec.nombre AS estado_cuenta,
        (upper(ec.nombre::text) = 'ACTIVO') AS es_activo,
        cu.fecha_cambio_estado
       FROM modulo1.usuarios u
         JOIN modulo1.roles r ON r.id_rol = u.id_rol
         JOIN modulo1.cuentas_usuarios cu ON cu.id_usuario = u.id_usuario
         JOIN modulo1.estados_cuentas ec ON ec.id_estado_cuenta = cu.id_estado_cuenta
      WHERE upper(r.nombre_rol::text) = 'ADMINISTRADOR';

    -- Matriz rol x recurso x {C,R,U,D,E} para la UI de permisos.
    CREATE OR REPLACE VIEW modulo1.vw_matriz_permisos_rol AS
     SELECT r.id_rol,
        r.nombre_rol,
        rec.id_recurso,
        rec.nombre_recurso,
        rec.es_proceso_especial,
        COALESCE(bool_or(a.codigo = 'C') FILTER (WHERE p.es_activo IS TRUE), false) AS puede_crear,
        COALESCE(bool_or(a.codigo = 'R') FILTER (WHERE p.es_activo IS TRUE), false) AS puede_leer,
        COALESCE(bool_or(a.codigo = 'U') FILTER (WHERE p.es_activo IS TRUE), false) AS puede_actualizar,
        COALESCE(bool_or(a.codigo = 'D') FILTER (WHERE p.es_activo IS TRUE), false) AS puede_eliminar,
        COALESCE(bool_or(a.codigo = 'E') FILTER (WHERE p.es_activo IS TRUE), false) AS puede_ejecutar,
        count(p.id_permiso) FILTER (WHERE p.es_activo IS TRUE) AS total_acciones_activas
       FROM modulo1.roles r
         CROSS JOIN modulo1.recursos rec
         LEFT JOIN modulo1.permisos p ON p.id_rol = r.id_rol AND p.id_recurso = rec.id_recurso
         LEFT JOIN modulo1.acciones a ON a.id_accion = p.id_accion
      GROUP BY r.id_rol, r.nombre_rol, rec.id_recurso, rec.nombre_recurso, rec.es_proceso_especial;

    -- Rol con su lista_permisos en jsonb (consulta de rol y propagacion a sesiones).
    CREATE OR REPLACE VIEW modulo1.vw_roles_lista_permisos AS
     SELECT r.id_rol,
        r.nombre_rol,
        r.es_protegido,
        COALESCE(jsonb_agg(jsonb_build_object(
            'id_permiso', p.id_permiso,
            'id_recurso', p.id_recurso,
            'recurso', rec.nombre_recurso,
            'id_accion', p.id_accion,
            'accion', a.codigo::text))
          FILTER (WHERE p.id_permiso IS NOT NULL AND p.es_activo IS TRUE), '[]'::jsonb) AS lista_permisos,
        count(p.id_permiso) FILTER (WHERE p.es_activo IS TRUE) AS total_permisos_activos,
        max(COALESCE(p.fecha_actualizacion, p.fecha_creacion)) AS ultima_modificacion_permisos
       FROM modulo1.roles r
         LEFT JOIN modulo1.permisos p ON p.id_rol = r.id_rol
         LEFT JOIN modulo1.recursos rec ON rec.id_recurso = p.id_recurso
         LEFT JOIN modulo1.acciones a ON a.id_accion = p.id_accion
      GROUP BY r.id_rol, r.nombre_rol, r.es_protegido;

    -- Elegibilidad de destinatarios segun estado de cuenta (reglas de RF-14).
    CREATE OR REPLACE VIEW modulo1.vw_usuarios_elegibilidad_notificacion AS
     SELECT u.id_usuario,
        u.correo_electronico,
        ec.id_estado_cuenta,
        ec.nombre AS estado_cuenta,
        cu.tiene_correo_verificado,
        (u.correo_electronico ~* '^[^@ ]+@[^@ ]+[.][^@ ]+$') AS correo_valido,
        ((upper(ec.nombre::text) = 'ACTIVO')
           AND cu.tiene_correo_verificado IS TRUE
           AND (u.correo_electronico ~* '^[^@ ]+@[^@ ]+[.][^@ ]+$')) AS recibe_notificaciones_generales,
        ((upper(ec.nombre::text) IN ('ACTIVO', 'BLOQUEADO'))
           AND cu.tiene_correo_verificado IS TRUE
           AND (u.correo_electronico ~* '^[^@ ]+@[^@ ]+[.][^@ ]+$')) AS recibe_notificaciones_seguridad
       FROM modulo1.usuarios u
         JOIN modulo1.cuentas_usuarios cu ON cu.id_usuario = u.id_usuario
         JOIN modulo1.estados_cuentas ec ON ec.id_estado_cuenta = cu.id_estado_cuenta;

    -- Bandeja interna del usuario (canal INTERNO de RF-14). Se filtra por nombre del
    -- canal porque notificaciones_canal.canal es un enum mal usado (issue conocido).
    CREATE OR REPLACE VIEW modulo1.vw_notificaciones_bandeja_usuario AS
     SELECT n.id_notificacion,
        n.id_usuario,
        te.id_tipo_evento,
        te.nombre AS tipo_evento,
        n.mensaje,
        e.fecha_evento,
        n.fecha_envio,
        n.es_leido,
        n.estado_envio
       FROM modulo1.notificaciones n
         JOIN modulo1.eventos e ON e.id_evento = n.id_evento
         JOIN modulo1.tipos_eventos te ON te.id_tipo_evento = e.tipo_evento
         JOIN modulo1.notificaciones_canal nc ON nc.id_notificacion_canal = n.id_notificacion_canal
      WHERE upper(nc.nombre::text) LIKE 'INTERN%'
        AND n.estado_envio = 'enviado'::modulo1.enum_estado_envio;

    -- Eventos vigentes que ya superan la retencion minima de 12 meses (candidatos a
    -- archivar; sirve para monitorear el job de archivado de RF-10).
    CREATE OR REPLACE VIEW modulo1.vw_auditoria_eventos_por_archivar AS
     SELECT e.id_evento,
        e.fecha_evento,
        (now() - e.fecha_evento) AS antiguedad,
        e.id_usuario,
        te.nombre AS tipo_evento,
        e.modulo,
        e.categoria,
        e.resultado
       FROM modulo1.eventos e
         JOIN modulo1.tipos_eventos te ON te.id_tipo_evento = e.tipo_evento
      WHERE e.fecha_evento < (now() - interval '12 months');

    -- Frecuencia/volumen de consultas por usuario (deteccion de extraccion masiva,
    -- RF-12). SUPUESTOS a validar: categoria = 'CONSULTA' y detalle->>'id_usuario_consultado'.
    CREATE OR REPLACE VIEW modulo1.vw_auditoria_frecuencia_consultas AS
     SELECT e.id_usuario,
        count(*) FILTER (WHERE e.fecha_evento >= now() - interval '1 minute') AS consultas_ultimo_minuto,
        count(*) FILTER (WHERE e.fecha_evento >= now() - interval '5 minutes') AS consultas_ultimos_5_min,
        count(*) AS consultas_ultima_hora,
        count(DISTINCT e.detalle ->> 'id_usuario_consultado')
          FILTER (WHERE e.fecha_evento >= now() - interval '5 minutes') AS usuarios_distintos_5_min,
        max(e.fecha_evento) AS ultima_consulta
       FROM modulo1.eventos e
      WHERE upper(e.categoria::text) = 'CONSULTA'
        AND e.fecha_evento >= now() - interval '1 hour'
      GROUP BY e.id_usuario;
    """)

    # =====================================================================
    # 3. COMENTARIOS (RF que respalda cada vista)
    # =====================================================================
    op.execute("""
    COMMENT ON VIEW modulo1.vw_registros_pendientes_activacion IS 'RF-01 (activacion por token 24h, reenvio), RF-05 (cuenta vuelve a PENDIENTE al cambiar correo), RF-06 (estado PENDIENTE). Cuentas sin verificar o en PENDIENTE, excluye ELIMINADO. Ventana de 24h medida desde fecha_cambio_estado.';
    COMMENT ON VIEW modulo1.vw_tokens_seguridad_estado IS 'RF-01 (token de activacion), RF-08/RF-09 (recuperacion y restablecimiento de contrasena). Estado derivado del token (VIGENTE/EXPIRADO/UTILIZADO) y usuario dueno via hash. Nunca expone hash_valor.';
    COMMENT ON VIEW modulo1.vw_control_acceso_cuenta IS 'RF-02 (5 intentos, bloqueo 15 min, cuenta activa), RF-01 (correo verificado), RF-06 (estado de cuenta). Decision puede_autenticar. No expone credenciales.';
    COMMENT ON VIEW modulo1.vw_usuarios_listado_admin IS 'RF-11 (listado paginado admin: nombre_usuario, correo, rol, estado; filtros AND), RF-06 (excluye ELIMINADO). Incluye fecha_cambio_estado/fecha_actualizacion/version para refresco y deteccion de cambios concurrentes. Orden y paginacion en backend.';
    COMMENT ON VIEW modulo1.vw_usuario_ficha_datos IS 'RF-12 (detalle de usuario por admin), RF-13 (perfil propio, id desde JWT). Identificacion enmascarada (4 primeros digitos); NULL si <=4. Sin contrasena/hash/token. Identificacion completa solo via permiso en backend (RF-04). Excluye ELIMINADO.';
    COMMENT ON VIEW modulo1.vw_cuentas_correo_estado IS 'RF-01 (verificacion de correo), RF-05 (reverificacion tras cambio de correo), RF-14 (precondicion: correo verificado).';
    COMMENT ON VIEW modulo1.vw_eventos_usuario_detalle IS 'RF-10 (historial de auditoria, version liviana por usuario/evento). Para consulta completa usar vw_auditoria_eventos_completa.';
    COMMENT ON VIEW modulo1.vw_eventos_usuario_sesion_activa IS 'RF-02 (sesion unica activa), RF-10 (trazabilidad por sesion). Eventos cuya id_sesion pertenece a una sesion activa.';
    COMMENT ON VIEW modulo1.vw_notificaciones_eventos IS 'RF-14 (notificaciones asociadas a eventos), RF-10 (evento origen). Incluye estado_envio y canal.';
    COMMENT ON VIEW modulo1.vw_permisos_roles IS 'RF-03 (consulta de roles y permisos), RF-04 (rol + recurso + accion; valida accion E en proceso especial).';
    COMMENT ON VIEW modulo1.vw_resumen_cuentas_usuarios IS 'RF-06 (gestion de cuentas: estado, ultimo cambio, motivo, ultimo administrador activo), RF-05 (datos de contacto y rol), RF-11 (supervision). Incluye cuentas ELIMINADO.';
    COMMENT ON VIEW modulo1.vw_sesiones_activas_usuario IS 'RF-02 (una sesion activa por usuario, vigencia 8h, invalidacion), RF-06 (invalidacion al cambiar estado), RF-10 (id_sesion, IP, agente).';
    COMMENT ON VIEW modulo1.vw_usuarios_contacto IS 'RF-05 (datos de contacto editables: correo, telefono), RF-14 (destinatario de notificaciones). Sin datos sensibles.';
    COMMENT ON VIEW modulo1.vw_gestiones_cuenta_historial IS 'RF-06 (bitacora de acciones administrativas con responsable y motivo), RF-10 (cambios de estado de cuenta auditables).';
    COMMENT ON VIEW modulo1.vw_auditoria_eventos_completa IS 'RF-10 (historial de auditoria: usuario, accion, modulo, fecha, resultado, IP, sesion, hash SHA-256), RF-12 (auditoria de acceso a ficha), RF-11. estado_integridad compara contra baseline; NO recalcula el hash.';
    COMMENT ON VIEW modulo1.vw_auditoria_eventos_historico IS 'RF-10 (retencion minima 12 meses: eventos vigentes + archivados en una sola consulta).';
    COMMENT ON VIEW modulo1.vw_notificaciones_usuario_canal IS 'RF-14 (notificaciones por usuario, evento, canal y estado QUEUED/SENT/FAILED), RF-06 (estado de la cuenta del destinatario).';
    COMMENT ON VIEW modulo1.vw_notificaciones_control_frecuencia IS 'RF-14 (politica anti-spam: 1 por tipo_evento + usuario + canal cada 5 min; fallidas sin reintento).';
    COMMENT ON VIEW modulo1.vw_permisos_efectivos_usuario IS 'RF-03 (permisos efectivos solo para cuentas ACTIVO, validacion en cada solicitud), RF-04 (propagacion dinamica a sesiones activas).';
    COMMENT ON VIEW modulo1.vw_roles_resumen_permisos IS 'RF-03 (rol con al menos un permiso, no eliminar con usuarios, rol Administrador protegido), RF-04 (cobertura de recursos).';
    COMMENT ON VIEW modulo1.vw_catalogo_recursos_acciones IS 'RF-04 (catalogo recurso x accion; E solo en procesos especiales, CRUD en el resto).';
    COMMENT ON VIEW modulo1.vw_usuarios_edicion_datos IS 'RF-05 (edicion de datos: campos editables, control de concurrencia optimista con version, restriccion de autogestion del administrador), RF-06 (estado), RF-03 (rol).';
    COMMENT ON VIEW modulo1.vw_administradores_sistema IS 'RF-03 (rol Administrador protegido), RF-05 y RF-06 (no degradar/desactivar al ultimo administrador activo), RF-10. Reemplazo de usuarios_admin sin datos sensibles.';
    COMMENT ON VIEW modulo1.vw_matriz_permisos_rol IS 'RF-04 (matriz rol x recurso con acciones C/R/U/D/E), RF-03 (interfaz de seleccion de permisos).';
    COMMENT ON VIEW modulo1.vw_roles_lista_permisos IS 'RF-03 (lista_permisos jsonb del rol, consulta de rol), RF-04 (marca ultima_modificacion_permisos para propagar cambios a sesiones activas).';
    COMMENT ON VIEW modulo1.vw_usuarios_elegibilidad_notificacion IS 'RF-14 (INACTIVO no recibe; BLOQUEADO solo seguridad; correo verificado y valido), RF-06 (estados de cuenta).';
    COMMENT ON VIEW modulo1.vw_notificaciones_bandeja_usuario IS 'RF-14 (visualizacion de notificaciones internas dentro de la plataforma, estado leido/no leido).';
    COMMENT ON VIEW modulo1.vw_auditoria_eventos_por_archivar IS 'RF-10 (politica de retencion: eventos con mas de 12 meses pendientes de archivado; monitoreo del job).';
    COMMENT ON VIEW modulo1.vw_auditoria_frecuencia_consultas IS 'RF-12 (deteccion de patrones de consulta inusual / extraccion masiva), RF-10 (consultas auditadas). Supuestos: categoria CONSULTA y detalle.id_usuario_consultado.';
    COMMENT ON VIEW modulo1.usuarios_admin IS 'LEGADO. Expone contrasena_cifrada y numero_identificacion completos, contrario a RF-11/RF-12/RF-13. Sustituir por vw_administradores_sistema y retirar tras verificar dependencias.';
    """)

    # =====================================================================
    # 4. PENDIENTE (no automatizado a proposito)
    # =====================================================================
    # Antes de retirar usuarios_admin, verificar dependencias:
    #   SELECT DISTINCT d.classid::regclass, d.objid
    #   FROM pg_depend d JOIN pg_rewrite rw ON rw.oid = d.objid
    #   WHERE d.refobjid = 'modulo1.usuarios_admin'::regclass AND rw.ev_class <> d.refobjid;
    #   (y buscar el nombre en funciones/triggers: pg_proc.prosrc ILIKE '%usuarios_admin%')
    # DROP VIEW modulo1.usuarios_admin;


def downgrade() -> None:
    # NOTA: Dado que el script original utiliza CREATE OR REPLACE y no provee 
    # las definiciones SQL previas de las vistas modificadas, el downgrade 
    # procede a eliminar las vistas creadas/alteradas en esta revisión.
    # Si necesitas restaurar la versión anterior de las vistas modificadas, 
    # deberás pegar el SQL antiguo de esas vistas aquí.
    
    views_to_drop = [
        'vw_registros_pendientes_activacion',
        'vw_tokens_seguridad_estado',
        'vw_control_acceso_cuenta',
        'vw_usuarios_listado_admin',
        'vw_usuario_ficha_datos',
        'vw_eventos_usuario_detalle',
        'vw_eventos_usuario_sesion_activa',
        'vw_notificaciones_eventos',
        'vw_permisos_roles',
        'vw_resumen_cuentas_usuarios',
        'vw_sesiones_activas_usuario',
        'vw_notificaciones_control_frecuencia',
        'vw_roles_resumen_permisos',
        'vw_usuarios_edicion_datos',
        'vw_administradores_sistema',
        'vw_matriz_permisos_rol',
        'vw_roles_lista_permisos',
        'vw_usuarios_elegibilidad_notificacion',
        'vw_notificaciones_bandeja_usuario',
        'vw_auditoria_eventos_por_archivar',
        'vw_auditoria_frecuencia_consultas'
    ]
    
    for view in views_to_drop:
        op.execute(f"DROP VIEW IF EXISTS modulo1.{view};")