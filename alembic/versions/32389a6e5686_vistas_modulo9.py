"""Vistas modulo9

Revision ID: 32389a6e5686
Revises: 58c0b8b18f74
Create Date: 2026-10-11 07:53:58.358796

vistas modulo9 v2: correcciones por RF-15..RF-32, vista base de area de dispositivo y comentarios con RF
 
Revision ID: a7c41e9b3d02
Revises: REEMPLAZAR_CON_alembic_heads
Create Date: 2026-10-11
 
Alcance: SOLO vistas de modulo9 (sin DDL de tablas). Upgrade: crea vw_rf21_dispositivo_area_actual,
reemplaza 28 vistas (CREATE OR REPLACE, columnas nuevas al final), crea 2 vistas de validacion y
escribe COMMENT ON VIEW con los RF de las 58 vistas. Downgrade: DROP de lo tocado y recreacion
de las definiciones originales (pg_get_viewdef previo); los comentarios se limpian.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '32389a6e5686'
down_revision: Union[str, Sequence[str], None] = '58c0b8b18f74'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


 
# --- upgrade -------------------------------------------------------------
VIEWS_UPGRADE = [
    r"""CREATE OR REPLACE VIEW modulo9.vw_rf21_dispositivo_area_actual AS
 SELECT DISTINCT ON (d0.id_dispositivo_iot)
    d0.id_dispositivo_iot,
    d0.serial,
    d0.descripcion,
    d0.es_activo,
    d0.fecha_creacion,
    COALESCE(saa.id_infraestructura, ab.id_infraestructura) AS id_infraestructura
   FROM modulo9.dispositivos_iot d0
     LEFT JOIN modulo9.sensores s ON s.id_dispositivo_iot = d0.id_dispositivo_iot
     LEFT JOIN modulo9.sensores_areas_asociadas saa ON saa.id_sensor = s.id_sensores
        AND saa.tiene_estado IS TRUE
        AND (saa.fecha_finalizacion IS NULL OR saa.fecha_finalizacion > now())
     LEFT JOIN modulo2.activos_biologicos ab ON ab.id_dispositivo_iot = d0.id_dispositivo_iot
  ORDER BY d0.id_dispositivo_iot,
    saa.fecha_asociacion DESC NULLS LAST,
    saa.id_sensores_area_asociada DESC NULLS LAST,
    ab.id_infraestructura DESC NULLS LAST""",
    r"""CREATE OR REPLACE VIEW modulo9.vw_rf19_fincas_nombre_normalizado AS
 SELECT f.id_finca,
    f.nombre,
    lower(f.nombre::text) AS nombre_normalizado,
    (f.ubicacion ->> 'departamento'::text) AS departamento,
    (f.ubicacion ->> 'municipio'::text) AS municipio,
    (f.ubicacion ->> 'vereda'::text) AS vereda
   FROM modulo9.fincas f""",
    r"""CREATE OR REPLACE VIEW modulo9.vw_rf17_umbrales_detalle_niveles AS
 SELECT ua.id_umbral_ambiental,
    ua.id_especie,
    e.nombre AS especie,
    ua.nombre,
    ua.unidad_medida,
    ua.descripcion,
    ua.es_activo,
    va.id_variable_ambiental,
    va.nombre AS variable,
    va.unidad,
    va.valor_fisico_min,
    va.valor_fisico_max,
    COALESCE(json_agg(json_build_object('id', na.id_nivel_alerta_ambiental, 'nivel', na.nivel, 'limite_inferior', na.limite_inferior, 'limite_superior', na.limite_superior) ORDER BY na.limite_inferior) FILTER (WHERE na.id_nivel_alerta_ambiental IS NOT NULL), '[]'::json) AS niveles_alerta,
    count(na.id_nivel_alerta_ambiental) AS total_niveles,
    min(na.limite_inferior) AS rango_min,
    max(na.limite_superior) AS rango_max
   FROM modulo9.umbrales_ambientales ua
     JOIN modulo9.especies e ON e.id_especie = ua.id_especie
     JOIN modulo9.variables_ambientales va ON va.id_variable_ambiental = ua.id_variable_ambiental
     LEFT JOIN modulo9.niveles_alerta_ambientales na ON na.id_umbral_ambiental = ua.id_umbral_ambiental
  GROUP BY ua.id_umbral_ambiental, ua.id_especie, e.nombre, ua.nombre, ua.unidad_medida, ua.descripcion, ua.es_activo, va.id_variable_ambiental, va.nombre, va.unidad, va.valor_fisico_min, va.valor_fisico_max""",
    r"""CREATE OR REPLACE VIEW modulo9.vw_rf17_umbrales_validacion AS
 SELECT v.*,
    ((v.total_niveles > 0) AND NOT v.hay_nivel_invertido AND NOT v.hay_solapamiento AND NOT v.hay_hueco AND v.dentro_limites_fisicos) AS cumple_semaforizacion
   FROM ( WITH niveles AS (
            SELECT na.id_umbral_ambiental,
                na.limite_inferior,
                na.limite_superior,
                lag(na.limite_superior) OVER (PARTITION BY na.id_umbral_ambiental ORDER BY na.limite_inferior, na.limite_superior) AS limite_superior_previo
               FROM modulo9.niveles_alerta_ambientales na
         )
         SELECT ua.id_umbral_ambiental,
            ua.id_especie,
            e.es_activo AS especie_activa,
            ua.id_variable_ambiental,
            ua.es_activo,
            count(n.limite_inferior) AS total_niveles,
            min(n.limite_inferior) AS rango_min,
            max(n.limite_superior) AS rango_max,
            COALESCE(bool_or(n.limite_inferior >= n.limite_superior), false) AS hay_nivel_invertido,
            COALESCE(bool_or(n.limite_superior_previo IS NOT NULL AND n.limite_inferior < n.limite_superior_previo), false) AS hay_solapamiento,
            COALESCE(bool_or(n.limite_superior_previo IS NOT NULL AND n.limite_inferior > n.limite_superior_previo), false) AS hay_hueco,
            COALESCE(bool_and(n.limite_inferior >= va.valor_fisico_min AND n.limite_superior <= va.valor_fisico_max), true) AS dentro_limites_fisicos
           FROM modulo9.umbrales_ambientales ua
             JOIN modulo9.especies e ON e.id_especie = ua.id_especie
             JOIN modulo9.variables_ambientales va ON va.id_variable_ambiental = ua.id_variable_ambiental
             LEFT JOIN niveles n ON n.id_umbral_ambiental = ua.id_umbral_ambiental
          GROUP BY ua.id_umbral_ambiental, ua.id_especie, e.es_activo, ua.id_variable_ambiental, ua.es_activo
        ) v""",
    r"""CREATE OR REPLACE VIEW modulo9.vw_rf20_areas_finca_resumen AS
 SELECT i.id_finca,
    i.id_infraestructura,
    i.nombre,
    i.descripcion,
    i.tipo,
    i.superficie,
    i.es_activo,
    count(d.id_dispositivo_iot) FILTER (WHERE d.es_activo IS TRUE) AS dispositivos_activos,
    count(d.id_dispositivo_iot) AS total_dispositivos,
    i.id_especie,
    e.nombre AS especie
   FROM modulo9.infraestructuras i
     LEFT JOIN modulo9.vw_rf21_dispositivo_area_actual d ON d.id_infraestructura = i.id_infraestructura
     LEFT JOIN modulo9.especies e ON e.id_especie = i.id_especie
  GROUP BY i.id_finca, i.id_infraestructura, i.nombre, i.descripcion, i.tipo, i.superficie, i.es_activo, i.id_especie, e.nombre""",
    r"""CREATE OR REPLACE VIEW modulo9.vw_rf20_areas_productivas_dispositivos AS
 SELECT i.id_infraestructura,
    i.id_finca,
    i.nombre AS area,
    i.tipo,
    i.es_activo,
    f.nombre AS finca,
    (f.ubicacion ->> 'municipio'::text) AS municipio,
    count(d.id_dispositivo_iot) AS total_dispositivos
   FROM modulo9.infraestructuras i
     JOIN modulo9.fincas f ON f.id_finca = i.id_finca
     LEFT JOIN modulo9.vw_rf21_dispositivo_area_actual d ON d.id_infraestructura = i.id_infraestructura
  GROUP BY i.id_infraestructura, i.id_finca, i.nombre, i.tipo, i.es_activo, f.nombre, f.ubicacion""",
    r"""CREATE OR REPLACE VIEW modulo9.vw_rf19_fincas_productor_resumen AS
 SELECT f.id_finca,
    f.nombre,
    f.ubicacion,
    f.tamano_h,
    f.es_activo,
    f.fecha_creacion,
    f.fecha_actualizacion,
    p.productores AS productor,
    p.correos_productores AS correo_electronico,
    COALESCE(a.areas_activas, 0::bigint) AS areas_activas,
    COALESCE(a.total_areas, 0::bigint) AS total_areas
   FROM modulo9.fincas f
     LEFT JOIN ( SELECT uf.id_finca,
            string_agg(concat_ws(' '::text, u.nombre, u.apellidos), ', '::text) AS productores,
            string_agg(u.correo_electronico::text, ', '::text) AS correos_productores
           FROM modulo9.usuarios_fincas uf
             JOIN modulo1.usuarios u ON u.id_usuario = uf.id_usuario
             JOIN modulo1.roles r ON r.id_rol = u.id_rol
          WHERE lower(r.nombre_rol::text) = 'productor'::text AND uf.es_activo IS TRUE
          GROUP BY uf.id_finca) p ON p.id_finca = f.id_finca
     LEFT JOIN ( SELECT i2.id_finca,
            count(*) FILTER (WHERE i2.es_activo IS TRUE) AS areas_activas,
            count(*) AS total_areas
           FROM modulo9.infraestructuras i2
          GROUP BY i2.id_finca) a ON a.id_finca = f.id_finca""",
    r"""CREATE OR REPLACE VIEW modulo9.vw_rf20_fincas_activas_selector AS
 SELECT f.id_finca,
    f.nombre,
    (f.ubicacion ->> 'municipio'::text) AS municipio,
    (f.ubicacion ->> 'departamento'::text) AS departamento,
    f.es_activo,
    p.productores AS productor,
    COALESCE(a.areas_activas, 0::bigint) AS areas_activas,
    COALESCE(a.total_areas, 0::bigint) AS total_areas
   FROM modulo9.fincas f
     LEFT JOIN ( SELECT uf.id_finca,
            string_agg(concat_ws(' '::text, u.nombre, u.apellidos), ', '::text) AS productores
           FROM modulo9.usuarios_fincas uf
             JOIN modulo1.usuarios u ON u.id_usuario = uf.id_usuario
             JOIN modulo1.roles r ON r.id_rol = u.id_rol
          WHERE lower(r.nombre_rol::text) = 'productor'::text AND uf.es_activo IS TRUE
          GROUP BY uf.id_finca) p ON p.id_finca = f.id_finca
     LEFT JOIN ( SELECT i2.id_finca,
            count(*) FILTER (WHERE i2.es_activo IS TRUE) AS areas_activas,
            count(*) AS total_areas
           FROM modulo9.infraestructuras i2
          GROUP BY i2.id_finca) a ON a.id_finca = f.id_finca
  WHERE f.es_activo IS TRUE""",
    r"""CREATE OR REPLACE VIEW modulo9.vw_rf19_productores_selector AS
 SELECT u.id_usuario,
    concat_ws(' '::text, u.nombre, u.apellidos) AS nombre_completo,
    u.correo_electronico
   FROM modulo1.usuarios u
     JOIN modulo1.roles r ON r.id_rol = u.id_rol
     JOIN modulo1.cuentas_usuarios cu ON cu.id_usuario = u.id_usuario
     JOIN modulo1.estados_cuentas ec ON ec.id_estado_cuenta = cu.id_estado_cuenta
  WHERE lower(r.nombre_rol::text) = 'productor'::text
    AND upper(ec.nombre::text) <> 'ELIMINADO'::text""",
    r"""CREATE OR REPLACE VIEW modulo9.vw_rf20_dependencias_infraestructuras AS
 SELECT x.id_infraestructura,
    x.nombre,
    x.dispositivos_activos,
    x.sensores_asociados_activos,
    x.activos_biologicos_alojados,
    ((x.dispositivos_activos = 0) AND (x.sensores_asociados_activos = 0) AND (x.activos_biologicos_alojados = 0)) AS puede_desactivarse
   FROM ( SELECT i.id_infraestructura,
            i.nombre,
            count(d.id_dispositivo_iot) FILTER (WHERE d.es_activo IS TRUE) AS dispositivos_activos,
            ( SELECT count(*)
                   FROM modulo9.sensores_areas_asociadas saa
                  WHERE saa.id_infraestructura = i.id_infraestructura
                    AND saa.tiene_estado IS TRUE
                    AND (saa.fecha_finalizacion IS NULL OR saa.fecha_finalizacion > now())) AS sensores_asociados_activos,
            ( SELECT count(*)
                   FROM modulo2.activos_biologicos a
                     JOIN modulo2.estados_activos_biologicos ea ON ea.id_estado_activo_biologico = a.id_estado
                  WHERE a.id_infraestructura = i.id_infraestructura
                    AND ea.nombre::text <> ALL (ARRAY['INACTIVO'::text, 'CERRADO'::text, 'BAJA'::text])) AS activos_biologicos_alojados
           FROM modulo9.infraestructuras i
             LEFT JOIN modulo9.vw_rf21_dispositivo_area_actual d ON d.id_infraestructura = i.id_infraestructura
          GROUP BY i.id_infraestructura, i.nombre) x""",
    r"""CREATE OR REPLACE VIEW modulo9.vw_rf23_dispositivos_configuracion_area AS
 SELECT d.id_dispositivo_iot,
    d.serial,
    d.descripcion,
    d.es_activo,
    cr.id_configuracion_remota,
    cr.frecuencia_captura,
    cr.intervalo_transmision,
    cr.estado AS estado_configuracion,
    cr.fecha_creacion AS fecha_configuracion,
    cr.fecha_aplicacion,
    i.id_infraestructura,
    i.nombre AS area,
    f.id_finca,
    f.nombre AS finca
   FROM modulo9.vw_rf21_dispositivo_area_actual d
     JOIN modulo9.infraestructuras i ON i.id_infraestructura = d.id_infraestructura
     JOIN modulo9.fincas f ON f.id_finca = i.id_finca
     LEFT JOIN LATERAL ( SELECT cr_actual.id_configuracion_remota,
            cr_actual.frecuencia_captura,
            cr_actual.intervalo_transmision,
            cr_actual.estado,
            cr_actual.fecha_creacion,
            cr_actual.fecha_aplicacion
           FROM modulo9.configuraciones_remotas cr_actual
          WHERE cr_actual.id_dispositivo_iot = d.id_dispositivo_iot
          ORDER BY cr_actual.fecha_creacion DESC NULLS LAST, cr_actual.id_configuracion_remota DESC
         LIMIT 1) cr ON true""",
    r"""CREATE OR REPLACE VIEW modulo9.vw_rf24_dispositivos_activos_calibraciones AS
 SELECT d.id_dispositivo_iot,
    d.serial,
    d.descripcion,
    d.es_activo,
    i.id_infraestructura,
    i.nombre AS area,
    f.id_finca,
    f.nombre AS finca,
    ( SELECT count(*) FROM modulo9.sensores s WHERE s.id_dispositivo_iot = d.id_dispositivo_iot) AS total_sensores,
    cal.total_calibraciones,
    cal.ultima_calibracion
   FROM modulo9.vw_rf21_dispositivo_area_actual d
     JOIN modulo9.infraestructuras i ON i.id_infraestructura = d.id_infraestructura
     JOIN modulo9.fincas f ON f.id_finca = i.id_finca
     LEFT JOIN LATERAL ( SELECT count(*) AS total_calibraciones,
            max(c.fecha_calibracion) AS ultima_calibracion
           FROM modulo9.calibraciones c
          WHERE c.id_dispositivo_iot = d.id_dispositivo_iot) cal ON true
  WHERE d.es_activo IS TRUE""",
    r"""CREATE OR REPLACE VIEW modulo9.vw_rf27_tema_usuario_global AS
 SELECT u.id_usuario,
    tv_user.id_tema_visual AS id_preferencia_usuario,
    tv_user.theme_mode AS tema_usuario,
    tv_user.fecha_actualizacion AS actualizado_en,
    tv_global.theme_mode AS tema_global,
    concat_ws(' '::text, u.nombre, u.apellidos) AS usuario,
    COALESCE(tv_user.theme_mode, tv_global.theme_mode, 1) AS tema_efectivo
   FROM modulo1.usuarios u
     LEFT JOIN LATERAL ( SELECT tv.id_tema_visual,
            tv.theme_mode,
            tv.fecha_actualizacion
           FROM modulo9.temas_visuales tv
          WHERE tv.id_usuario = u.id_usuario AND tv.es_global IS FALSE
          ORDER BY tv.fecha_actualizacion DESC, tv.id_tema_visual DESC
         LIMIT 1) tv_user ON true
     LEFT JOIN LATERAL ( SELECT tv.theme_mode
           FROM modulo9.temas_visuales tv
          WHERE tv.es_global IS TRUE
          ORDER BY tv.fecha_actualizacion DESC, tv.id_tema_visual DESC
         LIMIT 1) tv_global ON true""",
    r"""CREATE OR REPLACE VIEW modulo9.vw_rf28_dashboard_layout_usuario AS
 SELECT t.id_usuario,
    t.id_dashboard_layout,
    t.config,
    t.active_widget,
    t.fecha_actualizacion,
    t.total_widgets_configurados,
    t.total_widgets_activos,
    (t.total_widgets_activos > 12) AS excede_limite_widgets
   FROM ( SELECT DISTINCT ON (dl.id_usuario) dl.id_usuario,
            dl.id_dashboard_layout,
            dl.config,
            dl.active_widget,
            dl.fecha_actualizacion,
            jsonb_array_length(COALESCE(dl.config -> 'grid'::text, '[]'::jsonb)) AS total_widgets_configurados,
            ( SELECT count(*)
                   FROM jsonb_array_elements(COALESCE(dl.config -> 'grid'::text, '[]'::jsonb)) w(x)
                  WHERE (w.x ->> 'visible'::text) IS DISTINCT FROM 'false'::text) AS total_widgets_activos
           FROM modulo9.dashboard_layouts dl
          ORDER BY dl.id_usuario, dl.fecha_actualizacion DESC NULLS LAST, dl.id_dashboard_layout DESC) t""",
    r"""CREATE OR REPLACE VIEW modulo9.vw_rf28_widget_dispositivos_sin_configuracion AS
 SELECT d.id_dispositivo_iot,
    d.serial,
    d.descripcion,
    i.id_infraestructura,
    i.nombre AS area,
    f.id_finca,
    f.nombre AS finca
   FROM modulo9.vw_rf21_dispositivo_area_actual d
     JOIN modulo9.infraestructuras i ON i.id_infraestructura = d.id_infraestructura
     JOIN modulo9.fincas f ON f.id_finca = i.id_finca
  WHERE d.es_activo IS TRUE
    AND NOT EXISTS ( SELECT 1
           FROM modulo9.configuraciones_remotas cr
          WHERE cr.id_dispositivo_iot = d.id_dispositivo_iot)""",
    r"""CREATE OR REPLACE VIEW modulo9.vw_rf28_widget_estado_dispositivos AS
 SELECT d.id_dispositivo_iot,
    d.serial,
    d.es_activo,
    i.id_infraestructura,
    i.nombre AS area,
    f.id_finca,
    f.nombre AS finca,
    ultima_cal.ultima_calibracion,
    cr.frecuencia_captura,
    cr.intervalo_transmision,
    cr.estado AS estado_configuracion
   FROM modulo9.vw_rf21_dispositivo_area_actual d
     JOIN modulo9.infraestructuras i ON i.id_infraestructura = d.id_infraestructura
     JOIN modulo9.fincas f ON f.id_finca = i.id_finca
     LEFT JOIN LATERAL ( SELECT max(c.fecha_calibracion) AS ultima_calibracion
           FROM modulo9.calibraciones c
          WHERE c.id_dispositivo_iot = d.id_dispositivo_iot) ultima_cal ON true
     LEFT JOIN LATERAL ( SELECT cr_actual.frecuencia_captura,
            cr_actual.intervalo_transmision,
            cr_actual.estado
           FROM modulo9.configuraciones_remotas cr_actual
          WHERE cr_actual.id_dispositivo_iot = d.id_dispositivo_iot
          ORDER BY cr_actual.fecha_creacion DESC NULLS LAST, cr_actual.id_configuracion_remota DESC
         LIMIT 1) cr ON true""",
    r"""CREATE OR REPLACE VIEW modulo9.vw_rf28_widget_estado_fincas AS
 SELECT f.id_finca,
    f.nombre,
    f.es_activo,
    (f.ubicacion ->> 'departamento'::text) AS departamento,
    count(DISTINCT i.id_infraestructura) FILTER (WHERE i.es_activo IS TRUE) AS areas_activas,
    count(DISTINCT d.id_dispositivo_iot) FILTER (WHERE d.es_activo IS TRUE) AS dispositivos_activos
   FROM modulo9.fincas f
     LEFT JOIN modulo9.infraestructuras i ON i.id_finca = f.id_finca
     LEFT JOIN modulo9.vw_rf21_dispositivo_area_actual d ON d.id_infraestructura = i.id_infraestructura
  GROUP BY f.id_finca, f.nombre, f.es_activo, f.ubicacion""",
    r"""CREATE OR REPLACE VIEW modulo9.vw_rf29_idioma_usuario_global AS
 SELECT u.id_usuario,
    pi_user.id_preferencia_idioma,
    pi_user.locale_code AS idioma_usuario,
    pi_user.es_por_defecto,
    pi_user.fecha_actualizacion,
    pi_global.locale_code AS idioma_global,
    concat_ws(' '::text, u.nombre, u.apellidos) AS usuario,
    COALESCE(pi_user.locale_code, pi_global.locale_code, 'es-CO') AS idioma_efectivo
   FROM modulo1.usuarios u
     LEFT JOIN LATERAL ( SELECT pi.id_preferencia_idioma,
            pi.locale_code,
            pi.es_por_defecto,
            pi.fecha_actualizacion
           FROM modulo9.preferencias_idiomas pi
          WHERE pi.id_usuario = u.id_usuario AND pi.es_por_defecto IS FALSE
          ORDER BY pi.fecha_actualizacion DESC NULLS LAST, pi.id_preferencia_idioma DESC
         LIMIT 1) pi_user ON true
     LEFT JOIN LATERAL ( SELECT pi.locale_code
           FROM modulo9.preferencias_idiomas pi
          WHERE pi.es_por_defecto IS TRUE
          ORDER BY pi.fecha_actualizacion DESC NULLS LAST, pi.id_preferencia_idioma DESC
         LIMIT 1) pi_global ON true""",
    r"""CREATE OR REPLACE VIEW modulo9.vw_rf32_plantillas_detalle AS
 SELECT p.id_plantilla,
    p.template_name,
    p.version,
    p.fecha_creacion,
    p.params_snapshot,
    e.id_especie,
    e.nombre AS especie,
    e.es_activo AS especie_activa,
    p.id_usuario,
    concat_ws(' '::text, u.nombre, u.apellidos) AS creado_por,
    (p.version = max(p.version) OVER (PARTITION BY p.template_name)) AS es_ultima_version
   FROM modulo9.plantillas p
     JOIN modulo9.especies e ON e.id_especie = p.id_especie
     JOIN modulo1.usuarios u ON u.id_usuario = p.id_usuario""",
    r"""CREATE OR REPLACE VIEW modulo9.vw_rf15_dependencias_especie AS
 SELECT e.id_especie,
    e.nombre,
    count(DISTINCT ua.id_umbral_ambiental) FILTER (WHERE ua.es_activo IS TRUE) AS umbrales_activos,
    count(DISTINCT cb.id_ciclo_biologico) FILTER (WHERE cb.es_activo IS TRUE) AS ciclos_activos,
    count(DISTINCT ep.id_especies_patologias) AS patologias_asociadas,
    ( SELECT count(*)
           FROM modulo9.infraestructuras i
          WHERE i.id_especie = e.id_especie AND i.es_activo IS TRUE) AS areas_activas_asignadas,
    ( SELECT count(*)
           FROM modulo2.activos_biologicos a
             JOIN modulo2.estados_activos_biologicos ea ON ea.id_estado_activo_biologico = a.id_estado
          WHERE a.id_especie = e.id_especie
            AND a.id_infraestructura IS NOT NULL
            AND ea.nombre::text <> ALL (ARRAY['INACTIVO'::text, 'CERRADO'::text, 'BAJA'::text])) AS activos_biologicos_alojados
   FROM modulo9.especies e
     LEFT JOIN modulo9.umbrales_ambientales ua ON ua.id_especie = e.id_especie
     LEFT JOIN modulo9.ciclos_biologicos cb ON cb.id_especie = e.id_especie
     LEFT JOIN modulo9.especies_patologias ep ON ep.id_especie = e.id_especie
  GROUP BY e.id_especie, e.nombre""",
    r"""CREATE OR REPLACE VIEW modulo9.vw_rf17_umbral_activo_por_especie_variable AS
 SELECT id_especie,
    id_variable_ambiental,
    count(*) AS total_configuraciones_activas,
    array_agg(id_umbral_ambiental ORDER BY id_umbral_ambiental) AS umbrales_activos,
    (count(*) = 1) AS cumple_unicidad
   FROM modulo9.umbrales_ambientales ua
  WHERE es_activo IS TRUE
  GROUP BY id_especie, id_variable_ambiental""",
    r"""CREATE OR REPLACE VIEW modulo9.vw_rf17_variables_configuracion_especie AS
 SELECT e.id_especie,
    e.nombre AS especie,
    va.id_variable_ambiental,
    va.nombre,
    va.unidad,
    va.valor_fisico_min,
    va.valor_fisico_max,
    va.es_activo,
    (count(ua.id_umbral_ambiental) > 0) AS ya_configurada,
    min(ua.id_umbral_ambiental) AS id_umbral_ambiental,
    min(ua.nombre::text) AS nombre_umbral,
    count(ua.id_umbral_ambiental) AS total_umbrales_activos,
    e.es_activo AS especie_activa
   FROM modulo9.especies e
     CROSS JOIN modulo9.variables_ambientales va
     LEFT JOIN modulo9.umbrales_ambientales ua ON ua.id_variable_ambiental = va.id_variable_ambiental AND ua.id_especie = e.id_especie AND ua.es_activo IS TRUE
  WHERE va.es_activo IS TRUE
  GROUP BY e.id_especie, e.nombre, va.id_variable_ambiental, va.nombre, va.unidad, va.valor_fisico_min, va.valor_fisico_max, va.es_activo, e.es_activo""",
    r"""CREATE OR REPLACE VIEW modulo9.vw_rf18_configuracion_global_activa AS
 SELECT cg.id_configuracion_global,
    cg.frecuencia_muestreo,
    cg.heartbeat,
    cg.fecha_actualizacion,
    cg.es_activo,
    cg.id_usuario,
    concat_ws(' '::text, u.nombre, u.apellidos) AS modificado_por,
    u.correo_electronico,
    (cg.heartbeat >= cg.frecuencia_muestreo) AS heartbeat_coherente,
    count(*) OVER () AS total_activas
   FROM modulo9.configuraciones_globales cg
     JOIN modulo1.usuarios u ON u.id_usuario = cg.id_usuario
  WHERE cg.es_activo IS TRUE""",
    r"""CREATE OR REPLACE VIEW modulo9.vw_rf19_dependencias_fincas AS
 SELECT f.id_finca,
    f.nombre,
    count(DISTINCT i.id_infraestructura) FILTER (WHERE i.es_activo IS TRUE) AS infra_activas,
    count(DISTINCT d.id_dispositivo_iot) FILTER (WHERE d.es_activo IS TRUE) AS dispositivos_activos,
    ( SELECT count(*)
           FROM modulo2.activos_biologicos a
             JOIN modulo2.estados_activos_biologicos ea ON ea.id_estado_activo_biologico = a.id_estado
             JOIN modulo9.infraestructuras ii ON ii.id_infraestructura = a.id_infraestructura
          WHERE ii.id_finca = f.id_finca
            AND ea.nombre::text <> ALL (ARRAY['INACTIVO'::text, 'CERRADO'::text, 'BAJA'::text])) AS activos_biologicos_activos
   FROM modulo9.fincas f
     LEFT JOIN modulo9.infraestructuras i ON i.id_finca = f.id_finca
     LEFT JOIN modulo9.vw_rf21_dispositivo_area_actual d ON d.id_infraestructura = i.id_infraestructura
  GROUP BY f.id_finca, f.nombre""",
    r"""CREATE OR REPLACE VIEW modulo9.vw_rf21_dispositivos_area_sensores AS
 SELECT d.id_infraestructura,
    d.id_dispositivo_iot,
    d.serial,
    d.descripcion,
    d.es_activo,
    d.fecha_creacion,
    count(s.id_sensores) AS total_sensores,
    count(s.id_sensores) FILTER (WHERE s.es_activo IS TRUE) AS sensores_activos
   FROM modulo9.vw_rf21_dispositivo_area_actual d
     LEFT JOIN modulo9.sensores s ON s.id_dispositivo_iot = d.id_dispositivo_iot
  GROUP BY d.id_infraestructura, d.id_dispositivo_iot, d.serial, d.descripcion, d.es_activo, d.fecha_creacion""",
    r"""CREATE OR REPLACE VIEW modulo9.vw_rf21_dispositivos_sensores_asociacion AS
 SELECT d.id_dispositivo_iot,
    d.serial,
    d.descripcion,
    d.es_activo,
    i.id_infraestructura,
    i.nombre AS area,
    f.id_finca,
    f.nombre AS finca,
    count(s.id_sensores) AS total_sensores,
    count(s.id_sensores) FILTER (WHERE NOT EXISTS ( SELECT 1
           FROM modulo9.sensores_areas_asociadas saa
          WHERE saa.id_sensor = s.id_sensores AND saa.tiene_estado IS TRUE AND (saa.fecha_finalizacion IS NULL OR saa.fecha_finalizacion > now()))) AS sensores_libres,
    count(s.id_sensores) FILTER (WHERE EXISTS ( SELECT 1
           FROM modulo9.sensores_areas_asociadas saa
          WHERE saa.id_sensor = s.id_sensores AND saa.tiene_estado IS TRUE AND (saa.fecha_finalizacion IS NULL OR saa.fecha_finalizacion > now()))) AS sensores_asociados
   FROM modulo9.vw_rf21_dispositivo_area_actual d
     JOIN modulo9.infraestructuras i ON i.id_infraestructura = d.id_infraestructura
     JOIN modulo9.fincas f ON f.id_finca = i.id_finca
     LEFT JOIN modulo9.sensores s ON s.id_dispositivo_iot = d.id_dispositivo_iot
  WHERE d.es_activo IS TRUE
  GROUP BY d.id_dispositivo_iot, d.serial, d.descripcion, d.es_activo, i.id_infraestructura, i.nombre, f.id_finca, f.nombre""",
    r"""CREATE OR REPLACE VIEW modulo9.vw_rf21_dispositivos_seriales AS
 SELECT d.id_dispositivo_iot,
    d.serial,
    lower(d.serial::text) AS serial_normalizado
   FROM modulo9.dispositivos_iot d""",
    r"""CREATE OR REPLACE VIEW modulo9.vw_rf22_sensores_dispositivo_asociacion AS
 SELECT s.id_dispositivo_iot,
    s.id_sensores,
    s.nombre,
    s.es_activo,
    saa.id_sensores_area_asociada,
    saa.tiene_estado AS asociado_activo,
    saa.punto_instalacion,
    i.id_infraestructura,
    i.nombre AS area_asociada,
    f.id_finca,
    f.nombre AS finca_asociada,
    saa.fecha_asociacion
   FROM modulo9.sensores s
     LEFT JOIN LATERAL ( SELECT saa_actual.id_sensores_area_asociada,
            saa_actual.tiene_estado,
            saa_actual.punto_instalacion,
            saa_actual.id_infraestructura,
            saa_actual.fecha_asociacion
           FROM modulo9.sensores_areas_asociadas saa_actual
          WHERE saa_actual.id_sensor = s.id_sensores
            AND saa_actual.tiene_estado IS TRUE
            AND (saa_actual.fecha_finalizacion IS NULL OR saa_actual.fecha_finalizacion > now())
          ORDER BY saa_actual.fecha_asociacion DESC, saa_actual.id_sensores_area_asociada DESC
         LIMIT 1) saa ON true
     LEFT JOIN modulo9.infraestructuras i ON i.id_infraestructura = saa.id_infraestructura
     LEFT JOIN modulo9.fincas f ON f.id_finca = i.id_finca""",
    r"""CREATE OR REPLACE VIEW modulo9.vw_rf31_params_disponibles_especie AS
 SELECT e.id_especie,
    e.nombre AS especie,
    json_build_object('umbrales', ( SELECT COALESCE(json_agg(json_build_object('id', ua.id_umbral_ambiental, 'nombre', ua.nombre) ORDER BY ua.nombre), '[]'::json)
           FROM modulo9.umbrales_ambientales ua
          WHERE ua.id_especie = e.id_especie AND ua.es_activo IS TRUE), 'ciclos', ( SELECT COALESCE(json_agg(json_build_object('id', cb.id_ciclo_biologico, 'nombre', cb.nombre) ORDER BY cb.nombre), '[]'::json)
           FROM modulo9.ciclos_biologicos cb
          WHERE cb.id_especie = e.id_especie AND cb.es_activo IS TRUE), 'patologias', ( SELECT COALESCE(json_agg(json_build_object('id', p.id_patologia, 'nombre', p.nombre) ORDER BY p.nombre), '[]'::json)
           FROM modulo9.especies_patologias ep
             JOIN modulo9.patologias p ON p.id_patologia = ep.id_patologia
          WHERE ep.id_especie = e.id_especie AND p.es_activo IS TRUE)) AS params_disponibles,
    e.es_activo AS especie_activa
   FROM modulo9.especies e""",
    r"""CREATE OR REPLACE VIEW modulo9.vw_rf31_plantillas_listado AS
 SELECT p.id_plantilla,
    p.template_name,
    p.version,
    p.fecha_creacion,
    p.id_especie,
    e.nombre AS especie,
    p.id_usuario,
    concat_ws(' '::text, u.nombre, u.apellidos) AS creado_por,
    jsonb_array_length(COALESCE(p.params_snapshot -> 'umbrales'::text, '[]'::jsonb)) AS total_umbrales,
    jsonb_array_length(COALESCE(p.params_snapshot -> 'ciclos_biologicos'::text, '[]'::jsonb)) AS total_ciclos,
    jsonb_array_length(COALESCE(p.params_snapshot -> 'metricas'::text, '[]'::jsonb)) AS total_metricas,
        CASE
            WHEN jsonb_typeof(p.params_snapshot -> 'patologias'::text) = 'array'::text THEN jsonb_array_length(p.params_snapshot -> 'patologias'::text)
            ELSE 0
        END AS total_patologias,
    (p.version = max(p.version) OVER (PARTITION BY p.template_name)) AS es_ultima_version
   FROM modulo9.plantillas p
     JOIN modulo9.especies e ON e.id_especie = p.id_especie
     JOIN modulo1.usuarios u ON u.id_usuario = p.id_usuario""",
    r"""CREATE OR REPLACE VIEW modulo9.vw_rf16_patologias_especie_nombre_normalizado AS
 SELECT ep.id_especie,
    p.id_patologia AS id_patologias,
    p.nombre,
    lower(p.nombre::text) AS nombre_normalizado
   FROM modulo9.especies_patologias ep
     JOIN modulo9.patologias p ON p.id_patologia = ep.id_patologia""",
]
 
COMMENTS = {
    "vw_rf21_dispositivo_area_actual": "RF-21 (area actual de cada dispositivo), RF-22 (via sensor con asociacion vigente), RF-20. Base de las vistas de dispositivos. Deriva el area por sensor o por activo biologico hasta que dispositivos_iot guarde el area (RF-21 v2.0).",
    "vw_rf19_fincas_nombre_normalizado": "RF-19 (unicidad de nombre de finca, global y por productor/ubicacion, sin distinguir mayusculas). Incluye departamento, municipio y vereda para validar duplicidad por ubicacion.",
    "vw_rf17_umbrales_detalle_niveles": "RF-17 (umbrales por especie y variable ambiental con niveles de alerta semaforizados), RF-30 y RF-31 (fuente de umbrales para plantillas). Incluye total_niveles y rango_min/rango_max.",
    "vw_rf20_areas_finca_resumen": "RF-20 (areas productivas por finca y dispositivos asociados), RF-15 (especie del area), RF-21 (dispositivos por area).",
    "vw_rf20_areas_productivas_dispositivos": "RF-20 (areas productivas con finca y municipio), RF-19 (finca), RF-21 (conteo de dispositivos por area).",
    "vw_rf19_fincas_productor_resumen": "RF-19 (listado de fincas con productor asignado y estado), RF-20 (areas activas y totales), RF-01 (usuarios con rol Productor). Solo asignaciones activas en usuarios_fincas.",
    "vw_rf20_fincas_activas_selector": "RF-20 (finca activa como destino de areas), RF-19 (fincas activas con productor), RF-21 y RF-25 (selector de finca). Solo asignaciones activas en usuarios_fincas.",
    "vw_rf19_productores_selector": "RF-19 (seleccion del productor responsable), RF-01 (usuarios con rol Productor), RF-06 (excluye cuentas ELIMINADO).",
    "vw_rf20_dependencias_infraestructuras": "RF-20 (bloqueo de desactivacion por dispositivos, sensores o activos biologicos alojados), RF-21 (dispositivos), RF-22 (sensores asociados). puede_desactivarse resume la regla.",
    "vw_rf23_dispositivos_configuracion_area": "RF-23 (ultima configuracion remota por dispositivo), RF-21 (dispositivo), RF-20 (area), RF-19 (finca).",
    "vw_rf24_dispositivos_activos_calibraciones": "RF-24 (dispositivos activos con sensores y calibraciones), RF-21 (dispositivo), RF-22 (sensores del dispositivo). Modalidad VISION pendiente de modelado.",
    "vw_rf27_tema_usuario_global": "RF-27 (prioridad: preferencia de usuario, luego tema global, luego claro=1). tema_efectivo resuelve la regla.",
    "vw_rf28_dashboard_layout_usuario": "RF-28 (ultimo layout del dashboard por usuario; limite de 12 widgets activos), RF-02, RF-03.",
    "vw_rf28_widget_dispositivos_sin_configuracion": "RF-28 (widget de dispositivos), RF-23 (dispositivos sin configuracion remota), RF-21.",
    "vw_rf28_widget_estado_dispositivos": "RF-28 (widget estado de dispositivos), RF-21, RF-23 (configuracion vigente), RF-24 (ultima calibracion).",
    "vw_rf28_widget_estado_fincas": "RF-28 (widget estado de fincas), RF-19, RF-20 (areas activas), RF-21 (dispositivos activos), RF-25.",
    "vw_rf29_idioma_usuario_global": "RF-29 (idioma por usuario o global; fallback es-CO). idioma_efectivo resuelve la regla.",
    "vw_rf32_plantillas_detalle": "RF-30, RF-31, RF-32 (detalle de plantilla con params_snapshot; nombre historico rf32). es_ultima_version marca la version vigente.",
    "vw_rf15_dependencias_especie": "RF-15 (desactivacion y cambio de grupo_manejo; areas y activos alojados), RF-16 (ciclos y patologias), RF-17 (umbrales), RF-20 (areas por especie).",
    "vw_rf17_umbral_activo_por_especie_variable": "RF-17 (un solo umbral activo por especie y variable). cumple_unicidad indica la regla.",
    "vw_rf17_variables_configuracion_especie": "RF-17 (variables ambientales por especie y si ya estan configuradas), RF-15 (solo especies activas). especie_activa permite filtrar.",
    "vw_rf18_configuracion_global_activa": "RF-18 (configuracion operativa global unica y activa; heartbeat >= frecuencia), RF-10. total_activas debe ser 1.",
    "vw_rf19_dependencias_fincas": "RF-19 (bloqueo de desactivacion por areas, dispositivos o activos biologicos), RF-20, RF-21.",
    "vw_rf21_dispositivos_area_sensores": "RF-21 (dispositivos por area con sensores), RF-22 (sensores), RF-20 (area).",
    "vw_rf21_dispositivos_sensores_asociacion": "RF-21 (dispositivos activos), RF-22 (sensores libres y asociados), RF-20, RF-19.",
    "vw_rf21_dispositivos_seriales": "RF-21 (unicidad del serial fisico, normalizado a minusculas).",
    "vw_rf22_sensores_dispositivo_asociacion": "RF-22 (asociacion vigente sensor-area y reasignacion), RF-21 (sensores del dispositivo), RF-20.",
    "vw_rf31_params_disponibles_especie": "RF-31 (parametros seleccionables por especie), RF-30 (alcance de plantilla), RF-16, RF-17. especie_activa para exigir especie activa.",
    "vw_rf31_plantillas_listado": "RF-30 (listado con nombre, especie y version), RF-31 (creacion). es_ultima_version marca la version vigente.",
    "vw_rf17_umbrales_validacion": "RF-17 (validacion de semaforizacion: niveles invertidos, solapados, con huecos y dentro de limites fisicos; especie activa).",
    "vw_rf16_patologias_especie_nombre_normalizado": "RF-16 (unicidad case-insensitive de patologia por especie).",
    "vw_rf22_areas_destino_disponibles": "RF-22 (areas activas destino para asociar sensores), RF-20 (area activa), RF-19 (finca activa), RF-21 (area activa para registrar dispositivo).",
    "vw_rf26_identidad_visual_activa": "RF-26 (identidad visual vigente: logo, colores y nombre visible; ultima version por finca), RF-19 (finca u organizacion), RF-25 (adaptacion de interfaz), RF-27 (independiente del tema).",
    "vw_rf19_fincas_resumen_global": "RF-19 (totales de fincas activas e inactivas).",
    "vw_rf23_configuraciones_pendientes": "RF-23 (configuracion remota PENDIENTE; una sola por dispositivo), RF-21 (dispositivo IoT).",
    "vw_rf24_historial_calibraciones_sensor": "RF-24 (historial de calibraciones por sensor con tecnico), RF-10 (trazabilidad).",
    "vw_rf25_permisos_roles": "RF-25 (modulos y acciones habilitados por rol para adaptar la interfaz), RF-03, RF-04. Equivalente a modulo1.vw_permisos_roles; filtrar es_activo.",
    "vw_rf26_auditorias_visuales_historial": "RF-26 (auditoria de cambios de identidad visual: valor anterior y nuevo), RF-10 (historial de auditoria).",
    "vw_rf27_preferencias_tema_usuarios": "RF-27 (preferencias de tema individual y global), RF-02, RF-03 (rol del usuario).",
    "vw_rf29_preferencias_idioma_usuarios": "RF-29 (preferencias de idioma por usuario y por defecto), RF-03 (rol).",
    "vw_rf24_sensores_dispositivo_calibracion": "RF-24 (sensores activos con ultima calibracion), RF-22 (sensores del dispositivo), RF-21.",
    "vw_rf25_contexto_usuario": "RF-25 (rol, finca activa y especies configuradas para adaptar la interfaz), RF-19, RF-15, RF-20, RF-03.",
    "vw_rf33_aplicaciones_plantillas_historial": "RF-32 (aplicacion de plantilla con before/after; nombre historico rf33), RF-30, RF-10 (auditoria), RF-108 (aplicaciones recientes). Resultado SUCCESS/REJECTED/ROLLED_BACK pendiente de modelado.",
    "vw_rf17_gestion_especies_historial": "RF-15 (historial de gestion de especies), RF-17 (umbral relacionado), RF-10 (auditoria).",
    "vw_rf15_especies_activas_selector": "RF-15 (especies activas para formularios), RF-16, RF-17, RF-20 (especie del area), RF-31.",
    "vw_rf15_especies_nombre_normalizado": "RF-15 (unicidad case-insensitive del nombre de especie).",
    "vw_rf15_especies_resumen": "RF-15 (catalogo de especies con estado), RF-16 (totales de etapas y patologias).",
    "vw_rf16_cabecera_especie": "RF-16 (cabecera por especie: total de etapas y patologias), RF-15.",
    "vw_rf16_ciclos_biologicos_especie": "RF-16 (etapas del ciclo productivo por especie), RF-15 (especie), RF-31 (parametros de plantilla).",
    "vw_rf16_ciclos_nombre_normalizado": "RF-16 (unicidad case-insensitive de etapa por especie).",
    "vw_rf18_configuraciones_globales_historial": "RF-18 (historial de cambios de la configuracion global), RF-10 (auditoria).",
    "vw_rf20_infraestructuras_nombre_normalizado": "RF-20 (unicidad case-insensitive del nombre de area por finca).",
    "vw_rf31_plantillas_nombre_normalizado": "RF-31 (unicidad de nombre de plantilla), RF-30.",
    "vw_rf31_plantillas_resumen": "RF-30 y RF-31 (totales de plantillas, especies cubiertas y nombres unicos).",
    "vw_rf16_dependencias_ciclos": "RF-16 (bloqueo de desactivacion de etapa por referencias productivas).",
    "vw_rf16_dependencias_patologias": "RF-16 (bloqueo de desactivacion de patologia por especies, signos, predicciones y alertas).",
    "vw_rf16_patologias_especie": "RF-16 (patologias por especie), RF-15, RF-31 (parametros de plantilla).",
    "vw_rf16_patologias_nombre_normalizado": "RF-16 (unicidad case-insensitive de patologia; global, ver vw_rf16_patologias_especie_nombre_normalizado para unicidad por especie).",
}
 
# --- downgrade -----------------------------------------------------------
# Orden: primero todo lo que depende de la vista base, la base al final.
DROP_ORDER = [
    "vw_rf19_fincas_nombre_normalizado",
    "vw_rf17_umbrales_detalle_niveles",
    "vw_rf20_areas_finca_resumen",
    "vw_rf20_areas_productivas_dispositivos",
    "vw_rf19_fincas_productor_resumen",
    "vw_rf20_fincas_activas_selector",
    "vw_rf19_productores_selector",
    "vw_rf20_dependencias_infraestructuras",
    "vw_rf23_dispositivos_configuracion_area",
    "vw_rf24_dispositivos_activos_calibraciones",
    "vw_rf27_tema_usuario_global",
    "vw_rf28_dashboard_layout_usuario",
    "vw_rf28_widget_dispositivos_sin_configuracion",
    "vw_rf28_widget_estado_dispositivos",
    "vw_rf28_widget_estado_fincas",
    "vw_rf29_idioma_usuario_global",
    "vw_rf32_plantillas_detalle",
    "vw_rf15_dependencias_especie",
    "vw_rf17_umbral_activo_por_especie_variable",
    "vw_rf17_variables_configuracion_especie",
    "vw_rf18_configuracion_global_activa",
    "vw_rf19_dependencias_fincas",
    "vw_rf21_dispositivos_area_sensores",
    "vw_rf21_dispositivos_sensores_asociacion",
    "vw_rf21_dispositivos_seriales",
    "vw_rf22_sensores_dispositivo_asociacion",
    "vw_rf31_params_disponibles_especie",
    "vw_rf31_plantillas_listado",
    "vw_rf17_umbrales_validacion",
    "vw_rf16_patologias_especie_nombre_normalizado",
    "vw_rf21_dispositivo_area_actual",
]
 
VIEWS_ORIGINALES = [
    r"""CREATE VIEW modulo9.vw_rf19_fincas_nombre_normalizado AS
SELECT id_finca,
    nombre,
    lower((nombre)::text) AS nombre_normalizado
   FROM modulo9.fincas f""",
    r"""CREATE VIEW modulo9.vw_rf17_umbrales_detalle_niveles AS
SELECT ua.id_umbral_ambiental,
    ua.id_especie,
    e.nombre AS especie,
    ua.nombre,
    ua.unidad_medida,
    ua.descripcion,
    ua.es_activo,
    va.id_variable_ambiental,
    va.nombre AS variable,
    va.unidad,
    va.valor_fisico_min,
    va.valor_fisico_max,
    COALESCE(json_agg(json_build_object('id', na.id_nivel_alerta_ambiental, 'nivel', na.nivel, 'limite_inferior', na.limite_inferior, 'limite_superior', na.limite_superior) ORDER BY na.limite_inferior) FILTER (WHERE (na.id_nivel_alerta_ambiental IS NOT NULL)), '[]'::json) AS niveles_alerta
   FROM (((modulo9.umbrales_ambientales ua
     JOIN modulo9.especies e ON ((e.id_especie = ua.id_especie)))
     JOIN modulo9.variables_ambientales va ON ((va.id_variable_ambiental = ua.id_variable_ambiental)))
     LEFT JOIN modulo9.niveles_alerta_ambientales na ON ((na.id_umbral_ambiental = ua.id_umbral_ambiental)))
  GROUP BY ua.id_umbral_ambiental, ua.id_especie, e.nombre, ua.nombre, ua.unidad_medida, ua.descripcion, ua.es_activo, va.id_variable_ambiental, va.nombre, va.unidad, va.valor_fisico_min, va.valor_fisico_max""",
    r"""CREATE VIEW modulo9.vw_rf20_areas_finca_resumen AS
SELECT i.id_finca,
    i.id_infraestructura,
    i.nombre,
    i.descripcion,
    i.tipo,
    i.superficie,
    i.es_activo,
    count(d.id_dispositivo_iot) FILTER (WHERE (d.es_activo IS TRUE)) AS dispositivos_activos,
    count(d.id_dispositivo_iot) AS total_dispositivos
   FROM (modulo9.infraestructuras i
     LEFT JOIN ( SELECT DISTINCT ON (d0.id_dispositivo_iot) d0.id_dispositivo_iot,
            d0.serial,
            d0.descripcion,
            d0.es_activo,
            d0.fecha_creacion,
            COALESCE(saa.id_infraestructura, ab.id_infraestructura) AS id_infraestructura
           FROM (((modulo9.dispositivos_iot d0
             LEFT JOIN modulo9.sensores s ON ((s.id_dispositivo_iot = d0.id_dispositivo_iot)))
             LEFT JOIN modulo9.sensores_areas_asociadas saa ON (((saa.id_sensor = s.id_sensores) AND ((saa.fecha_finalizacion IS NULL) OR (saa.fecha_finalizacion > now())))))
             LEFT JOIN modulo2.activos_biologicos ab ON ((ab.id_dispositivo_iot = d0.id_dispositivo_iot)))
          ORDER BY d0.id_dispositivo_iot, saa.fecha_asociacion DESC NULLS LAST, saa.id_sensores_area_asociada DESC NULLS LAST) d ON ((d.id_infraestructura = i.id_infraestructura)))
  GROUP BY i.id_finca, i.id_infraestructura, i.nombre, i.descripcion, i.tipo, i.superficie, i.es_activo""",
    r"""CREATE VIEW modulo9.vw_rf20_areas_productivas_dispositivos AS
SELECT i.id_infraestructura,
    i.id_finca,
    i.nombre AS area,
    i.tipo,
    i.es_activo,
    f.nombre AS finca,
    (f.ubicacion ->> 'municipio'::text) AS municipio,
    count(d.id_dispositivo_iot) AS total_dispositivos
   FROM ((modulo9.infraestructuras i
     JOIN modulo9.fincas f ON ((f.id_finca = i.id_finca)))
     LEFT JOIN ( SELECT DISTINCT ON (d0.id_dispositivo_iot) d0.id_dispositivo_iot,
            d0.serial,
            d0.descripcion,
            d0.es_activo,
            d0.fecha_creacion,
            COALESCE(saa.id_infraestructura, ab.id_infraestructura) AS id_infraestructura
           FROM (((modulo9.dispositivos_iot d0
             LEFT JOIN modulo9.sensores s ON ((s.id_dispositivo_iot = d0.id_dispositivo_iot)))
             LEFT JOIN modulo9.sensores_areas_asociadas saa ON (((saa.id_sensor = s.id_sensores) AND ((saa.fecha_finalizacion IS NULL) OR (saa.fecha_finalizacion > now())))))
             LEFT JOIN modulo2.activos_biologicos ab ON ((ab.id_dispositivo_iot = d0.id_dispositivo_iot)))
          ORDER BY d0.id_dispositivo_iot, saa.fecha_asociacion DESC NULLS LAST, saa.id_sensores_area_asociada DESC NULLS LAST) d ON ((d.id_infraestructura = i.id_infraestructura)))
  GROUP BY i.id_infraestructura, i.id_finca, i.nombre, i.tipo, i.es_activo, f.nombre, f.ubicacion""",
    r"""CREATE VIEW modulo9.vw_rf19_fincas_productor_resumen AS
SELECT f.id_finca,
    f.nombre,
    f.ubicacion,
    f.tamano_h,
    f.es_activo,
    f.fecha_creacion,
    f.fecha_actualizacion,
    p.productores AS productor,
    p.correos_productores AS correo_electronico,
    COALESCE(a.areas_activas, (0)::bigint) AS areas_activas,
    COALESCE(a.total_areas, (0)::bigint) AS total_areas
   FROM ((modulo9.fincas f
     LEFT JOIN ( SELECT uf.id_finca,
            string_agg(concat_ws(' '::text, u.nombre, u.apellidos), ', '::text) AS productores,
            string_agg((u.correo_electronico)::text, ', '::text) AS correos_productores
           FROM ((modulo9.usuarios_fincas uf
             JOIN modulo1.usuarios u ON ((u.id_usuario = uf.id_usuario)))
             JOIN modulo1.roles r ON ((r.id_rol = u.id_rol)))
          WHERE ((r.nombre_rol)::text = 'Productor'::text)
          GROUP BY uf.id_finca) p ON ((p.id_finca = f.id_finca)))
     LEFT JOIN ( SELECT infraestructuras.id_finca,
            count(*) FILTER (WHERE (infraestructuras.es_activo IS TRUE)) AS areas_activas,
            count(*) AS total_areas
           FROM modulo9.infraestructuras
          GROUP BY infraestructuras.id_finca) a ON ((a.id_finca = f.id_finca)))""",
    r"""CREATE VIEW modulo9.vw_rf20_fincas_activas_selector AS
SELECT f.id_finca,
    f.nombre,
    (f.ubicacion ->> 'municipio'::text) AS municipio,
    (f.ubicacion ->> 'departamento'::text) AS departamento,
    f.es_activo,
    p.productores AS productor,
    COALESCE(a.areas_activas, (0)::bigint) AS areas_activas,
    COALESCE(a.total_areas, (0)::bigint) AS total_areas
   FROM ((modulo9.fincas f
     LEFT JOIN ( SELECT uf.id_finca,
            string_agg(concat_ws(' '::text, u.nombre, u.apellidos), ', '::text) AS productores
           FROM ((modulo9.usuarios_fincas uf
             JOIN modulo1.usuarios u ON ((u.id_usuario = uf.id_usuario)))
             JOIN modulo1.roles r ON ((r.id_rol = u.id_rol)))
          WHERE ((r.nombre_rol)::text = 'Productor'::text)
          GROUP BY uf.id_finca) p ON ((p.id_finca = f.id_finca)))
     LEFT JOIN ( SELECT infraestructuras.id_finca,
            count(*) FILTER (WHERE (infraestructuras.es_activo IS TRUE)) AS areas_activas,
            count(*) AS total_areas
           FROM modulo9.infraestructuras
          GROUP BY infraestructuras.id_finca) a ON ((a.id_finca = f.id_finca)))
  WHERE (f.es_activo IS TRUE)""",
    r"""CREATE VIEW modulo9.vw_rf19_productores_selector AS
SELECT u.id_usuario,
    concat_ws(' '::text, u.nombre, u.apellidos) AS nombre_completo,
    u.correo_electronico
   FROM (modulo1.usuarios u
     JOIN modulo1.roles r ON ((r.id_rol = u.id_rol)))
  WHERE (lower((r.nombre_rol)::text) = 'productor'::text)""",
    r"""CREATE VIEW modulo9.vw_rf20_dependencias_infraestructuras AS
SELECT i.id_infraestructura,
    i.nombre,
    count(d.id_dispositivo_iot) FILTER (WHERE (d.es_activo IS TRUE)) AS dispositivos_activos
   FROM (modulo9.infraestructuras i
     LEFT JOIN ( SELECT DISTINCT ON (d0.id_dispositivo_iot) d0.id_dispositivo_iot,
            d0.serial,
            d0.descripcion,
            d0.es_activo,
            d0.fecha_creacion,
            COALESCE(saa.id_infraestructura, ab.id_infraestructura) AS id_infraestructura
           FROM (((modulo9.dispositivos_iot d0
             LEFT JOIN modulo9.sensores s ON ((s.id_dispositivo_iot = d0.id_dispositivo_iot)))
             LEFT JOIN modulo9.sensores_areas_asociadas saa ON (((saa.id_sensor = s.id_sensores) AND ((saa.fecha_finalizacion IS NULL) OR (saa.fecha_finalizacion > now())))))
             LEFT JOIN modulo2.activos_biologicos ab ON ((ab.id_dispositivo_iot = d0.id_dispositivo_iot)))
          ORDER BY d0.id_dispositivo_iot, saa.fecha_asociacion DESC NULLS LAST, saa.id_sensores_area_asociada DESC NULLS LAST) d ON ((d.id_infraestructura = i.id_infraestructura)))
  GROUP BY i.id_infraestructura, i.nombre""",
    r"""CREATE VIEW modulo9.vw_rf23_dispositivos_configuracion_area AS
SELECT d.id_dispositivo_iot,
    d.serial,
    d.descripcion,
    d.es_activo,
    cr.id_configuracion_remota,
    cr.frecuencia_captura,
    cr.intervalo_transmision,
    cr.estado AS estado_configuracion,
    cr.fecha_creacion AS fecha_configuracion,
    cr.fecha_aplicacion,
    i.id_infraestructura,
    i.nombre AS area,
    f.id_finca,
    f.nombre AS finca
   FROM (((( SELECT DISTINCT ON (d0.id_dispositivo_iot) d0.id_dispositivo_iot,
            d0.serial,
            d0.descripcion,
            d0.es_activo,
            d0.fecha_creacion,
            COALESCE(saa.id_infraestructura, ab.id_infraestructura) AS id_infraestructura
           FROM (((modulo9.dispositivos_iot d0
             LEFT JOIN modulo9.sensores s ON ((s.id_dispositivo_iot = d0.id_dispositivo_iot)))
             LEFT JOIN modulo9.sensores_areas_asociadas saa ON (((saa.id_sensor = s.id_sensores) AND ((saa.fecha_finalizacion IS NULL) OR (saa.fecha_finalizacion > now())))))
             LEFT JOIN modulo2.activos_biologicos ab ON ((ab.id_dispositivo_iot = d0.id_dispositivo_iot)))
          ORDER BY d0.id_dispositivo_iot, saa.fecha_asociacion DESC NULLS LAST, saa.id_sensores_area_asociada DESC NULLS LAST) d
     JOIN modulo9.infraestructuras i ON ((i.id_infraestructura = d.id_infraestructura)))
     JOIN modulo9.fincas f ON ((f.id_finca = i.id_finca)))
     LEFT JOIN LATERAL ( SELECT cr_actual.id_configuracion_remota,
            cr_actual.frecuencia_captura,
            cr_actual.intervalo_transmision,
            cr_actual.estado,
            cr_actual.fecha_creacion,
            cr_actual.fecha_aplicacion
           FROM modulo9.configuraciones_remotas cr_actual
          WHERE (cr_actual.id_dispositivo_iot = d.id_dispositivo_iot)
          ORDER BY cr_actual.fecha_creacion DESC NULLS LAST, cr_actual.id_configuracion_remota DESC
         LIMIT 1) cr ON (true))""",
    r"""CREATE VIEW modulo9.vw_rf24_dispositivos_activos_calibraciones AS
SELECT d.id_dispositivo_iot,
    d.serial,
    d.descripcion,
    d.es_activo,
    i.id_infraestructura,
    i.nombre AS area,
    f.id_finca,
    f.nombre AS finca,
    count(DISTINCT s.id_sensores) AS total_sensores,
    count(DISTINCT c.id_calibracion) AS total_calibraciones,
    max(c.fecha_calibracion) AS ultima_calibracion
   FROM ((((( SELECT DISTINCT ON (d0.id_dispositivo_iot) d0.id_dispositivo_iot,
            d0.serial,
            d0.descripcion,
            d0.es_activo,
            d0.fecha_creacion,
            COALESCE(saa.id_infraestructura, ab.id_infraestructura) AS id_infraestructura
           FROM (((modulo9.dispositivos_iot d0
             LEFT JOIN modulo9.sensores s_1 ON ((s_1.id_dispositivo_iot = d0.id_dispositivo_iot)))
             LEFT JOIN modulo9.sensores_areas_asociadas saa ON (((saa.id_sensor = s_1.id_sensores) AND ((saa.fecha_finalizacion IS NULL) OR (saa.fecha_finalizacion > now())))))
             LEFT JOIN modulo2.activos_biologicos ab ON ((ab.id_dispositivo_iot = d0.id_dispositivo_iot)))
          ORDER BY d0.id_dispositivo_iot, saa.fecha_asociacion DESC NULLS LAST, saa.id_sensores_area_asociada DESC NULLS LAST) d
     JOIN modulo9.infraestructuras i ON ((i.id_infraestructura = d.id_infraestructura)))
     JOIN modulo9.fincas f ON ((f.id_finca = i.id_finca)))
     LEFT JOIN modulo9.sensores s ON ((s.id_dispositivo_iot = d.id_dispositivo_iot)))
     LEFT JOIN modulo9.calibraciones c ON ((c.id_dispositivo_iot = d.id_dispositivo_iot)))
  WHERE (d.es_activo IS TRUE)
  GROUP BY d.id_dispositivo_iot, d.serial, d.descripcion, d.es_activo, i.id_infraestructura, i.nombre, f.id_finca, f.nombre""",
    r"""CREATE VIEW modulo9.vw_rf27_tema_usuario_global AS
SELECT u.id_usuario,
    tv_user.id_tema_visual AS id_preferencia_usuario,
    tv_user.theme_mode AS tema_usuario,
    tv_user.fecha_actualizacion AS actualizado_en,
    tv_global.theme_mode AS tema_global,
    concat_ws(' '::text, u.nombre, u.apellidos) AS usuario
   FROM ((modulo1.usuarios u
     LEFT JOIN LATERAL ( SELECT tv.id_tema_visual,
            tv.theme_mode,
            tv.fecha_actualizacion
           FROM modulo9.temas_visuales tv
          WHERE ((tv.id_usuario = u.id_usuario) AND (tv.es_global IS FALSE))
          ORDER BY tv.fecha_actualizacion DESC, tv.id_tema_visual DESC
         LIMIT 1) tv_user ON (true))
     LEFT JOIN LATERAL ( SELECT tv.theme_mode
           FROM modulo9.temas_visuales tv
          WHERE (tv.es_global IS TRUE)
          ORDER BY tv.fecha_actualizacion DESC, tv.id_tema_visual DESC
         LIMIT 1) tv_global ON (true))""",
    r"""CREATE VIEW modulo9.vw_rf28_dashboard_layout_usuario AS
SELECT DISTINCT ON (id_usuario) id_usuario,
    id_dashboard_layout,
    config,
    active_widget,
    fecha_actualizacion,
    jsonb_array_length(COALESCE((config -> 'grid'::text), '[]'::jsonb)) AS total_widgets_configurados
   FROM modulo9.dashboard_layouts dl
  ORDER BY id_usuario, fecha_actualizacion DESC NULLS LAST, id_dashboard_layout DESC""",
    r"""CREATE VIEW modulo9.vw_rf28_widget_dispositivos_sin_configuracion AS
SELECT d.id_dispositivo_iot,
    d.serial,
    d.descripcion,
    i.id_infraestructura,
    i.nombre AS area,
    f.id_finca,
    f.nombre AS finca
   FROM ((( SELECT DISTINCT ON (d0.id_dispositivo_iot) d0.id_dispositivo_iot,
            d0.serial,
            d0.descripcion,
            d0.es_activo,
            d0.fecha_creacion,
            COALESCE(saa.id_infraestructura, ab.id_infraestructura) AS id_infraestructura
           FROM (((modulo9.dispositivos_iot d0
             LEFT JOIN modulo9.sensores s ON ((s.id_dispositivo_iot = d0.id_dispositivo_iot)))
             LEFT JOIN modulo9.sensores_areas_asociadas saa ON (((saa.id_sensor = s.id_sensores) AND ((saa.fecha_finalizacion IS NULL) OR (saa.fecha_finalizacion > now())))))
             LEFT JOIN modulo2.activos_biologicos ab ON ((ab.id_dispositivo_iot = d0.id_dispositivo_iot)))
          ORDER BY d0.id_dispositivo_iot, saa.fecha_asociacion DESC NULLS LAST, saa.id_sensores_area_asociada DESC NULLS LAST) d
     JOIN modulo9.infraestructuras i ON ((i.id_infraestructura = d.id_infraestructura)))
     JOIN modulo9.fincas f ON ((f.id_finca = i.id_finca)))
  WHERE ((d.es_activo IS TRUE) AND (NOT (EXISTS ( SELECT 1
           FROM modulo9.configuraciones_remotas cr
          WHERE (cr.id_dispositivo_iot = d.id_dispositivo_iot)))))""",
    r"""CREATE VIEW modulo9.vw_rf28_widget_estado_dispositivos AS
SELECT d.id_dispositivo_iot,
    d.serial,
    d.es_activo,
    i.id_infraestructura,
    i.nombre AS area,
    f.id_finca,
    f.nombre AS finca,
    ultima_cal.ultima_calibracion,
    cr.frecuencia_captura,
    cr.intervalo_transmision,
    cr.estado AS estado_configuracion
   FROM ((((( SELECT DISTINCT ON (d0.id_dispositivo_iot) d0.id_dispositivo_iot,
            d0.serial,
            d0.descripcion,
            d0.es_activo,
            d0.fecha_creacion,
            COALESCE(saa.id_infraestructura, ab.id_infraestructura) AS id_infraestructura
           FROM (((modulo9.dispositivos_iot d0
             LEFT JOIN modulo9.sensores s ON ((s.id_dispositivo_iot = d0.id_dispositivo_iot)))
             LEFT JOIN modulo9.sensores_areas_asociadas saa ON (((saa.id_sensor = s.id_sensores) AND ((saa.fecha_finalizacion IS NULL) OR (saa.fecha_finalizacion > now())))))
             LEFT JOIN modulo2.activos_biologicos ab ON ((ab.id_dispositivo_iot = d0.id_dispositivo_iot)))
          ORDER BY d0.id_dispositivo_iot, saa.fecha_asociacion DESC NULLS LAST, saa.id_sensores_area_asociada DESC NULLS LAST) d
     JOIN modulo9.infraestructuras i ON ((i.id_infraestructura = d.id_infraestructura)))
     JOIN modulo9.fincas f ON ((f.id_finca = i.id_finca)))
     LEFT JOIN LATERAL ( SELECT max(c.fecha_calibracion) AS ultima_calibracion
           FROM modulo9.calibraciones c
          WHERE (c.id_dispositivo_iot = d.id_dispositivo_iot)) ultima_cal ON (true))
     LEFT JOIN LATERAL ( SELECT cr_actual.frecuencia_captura,
            cr_actual.intervalo_transmision,
            cr_actual.estado
           FROM modulo9.configuraciones_remotas cr_actual
          WHERE (cr_actual.id_dispositivo_iot = d.id_dispositivo_iot)
          ORDER BY cr_actual.fecha_creacion DESC NULLS LAST, cr_actual.id_configuracion_remota DESC
         LIMIT 1) cr ON (true))""",
    r"""CREATE VIEW modulo9.vw_rf28_widget_estado_fincas AS
SELECT f.id_finca,
    f.nombre,
    f.es_activo,
    (f.ubicacion ->> 'departamento'::text) AS departamento,
    count(DISTINCT i.id_infraestructura) FILTER (WHERE (i.es_activo IS TRUE)) AS areas_activas,
    count(DISTINCT d.id_dispositivo_iot) FILTER (WHERE (d.es_activo IS TRUE)) AS dispositivos_activos
   FROM ((modulo9.fincas f
     LEFT JOIN modulo9.infraestructuras i ON ((i.id_finca = f.id_finca)))
     LEFT JOIN ( SELECT DISTINCT ON (d0.id_dispositivo_iot) d0.id_dispositivo_iot,
            d0.serial,
            d0.descripcion,
            d0.es_activo,
            d0.fecha_creacion,
            COALESCE(saa.id_infraestructura, ab.id_infraestructura) AS id_infraestructura
           FROM (((modulo9.dispositivos_iot d0
             LEFT JOIN modulo9.sensores s ON ((s.id_dispositivo_iot = d0.id_dispositivo_iot)))
             LEFT JOIN modulo9.sensores_areas_asociadas saa ON (((saa.id_sensor = s.id_sensores) AND ((saa.fecha_finalizacion IS NULL) OR (saa.fecha_finalizacion > now())))))
             LEFT JOIN modulo2.activos_biologicos ab ON ((ab.id_dispositivo_iot = d0.id_dispositivo_iot)))
          ORDER BY d0.id_dispositivo_iot, saa.fecha_asociacion DESC NULLS LAST, saa.id_sensores_area_asociada DESC NULLS LAST) d ON ((d.id_infraestructura = i.id_infraestructura)))
  GROUP BY f.id_finca, f.nombre, f.es_activo, f.ubicacion""",
    r"""CREATE VIEW modulo9.vw_rf29_idioma_usuario_global AS
SELECT u.id_usuario,
    pi_user.id_preferencia_idioma,
    pi_user.locale_code AS idioma_usuario,
    pi_user.es_por_defecto,
    pi_user.fecha_actualizacion,
    pi_global.locale_code AS idioma_global,
    concat_ws(' '::text, u.nombre, u.apellidos) AS usuario
   FROM ((modulo1.usuarios u
     LEFT JOIN LATERAL ( SELECT pi.id_preferencia_idioma,
            pi.locale_code,
            pi.es_por_defecto,
            pi.fecha_actualizacion
           FROM modulo9.preferencias_idiomas pi
          WHERE ((pi.id_usuario = u.id_usuario) AND (pi.es_por_defecto IS FALSE))
          ORDER BY pi.fecha_actualizacion DESC NULLS LAST, pi.id_preferencia_idioma DESC
         LIMIT 1) pi_user ON (true))
     LEFT JOIN LATERAL ( SELECT pi.locale_code
           FROM modulo9.preferencias_idiomas pi
          WHERE (pi.es_por_defecto IS TRUE)
          ORDER BY pi.fecha_actualizacion DESC NULLS LAST, pi.id_preferencia_idioma DESC
         LIMIT 1) pi_global ON (true))""",
    r"""CREATE VIEW modulo9.vw_rf32_plantillas_detalle AS
SELECT p.id_plantilla,
    p.template_name,
    p.version,
    p.fecha_creacion,
    p.params_snapshot,
    e.id_especie,
    e.nombre AS especie,
    e.es_activo AS especie_activa,
    p.id_usuario,
    concat_ws(' '::text, u.nombre, u.apellidos) AS creado_por
   FROM ((modulo9.plantillas p
     JOIN modulo9.especies e ON ((e.id_especie = p.id_especie)))
     JOIN modulo1.usuarios u ON ((u.id_usuario = p.id_usuario)))""",
    r"""CREATE VIEW modulo9.vw_rf15_dependencias_especie AS
SELECT e.id_especie,
    e.nombre,
    count(DISTINCT ua.id_umbral_ambiental) FILTER (WHERE (ua.es_activo IS TRUE)) AS umbrales_activos,
    count(DISTINCT cb.id_ciclo_biologico) FILTER (WHERE (cb.es_activo IS TRUE)) AS ciclos_activos,
    count(DISTINCT ep.id_especies_patologias) AS patologias_asociadas
   FROM (((modulo9.especies e
     LEFT JOIN modulo9.umbrales_ambientales ua ON ((ua.id_especie = e.id_especie)))
     LEFT JOIN modulo9.ciclos_biologicos cb ON ((cb.id_especie = e.id_especie)))
     LEFT JOIN modulo9.especies_patologias ep ON ((ep.id_especie = e.id_especie)))
  GROUP BY e.id_especie, e.nombre""",
    r"""CREATE VIEW modulo9.vw_rf17_umbral_activo_por_especie_variable AS
SELECT id_especie,
    id_variable_ambiental,
    count(*) AS total_configuraciones_activas,
    array_agg(id_umbral_ambiental ORDER BY id_umbral_ambiental) AS umbrales_activos
   FROM modulo9.umbrales_ambientales ua
  WHERE (es_activo IS TRUE)
  GROUP BY id_especie, id_variable_ambiental""",
    r"""CREATE VIEW modulo9.vw_rf17_variables_configuracion_especie AS
SELECT e.id_especie,
    e.nombre AS especie,
    va.id_variable_ambiental,
    va.nombre,
    va.unidad,
    va.valor_fisico_min,
    va.valor_fisico_max,
    va.es_activo,
    (count(ua.id_umbral_ambiental) > 0) AS ya_configurada,
    min(ua.id_umbral_ambiental) AS id_umbral_ambiental,
    min((ua.nombre)::text) AS nombre_umbral,
    count(ua.id_umbral_ambiental) AS total_umbrales_activos
   FROM ((modulo9.especies e
     CROSS JOIN modulo9.variables_ambientales va)
     LEFT JOIN modulo9.umbrales_ambientales ua ON (((ua.id_variable_ambiental = va.id_variable_ambiental) AND (ua.id_especie = e.id_especie) AND (ua.es_activo IS TRUE))))
  WHERE (va.es_activo IS TRUE)
  GROUP BY e.id_especie, e.nombre, va.id_variable_ambiental, va.nombre, va.unidad, va.valor_fisico_min, va.valor_fisico_max, va.es_activo""",
    r"""CREATE VIEW modulo9.vw_rf18_configuracion_global_activa AS
SELECT cg.id_configuracion_global,
    cg.frecuencia_muestreo,
    cg.heartbeat,
    cg.fecha_actualizacion,
    cg.es_activo,
    cg.id_usuario,
    concat_ws(' '::text, u.nombre, u.apellidos) AS modificado_por,
    u.correo_electronico
   FROM (modulo9.configuraciones_globales cg
     JOIN modulo1.usuarios u ON ((u.id_usuario = cg.id_usuario)))
  WHERE (cg.es_activo IS TRUE)""",
    r"""CREATE VIEW modulo9.vw_rf19_dependencias_fincas AS
SELECT f.id_finca,
    f.nombre,
    count(DISTINCT i.id_infraestructura) FILTER (WHERE (i.es_activo IS TRUE)) AS infra_activas,
    count(DISTINCT d.id_dispositivo_iot) FILTER (WHERE (d.es_activo IS TRUE)) AS dispositivos_activos
   FROM ((modulo9.fincas f
     LEFT JOIN modulo9.infraestructuras i ON ((i.id_finca = f.id_finca)))
     LEFT JOIN ( SELECT DISTINCT ON (d0.id_dispositivo_iot) d0.id_dispositivo_iot,
            d0.serial,
            d0.descripcion,
            d0.es_activo,
            d0.fecha_creacion,
            COALESCE(saa.id_infraestructura, ab.id_infraestructura) AS id_infraestructura
           FROM (((modulo9.dispositivos_iot d0
             LEFT JOIN modulo9.sensores s ON ((s.id_dispositivo_iot = d0.id_dispositivo_iot)))
             LEFT JOIN modulo9.sensores_areas_asociadas saa ON (((saa.id_sensor = s.id_sensores) AND ((saa.fecha_finalizacion IS NULL) OR (saa.fecha_finalizacion > now())))))
             LEFT JOIN modulo2.activos_biologicos ab ON ((ab.id_dispositivo_iot = d0.id_dispositivo_iot)))
          ORDER BY d0.id_dispositivo_iot, saa.fecha_asociacion DESC NULLS LAST, saa.id_sensores_area_asociada DESC NULLS LAST) d ON ((d.id_infraestructura = i.id_infraestructura)))
  GROUP BY f.id_finca, f.nombre""",
    r"""CREATE VIEW modulo9.vw_rf21_dispositivos_area_sensores AS
SELECT d.id_infraestructura,
    d.id_dispositivo_iot,
    d.serial,
    d.descripcion,
    d.es_activo,
    d.fecha_creacion,
    count(s.id_sensores) AS total_sensores,
    count(s.id_sensores) FILTER (WHERE (s.es_activo IS TRUE)) AS sensores_activos
   FROM (( SELECT DISTINCT ON (d0.id_dispositivo_iot) d0.id_dispositivo_iot,
            d0.serial,
            d0.descripcion,
            d0.es_activo,
            d0.fecha_creacion,
            COALESCE(saa.id_infraestructura, ab.id_infraestructura) AS id_infraestructura
           FROM (((modulo9.dispositivos_iot d0
             LEFT JOIN modulo9.sensores s_1 ON ((s_1.id_dispositivo_iot = d0.id_dispositivo_iot)))
             LEFT JOIN modulo9.sensores_areas_asociadas saa ON (((saa.id_sensor = s_1.id_sensores) AND ((saa.fecha_finalizacion IS NULL) OR (saa.fecha_finalizacion > now())))))
             LEFT JOIN modulo2.activos_biologicos ab ON ((ab.id_dispositivo_iot = d0.id_dispositivo_iot)))
          ORDER BY d0.id_dispositivo_iot, saa.fecha_asociacion DESC NULLS LAST, saa.id_sensores_area_asociada DESC NULLS LAST) d
     LEFT JOIN modulo9.sensores s ON ((s.id_dispositivo_iot = d.id_dispositivo_iot)))
  GROUP BY d.id_infraestructura, d.id_dispositivo_iot, d.serial, d.descripcion, d.es_activo, d.fecha_creacion""",
    r"""CREATE VIEW modulo9.vw_rf21_dispositivos_sensores_asociacion AS
SELECT d.id_dispositivo_iot,
    d.serial,
    d.descripcion,
    d.es_activo,
    i.id_infraestructura,
    i.nombre AS area,
    f.id_finca,
    f.nombre AS finca,
    count(s.id_sensores) AS total_sensores,
    count(s.id_sensores) FILTER (WHERE (NOT (EXISTS ( SELECT 1
           FROM modulo9.sensores_areas_asociadas saa
          WHERE ((saa.id_sensor = s.id_sensores) AND (saa.tiene_estado IS TRUE)))))) AS sensores_libres,
    count(s.id_sensores) FILTER (WHERE (EXISTS ( SELECT 1
           FROM modulo9.sensores_areas_asociadas saa
          WHERE ((saa.id_sensor = s.id_sensores) AND (saa.tiene_estado IS TRUE))))) AS sensores_asociados
   FROM (((( SELECT DISTINCT ON (d0.id_dispositivo_iot) d0.id_dispositivo_iot,
            d0.serial,
            d0.descripcion,
            d0.es_activo,
            d0.fecha_creacion,
            COALESCE(saa.id_infraestructura, ab.id_infraestructura) AS id_infraestructura
           FROM (((modulo9.dispositivos_iot d0
             LEFT JOIN modulo9.sensores s_1 ON ((s_1.id_dispositivo_iot = d0.id_dispositivo_iot)))
             LEFT JOIN modulo9.sensores_areas_asociadas saa ON (((saa.id_sensor = s_1.id_sensores) AND ((saa.fecha_finalizacion IS NULL) OR (saa.fecha_finalizacion > now())))))
             LEFT JOIN modulo2.activos_biologicos ab ON ((ab.id_dispositivo_iot = d0.id_dispositivo_iot)))
          ORDER BY d0.id_dispositivo_iot, saa.fecha_asociacion DESC NULLS LAST, saa.id_sensores_area_asociada DESC NULLS LAST) d
     JOIN modulo9.infraestructuras i ON ((i.id_infraestructura = d.id_infraestructura)))
     JOIN modulo9.fincas f ON ((f.id_finca = i.id_finca)))
     LEFT JOIN modulo9.sensores s ON ((s.id_dispositivo_iot = d.id_dispositivo_iot)))
  WHERE (d.es_activo IS TRUE)
  GROUP BY d.id_dispositivo_iot, d.serial, d.descripcion, d.es_activo, i.id_infraestructura, i.nombre, f.id_finca, f.nombre""",
    r"""CREATE VIEW modulo9.vw_rf21_dispositivos_seriales AS
SELECT id_dispositivo_iot,
    serial,
    lower((serial)::text) AS serial_normalizado
   FROM ( SELECT DISTINCT ON (d0.id_dispositivo_iot) d0.id_dispositivo_iot,
            d0.serial,
            d0.descripcion,
            d0.es_activo,
            d0.fecha_creacion,
            COALESCE(saa.id_infraestructura, ab.id_infraestructura) AS id_infraestructura
           FROM (((modulo9.dispositivos_iot d0
             LEFT JOIN modulo9.sensores s ON ((s.id_dispositivo_iot = d0.id_dispositivo_iot)))
             LEFT JOIN modulo9.sensores_areas_asociadas saa ON (((saa.id_sensor = s.id_sensores) AND ((saa.fecha_finalizacion IS NULL) OR (saa.fecha_finalizacion > now())))))
             LEFT JOIN modulo2.activos_biologicos ab ON ((ab.id_dispositivo_iot = d0.id_dispositivo_iot)))
          ORDER BY d0.id_dispositivo_iot, saa.fecha_asociacion DESC NULLS LAST, saa.id_sensores_area_asociada DESC NULLS LAST) d""",
    r"""CREATE VIEW modulo9.vw_rf22_sensores_dispositivo_asociacion AS
SELECT s.id_dispositivo_iot,
    s.id_sensores,
    s.nombre,
    s.es_activo,
    saa.id_sensores_area_asociada,
    saa.tiene_estado AS asociado_activo,
    saa.punto_instalacion,
    i.id_infraestructura,
    i.nombre AS area_asociada,
    f.id_finca,
    f.nombre AS finca_asociada,
    saa.fecha_asociacion
   FROM (((modulo9.sensores s
     LEFT JOIN LATERAL ( SELECT saa_actual.id_sensores_area_asociada,
            saa_actual.tiene_estado,
            saa_actual.punto_instalacion,
            saa_actual.id_infraestructura,
            saa_actual.fecha_asociacion
           FROM modulo9.sensores_areas_asociadas saa_actual
          WHERE ((saa_actual.id_sensor = s.id_sensores) AND (saa_actual.tiene_estado IS TRUE))
          ORDER BY saa_actual.fecha_asociacion DESC, saa_actual.id_sensores_area_asociada DESC
         LIMIT 1) saa ON (true))
     LEFT JOIN modulo9.infraestructuras i ON ((i.id_infraestructura = saa.id_infraestructura)))
     LEFT JOIN modulo9.fincas f ON ((f.id_finca = i.id_finca)))""",
    r"""CREATE VIEW modulo9.vw_rf31_params_disponibles_especie AS
SELECT id_especie,
    nombre AS especie,
    json_build_object('umbrales', ( SELECT COALESCE(json_agg(json_build_object('id', ua.id_umbral_ambiental, 'nombre', ua.nombre) ORDER BY ua.nombre), '[]'::json) AS "coalesce"
           FROM modulo9.umbrales_ambientales ua
          WHERE ((ua.id_especie = e.id_especie) AND (ua.es_activo IS TRUE))), 'ciclos', ( SELECT COALESCE(json_agg(json_build_object('id', cb.id_ciclo_biologico, 'nombre', cb.nombre) ORDER BY cb.nombre), '[]'::json) AS "coalesce"
           FROM modulo9.ciclos_biologicos cb
          WHERE ((cb.id_especie = e.id_especie) AND (cb.es_activo IS TRUE))), 'patologias', ( SELECT COALESCE(json_agg(json_build_object('id', p.id_patologia, 'nombre', p.nombre) ORDER BY p.nombre), '[]'::json) AS "coalesce"
           FROM (modulo9.especies_patologias ep
             JOIN modulo9.patologias p ON ((p.id_patologia = ep.id_patologia)))
          WHERE ((ep.id_especie = e.id_especie) AND (p.es_activo IS TRUE)))) AS params_disponibles
   FROM modulo9.especies e""",
    r"""CREATE VIEW modulo9.vw_rf31_plantillas_listado AS
SELECT p.id_plantilla,
    p.template_name,
    p.version,
    p.fecha_creacion,
    p.id_especie,
    e.nombre AS especie,
    p.id_usuario,
    concat_ws(' '::text, u.nombre, u.apellidos) AS creado_por,
    jsonb_array_length(COALESCE((p.params_snapshot -> 'umbrales'::text), '[]'::jsonb)) AS total_umbrales,
    jsonb_array_length(COALESCE((p.params_snapshot -> 'ciclos_biologicos'::text), '[]'::jsonb)) AS total_ciclos,
    jsonb_array_length(COALESCE((p.params_snapshot -> 'metricas'::text), '[]'::jsonb)) AS total_metricas
   FROM ((modulo9.plantillas p
     JOIN modulo9.especies e ON ((e.id_especie = p.id_especie)))
     JOIN modulo1.usuarios u ON ((u.id_usuario = p.id_usuario)))""",
] 
 
UNTOUCHED = [
    "vw_rf22_areas_destino_disponibles",
    "vw_rf26_identidad_visual_activa",
    "vw_rf19_fincas_resumen_global",
    "vw_rf23_configuraciones_pendientes",
    "vw_rf24_historial_calibraciones_sensor",
    "vw_rf25_permisos_roles",
    "vw_rf26_auditorias_visuales_historial",
    "vw_rf27_preferencias_tema_usuarios",
    "vw_rf29_preferencias_idioma_usuarios",
    "vw_rf24_sensores_dispositivo_calibracion",
    "vw_rf25_contexto_usuario",
    "vw_rf33_aplicaciones_plantillas_historial",
    "vw_rf17_gestion_especies_historial",
    "vw_rf15_especies_activas_selector",
    "vw_rf15_especies_nombre_normalizado",
    "vw_rf15_especies_resumen",
    "vw_rf16_cabecera_especie",
    "vw_rf16_ciclos_biologicos_especie",
    "vw_rf16_ciclos_nombre_normalizado",
    "vw_rf18_configuraciones_globales_historial",
    "vw_rf20_infraestructuras_nombre_normalizado",
    "vw_rf31_plantillas_nombre_normalizado",
    "vw_rf31_plantillas_resumen",
    "vw_rf16_dependencias_ciclos",
    "vw_rf16_dependencias_patologias",
    "vw_rf16_patologias_especie",
    "vw_rf16_patologias_nombre_normalizado",
]
 
 
def upgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '10s'")
    for sql in VIEWS_UPGRADE:
        op.execute(sql)
    for name, text in COMMENTS.items():
        op.execute(f"COMMENT ON VIEW modulo9.{name} IS '{text}'")
 
 
def downgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '10s'")
    for name in DROP_ORDER:
        op.execute(f"DROP VIEW IF EXISTS modulo9.{name}")
    for sql in VIEWS_ORIGINALES:
        op.execute(sql)
    for name in UNTOUCHED:
        op.execute(f"COMMENT ON VIEW modulo9.{name} IS NULL")
 
