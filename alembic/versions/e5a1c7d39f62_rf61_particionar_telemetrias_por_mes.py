# | Fecha      | Nombre     | Que se hizo                                                    |
# |------------|------------|----------------------------------------------------------------|
# | 2026-10-30 | SamuelPR21 | CARGA-FREC RF-61: particiona telemetrias por mes de captura     |
# | 2026-10-31 | Arekkazu   | PR-891 RF-61: RLS en particiones y telemetrias_registradas sin DML de la app |
"""rf61: telemetrias pasa a ser una tabla particionada por mes

Revision ID: e5a1c7d39f62
Revises: c3d8f5a27b41
Create Date: 2026-10-30

PostgreSQL no convierte una tabla en particionada: se crea una nueva, se copian las
filas y se reemplaza la anterior. Vistas, políticas, triggers, índices y permisos se
leen del catálogo antes de empezar para no copiar definiciones a mano.

Decisiones:

- Rango por `timestamp_captura`, en meses UTC. La PK pasa a ser
  (id_telemetria, timestamp_captura) porque debe incluir la llave de partición.
- Una tabla particionada no admite UNIQUE solo sobre id_telemetria, y las 5 FK que
  apuntan a esa columna lo necesitan. Se crea `telemetrias_registradas`, con solo el
  id, y las FK apuntan ahí. Un trigger de validación no servía: con RLS forzada no
  vería las lecturas de otra finca. Además, archivar una partición no rompe las FK.
- `telemetrias_fuera_de_rango` es la partición DEFAULT: un buffer con una fecha sin
  partición se guarda en lugar de perderse.
- `fn_asegurar_particiones_telemetrias()` crea los meses siguientes. La llama a
  diario `main.py`; si deja de correr, las lecturas caen en la DEFAULT, sin error.

Las particiones no heredan el RLS del padre y sí los privilegios por defecto del
esquema: se les activa RLS sin políticas, así que nadie las lee directo y por el padre
todo sigue igual. `telemetrias_registradas` solo la escribe el trigger (SECURITY
DEFINER); se le retiran los privilegios a los demás roles para que nadie registre ids
sin lectura.

El modelo ORM sigue declarando id_telemetria como PK a propósito: `db.get()` busca
por ese id y sigue siendo único, pues lo da una secuencia.

Operación: todo corre en una transacción con ACCESS EXCLUSIVE sobre telemetrias y sus
5 tablas hijas. Detener el backend antes. No retira particiones: la ventana de 24
meses se aplicará al definir el archivado en el lake.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'e5a1c7d39f62'
down_revision: Union[str, Sequence[str], None] = 'c3d8f5a27b41'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_FKS = """
    ('modulo3.alertas', 'fk_alertas_telemetria_id'),
    ('modulo3.bitacora_ingest', 'fk_bitacora_ingest_telemetria_id'),
    ('modulo3.vinculaciones_lecturas', 'fk_vinculacion_lecturas_telemetria'),
    ('modulo3.telemetria_calidad', 'telemetria_calidad_id_telemetria_fkey'),
    ('modulo6.cadenas_trazabilidad_contable', 'cadenas_trazabilidad_contable_id_telemetria_fkey')
"""

_FUNCIONES = """
CREATE FUNCTION modulo3.fn_crear_particion_telemetria(p_mes date) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog AS $funcion$
DECLARE
    v_inicio date := make_date(extract(year FROM p_mes)::int, extract(month FROM p_mes)::int, 1);
    v_fin date := (v_inicio + interval '1 month')::date;
    v_nombre text := 'telemetrias_' || to_char(v_inicio, 'YYYY_MM');
BEGIN
    IF to_regclass('modulo3.' || v_nombre) IS NOT NULL THEN
        RETURN;
    END IF;
    EXECUTE format(
        'CREATE TABLE modulo3.%I PARTITION OF modulo3.telemetrias FOR VALUES FROM (%L) TO (%L)',
        v_nombre, v_inicio::text || ' 00:00:00+00', v_fin::text || ' 00:00:00+00');
    EXECUTE format('ALTER TABLE modulo3.%I ENABLE ROW LEVEL SECURITY', v_nombre);
    EXECUTE format('ALTER TABLE modulo3.%I FORCE ROW LEVEL SECURITY', v_nombre);
END;
$funcion$;

CREATE FUNCTION modulo3.fn_asegurar_particiones_telemetrias(p_meses_adelante integer DEFAULT 6) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog AS $funcion$
DECLARE
    v_hoy date := (now() AT TIME ZONE 'UTC')::date;
BEGIN
    FOR i IN 0..p_meses_adelante LOOP
        PERFORM modulo3.fn_crear_particion_telemetria((v_hoy + make_interval(months => i))::date);
    END LOOP;
END;
$funcion$;

CREATE FUNCTION modulo3.fn_registrar_id_telemetria() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog AS $funcion$
BEGIN
    INSERT INTO modulo3.telemetrias_registradas (id_telemetria) VALUES (NEW.id_telemetria);
    RETURN NEW;
END;
$funcion$;

REVOKE ALL ON FUNCTION modulo3.fn_crear_particion_telemetria(date) FROM PUBLIC;
REVOKE ALL ON FUNCTION modulo3.fn_asegurar_particiones_telemetrias(integer) FROM PUBLIC;
"""

# @ESTRUCTURA@, @CARGA@ y @LLAVES@ distinguen upgrade de downgrade.
_RECONSTRUIR = """
DO $migracion$
DECLARE
    v_ruta text := current_setting('search_path');
    v_dueno text;
    v_comentario text;
    v_vistas text[];
    v_antes text[];
    v_despues text[];
    v_permisos text[];
    v_sentencia text;
BEGIN
    -- Con la ruta vacía el catálogo escribe todo con su esquema.
    PERFORM set_config('search_path', 'pg_catalog', true);

    SELECT relowner::regrole::text, obj_description(oid, 'pg_class')
    INTO STRICT v_dueno, v_comentario
    FROM pg_class WHERE oid = 'modulo3.telemetrias'::regclass;

    SELECT array_agg(format('CREATE OR REPLACE VIEW %s %s AS %s', c.oid::regclass,
               CASE WHEN c.reloptions IS NULL THEN '' ELSE 'WITH (' || array_to_string(c.reloptions, ', ') || ')' END,
               pg_get_viewdef(c.oid)))
    INTO v_vistas
    FROM pg_class c
    WHERE c.relkind = 'v' AND c.oid IN (
        SELECT r.ev_class FROM pg_depend d JOIN pg_rewrite r ON r.oid = d.objid
        WHERE d.classid = 'pg_rewrite'::regclass AND d.refobjid = 'modulo3.telemetrias'::regclass);

    -- Políticas de otras tablas que leen telemetrias: se quitan antes y vuelven después.
    SELECT array_agg(format('DROP POLICY %I ON %s', p.polname, p.polrelid::regclass))
    INTO v_antes
    FROM pg_policy p
    WHERE p.polrelid <> 'modulo3.telemetrias'::regclass AND p.oid IN (
        SELECT d.objid FROM pg_depend d
        WHERE d.classid = 'pg_policy'::regclass AND d.refobjid = 'modulo3.telemetrias'::regclass);

    SELECT array_agg(s) INTO v_despues FROM (
        SELECT format('CREATE POLICY %I ON %I.%I AS %s FOR %s TO %s%s%s',
                   pp.policyname, pp.schemaname, pp.tablename, pp.permissive, pp.cmd,
                   (SELECT string_agg(quote_ident(r), ', ') FROM unnest(pp.roles) r),
                   CASE WHEN pp.qual IS NULL THEN '' ELSE ' USING (' || pp.qual || ')' END,
                   CASE WHEN pp.with_check IS NULL THEN '' ELSE ' WITH CHECK (' || pp.with_check || ')' END) AS s
        FROM pg_policies pp
        WHERE (pp.schemaname = 'modulo3' AND pp.tablename = 'telemetrias')
           OR (pp.schemaname, pp.tablename, pp.policyname) IN (
               SELECT n.nspname, c.relname, p.polname
               FROM pg_policy p
               JOIN pg_class c ON c.oid = p.polrelid
               JOIN pg_namespace n ON n.oid = c.relnamespace
               JOIN pg_depend d ON d.objid = p.oid AND d.classid = 'pg_policy'::regclass
               WHERE d.refobjid = 'modulo3.telemetrias'::regclass)
        UNION ALL
        SELECT pg_get_triggerdef(oid) FROM pg_trigger
        WHERE tgrelid = 'modulo3.telemetrias'::regclass AND NOT tgisinternal
          AND tgname <> 'trg_aux_00_registrar_id_telemetria'
        UNION ALL
        SELECT pg_get_indexdef(i.indexrelid) FROM pg_index i
        WHERE i.indrelid = 'modulo3.telemetrias'::regclass
          AND NOT EXISTS (SELECT 1 FROM pg_constraint k WHERE k.conindid = i.indexrelid AND k.conrelid = i.indrelid)
        UNION ALL
        SELECT format('ALTER TABLE modulo3.telemetrias ADD CONSTRAINT %I %s', conname, pg_get_constraintdef(oid))
        FROM pg_constraint
        WHERE conrelid = 'modulo3.telemetrias'::regclass AND contype IN ('u', 'f')
    ) x;

    SELECT array_agg(format('GRANT %s ON modulo3.telemetrias TO %s', privilege_type, CASE grantee WHEN 'PUBLIC' THEN 'PUBLIC' ELSE quote_ident(grantee) END))
    INTO v_permisos
    FROM information_schema.role_table_grants
    WHERE table_schema = 'modulo3' AND table_name = 'telemetrias' AND grantee <> v_dueno;

    FOREACH v_sentencia IN ARRAY coalesce(v_antes, '{}') LOOP EXECUTE v_sentencia; END LOOP;
    FOR v_sentencia IN SELECT 'ALTER TABLE ' || t || ' DROP CONSTRAINT ' || c FROM (VALUES @FKS@) f(t, c) LOOP
        EXECUTE v_sentencia;
    END LOOP;

    ALTER TABLE modulo3.telemetrias RENAME TO telemetrias_previa;
    CREATE TABLE modulo3.telemetrias (
        LIKE modulo3.telemetrias_previa INCLUDING DEFAULTS INCLUDING CONSTRAINTS INCLUDING COMMENTS
    ) @ESTRUCTURA@;
    EXECUTE format('ALTER TABLE modulo3.telemetrias OWNER TO %s', v_dueno);
    IF v_comentario IS NOT NULL THEN
        EXECUTE format('COMMENT ON TABLE modulo3.telemetrias IS %L', v_comentario);
    END IF;

    @CARGA@

    FOREACH v_sentencia IN ARRAY coalesce(v_vistas, '{}') LOOP EXECUTE v_sentencia; END LOOP;
    ALTER SEQUENCE modulo3.telemetrias_id_telemetria_seq OWNED BY modulo3.telemetrias.id_telemetria;
    DROP TABLE modulo3.telemetrias_previa;

    @PK@
    FOREACH v_sentencia IN ARRAY coalesce(v_despues, '{}') LOOP EXECUTE v_sentencia; END LOOP;
    FOREACH v_sentencia IN ARRAY coalesce(v_permisos, '{}') LOOP EXECUTE v_sentencia; END LOOP;
    ALTER TABLE modulo3.telemetrias ENABLE ROW LEVEL SECURITY;
    ALTER TABLE modulo3.telemetrias FORCE ROW LEVEL SECURITY;

    @LLAVES@
    ANALYZE modulo3.telemetrias;
    PERFORM set_config('search_path', v_ruta, true);
END
$migracion$
"""

_CARGA_PARTICIONADA = """
    CREATE TABLE modulo3.telemetrias_registradas (id_telemetria integer PRIMARY KEY);
    EXECUTE format('ALTER TABLE modulo3.telemetrias_registradas OWNER TO %s', v_dueno);
    FOR v_sentencia IN
        SELECT DISTINCT format('REVOKE ALL ON modulo3.telemetrias_registradas FROM %s',
                               CASE a.grantee WHEN 0 THEN 'PUBLIC' ELSE a.grantee::regrole::text END)
        FROM pg_class c, aclexplode(c.relacl) a
        WHERE c.oid = 'modulo3.telemetrias_registradas'::regclass AND a.grantee <> c.relowner
    LOOP
        EXECUTE v_sentencia;
    END LOOP;
    INSERT INTO modulo3.telemetrias_registradas SELECT id_telemetria FROM modulo3.telemetrias_previa;

    EXECUTE format('ALTER FUNCTION modulo3.fn_crear_particion_telemetria(date) OWNER TO %s', v_dueno);
    EXECUTE format('ALTER FUNCTION modulo3.fn_asegurar_particiones_telemetrias(integer) OWNER TO %s', v_dueno);
    EXECUTE format('ALTER FUNCTION modulo3.fn_registrar_id_telemetria() OWNER TO %s', v_dueno);
    PERFORM modulo3.fn_crear_particion_telemetria(m::date)
    FROM (SELECT DISTINCT date_trunc('month', timestamp_captura AT TIME ZONE 'UTC') AS m
          FROM modulo3.telemetrias_previa) meses;
    PERFORM modulo3.fn_asegurar_particiones_telemetrias();
    CREATE TABLE modulo3.telemetrias_fuera_de_rango PARTITION OF modulo3.telemetrias DEFAULT;
    EXECUTE format('ALTER TABLE modulo3.telemetrias_fuera_de_rango OWNER TO %s', v_dueno);
    ALTER TABLE modulo3.telemetrias_fuera_de_rango ENABLE ROW LEVEL SECURITY;
    ALTER TABLE modulo3.telemetrias_fuera_de_rango FORCE ROW LEVEL SECURITY;

    INSERT INTO modulo3.telemetrias SELECT * FROM modulo3.telemetrias_previa;
"""

_LLAVES_PARTICIONADA = """
    CREATE TRIGGER trg_aux_00_registrar_id_telemetria BEFORE INSERT ON modulo3.telemetrias
        FOR EACH ROW EXECUTE FUNCTION modulo3.fn_registrar_id_telemetria();
    FOR v_sentencia IN
        SELECT format('ALTER TABLE %s ADD CONSTRAINT %s FOREIGN KEY (id_telemetria) '
                      'REFERENCES modulo3.telemetrias_registradas (id_telemetria)', t, c)
        FROM (VALUES @FKS@) f(t, c)
    LOOP
        EXECUTE v_sentencia;
    END LOOP;
    SELECT array_agg(DISTINCT format('GRANT EXECUTE ON FUNCTION modulo3.fn_asegurar_particiones_telemetrias(integer) TO %s', CASE grantee WHEN 'PUBLIC' THEN 'PUBLIC' ELSE quote_ident(grantee) END))
    INTO v_permisos
    FROM information_schema.role_table_grants
    WHERE table_schema = 'modulo3' AND table_name = 'telemetrias' AND privilege_type = 'INSERT'
      AND grantee <> v_dueno;
    FOREACH v_sentencia IN ARRAY coalesce(v_permisos, '{}') LOOP EXECUTE v_sentencia; END LOOP;
"""

_LLAVES_SIMPLE = """
    FOR v_sentencia IN
        SELECT format('ALTER TABLE %s ADD CONSTRAINT %s FOREIGN KEY (id_telemetria) '
                      'REFERENCES modulo3.telemetrias (id_telemetria)', t, c)
        FROM (VALUES @FKS@) f(t, c)
    LOOP
        EXECUTE v_sentencia;
    END LOOP;
    DROP TABLE modulo3.telemetrias_registradas;
    DROP FUNCTION modulo3.fn_registrar_id_telemetria();
    DROP FUNCTION modulo3.fn_asegurar_particiones_telemetrias(integer);
    DROP FUNCTION modulo3.fn_crear_particion_telemetria(date);
"""


def _sql(estructura: str, carga: str, pk: str, llaves: str) -> str:
    return (
        _RECONSTRUIR.replace('@ESTRUCTURA@', estructura)
        .replace('@CARGA@', carga)
        .replace('@PK@', pk)
        .replace('@LLAVES@', llaves)
        .replace('@FKS@', _FKS)
    )


def upgrade() -> None:
    op.execute(_FUNCIONES)
    op.execute(_sql(
        'PARTITION BY RANGE (timestamp_captura)',
        _CARGA_PARTICIONADA,
        'ALTER TABLE modulo3.telemetrias ADD CONSTRAINT telemetrias_pkey '
        'PRIMARY KEY (id_telemetria, timestamp_captura);',
        _LLAVES_PARTICIONADA,
    ))


def downgrade() -> None:
    op.execute('DROP TRIGGER trg_aux_00_registrar_id_telemetria ON modulo3.telemetrias')
    op.execute(_sql(
        '',
        'INSERT INTO modulo3.telemetrias SELECT * FROM modulo3.telemetrias_previa;',
        'ALTER TABLE modulo3.telemetrias ADD CONSTRAINT telemetrias_pkey PRIMARY KEY (id_telemetria);',
        _LLAVES_SIMPLE,
    ))
