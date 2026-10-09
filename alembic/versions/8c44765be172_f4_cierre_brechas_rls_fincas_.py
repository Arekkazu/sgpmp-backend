"""F4: cierre brechas RLS fincas infraestructuras y triggers

Revision ID: 8c44765be172
Revises: a7380032a23b
Create Date: 2026-10-08 01:50:37.265678


1. Quita el alcance global (Administrador) de las políticas de fincas e infraestructuras.
2. Corrige triggers para que no dejen pasar operaciones cuando el RLS les oculta filas:
   - trg_fn_fase_activo_estado_valido: Falla si el activo no es visible.
   - trg_finca_nombre_unique: Valida unicidad global ignorando RLS + Índice Único.
   - trg_finca_no_delete: Cuenta dependencias ignorando RLS.


"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8c44765be172'
down_revision: Union[str, Sequence[str], None] = 'a7380032a23b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None




def upgrade() -> None:
    # =========================================================
    # 1. POLÍTICAS: Quitar OR fn_rol_actual() = 'Administrador'
    # =========================================================
    op.execute("""
        DO $$
        DECLARE
            r RECORD;
            v_new_qual text;
            v_new_with_check text;
            v_admin_pattern1 text := ' OR (modulo1.fn_rol_actual() = ''Administrador''::text)';
            v_admin_pattern2 text := ' OR modulo1.fn_rol_actual() = ''Administrador''::text';
        BEGIN
            FOR r IN
                SELECT schemaname, tablename, policyname, qual, with_check
                FROM pg_policies
                WHERE tablename IN ('fincas', 'infraestructuras') AND schemaname = 'modulo9'
            LOOP
                -- Arreglar USING (qual)
                IF r.qual IS NOT NULL THEN
                    v_new_qual := replace(r.qual, v_admin_pattern1, '');
                    v_new_qual := replace(v_new_qual, v_admin_pattern2, '');
                    EXECUTE format('ALTER POLICY %I ON modulo9.%I USING (%s)', r.policyname, r.tablename, v_new_qual);
                END IF;

                -- Arreglar WITH CHECK
                IF r.with_check IS NOT NULL THEN
                    v_new_with_check := replace(r.with_check, v_admin_pattern1, '');
                    v_new_with_check := replace(v_new_with_check, v_admin_pattern2, '');
                    EXECUTE format('ALTER POLICY %I ON modulo9.%I WITH CHECK (%s)', r.policyname, r.tablename, v_new_with_check);
                END IF;
            END LOOP;
        END $$;
    """)

    # =========================================================
    # 2. TRIGGERS: Hacerlos SECURITY DEFINER y corregir lógica
    # =========================================================
    
    # 2.1 Fase de activo (Falla si RLS oculta el activo)
    op.execute("""
        CREATE OR REPLACE FUNCTION modulo2.trg_fn_fase_activo_estado_valido()
        RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, modulo2 AS $$
        DECLARE
            v_ultimo_estado VARCHAR(25);
        BEGIN
            SELECT e.nombre INTO v_ultimo_estado
            FROM modulo2.historicos_estados_activos h
            JOIN modulo2.estados_activos_biologicos e ON e.id_estado_activo_biologico = h.id_estado_nuevo
            WHERE h.id_activo_biologico = NEW.id_activo_biologico
            ORDER BY h.fecha_cambio DESC LIMIT 1;

            IF v_ultimo_estado IS NULL THEN
                SELECT e.nombre INTO v_ultimo_estado
                FROM modulo2.activos_biologicos a
                JOIN modulo2.estados_activos_biologicos e ON e.id_estado_activo_biologico = a.id_estado
                WHERE a.id_activo_biologico = NEW.id_activo_biologico;
            END IF;

            -- NUEVO: Si sigue NULL, es porque el RLS ocultó el activo o no existe.
            IF v_ultimo_estado IS NULL THEN
                RAISE EXCEPTION 'RLS_BLOCKED_OR_MISSING: No se puede validar la fase. El activo ID % no es visible por RLS o no existe.', NEW.id_activo_biologico
                USING ERRCODE = 'P0229';
            END IF;

            IF UPPER(v_ultimo_estado) IN ('CERRADO', 'BAJA') THEN
                RAISE EXCEPTION 'INVALID_STATE: No se puede cambiar fase en activo ID % (estado %).', NEW.id_activo_biologico, v_ultimo_estado
                USING ERRCODE = 'P0228';
            END IF;

            RETURN NEW;
        END;
        $$;
    """)

    # 2.2 Unicidad de Finca (SECURITY DEFINER + Índice Único)
    op.execute("""
        CREATE OR REPLACE FUNCTION modulo9.trg_fn_finca_nombre_unique()
        RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, modulo9 AS $$
        DECLARE
            v_count_global    INTEGER;
        BEGIN
            NEW.nombre := TRIM(NEW.nombre);
            IF NEW.nombre !~ '^[A-Za-záéíóúÁÉÍÓÚñÑüÜ\s]+$' THEN
                RAISE EXCEPTION 'INVALID_FORMAT: El nombre de la finca solo permite letras y español. Valor: "%".', NEW.nombre USING ERRCODE = 'P0118';
            END IF;

            SELECT COUNT(*) INTO v_count_global
            FROM modulo9.fincas
            WHERE LOWER(TRIM(nombre)) = LOWER(NEW.nombre) AND id_finca <> COALESCE(NEW.id_finca, -1);

            IF v_count_global > 0 THEN
                RAISE EXCEPTION 'DUPLICATE_FARM_GLOBAL: Ya existe una finca con el nombre "%".', NEW.nombre USING ERRCODE = 'P0119';
            END IF;
            RETURN NEW;
        END;
        $$;
    """)
    # El índice único es el verdadero garante a nivel de motor de BD
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_finca_nombre_global_unique ON modulo9.fincas (LOWER(TRIM(nombre)));")

    # 2.3 No Delete Finca (SECURITY DEFINER para contar dependencias reales)
    op.execute("""
        CREATE OR REPLACE FUNCTION modulo9.trg_fn_finca_no_delete()
        RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, modulo9, modulo2 AS $$
        DECLARE
            v_infra_count   INTEGER; v_iot_count INTEGER; v_activos_count INTEGER;
        BEGIN
            SELECT COUNT(*) INTO v_infra_count FROM modulo9.infraestructuras WHERE id_finca = OLD.id_finca;
            SELECT COUNT(*) INTO v_iot_count FROM modulo9.dispositivos_iot d JOIN modulo9.infraestructuras i ON d.id_infraestructura = i.id_infraestructura WHERE i.id_finca = OLD.id_finca;
            SELECT COUNT(*) INTO v_activos_count FROM modulo2.activos_biologicos ab JOIN modulo9.infraestructuras i ON ab.id_infraestructura = i.id_infraestructura WHERE i.id_finca = OLD.id_finca;

            IF v_infra_count > 0 OR v_iot_count > 0 OR v_activos_count > 0 THEN
                RAISE EXCEPTION 'FARM_HAS_DEPENDENCIES: Finca "%" no se puede borrar. Tiene % infra, % iot, % activos.', OLD.nombre, v_infra_count, v_iot_count, v_activos_count USING ERRCODE = 'P0124';
            END IF;

            RAISE EXCEPTION 'NO_PHYSICAL_DELETE: Finca "%" no se puede borrar físicamente.', OLD.nombre USING ERRCODE = 'P0124';
            RETURN NULL;
        END;
        $$;
    """)

    # =========================================================
    # 3. ESTADÍSTICAS (Para la F5)
    # =========================================================
    op.execute("ANALYZE modulo9.fincas;")
    op.execute("ANALYZE modulo9.infraestructuras;")
    op.execute("ANALYZE modulo2.activos_biologicos;")


def downgrade() -> None:
    # 1. Restaurar Políticas (Agregando de vuelta el bypass del Administrador)
    op.execute("""
        DO $$
        DECLARE
            r RECORD;
            v_admin_append text := ' OR (modulo1.fn_rol_actual() = ''Administrador''::text)';
        BEGIN
            FOR r IN
                SELECT schemaname, tablename, policyname, qual, with_check
                FROM pg_policies WHERE tablename IN ('fincas', 'infraestructuras') AND schemaname = 'modulo9'
            LOOP
                IF r.qual IS NOT NULL AND r.qual NOT LIKE '%Administrador%' THEN
                    EXECUTE format('ALTER POLICY %I ON modulo9.%I USING (%s)', r.policyname, r.tablename, r.qual || v_admin_append);
                END IF;
                IF r.with_check IS NOT NULL AND r.with_check NOT LIKE '%Administrador%' THEN
                    EXECUTE format('ALTER POLICY %I ON modulo9.%I WITH CHECK (%s)', r.policyname, r.tablename, r.with_check || v_admin_append);
                END IF;
            END LOOP;
        END $$;
    """)

    # 2. Borrar índice único
    op.execute("DROP INDEX IF EXISTS modulo9.idx_finca_nombre_global_unique;")

    # 3. Restaurar Triggers originales (Sin SECURITY DEFINER y lógica vieja)
    op.execute("""
        CREATE OR REPLACE FUNCTION modulo2.trg_fn_fase_activo_estado_valido() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE v_ultimo_estado VARCHAR(25); BEGIN
            SELECT e.nombre INTO v_ultimo_estado FROM modulo2.historicos_estados_activos h JOIN modulo2.estados_activos_biologicos e ON e.id_estado_activo_biologico = h.id_estado_nuevo WHERE h.id_activo_biologico = NEW.id_activo_biologico ORDER BY h.fecha_cambio DESC LIMIT 1;
            IF v_ultimo_estado IS NULL THEN SELECT e.nombre INTO v_ultimo_estado FROM modulo2.activos_biologicos a JOIN modulo2.estados_activos_biologicos e ON e.id_estado_activo_biologico = a.id_estado WHERE a.id_activo_biologico = NEW.id_activo_biologico; END IF;
            IF UPPER(v_ultimo_estado) IN ('CERRADO', 'BAJA') THEN RAISE EXCEPTION 'INVALID_STATE: ...', NEW.id_activo_biologico, v_ultimo_estado USING ERRCODE = 'P0228'; END IF;
            RETURN NEW; END; $$;
            
        CREATE OR REPLACE FUNCTION modulo9.trg_fn_finca_nombre_unique() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE v_count_global INTEGER; BEGIN NEW.nombre := TRIM(NEW.nombre);
            IF NEW.nombre !~ '^[A-Za-záéíóúÁÉÍÓÚñÑüÜ\s]+$' THEN RAISE EXCEPTION 'INVALID_FORMAT...', NEW.nombre USING ERRCODE = 'P0118'; END IF;
            SELECT COUNT(*) INTO v_count_global FROM modulo9.fincas WHERE LOWER(TRIM(nombre)) = LOWER(NEW.nombre) AND id_finca <> COALESCE(NEW.id_finca, -1);
            IF v_count_global > 0 THEN RAISE EXCEPTION 'DUPLICATE_FARM_GLOBAL...', NEW.nombre USING ERRCODE = 'P0119'; END IF; RETURN NEW; END; $$;

        CREATE OR REPLACE FUNCTION modulo9.trg_fn_finca_no_delete() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE v_infra_count INTEGER; v_iot_count INTEGER; v_activos_count INTEGER; BEGIN
            SELECT COUNT(*) INTO v_infra_count FROM modulo9.infraestructuras WHERE id_finca = OLD.id_finca;
            SELECT COUNT(*) INTO v_iot_count FROM modulo9.dispositivos_iot d JOIN modulo9.infraestructuras i ON d.id_infraestructura = i.id_infraestructura WHERE i.id_finca = OLD.id_finca;
            SELECT COUNT(*) INTO v_activos_count FROM modulo2.activos_biologicos ab JOIN modulo9.infraestructuras i ON ab.id_infraestructura = i.id_infraestructura WHERE i.id_finca = OLD.id_finca;
            IF v_infra_count > 0 OR v_iot_count > 0 OR v_activos_count > 0 THEN RAISE EXCEPTION 'FARM_HAS_DEPENDENCIES...', OLD.nombre, v_infra_count, v_iot_count, v_activos_count USING ERRCODE = 'P0124'; END IF;
            RAISE EXCEPTION 'NO_PHYSICAL_DELETE...', OLD.nombre USING ERRCODE = 'P0124'; RETURN NULL; END; $$;
    """)