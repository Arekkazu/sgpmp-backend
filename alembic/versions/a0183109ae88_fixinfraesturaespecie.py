# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-23 | Arekkazu | INTEG RFC-012..016 DB-06: roles opcionales en BD nueva y PK/FK segun la convencion |
"""FixInfraesturaEspecie

Revision ID: a0183109ae88
Revises: e5a3c9b17d42
Create Date: 2026-10-20 15:28:38.232075

"""
from __future__ import annotations

import logging
import os
import re

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa



# revision identifiers, used by Alembic.
revision: str = 'a0183109ae88'
down_revision: Union[str, Sequence[str], None] = 'e5a3c9b17d42'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None



log = logging.getLogger("alembic.runtime.migration")

# --------------------------------------------------------------------------
# Constantes
# --------------------------------------------------------------------------
PUENTE = "modulo9.infraestructuras_especies"
TABLA_PUENTE = "infraestructuras_especies"
TABLA_PLANTILLA_RLS = "sensores_areas_asociadas"  # origen de las políticas RLS
OWNER = "sgpmp_owner"
ROL_APP = "sgpmp_app"
# Rol del broker (ingesta IoT). Ajustable sin tocar el código.
ROL_BROKER = os.getenv("SGPMP_BROKER_ROLE", "rol_aiot")
# Convención del repo: REVOKE ALL a estos roles y luego GRANT explícito.
ROLES_REVOKE = ("rol_aiot", "rol_app", "rol_dev", "rol_impl", "rol_migracion", "sgpmp_app")
# Spec RFC-012: solo sgpmp_app y broker. El broker solo lee (fn_ingesta_telemetria
# únicamente hace SELECT sobre la puente) -> mínimo privilegio.
GRANTS_PUENTE = {ROL_APP: "SELECT, INSERT, UPDATE, DELETE", ROL_BROKER: "SELECT"}
# Misma definición de "activo vivo" que usan las vistas/funciones existentes.
ESTADOS_NO_VIVOS = ("INACTIVO", "CERRADO", "BAJA")
# Tablas con FORCE RLS que se leen/escriben durante el backfill.
TABLAS_FORCE_RLS = ("modulo9.infraestructuras", "modulo2.activos_biologicos")
# Si =1, el upgrade aborta cuando el backfill deja áreas con grupos incompatibles.
ABORTAR_SI_INCOMPATIBLES = os.getenv("RFC012_ABORTAR_SI_INCOMPATIBLES", "0") == "1"

MARCA_RFC = " | RFC-012: ya no lee infraestructuras.id_especie; usa modulo9.infraestructuras_especies."

VISTAS = (
    "vw_rf20_areas_finca_resumen",
    "vw_rf25_contexto_usuario",
    "vw_rf15_dependencias_especie",
)
FUNCIONES_AFECTADAS = {
    ("modulo9", "fn_seriales_gateway_edge_por_especie"),
    ("modulo3", "fn_gateways_edge_por_regla_alerta"),
    ("modulo3", "fn_ingesta_telemetria"),
}


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def _sql(sentencia: str) -> None:
    op.execute(sa.text(sentencia))


def _fetch(sentencia: str, **params):
    return op.get_bind().execute(sa.text(sentencia), params).mappings().all()


def _lit(valor: str) -> str:
    """Literal SQL seguro para sa.text (comillas y ':' escapados)."""
    return "'" + valor.replace("'", "''").replace(":", r"\:") + "'"


def _existe_rol(rol: str) -> bool:
    return bool(_fetch("SELECT 1 FROM pg_roles WHERE rolname = :r", r=rol))


def _exigir_transaccion() -> None:
    # Se desactiva FORCE RLS temporalmente: solo es seguro si todo es atómico.
    if not op.get_context().impl.transactional_ddl:
        raise RuntimeError("RFC-012 exige DDL transaccional (una sola transacción).")


def _forzar_rls(activar: bool, tablas=TABLAS_FORCE_RLS) -> None:
    modo = "FORCE" if activar else "NO FORCE"
    for t in tablas:
        _sql(f"ALTER TABLE {t} {modo} ROW LEVEL SECURITY")


def _verificar_force(tablas) -> None:
    for t in tablas:
        f = _fetch("SELECT relforcerowsecurity AS f FROM pg_class WHERE oid = to_regclass(:t)", t=t)
        if not f or not f[0]["f"]:
            raise RuntimeError(f"FORCE ROW LEVEL SECURITY no quedó activo en {t}")


def _patch(fuente: str, patron: str, reemplazo: str, flags: int = 0) -> str:
    nuevo, n = re.subn(patron, lambda _m: reemplazo, fuente, flags=flags)
    if n != 1:
        raise RuntimeError(f"Parche RFC-012 aplicó {n} veces (esperado 1): {patron[:60]}")
    return nuevo


# ---- Snapshot / restauración de vistas (owner, reloptions, comentario, ACL) ----
def _snapshot_vista(fq: str) -> dict:
    fila = _fetch(
        """
        SELECT quote_ident(pg_get_userbyid(c.relowner)) AS propietario,
               (pg_get_userbyid(c.relowner) = current_user) AS es_actual,
               c.reloptions AS opciones,
               obj_description(c.oid, 'pg_class') AS comentario
        FROM pg_class c WHERE c.oid = to_regclass(:fq) AND c.relkind = 'v'
        """,
        fq=fq,
    )
    if not fila:
        raise RuntimeError(f"La vista {fq} no existe")
    privs = _fetch(
        """
        SELECT CASE WHEN a.grantee = 0 THEN 'PUBLIC'
                    ELSE quote_ident(pg_get_userbyid(a.grantee)) END AS grantee,
               a.privilege_type AS privilegio, a.is_grantable AS con_opcion
        FROM pg_class c CROSS JOIN LATERAL aclexplode(c.relacl) a
        WHERE c.oid = to_regclass(:fq) AND a.grantee <> c.relowner
        """,
        fq=fq,
    )
    return {**dict(fila[0]), "privs": [dict(p) for p in privs]}


def _restaurar_vista(fq: str, snap: dict, comentario: str | None) -> None:
    if not snap["es_actual"]:
        _sql(f"ALTER VIEW {fq} OWNER TO {snap['propietario']}")
    if snap["opciones"]:
        _sql(f"ALTER VIEW {fq} SET ({', '.join(snap['opciones'])})")
    for p in snap["privs"]:
        opcion = " WITH GRANT OPTION" if p["con_opcion"] else ""
        _sql(f"GRANT {p['privilegio']} ON TABLE {fq} TO {p['grantee']}{opcion}")
    if comentario:
        _sql(f"COMMENT ON VIEW {fq} IS {_lit(comentario)}")


# ---- Políticas RLS: copiadas de sensores_areas_asociadas ----
_CMD = {"r": "SELECT", "a": "INSERT", "w": "UPDATE", "d": "DELETE", "*": "ALL"}


def _copiar_politicas_rls() -> None:
    origen = _fetch(
        """
        SELECT n.nspname || '.' || c.relname AS fq
        FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relname = :t AND c.relkind IN ('r', 'p')
        """,
        t=TABLA_PLANTILLA_RLS,
    )
    if len(origen) != 1:
        raise RuntimeError(f"Se esperaba 1 tabla {TABLA_PLANTILLA_RLS}, hay {len(origen)}")
    fq_origen = origen[0]["fq"]
    pols = _fetch(
        """
        SELECT p.polname, p.polcmd, p.polpermissive,
               pg_get_expr(p.polqual, p.polrelid) AS usando,
               pg_get_expr(p.polwithcheck, p.polrelid) AS con_check,
               CASE WHEN p.polroles = '{0}'::oid[] THEN ARRAY['PUBLIC']
                    ELSE ARRAY(SELECT quote_ident(r.rolname) FROM pg_roles r
                               WHERE r.oid = ANY (p.polroles) ORDER BY r.rolname) END AS roles
        FROM pg_policy p WHERE p.polrelid = to_regclass(:fq) ORDER BY p.polname
        """,
        fq=fq_origen,
    )
    if not pols:
        # RLS FORCE sin políticas = denegar todo: mejor abortar que dejar la tabla muerta.
        raise RuntimeError(f"{fq_origen} no tiene políticas RLS que copiar")
    for p in pols:
        cmd = _CMD[p["polcmd"]]
        nombre = (
            p["polname"].replace(TABLA_PLANTILLA_RLS, TABLA_PUENTE)
            if TABLA_PLANTILLA_RLS in p["polname"]
            else f"pol_{TABLA_PUENTE}_{cmd.lower()}"
        )
        sql = (
            f"CREATE POLICY {nombre} ON {PUENTE} "
            f"AS {'PERMISSIVE' if p['polpermissive'] else 'RESTRICTIVE'} "
            f"FOR {cmd} TO {', '.join(p['roles'])}"
        )
        if p["usando"]:
            sql += f" USING ({p['usando'].replace(TABLA_PLANTILLA_RLS + '.', TABLA_PUENTE + '.')})"
        if p["con_check"]:
            sql += f" WITH CHECK ({p['con_check'].replace(TABLA_PLANTILLA_RLS + '.', TABLA_PUENTE + '.')})"
        _sql(sql)  # si la expresión usa columnas que la puente no tiene, falla aquí (ruidoso)


# ---- Preflight: dependientes "ocultos" que DROP COLUMN no detecta (cuerpos de funciones) ----
def _advertir_dependencias_ocultas() -> None:
    filas = _fetch(
        r"""
        SELECT n.nspname AS esquema, p.proname AS nombre
        FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE p.prokind IN ('f', 'p')
          AND n.nspname NOT IN ('pg_catalog', 'information_schema')
          AND p.prosrc ILIKE '%infraestructuras%'
          AND (p.prosrc ~* 'capacidad_maxima' OR p.prosrc ~* '\m(infraestructuras|infra|inf|i)\.id_especie')
        """
    )
    otros = [f"{f['esquema']}.{f['nombre']}" for f in filas
             if (f["esquema"], f["nombre"]) not in FUNCIONES_AFECTADAS]
    if otros:
        log.warning(
            "RFC-012 PREFLIGHT: funciones fuera de las 6 que parecen leer "
            "infraestructuras.id_especie/capacidad_maxima (fallarán en runtime tras el DROP COLUMN): %s",
            ", ".join(sorted(otros)),
        )


# --------------------------------------------------------------------------
# UPGRADE - bloques
# --------------------------------------------------------------------------
def _crear_tabla_puente() -> None:
    _sql(f"""
        CREATE TABLE {PUENTE} (
            id_infraestructura_especie integer GENERATED BY DEFAULT AS IDENTITY,
            id_infraestructura integer NOT NULL,
            id_especie integer NOT NULL,
            fecha_creacion timestamp with time zone NOT NULL DEFAULT now(),
            CONSTRAINT infraestructuras_especies_pkey PRIMARY KEY (id_infraestructura_especie),
            CONSTRAINT uq_infraestructuras_especies UNIQUE (id_infraestructura, id_especie),
            -- Fila dependiente del área: no tiene sentido sin ella.
            CONSTRAINT infraestructuras_especies_id_infraestructura_fkey
                FOREIGN KEY (id_infraestructura) REFERENCES modulo9.infraestructuras (id_infraestructura)
                ON UPDATE NO ACTION ON DELETE CASCADE,
            -- El catálogo de especies no puede perder una especie en uso (además especies tiene trg no_delete).
            CONSTRAINT infraestructuras_especies_id_especie_fkey
                FOREIGN KEY (id_especie) REFERENCES modulo9.especies (id_especie)
                ON UPDATE NO ACTION ON DELETE RESTRICT
        )
    """)
    # El UNIQUE ya cubre búsquedas por área; este índice cubre el sentido inverso (especie -> áreas).
    _sql(f"CREATE INDEX idx_infraestructuras_especies_id_especie ON {PUENTE} (id_especie)")
    # En una BD construida desde cero (pruebas, CI) los roles de los ambientes no
    # existen: se omiten igual que en a3c9e5d17b42 / e3b8c1d9f702.
    if _existe_rol(OWNER):
        _sql(f"ALTER TABLE {PUENTE} OWNER TO {OWNER}")
    _sql(f"ALTER TABLE {PUENTE} ENABLE ROW LEVEL SECURITY")  # FORCE se aplica al final (post-backfill)
    _copiar_politicas_rls()
    revocar = [r for r in ROLES_REVOKE if _existe_rol(r)]
    if revocar:
        _sql(f"REVOKE ALL ON TABLE {PUENTE} FROM {', '.join(revocar)}")
    for rol, privs in GRANTS_PUENTE.items():
        if _existe_rol(rol):
            _sql(f"GRANT {privs} ON TABLE {PUENTE} TO {rol}")
    if _existe_rol(OWNER):
        _sql(f"GRANT ALL ON TABLE {PUENTE} TO {OWNER}")
    _sql(f"COMMENT ON TABLE {PUENTE} IS {_lit('Tabla puente N:M entre infraestructura (área) y especie (RFC-012). Un área puede alojar varias especies del mismo grupo_manejo.')}")
    _sql(f"COMMENT ON COLUMN {PUENTE}.id_infraestructura IS {_lit('Área (infraestructura) que aloja la especie.')}")
    _sql(f"COMMENT ON COLUMN {PUENTE}.id_especie IS {_lit('Especie habilitada/presente en el área.')}")
    _sql(f"COMMENT ON COLUMN {PUENTE}.fecha_creacion IS {_lit('Cuándo se asoció la especie al área. En el downgrade define la especie principal (la más antigua).')}")


def _backfill() -> None:
    # 1) Especie actualmente asignada a cada área. Se inserta PRIMERO y ordenado por área:
    #    en el downgrade, la fila más antigua (fecha_creacion, PK) es la "especie principal"
    #    y por tanto coincide con la asignación original.
    _sql(f"""
        INSERT INTO {PUENTE} (id_infraestructura, id_especie)
        SELECT i.id_infraestructura, i.id_especie
        FROM modulo9.infraestructuras i
        WHERE i.id_especie IS NOT NULL
        ORDER BY i.id_infraestructura
        ON CONFLICT (id_infraestructura, id_especie) DO NOTHING
    """)
    # 2) Barrido de activos vivos: especies presentes que no estaban asignadas al área.
    #    Se ordena por cantidad de activos desc: en áreas sin especie asignada (id_especie NULL),
    #    la especie dominante queda como primera/principal. Se incluyen áreas inactivas
    #    (la realidad física existe aunque el área esté desactivada).
    estados = ", ".join(f"'{e}'" for e in ESTADOS_NO_VIVOS)
    _sql(f"""
        INSERT INTO {PUENTE} (id_infraestructura, id_especie)
        SELECT a.id_infraestructura, a.id_especie
        FROM modulo2.activos_biologicos a
        JOIN modulo2.estados_activos_biologicos ea ON ea.id_estado_activo_biologico = a.id_estado
        WHERE ea.nombre::text <> ALL (ARRAY[{estados}])
        GROUP BY a.id_infraestructura, a.id_especie
        ORDER BY a.id_infraestructura, count(*) DESC, a.id_especie
        ON CONFLICT (id_infraestructura, id_especie) DO NOTHING
    """)


def _verificar_backfill() -> None:
    estados = ", ".join(f"'{e}'" for e in ESTADOS_NO_VIVOS)
    faltan_areas = _fetch(f"""
        SELECT count(*) AS n FROM modulo9.infraestructuras i
        WHERE i.id_especie IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM {PUENTE} ie WHERE ie.id_infraestructura = i.id_infraestructura
                                         AND ie.id_especie = i.id_especie)
    """)[0]["n"]
    faltan_activos = _fetch(f"""
        SELECT count(*) AS n FROM modulo2.activos_biologicos a
        JOIN modulo2.estados_activos_biologicos ea ON ea.id_estado_activo_biologico = a.id_estado
        WHERE ea.nombre::text <> ALL (ARRAY[{estados}]) AND NOT EXISTS (
            SELECT 1 FROM {PUENTE} ie WHERE ie.id_infraestructura = a.id_infraestructura
                                         AND ie.id_especie = a.id_especie)
    """)[0]["n"]
    if faltan_areas or faltan_activos:
        raise RuntimeError(f"Backfill incompleto: áreas={faltan_areas}, activos vivos={faltan_activos}")
    total = _fetch(f"SELECT count(*) AS n FROM {PUENTE}")[0]["n"]
    log.info("RFC-012 backfill OK: %s filas en %s", total, PUENTE)


def _alertar_incompatibles() -> None:
    """Áreas con especies de distinto grupo_manejo tras el backfill (NULL cuenta como grupo propio).
    Se loguea desde Python (RAISE NOTICE no se vería en la salida de Alembic)."""
    filas = _fetch(f"""
        SELECT i.id_infraestructura, i.nombre, i.id_finca,
               string_agg(e.nombre || ' [' || COALESCE(e.grupo_manejo, 'SIN_GRUPO') || ']', ', '
                          ORDER BY e.nombre) AS especies
        FROM {PUENTE} ie
        JOIN modulo9.infraestructuras i ON i.id_infraestructura = ie.id_infraestructura
        JOIN modulo9.especies e ON e.id_especie = ie.id_especie
        GROUP BY i.id_infraestructura, i.nombre, i.id_finca
        HAVING count(DISTINCT COALESCE(e.grupo_manejo, 'SIN_GRUPO')) > 1
        ORDER BY i.id_finca, i.id_infraestructura
    """)
    if not filas:
        log.info("RFC-012: ninguna área con especies de grupos de manejo incompatibles.")
        return
    log.warning("RFC-012 ALERTA: %s área(s) con especies de DISTINTO grupo_manejo tras el backfill:", len(filas))
    for f in filas:
        log.warning("  finca=%s area=%s (%s): %s", f["id_finca"], f["id_infraestructura"], f["nombre"], f["especies"])
    if ABORTAR_SI_INCOMPATIBLES:
        raise RuntimeError("RFC-012: áreas incompatibles y RFC012_ABORTAR_SI_INCOMPATIBLES=1")


# --------------------------------------------------------------------------
# UPGRADE - definiciones nuevas
# --------------------------------------------------------------------------
# Vista 1: especies agregadas con LATERAL. Un JOIN directo a la puente multiplicaría
# count(dispositivos) por el número de especies del área.
VISTA_RF20_NUEVA = """
CREATE VIEW modulo9.vw_rf20_areas_finca_resumen AS
 SELECT i.id_finca,
    i.id_infraestructura,
    i.nombre,
    i.descripcion,
    i.tipo,
    i.superficie,
    i.es_activo,
    count(d.id_dispositivo_iot) FILTER (WHERE (d.es_activo IS TRUE)) AS dispositivos_activos,
    count(d.id_dispositivo_iot) AS total_dispositivos,
    esp.ids_especies,
    esp.especies
   FROM ((modulo9.infraestructuras i
     LEFT JOIN modulo9.vw_rf21_dispositivo_area_actual d ON ((d.id_infraestructura = i.id_infraestructura)))
     LEFT JOIN LATERAL ( SELECT COALESCE(array_agg(e.id_especie ORDER BY e.nombre), ARRAY[]::integer[]) AS ids_especies,
            COALESCE(array_agg((e.nombre)::text ORDER BY e.nombre), ARRAY[]::text[]) AS especies
           FROM (modulo9.infraestructuras_especies ie
             JOIN modulo9.especies e ON ((e.id_especie = ie.id_especie)))
          WHERE (ie.id_infraestructura = i.id_infraestructura)) esp ON (true))
  GROUP BY i.id_finca, i.id_infraestructura, i.nombre, i.descripcion, i.tipo, i.superficie, i.es_activo, esp.ids_especies, esp.especies;
"""

VISTA_RF25_NUEVA = """
CREATE VIEW modulo9.vw_rf25_contexto_usuario AS
 SELECT u.id_usuario,
    concat_ws(' '::text, u.nombre, u.apellidos) AS nombre_completo,
    r.id_rol,
    r.nombre_rol,
    f.id_finca,
    f.nombre AS finca_activa,
    (f.ubicacion ->> 'departamento'::text) AS departamento,
    f.es_activo AS finca_activa_estado,
    especies.especies_configuradas AS especies_en_finca
   FROM (((modulo1.usuarios u
     JOIN modulo1.roles r ON ((r.id_rol = u.id_rol)))
     LEFT JOIN (modulo9.usuarios_fincas uf
     JOIN modulo9.fincas f ON (((f.id_finca = uf.id_finca) AND (f.es_activo IS TRUE)))) ON (((uf.id_usuario = u.id_usuario) AND (uf.es_activo IS TRUE))))
     LEFT JOIN LATERAL ( SELECT COALESCE(array_agg(DISTINCT (e.nombre)::text ORDER BY (e.nombre)::text), ARRAY[]::text[]) AS especies_configuradas
           FROM (( SELECT ie.id_especie
                   FROM (modulo9.infraestructuras i
                     JOIN modulo9.infraestructuras_especies ie ON ((ie.id_infraestructura = i.id_infraestructura)))
                  WHERE ((i.id_finca = f.id_finca) AND (i.es_activo IS TRUE))
                UNION
                 SELECT a.id_especie
                   FROM ((modulo2.activos_biologicos a
                     JOIN modulo9.infraestructuras i ON ((i.id_infraestructura = a.id_infraestructura)))
                     JOIN modulo2.estados_activos_biologicos ea ON ((ea.id_estado_activo_biologico = a.id_estado)))
                  WHERE ((i.id_finca = f.id_finca) AND (i.es_activo IS TRUE) AND ((ea.nombre)::text <> ALL (ARRAY['INACTIVO'::text, 'CERRADO'::text, 'BAJA'::text])))) en_finca
             JOIN modulo9.especies e ON (((e.id_especie = en_finca.id_especie) AND (e.es_activo IS TRUE))))) especies ON (true));
"""

VISTA_RF15_NUEVA = """
CREATE VIEW modulo9.vw_rf15_dependencias_especie AS
 SELECT e.id_especie,
    e.nombre,
    count(DISTINCT ua.id_umbral_ambiental) FILTER (WHERE (ua.es_activo IS TRUE)) AS umbrales_activos,
    count(DISTINCT cb.id_ciclo_biologico) FILTER (WHERE (cb.es_activo IS TRUE)) AS ciclos_activos,
    count(DISTINCT ep.id_especies_patologias) AS patologias_asociadas,
    ( SELECT count(*) AS count
           FROM (modulo9.infraestructuras_especies ie
             JOIN modulo9.infraestructuras i ON ((i.id_infraestructura = ie.id_infraestructura)))
          WHERE ((ie.id_especie = e.id_especie) AND (i.es_activo IS TRUE))) AS areas_activas_asignadas,
    ( SELECT count(*) AS count
           FROM (modulo2.activos_biologicos a
             JOIN modulo2.estados_activos_biologicos ea ON ((ea.id_estado_activo_biologico = a.id_estado)))
          WHERE ((a.id_especie = e.id_especie) AND (a.id_infraestructura IS NOT NULL) AND ((ea.nombre)::text <> ALL (ARRAY['INACTIVO'::text, 'CERRADO'::text, 'BAJA'::text])))) AS activos_biologicos_alojados
   FROM (((modulo9.especies e
     LEFT JOIN modulo9.umbrales_ambientales ua ON ((ua.id_especie = e.id_especie)))
     LEFT JOIN modulo9.ciclos_biologicos cb ON ((cb.id_especie = e.id_especie)))
     LEFT JOIN modulo9.especies_patologias ep ON ((ep.id_especie = e.id_especie)))
  GROUP BY e.id_especie, e.nombre;
"""

VISTAS_NUEVAS = {
    "vw_rf20_areas_finca_resumen": VISTA_RF20_NUEVA,
    "vw_rf25_contexto_usuario": VISTA_RF25_NUEVA,
    "vw_rf15_dependencias_especie": VISTA_RF15_NUEVA,
}

FN_SERIALES_NUEVA = """
CREATE OR REPLACE FUNCTION modulo9.fn_seriales_gateway_edge_por_especie(p_id_especie integer)
 RETURNS TABLE(serial character varying)
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'modulo9'
AS $function$
            WITH areas_de_la_especie AS (
                SELECT i.id_infraestructura
                FROM modulo9.infraestructuras_especies ie
                JOIN modulo9.infraestructuras i
                  ON i.id_infraestructura = ie.id_infraestructura
                WHERE ie.id_especie = p_id_especie
                  AND i.es_activo
                UNION
                SELECT i.id_infraestructura
                FROM modulo2.activos_biologicos a
                JOIN modulo2.estados_activos_biologicos ea
                  ON ea.id_estado_activo_biologico = a.id_estado
                JOIN modulo9.infraestructuras i
                  ON i.id_infraestructura = a.id_infraestructura
                 AND i.es_activo
                WHERE a.id_especie = p_id_especie
                  AND ea.nombre::text <> ALL (ARRAY['INACTIVO', 'CERRADO', 'BAJA'])
            )
            SELECT DISTINCT g.serial
            FROM areas_de_la_especie ae
            JOIN modulo9.dispositivos_iot d
              ON d.id_infraestructura = ae.id_infraestructura
             AND d.es_activo
            JOIN modulo9.dispositivos_iot g
              ON g.id_dispositivo_iot = COALESCE(d.id_dispositivo_gateway, d.id_dispositivo_iot)
             AND g.es_activo
            JOIN modulo9.tipos_dispositivo_iot t
              ON t.id_tipo_dispositivo = g.id_tipo_dispositivo
             AND t.nombre = 'GATEWAY_EDGE'
            ORDER BY g.serial;
        $function$
"""

FN_GATEWAYS_NUEVA = """
CREATE OR REPLACE FUNCTION modulo3.fn_gateways_edge_por_regla_alerta(p_id_regla_alertas integer)
 RETURNS TABLE(id_dispositivo_iot integer, serial character varying)
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'modulo3', 'modulo9'
AS $function$
            WITH regla AS (
                SELECT r.id_finca, r.id_especie
                FROM modulo3.reglas_alertas r
                WHERE r.id_regla_alertas = p_id_regla_alertas
            ),
            areas_de_la_regla AS (
                SELECT i.id_infraestructura
                FROM regla r
                JOIN modulo9.infraestructuras i
                  ON i.es_activo
                 AND (r.id_finca IS NULL OR i.id_finca = r.id_finca)
                WHERE r.id_especie IS NULL
                   OR EXISTS (
                        SELECT 1
                        FROM modulo9.infraestructuras_especies ie
                        WHERE ie.id_infraestructura = i.id_infraestructura
                          AND ie.id_especie = r.id_especie
                   )
                   OR EXISTS (
                        SELECT 1
                        FROM modulo2.activos_biologicos a
                        JOIN modulo2.estados_activos_biologicos ea
                          ON ea.id_estado_activo_biologico = a.id_estado
                        WHERE a.id_infraestructura = i.id_infraestructura
                          AND a.id_especie = r.id_especie
                          AND ea.nombre::text <> ALL (ARRAY['INACTIVO', 'CERRADO', 'BAJA'])
                   )
            )
            SELECT DISTINCT g.id_dispositivo_iot, g.serial
            FROM areas_de_la_regla ar
            JOIN modulo9.dispositivos_iot d
              ON d.id_infraestructura = ar.id_infraestructura
             AND d.es_activo
            JOIN modulo9.dispositivos_iot g
              ON g.id_dispositivo_iot = COALESCE(d.id_dispositivo_gateway, d.id_dispositivo_iot)
             AND g.es_activo
            JOIN modulo9.tipos_dispositivo_iot t
              ON t.id_tipo_dispositivo = g.id_tipo_dispositivo
             AND t.nombre = 'GATEWAY_EDGE'
            ORDER BY g.serial;
        $function$
"""

# ---------------------------------------------------------------------------
# fn_ingesta_telemetria - DECISIÓN DE UMBRAL (RFC-012)
# Con N especies en el área no existe "el" umbral: se usa el MÁS RESTRICTIVO, es decir
# el intervalo más estrecho = MAX(valor_min) y MIN(valor_max) sobre los umbrales ACTIVOS
# de las especies del área para esa variable.
#  - Una especie sin umbral activo para la variable no restringe (se ignora). Si ninguna
#    lo tiene, ambos quedan NULL y no se evalúa FUERA_DE_RANGO (igual que antes).
#  - Con 1 especie el resultado es idéntico al comportamiento previo.
#  - Si los intervalos no se intersectan (min > max) todo valor sale FUERA_DE_RANGO:
#    es deliberado, ninguna lectura satisface a todas las especies; coincide con la
#    alerta de incompatibilidad del backfill.
#  - "Especies del área" = filas de la puente (asignación formal). Que las especies de
#    activos vivos estén en la puente debe garantizarlo una regla/trigger aparte.
# Se mantiene el mensaje v_mensaje (contrato con QA) y se cambia el payload de
# ERROR_UNIDAD: 'id_especie' -> 'ids_especies' (array).
# El nuevo texto se deriva del ORIGINAL con parches que fallan si no aplican 1 vez.
# ---------------------------------------------------------------------------
_NUEVO_BLOQUE_4 = """SELECT COALESCE(array_agg(ie.id_especie ORDER BY ie.id_especie), ARRAY[]::INTEGER[])
            INTO v_ids_especies
            FROM modulo9.sensores s
            JOIN modulo9.dispositivos_iot d ON s.id_dispositivo_iot = d.id_dispositivo_iot
            JOIN modulo9.infraestructuras_especies ie ON ie.id_infraestructura = d.id_infraestructura
            WHERE s.id_sensores = p_id_sensor;

            -- 4.2. Unidad y rango físico (independientes de la especie) + umbral MÁS RESTRICTIVO
            -- entre todas las especies del área (RFC-012): MAX(valor_min) / MIN(valor_max).
            SELECT
                va.unidad,
                ua_r.valor_min,
                ua_r.valor_max,
                va.valor_fisico_min,
                va.valor_fisico_max
            INTO
                v_unidad_esperada,
                v_umbral_min,
                v_umbral_max,
                v_rango_fisico_min,
                v_rango_fisico_max
            FROM modulo9.variables_ambientales va
            LEFT JOIN LATERAL (
                SELECT MAX(ua.valor_min) AS valor_min, MIN(ua.valor_max) AS valor_max
                FROM modulo9.umbrales_ambientales ua
                WHERE ua.id_variable_ambiental = va.id_variable_ambiental
                  AND ua.id_especie = ANY (v_ids_especies)
                  AND ua.es_activo = TRUE
            ) ua_r ON TRUE
            WHERE va.id_variable_ambiental = p_id_variable AND va.es_activo = TRUE;"""


def _fn_ingesta_nueva() -> str:
    s = FN_INGESTA_ORIGINAL
    s = _patch(s, r"v_id_especie\s+INTEGER;", "v_ids_especies         INTEGER[];  -- RFC-012: especies del área")
    s = _patch(
        s,
        r"SELECT\s+inf\.id_especie\s+INTO\s+v_id_especie.*?AND\s+va\.es_activo\s*=\s*TRUE;",
        _NUEVO_BLOQUE_4,
        flags=re.DOTALL,
    )
    s = _patch(s, r"'id_especie',\s*v_id_especie", "'ids_especies', to_jsonb(v_ids_especies)")
    if re.search(r"\bv_id_especie\b|inf\.id_especie", s):
        raise RuntimeError("fn_ingesta_telemetria aún referencia id_especie")
    return s


# --------------------------------------------------------------------------
# UPGRADE
# --------------------------------------------------------------------------
def upgrade() -> None:
    _exigir_transaccion()
    # Congela escrituras concurrentes durante el backfill (lecturas siguen).
    _sql("LOCK TABLE modulo9.infraestructuras, modulo2.activos_biologicos IN SHARE ROW EXCLUSIVE MODE")
    _advertir_dependencias_ocultas()

    # FORCE RLS aplica también al dueño: sin contexto de usuario el backfill leería 0 filas
    # SIN error. Se desactiva solo dentro de esta transacción y se re-verifica al final.
    _forzar_rls(False)

    _crear_tabla_puente()
    _backfill()
    _verificar_backfill()
    _alertar_incompatibles()

    # Vistas: snapshot (owner, opciones, comentario, ACL) -> DROP explícito (no CREATE OR REPLACE,
    # que no permite quitar id_especie) -> DROP COLUMN -> CREATE -> restaurar.
    # DROP sin CASCADE: si alguna otra vista depende de estas, falla ruidosamente.
    snaps = {v: _snapshot_vista(f"modulo9.{v}") for v in VISTAS}
    for v in VISTAS:
        _sql(f"DROP VIEW modulo9.{v}")

    _sql("ALTER TABLE modulo9.infraestructuras DROP COLUMN id_especie, DROP COLUMN capacidad_maxima")

    for v, ddl in VISTAS_NUEVAS.items():
        fq = f"modulo9.{v}"
        _sql(ddl)
        com = snaps[v]["comentario"] or ""
        _restaurar_vista(fq, snaps[v], com if MARCA_RFC in com else com + MARCA_RFC)

    # Funciones: misma firma y tipo de retorno -> CREATE OR REPLACE conserva owner y ACL.
    _sql(FN_SERIALES_NUEVA)
    _sql(FN_GATEWAYS_NUEVA)
    _sql(_fn_ingesta_nueva())

    # Auditoría DML (convención del repo) se crea DESPUÉS del backfill para no auditar la carga masiva.
    _sql(f"""
        CREATE TRIGGER trg_auditoria
            AFTER INSERT OR DELETE OR UPDATE ON {PUENTE}
            FOR EACH ROW EXECUTE FUNCTION auditoria.fn_auditoria_dml()
    """)

    _forzar_rls(True, TABLAS_FORCE_RLS + (PUENTE,))
    _verificar_force(TABLAS_FORCE_RLS + (PUENTE,))


# --------------------------------------------------------------------------
# DOWNGRADE
# --------------------------------------------------------------------------
def _alertar_perdida_downgrade() -> None:
    filas = _fetch(f"""
        SELECT i.id_infraestructura, i.nombre, count(*) AS n,
               string_agg(e.nombre, ', ' ORDER BY ie.fecha_creacion, ie.id_infraestructura_especie) AS especies
        FROM {PUENTE} ie
        JOIN modulo9.infraestructuras i ON i.id_infraestructura = ie.id_infraestructura
        JOIN modulo9.especies e ON e.id_especie = ie.id_especie
        GROUP BY i.id_infraestructura, i.nombre HAVING count(*) > 1
        ORDER BY i.id_infraestructura
    """)
    for f in filas:
        log.warning("RFC-012 DOWNGRADE: area=%s (%s) tenía %s especies; se conserva la primera -> [%s]",
                    f["id_infraestructura"], f["nombre"], f["n"], f["especies"])


def downgrade() -> None:
    _exigir_transaccion()
    _sql(f"LOCK TABLE modulo9.infraestructuras, {PUENTE} IN SHARE ROW EXCLUSIVE MODE")
    tablas = ("modulo9.infraestructuras", PUENTE)
    _forzar_rls(False, tablas)

    # 1) Quitar las vistas nuevas (dependen de la puente), guardando su metadata actual.
    snaps = {v: _snapshot_vista(f"modulo9.{v}") for v in VISTAS}
    for v in VISTAS:
        _sql(f"DROP VIEW modulo9.{v}")

    # 2) Recrear columnas. capacidad_maxima es un dato DERIVADO que se eliminó a propósito:
    #    vuelve en NULL (recalculable como superficie x densidad de la especie principal).
    _sql("ALTER TABLE modulo9.infraestructuras ADD COLUMN id_especie integer, ADD COLUMN capacidad_maxima integer")

    # 3) Backfill inverso: especie principal = la primera asociada al área
    #    (fecha_creacion, luego PK). En áreas migradas coincide con la asignación original.
    _alertar_perdida_downgrade()
    _sql(f"""
        UPDATE modulo9.infraestructuras i
        SET id_especie = x.id_especie
        FROM (
            SELECT DISTINCT ON (ie.id_infraestructura) ie.id_infraestructura, ie.id_especie
            FROM {PUENTE} ie
            ORDER BY ie.id_infraestructura, ie.fecha_creacion, ie.id_infraestructura_especie
        ) x
        WHERE x.id_infraestructura = i.id_infraestructura
    """)
    # FK después del backfill (misma definición que el original).
    _sql("""
        ALTER TABLE modulo9.infraestructuras
            ADD CONSTRAINT infraestructuras_id_especie_fkey FOREIGN KEY (id_especie)
            REFERENCES modulo9.especies (id_especie) MATCH SIMPLE
            ON UPDATE NO ACTION ON DELETE NO ACTION
    """)
    sin_principal = _fetch(f"""
        SELECT count(*) AS n FROM modulo9.infraestructuras i
        WHERE i.id_especie IS NULL AND EXISTS (SELECT 1 FROM {PUENTE} ie WHERE ie.id_infraestructura = i.id_infraestructura)
    """)[0]["n"]
    if sin_principal:
        raise RuntimeError(f"Backfill inverso incompleto: {sin_principal} áreas sin especie principal")

    # 4) Restaurar vistas originales (DROP ya hecho) con su metadata, sin la marca RFC-012.
    for v, ddl in VISTAS_ORIGINALES.items():
        _sql(ddl)
        com = (snaps[v]["comentario"] or "").replace(MARCA_RFC, "")
        _restaurar_vista(f"modulo9.{v}", snaps[v], com or None)

    # 5) Restaurar funciones originales (antes de eliminar la puente).
    _sql(FN_SERIALES_ORIGINAL)
    _sql(FN_GATEWAYS_ORIGINAL)
    _sql(FN_INGESTA_ORIGINAL)

    # 6) Eliminar la tabla N:M (arrastra índices, políticas, trigger y constraints).
    _sql(f"DROP TABLE {PUENTE}")

    _forzar_rls(True, ("modulo9.infraestructuras",))
    _verificar_force(("modulo9.infraestructuras", "modulo2.activos_biologicos"))


# ==========================================================================
# CÓDIGO ORIGINAL (fuente: CSV). No editar: es lo que restaura el downgrade.
# ==========================================================================
VISTAS_ORIGINALES = {
    "vw_rf20_areas_finca_resumen": """
CREATE VIEW modulo9.vw_rf20_areas_finca_resumen AS
 SELECT i.id_finca,
    i.id_infraestructura,
    i.nombre,
    i.descripcion,
    i.tipo,
    i.superficie,
    i.es_activo,
    count(d.id_dispositivo_iot) FILTER (WHERE (d.es_activo IS TRUE)) AS dispositivos_activos,
    count(d.id_dispositivo_iot) AS total_dispositivos,
    i.id_especie,
    e.nombre AS especie
   FROM ((modulo9.infraestructuras i
     LEFT JOIN modulo9.vw_rf21_dispositivo_area_actual d ON ((d.id_infraestructura = i.id_infraestructura)))
     LEFT JOIN modulo9.especies e ON ((e.id_especie = i.id_especie)))
  GROUP BY i.id_finca, i.id_infraestructura, i.nombre, i.descripcion, i.tipo, i.superficie, i.es_activo, i.id_especie, e.nombre;
""",
    "vw_rf25_contexto_usuario": """
CREATE VIEW modulo9.vw_rf25_contexto_usuario AS
 SELECT u.id_usuario,
    concat_ws(' '::text, u.nombre, u.apellidos) AS nombre_completo,
    r.id_rol,
    r.nombre_rol,
    f.id_finca,
    f.nombre AS finca_activa,
    (f.ubicacion ->> 'departamento'::text) AS departamento,
    f.es_activo AS finca_activa_estado,
    especies.especies_configuradas AS especies_en_finca
   FROM (((modulo1.usuarios u
     JOIN modulo1.roles r ON ((r.id_rol = u.id_rol)))
     LEFT JOIN (modulo9.usuarios_fincas uf
     JOIN modulo9.fincas f ON (((f.id_finca = uf.id_finca) AND (f.es_activo IS TRUE)))) ON (((uf.id_usuario = u.id_usuario) AND (uf.es_activo IS TRUE))))
     LEFT JOIN LATERAL ( SELECT COALESCE(array_agg(DISTINCT (e.nombre)::text ORDER BY (e.nombre)::text), ARRAY[]::text[]) AS especies_configuradas
           FROM (( SELECT i.id_especie
                   FROM modulo9.infraestructuras i
                  WHERE ((i.id_finca = f.id_finca) AND (i.es_activo IS TRUE))
                UNION
                 SELECT a.id_especie
                   FROM ((modulo2.activos_biologicos a
                     JOIN modulo9.infraestructuras i ON ((i.id_infraestructura = a.id_infraestructura)))
                     JOIN modulo2.estados_activos_biologicos ea ON ((ea.id_estado_activo_biologico = a.id_estado)))
                  WHERE ((i.id_finca = f.id_finca) AND (i.es_activo IS TRUE) AND ((ea.nombre)::text <> ALL (ARRAY['INACTIVO'::text, 'CERRADO'::text, 'BAJA'::text])))) en_finca
             JOIN modulo9.especies e ON (((e.id_especie = en_finca.id_especie) AND (e.es_activo IS TRUE))))) especies ON (true));
""",
    "vw_rf15_dependencias_especie": """
CREATE VIEW modulo9.vw_rf15_dependencias_especie AS
 SELECT e.id_especie,
    e.nombre,
    count(DISTINCT ua.id_umbral_ambiental) FILTER (WHERE (ua.es_activo IS TRUE)) AS umbrales_activos,
    count(DISTINCT cb.id_ciclo_biologico) FILTER (WHERE (cb.es_activo IS TRUE)) AS ciclos_activos,
    count(DISTINCT ep.id_especies_patologias) AS patologias_asociadas,
    ( SELECT count(*) AS count
           FROM modulo9.infraestructuras i
          WHERE ((i.id_especie = e.id_especie) AND (i.es_activo IS TRUE))) AS areas_activas_asignadas,
    ( SELECT count(*) AS count
           FROM (modulo2.activos_biologicos a
             JOIN modulo2.estados_activos_biologicos ea ON ((ea.id_estado_activo_biologico = a.id_estado)))
          WHERE ((a.id_especie = e.id_especie) AND (a.id_infraestructura IS NOT NULL) AND ((ea.nombre)::text <> ALL (ARRAY['INACTIVO'::text, 'CERRADO'::text, 'BAJA'::text])))) AS activos_biologicos_alojados
   FROM (((modulo9.especies e
     LEFT JOIN modulo9.umbrales_ambientales ua ON ((ua.id_especie = e.id_especie)))
     LEFT JOIN modulo9.ciclos_biologicos cb ON ((cb.id_especie = e.id_especie)))
     LEFT JOIN modulo9.especies_patologias ep ON ((ep.id_especie = e.id_especie)))
  GROUP BY e.id_especie, e.nombre;
""",
}

FN_SERIALES_ORIGINAL = """
CREATE OR REPLACE FUNCTION modulo9.fn_seriales_gateway_edge_por_especie(p_id_especie integer)
 RETURNS TABLE(serial character varying)
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'modulo9'
AS $function$
            WITH areas_de_la_especie AS (
                SELECT i.id_infraestructura
                FROM modulo9.infraestructuras i
                WHERE i.id_especie = p_id_especie
                  AND i.es_activo
                UNION
                SELECT i.id_infraestructura
                FROM modulo2.activos_biologicos a
                JOIN modulo2.estados_activos_biologicos ea
                  ON ea.id_estado_activo_biologico = a.id_estado
                JOIN modulo9.infraestructuras i
                  ON i.id_infraestructura = a.id_infraestructura
                 AND i.es_activo
                WHERE a.id_especie = p_id_especie
                  AND ea.nombre::text <> ALL (ARRAY['INACTIVO', 'CERRADO', 'BAJA'])
            )
            SELECT DISTINCT g.serial
            FROM areas_de_la_especie ae
            JOIN modulo9.dispositivos_iot d
              ON d.id_infraestructura = ae.id_infraestructura
             AND d.es_activo
            JOIN modulo9.dispositivos_iot g
              ON g.id_dispositivo_iot = COALESCE(d.id_dispositivo_gateway, d.id_dispositivo_iot)
             AND g.es_activo
            JOIN modulo9.tipos_dispositivo_iot t
              ON t.id_tipo_dispositivo = g.id_tipo_dispositivo
             AND t.nombre = 'GATEWAY_EDGE'
            ORDER BY g.serial;
        $function$
"""

FN_GATEWAYS_ORIGINAL = """
CREATE OR REPLACE FUNCTION modulo3.fn_gateways_edge_por_regla_alerta(p_id_regla_alertas integer)
 RETURNS TABLE(id_dispositivo_iot integer, serial character varying)
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'modulo3', 'modulo9'
AS $function$
            WITH regla AS (
                SELECT r.id_finca, r.id_especie
                FROM modulo3.reglas_alertas r
                WHERE r.id_regla_alertas = p_id_regla_alertas
            ),
            areas_de_la_regla AS (
                SELECT i.id_infraestructura
                FROM regla r
                JOIN modulo9.infraestructuras i
                  ON i.es_activo
                 AND (r.id_finca IS NULL OR i.id_finca = r.id_finca)
                WHERE r.id_especie IS NULL
                   OR i.id_especie = r.id_especie
                   OR EXISTS (
                        SELECT 1
                        FROM modulo2.activos_biologicos a
                        JOIN modulo2.estados_activos_biologicos ea
                          ON ea.id_estado_activo_biologico = a.id_estado
                        WHERE a.id_infraestructura = i.id_infraestructura
                          AND a.id_especie = r.id_especie
                          AND ea.nombre::text <> ALL (ARRAY['INACTIVO', 'CERRADO', 'BAJA'])
                   )
            )
            SELECT DISTINCT g.id_dispositivo_iot, g.serial
            FROM areas_de_la_regla ar
            JOIN modulo9.dispositivos_iot d
              ON d.id_infraestructura = ar.id_infraestructura
             AND d.es_activo
            JOIN modulo9.dispositivos_iot g
              ON g.id_dispositivo_iot = COALESCE(d.id_dispositivo_gateway, d.id_dispositivo_iot)
             AND g.es_activo
            JOIN modulo9.tipos_dispositivo_iot t
              ON t.id_tipo_dispositivo = g.id_tipo_dispositivo
             AND t.nombre = 'GATEWAY_EDGE'
            ORDER BY g.serial;
        $function$
"""

FN_INGESTA_ORIGINAL = """
CREATE OR REPLACE FUNCTION modulo3.fn_ingesta_telemetria(p_id_dispositivo integer, p_id_sensor integer, p_id_variable integer, p_valor_crudo numeric, p_unidad character varying, p_timestamp_captura timestamp with time zone, p_timestamp_envio timestamp with time zone, p_origen modulo3.enum_telemetria_origen, p_categoria_variable modulo3.enum_telemetria_categoria_variable, p_tipo_dato modulo3.enum_telemetria_tipo_dato, p_valor_agregado boolean, p_ventana_agregacion integer, p_latitud numeric, p_longitud numeric, p_nivel_bateria numeric, p_calidad_rssi numeric, p_calidad_snr numeric, p_estado_conectividad boolean, p_metadatos jsonb)
 RETURNS TABLE(id_telemetria integer, estado_calidad modulo3.enum_telemetria_estado_calidad, mensaje text)
 LANGUAGE plpgsql
AS $function$
        DECLARE
            v_ts_procesamiento    TIMESTAMPTZ := NOW();
            v_valor_ajustado      NUMERIC(10,4) := NULL;
            v_calibrado           BOOLEAN := FALSE;
            v_offset              NUMERIC;
            v_ganancia            NUMERIC;
            v_cal_encontrada      BOOLEAN;
            
            -- Variables para contexto, umbrales y rangos físicos
            v_id_especie          INTEGER;
            v_umbral_min          NUMERIC(8,2);
            v_umbral_max          NUMERIC(8,2);
            v_rango_fisico_min    NUMERIC(8,2);
            v_rango_fisico_max    NUMERIC(8,2);
            v_unidad_esperada     VARCHAR(10);
            
            -- Latencia dinámica
            v_latencia_max_ms     INTEGER := 30000;  -- ← CORREGIDO: fallback de 30s según #3546
            v_latencia_ms         INTEGER;
            v_latencia_alta       BOOLEAN := FALSE;
            
            v_frecuencia_esp      INTEGER := NULL;
            v_dato_buferizado     BOOLEAN;
            v_estado              modulo3.enum_telemetria_estado_calidad := 'LECTURA_VALIDA'::modulo3.enum_telemetria_estado_calidad;
            v_mensaje             TEXT := 'OK';
            vid_telemetria        INTEGER;
            
            -- Manejo de opcionales
            v_tipo_dato           modulo3.enum_telemetria_tipo_dato;
            v_valor_agregado      BOOLEAN;
            v_ventana_agregacion  INTEGER;
            v_lat                 NUMERIC;
            v_lon                 NUMERIC;
            v_bateria             NUMERIC;
            v_rssi                NUMERIC;
            v_snr                 NUMERIC;
            v_conectividad        BOOLEAN;
            v_metadatos           JSONB;
            
            -- Variables para validación de FK en bitácora
            v_id_dispositivo_valido  INTEGER;
            v_id_sensor_valido       INTEGER;
        BEGIN
            v_tipo_dato          := COALESCE(p_tipo_dato, 'CRUDO'::modulo3.enum_telemetria_tipo_dato);
            v_valor_agregado     := COALESCE(p_valor_agregado, FALSE);
            v_ventana_agregacion := p_ventana_agregacion;
            v_lat                := p_latitud;
            v_lon                := p_longitud;
            v_bateria            := p_nivel_bateria;
            v_rssi               := p_calidad_rssi;
            v_snr                := p_calidad_snr;
            v_conectividad       := COALESCE(p_estado_conectividad, TRUE);
            v_metadatos          := COALESCE(p_metadatos, '{}'::JSONB);

            ----------------------------------------------------------------------------
            -- FASE 0: LATENCIA ALINEADA (HU #3546)
            ----------------------------------------------------------------------------
            -- 1. Intentar obtener el intervalo de transmisión específico del dispositivo (en ms)
            -- CORREGIDO: intervalo_transmision está en MINUTOS, multiplicar por 60000
            SELECT (cr.intervalo_transmision * 60000) INTO v_latencia_max_ms
            FROM modulo9.configuraciones_remotas cr
            WHERE cr.id_dispositivo_iot = p_id_dispositivo 
            AND cr.estado = 'APLICADA'
            ORDER BY cr.fecha_aplicacion DESC
            LIMIT 1;

            -- 2. Si el dispositivo no tiene configuración específica, usar la global (en ms)
            -- CORREGIDO: frecuencia_muestreo está en MINUTOS, multiplicar por 60000
            IF v_latencia_max_ms IS NULL THEN
                SELECT (cg.frecuencia_muestreo * 60000) INTO v_latencia_max_ms
                FROM modulo9.configuraciones_globales cg
                WHERE cg.es_activo = TRUE
                LIMIT 1;
            END IF;

            -- 3. Fallback de seguridad si no hay registros en M09 (30000 ms = 30 segundos según #3546)
            v_latencia_max_ms := COALESCE(v_latencia_max_ms, 30000);

            -- 4. Cálculo de latencia y evaluación
            v_latencia_ms   := EXTRACT(EPOCH FROM (v_ts_procesamiento - p_timestamp_envio))::INTEGER * 1000;
            v_latencia_alta := (v_latencia_ms > v_latencia_max_ms);

            ----------------------------------------------------------------------------
            -- FASE 1: VALIDACIÓN ESTRUCTURAL (HU #3547)
            ----------------------------------------------------------------------------
            IF p_id_dispositivo IS NULL OR p_id_sensor IS NULL OR p_id_variable IS NULL
            OR p_valor_crudo IS NULL OR p_unidad IS NULL OR p_timestamp_captura IS NULL THEN
            
                -- CORREGIDO: Validar IDs antes de INSERT para evitar FK violations
                SELECT id_dispositivo_iot INTO v_id_dispositivo_valido
                FROM modulo9.dispositivos_iot WHERE id_dispositivo_iot = p_id_dispositivo;
                
                SELECT id_sensores INTO v_id_sensor_valido
                FROM modulo9.sensores WHERE id_sensores = p_id_sensor;

                INSERT INTO modulo3.bitacora_ingest (
                    id_dispositivo_iot,
                    id_sensor,
                    estado_calidad,
                    descripcion_text,
                    payload_recibido,
                    fecha_evento,
                    fecha_captura_dato
                )
                VALUES (
                    v_id_dispositivo_valido,  -- NULL si no existe
                    v_id_sensor_valido,       -- NULL si no existe
                    'ERROR_ESTRUCTURA'::modulo3.enum_bitacora_ingest_estado_calidad,
                    'ERROR_ESTRUCTURA: Campos obligatorios faltantes.',
                    jsonb_build_object(
                        'id_dispositivo_recibido', p_id_dispositivo,
                        'id_sensor_recibido', p_id_sensor,
                        'valor_crudo', p_valor_crudo,
                        'unidad', p_unidad,
                        'id_variable', p_id_variable
                    ),
                    v_ts_procesamiento,
                    p_timestamp_captura
                );

                RETURN QUERY SELECT NULL::INTEGER, 
                                    NULL::modulo3.enum_telemetria_estado_calidad,
                                    'ERROR_ESTRUCTURA: Campos obligatorios faltantes.'::TEXT;
                RETURN;
            END IF;

            ----------------------------------------------------------------------------
            -- FASE 2: AUTENTICACIÓN (HU #3547)
            ----------------------------------------------------------------------------
            IF NOT modulo3.fn_validar_dispositivo(p_id_dispositivo, p_id_sensor) THEN
            
                -- CORREGIDO: Validar IDs antes de INSERT para evitar FK violations
                SELECT id_dispositivo_iot INTO v_id_dispositivo_valido
                FROM modulo9.dispositivos_iot WHERE id_dispositivo_iot = p_id_dispositivo;
                
                SELECT id_sensores INTO v_id_sensor_valido
                FROM modulo9.sensores WHERE id_sensores = p_id_sensor;
            
                -- CORREGIDO: Usar columnas correctas de bitacora_ingest
                INSERT INTO modulo3.bitacora_ingest (
                    id_dispositivo_iot,
                    id_sensor,
                    estado_calidad,
                    descripcion_text,
                    payload_recibido,
                    fecha_evento,
                    fecha_captura_dato
                )
                VALUES (
                    v_id_dispositivo_valido,
                    v_id_sensor_valido,
                    'ERROR_AUTENTICACION'::modulo3.enum_bitacora_ingest_estado_calidad,
                    'ERROR_AUTENTICACION: Dispositivo o sensor no activo.',
                    jsonb_build_object(
                        'id_dispositivo_recibido', p_id_dispositivo,
                        'id_sensor_recibido', p_id_sensor,
                        'valor_crudo', p_valor_crudo
                    ),
                    v_ts_procesamiento,
                    v_ts_procesamiento
                );

                RETURN QUERY SELECT NULL::INTEGER, NULL::modulo3.enum_telemetria_estado_calidad,
                                    'ERROR_AUTENTICACION: Dispositivo o sensor no activo.'::TEXT;
                RETURN;
            END IF;

            ----------------------------------------------------------------------------
            -- FASE 3: COHERENCIA TEMPORAL (HU #3547)
            ----------------------------------------------------------------------------
            -- 3.1. Validación de fecha futura
            IF p_timestamp_captura > v_ts_procesamiento THEN

                INSERT INTO modulo3.bitacora_ingest (
                    id_dispositivo_iot,
                    id_sensor,
                    estado_calidad,
                    descripcion_text,
                    payload_recibido,
                    fecha_evento,
                    fecha_captura_dato
                )
                VALUES (
                    p_id_dispositivo,
                    p_id_sensor,
                    'ERROR_TIEMPO'::modulo3.enum_bitacora_ingest_estado_calidad,
                    'ERROR_TIEMPO: timestamp_captura futuro.',
                    jsonb_build_object(
                        'valor_crudo', p_valor_crudo,
                        'timestamp_captura', p_timestamp_captura,
                        'origen', p_origen
                    ),
                    v_ts_procesamiento,
                    p_timestamp_captura
                );

                RETURN QUERY SELECT NULL::INTEGER, 
                                    NULL::modulo3.enum_telemetria_estado_calidad,
                                    'ERROR_TIEMPO: timestamp_captura futuro.'::TEXT;
                RETURN;
            END IF;

            -- 3.2. Validación de antigüedad máxima para datos buferizados (> 72 horas)
            v_dato_buferizado := (p_origen = 'BUFFER_LOCAL');

            IF v_dato_buferizado AND p_timestamp_captura < v_ts_procesamiento - INTERVAL '72 hours' THEN

                INSERT INTO modulo3.bitacora_ingest (
                    id_dispositivo_iot,
                    id_sensor,
                    estado_calidad,
                    descripcion_text,
                    payload_recibido,
                    fecha_evento,
                    fecha_captura_dato
                )
                VALUES (
                    p_id_dispositivo,
                    p_id_sensor,
                    'ERROR_TIEMPO'::modulo3.enum_bitacora_ingest_estado_calidad,
                    'ERROR_TIEMPO: Dato buffer > 72h.',
                    jsonb_build_object(
                        'valor_crudo', p_valor_crudo,
                        'timestamp_captura', p_timestamp_captura,
                        'origen', p_origen
                    ),
                    v_ts_procesamiento,
                    p_timestamp_captura
                );

                RETURN QUERY SELECT NULL::INTEGER, 
                                    NULL::modulo3.enum_telemetria_estado_calidad,
                                    'ERROR_TIEMPO: Dato buffer > 72h.'::TEXT;
                RETURN;
            END IF;

            ----------------------------------------------------------------------------
            -- FASE 4: CRUCE DE UNIDAD Y UMBRAL POR ESPECIE (HU #3544 y #3547)
            ----------------------------------------------------------------------------
            -- 4.1. Buscar la especie asociada a la infraestructura/área del sensor
            SELECT inf.id_especie INTO v_id_especie
            FROM modulo9.sensores s
            JOIN modulo9.dispositivos_iot d ON s.id_dispositivo_iot = d.id_dispositivo_iot
            JOIN modulo9.infraestructuras inf ON d.id_infraestructura = inf.id_infraestructura
            WHERE s.id_sensores = p_id_sensor;

            -- 4.2. Consultar unidad, umbral por especie específica y rango físico de M09
            -- CORREGIDO: Nombre de columnas correcto (valor_fisico_min/max en lugar de rango_fisico_min/max)
            -- CORREGIDO: Agregar filtro ua.es_activo = TRUE en LEFT JOIN
            SELECT 
                va.unidad, 
                ua.valor_min, 
                ua.valor_max,
                va.valor_fisico_min,
                va.valor_fisico_max
            INTO 
                v_unidad_esperada, 
                v_umbral_min, 
                v_umbral_max,
                v_rango_fisico_min,
                v_rango_fisico_max
            FROM modulo9.variables_ambientales va
            LEFT JOIN modulo9.umbrales_ambientales ua 
                ON ua.id_variable_ambiental = va.id_variable_ambiental 
                AND ua.id_especie = v_id_especie
                AND ua.es_activo = TRUE  -- ← CORREGIDO: solo umbrales activos
            WHERE va.id_variable_ambiental = p_id_variable AND va.es_activo = TRUE;

            -- 4.3. Validar coincidencia de unidad de medida
            IF v_unidad_esperada IS NOT NULL AND LOWER(p_unidad) <> LOWER(v_unidad_esperada) THEN

                INSERT INTO modulo3.bitacora_ingest (
                    id_dispositivo_iot,
                    id_sensor,
                    estado_calidad,
                    descripcion_text,
                    payload_recibido,
                    fecha_evento,
                    fecha_captura_dato
                )
                VALUES (
                    p_id_dispositivo,
                    p_id_sensor,
                    'ERROR_UNIDAD'::modulo3.enum_bitacora_ingest_estado_calidad,
                    'ERROR_UNIDAD: Unidad incorrecta.',
                    jsonb_build_object(
                        'unidad_recibida', p_unidad,
                        'unidad_esperada', v_unidad_esperada,
                        'id_variable', p_id_variable,
                        'id_especie', v_id_especie
                    ),
                    v_ts_procesamiento,
                    p_timestamp_captura
                );

                RETURN QUERY SELECT NULL::INTEGER, 
                                    NULL::modulo3.enum_telemetria_estado_calidad,
                                    'ERROR_UNIDAD: Unidad incorrecta.'::TEXT;
                RETURN;
            END IF;

            ----------------------------------------------------------------------------
            -- FASE 5: RANGO FÍSICO M09 (HU #3545 y #3547)
            ----------------------------------------------------------------------------
            IF v_rango_fisico_min IS NOT NULL AND v_rango_fisico_max IS NOT NULL THEN
                IF p_valor_crudo > v_rango_fisico_max OR p_valor_crudo < v_rango_fisico_min THEN

                    INSERT INTO modulo3.bitacora_ingest (
                        id_dispositivo_iot,
                        id_sensor,
                        estado_calidad,
                        descripcion_text,
                        payload_recibido,
                        fecha_evento,
                        fecha_captura_dato
                    )
                    VALUES (
                        p_id_dispositivo,
                        p_id_sensor,
                        'ERROR_SENSOR'::modulo3.enum_bitacora_ingest_estado_calidad,
                        'ERROR_SENSOR: Valor físicamente imposible.',
                        jsonb_build_object(
                            'valor_crudo', p_valor_crudo,
                            'rango_fisico_min', v_rango_fisico_min,
                            'rango_fisico_max', v_rango_fisico_max,
                            'id_variable', p_id_variable
                        ),
                        v_ts_procesamiento,
                        p_timestamp_captura
                    );

                    RETURN QUERY SELECT NULL::INTEGER, 
                                        NULL::modulo3.enum_telemetria_estado_calidad,
                                        'ERROR_SENSOR: Valor físicamente imposible.'::TEXT;
                    RETURN;
                END IF;
            END IF;

            ----------------------------------------------------------------------------
            -- FASE 6: DUPLICADOS (HU #3547)
            ----------------------------------------------------------------------------
            IF modulo3.fn_es_duplicado(p_id_sensor, p_id_variable, p_timestamp_captura, p_origen) THEN

                INSERT INTO modulo3.bitacora_ingest (
                    id_dispositivo_iot,
                    id_sensor,
                    estado_calidad,
                    descripcion_text,
                    payload_recibido,
                    fecha_evento,
                    fecha_captura_dato
                )
                VALUES (
                    p_id_dispositivo,
                    p_id_sensor,
                    'ERROR_DUPLICADO'::modulo3.enum_bitacora_ingest_estado_calidad,
                    'ERROR_DUPLICADO: Registro ya existe.',
                    jsonb_build_object(
                        'valor_crudo', p_valor_crudo,
                        'id_variable', p_id_variable,
                        'origen', p_origen
                    ),
                    v_ts_procesamiento,
                    p_timestamp_captura
                );

                RETURN QUERY SELECT NULL::INTEGER, 
                                    NULL::modulo3.enum_telemetria_estado_calidad,
                                    'ERROR_DUPLICADO: Registro ya existe.'::TEXT;
                RETURN;
            END IF;

            ----------------------------------------------------------------------------
            -- FASE 7: CALIBRACIÓN NULL Y FUERA DE RANGO OPERATIVO (HU #3544 y #3545)
            ----------------------------------------------------------------------------
            SELECT p_offset, p_ganancia, p_encontrado
            INTO v_offset, v_ganancia, v_cal_encontrada
            FROM modulo3.fn_obtener_calibracion(p_id_sensor, p_id_dispositivo);

            IF v_cal_encontrada THEN
                v_valor_ajustado := (p_valor_crudo * v_ganancia) + v_offset;
                v_calibrado      := TRUE;
            ELSE
                -- HU #3545: Sin calibración, el valor ajustado DEBE ser explícitamente NULL
                v_valor_ajustado := NULL;
                v_calibrado      := FALSE;
                v_estado         := 'ERROR_CALIBRACION'::modulo3.enum_telemetria_estado_calidad;
                v_mensaje        := 'Sin calibración – valor ajustado es nulo.';
            END IF;

            -- Evaluamos FUERA_DE_RANGO (HU #3544) en línea (Sin abortar, solo marcando estado de calidad)
            -- DECISIÓN DEV-05: Sin calibración, NO debe llegar a FUERA_DE_RANGO
            IF v_umbral_min IS NOT NULL AND v_umbral_max IS NOT NULL THEN
                
                -- Usamos el ajustado, pero si es null por falta de calibración, evaluamos el crudo
                IF COALESCE(v_valor_ajustado, p_valor_crudo) < v_umbral_min OR 
                COALESCE(v_valor_ajustado, p_valor_crudo) > v_umbral_max THEN
                
                    -- Jerarquía: Solo marcamos FUERA_DE_RANGO si venía limpio. 
                    -- Si ya era ERROR_CALIBRACION arriba, se conserva ese error primario.
                    IF v_estado = 'LECTURA_VALIDA'::modulo3.enum_telemetria_estado_calidad THEN
                        v_estado  := 'FUERA_DE_RANGO'::modulo3.enum_telemetria_estado_calidad;
                        v_mensaje := 'Valor fuera de rango operativo de la especie.';
                    END IF;
                END IF;
            END IF;

            ----------------------------------------------------------------------------
            -- FASE 8: ESTRUCTURA AGREGADO (HU #3547)
            ----------------------------------------------------------------------------
            IF v_valor_agregado AND v_ventana_agregacion IS NULL THEN

                INSERT INTO modulo3.bitacora_ingest (
                    id_dispositivo_iot,
                    id_sensor,
                    estado_calidad,
                    descripcion_text,
                    payload_recibido,
                    fecha_evento,
                    fecha_captura_dato
                )
                VALUES (
                    p_id_dispositivo,
                    p_id_sensor,
                    'ERROR_ESTRUCTURA'::modulo3.enum_bitacora_ingest_estado_calidad,
                    'ERROR_ESTRUCTURA: Agregado sin ventana.',
                    jsonb_build_object(
                        'valor_crudo', p_valor_crudo,
                        'valor_agregado', v_valor_agregado,
                        'ventana_agregacion', v_ventana_agregacion
                    ),
                    v_ts_procesamiento,
                    p_timestamp_captura
                );

                RETURN QUERY SELECT NULL::INTEGER, 
                                    NULL::modulo3.enum_telemetria_estado_calidad,
                                    'ERROR_ESTRUCTURA: Agregado sin ventana.'::TEXT;
                RETURN;
            END IF;

            ----------------------------------------------------------------------------
            -- FASE 9: PERSISTENCIA FINAL EN TELEMETRIAS
            ----------------------------------------------------------------------------
            INSERT INTO modulo3.telemetrias (
                id_sensor, 
                id_variable, 
                id_dispositivo_iot,
                valor_crudo, 
                valor_ajustado,
                timestamp_captura, 
                timestamp_envio, 
                timestamp_procesamiento,
                origen, 
                estado_calidad, 
                calibrado,
                latitud, 
                longitud, 
                metadatos,
                categoria_variable, 
                unidad_medida,
                valor_agregado, 
                ventana_agregacion_min,
                tipo_dato,
                latencia_alta, 
                frecuencia_anomala,
                posible_drift, 
                dato_buferizado,
                dato_agredado_edge, 
                latencia_procesamiento_ms,
                nivel_bateria_pct, 
                calidad_senal_rssi, 
                calidad_senal_snr,
                frecuencia_muestreo_min, 
                estado_conectividad
            )
            VALUES (
                p_id_sensor, 
                p_id_variable, 
                p_id_dispositivo,
                p_valor_crudo, 
                v_valor_ajustado,
                p_timestamp_captura, 
                p_timestamp_envio, 
                v_ts_procesamiento,
                p_origen, 
                v_estado, 
                v_calibrado,
                v_lat, 
                v_lon, 
                v_metadatos,
                p_categoria_variable, 
                p_unidad,
                v_valor_agregado, 
                v_ventana_agregacion,
                v_tipo_dato,
                v_latencia_alta, 
                FALSE, -- frecuencia_anomala
                FALSE, -- posible_drift
                v_dato_buferizado,
                (v_tipo_dato = 'EVENTO_EDGE'), -- dato_agredado_edge
                v_latencia_ms,
                v_bateria, 
                v_rssi, 
                v_snr,
                NULL, -- frecuencia_muestreo_min (fijo en nulo por ahora)
                v_conectividad
            )
            RETURNING telemetrias.id_telemetria INTO vid_telemetria;

            RETURN QUERY SELECT vid_telemetria, v_estado, v_mensaje;
        END;
        $function$
"""