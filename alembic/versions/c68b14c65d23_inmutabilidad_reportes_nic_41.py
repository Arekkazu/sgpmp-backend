# | Fecha      | Nombre | Que se hizo |
# |------------|--------|-------------|
# | 2026-11-09 | SamuelPR21    | CA-7: provision_nic41 inmutable salvo GENERADO→SUPERADO y entrega a M06; sin DELETE para la app (INC-M05-262-G35) |
# | 2026-11-10 | Arekkazu | Lote M05/M06: RF-79 CA-7: triggers con la convención de nombres y SQLSTATE P0501 (P0125 es de modulo9) |

"""inmutabilidad_reportes_nic_41

Revision ID: c68b14c65d23
Revises: b7e2d94c1a68
Create Date: 2026-11-10 06:51:48.469476

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c68b14c65d23'
down_revision: Union[str, Sequence[str], None] = 'b7e2d94c1a68'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ROLES_APP = "('sgpmp_app', 'rol_app', 'rol_dev', 'rol_impl')"


def upgrade() -> None:
    op.execute("""
        CREATE OR REPLACE FUNCTION modulo5.fn_proteger_provision_nic41()
        RETURNS trigger LANGUAGE plpgsql
        SET search_path = pg_catalog, modulo5 AS $$
        DECLARE
            -- El hash lo recalcula el trigger existente; no se compara.
            v_ignorar text[] := ARRAY['estado', 'fecha_entrega_m06', 'hash_integridad'];
        BEGIN
            IF TG_OP = 'UPDATE'
               AND (to_jsonb(NEW) - v_ignorar) = (to_jsonb(OLD) - v_ignorar)
               -- Corrección: GENERADO -> SUPERADO (o el estado no cambia).
               AND (NEW.estado IS NOT DISTINCT FROM OLD.estado
                    OR (OLD.estado = 'GENERADO' AND NEW.estado = 'SUPERADO'))
               -- Entrega a M06: se llena una sola vez.
               AND (NEW.fecha_entrega_m06 IS NOT DISTINCT FROM OLD.fecha_entrega_m06
                    OR (OLD.fecha_entrega_m06 IS NULL AND NEW.fecha_entrega_m06 IS NOT NULL))
            THEN
                RETURN NEW;
            END IF;

            -- Rastro que sobrevive al rollback.
            RAISE LOG '[SEGURIDAD][M05] Intento de % rechazado sobre provision_nic41 id=% por rol=% usuario_app=%',
                TG_OP, OLD.id_provision, current_user, current_setting('app.current_user_id', true);

            RAISE EXCEPTION '[TGR-M05-NIC41] REPORTE_NIC41_INMUTABLE: el reporte id=% no admite %. CA-7.',
                OLD.id_provision, TG_OP USING ERRCODE = 'P0501';
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER trg_antes_modificar_provision_nic41
            BEFORE UPDATE OR DELETE ON modulo5.provision_nic41
            FOR EACH ROW EXECUTE FUNCTION modulo5.fn_proteger_provision_nic41()
    """)

    # TRUNCATE no dispara triggers de fila: se bloquea aparte.
    op.execute("""
        CREATE OR REPLACE FUNCTION modulo5.fn_bloquear_truncate_provision_nic41()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE LOG '[SEGURIDAD][M05] Intento de TRUNCATE rechazado sobre provision_nic41 por rol=%', current_user;
            RAISE EXCEPTION '[TGR-M05-NIC41] REPORTE_NIC41_INMUTABLE: provision_nic41 no admite TRUNCATE. CA-7.'
                USING ERRCODE = 'P0501';
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER trg_antes_truncar_provision_nic41
            BEFORE TRUNCATE ON modulo5.provision_nic41
            FOR EACH STATEMENT EXECUTE FUNCTION modulo5.fn_bloquear_truncate_provision_nic41()
    """)

    # Defensa en profundidad: la app no puede borrar aunque el trigger se desactive.
    op.execute(f"""
        DO $$
        DECLARE r text;
        BEGIN
            FOR r IN SELECT rolname FROM pg_roles WHERE rolname IN {_ROLES_APP} LOOP
                EXECUTE format('REVOKE DELETE, TRUNCATE ON modulo5.provision_nic41 FROM %I', r);
            END LOOP;
        END $$;
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_antes_truncar_provision_nic41 ON modulo5.provision_nic41")
    op.execute("DROP TRIGGER IF EXISTS trg_antes_modificar_provision_nic41 ON modulo5.provision_nic41")
    op.execute("DROP FUNCTION IF EXISTS modulo5.fn_bloquear_truncate_provision_nic41()")
    op.execute("DROP FUNCTION IF EXISTS modulo5.fn_proteger_provision_nic41()")
    op.execute(f"""
        DO $$
        DECLARE r text;
        BEGIN
            FOR r IN SELECT rolname FROM pg_roles WHERE rolname IN {_ROLES_APP} LOOP
                EXECUTE format('GRANT DELETE ON modulo5.provision_nic41 TO %I', r);
            END LOOP;
        END $$;
    """)