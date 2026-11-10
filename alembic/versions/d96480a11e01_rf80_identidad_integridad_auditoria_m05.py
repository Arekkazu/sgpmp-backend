# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-11-08 | Leandro | INC-M05-278-G39 RF-80: agregar UUID deduplicable, proteger nuevos registros y preservar hashes históricos. |
"""RF-80: identidad de emisión, completitud e integridad de la bitácora.

Revision ID: d96480a11e01
Revises: b7e2d94c1a68
"""
from alembic import op

revision = 'd96480a11e01'
down_revision = 'b7e2d94c1a68'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ADD COLUMN asigna metadatos técnicos sin UPDATE de las entradas históricas.
    # V1 conserva exactamente la proyección sellada antes de esta migración.
    op.execute("""
        ALTER TABLE modulo5.auditorias_suministros
          ADD COLUMN id_evento_m05 uuid NOT NULL DEFAULT gen_random_uuid(),
          ADD COLUMN version_hash_integridad integer NOT NULL DEFAULT 1;
        ALTER TABLE modulo5.auditorias_suministros
          ALTER COLUMN version_hash_integridad SET DEFAULT 2,
          ADD CONSTRAINT uq_auditorias_suministros_id_evento_m05 UNIQUE(id_evento_m05),
          ADD CONSTRAINT ck_auditorias_suministros_version_hash CHECK(version_hash_integridad IN (1,2)),
          ADD CONSTRAINT ck_auditorias_suministros_incompleto_causa
            CHECK(registro_incompleto IS NOT TRUE OR NULLIF(btrim(detalle_causa),'') IS NOT NULL) NOT VALID;
    """)
    op.execute("""
        CREATE FUNCTION modulo5.hash_evento_auditoria_m05(datos jsonb, version integer)
        RETURNS text LANGUAGE sql IMMUTABLE STRICT AS $$
          SELECT encode(public.digest((SELECT string_agg(format('%I=%L',key,value),' & ' ORDER BY key)
            FROM jsonb_each_text(CASE WHEN version=1 THEN
              datos - 'hash_integridad' - 'creado_en' - 'id_registro_suministro'
                    - 'id_evento_m05' - 'version_hash_integridad'
              ELSE datos - 'hash_integridad' END)), 'sha256'), 'hex');
        $$;
        CREATE FUNCTION modulo5.sellar_auditoria_m05() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          NEW.version_hash_integridad := 2;
          NEW.hash_integridad := modulo5.hash_evento_auditoria_m05(to_jsonb(NEW),2);
          RETURN NEW;
        END;
        $$;
        DROP TRIGGER trg_audit_hash ON modulo5.auditorias_suministros;
        CREATE TRIGGER trg_audit_hash BEFORE INSERT ON modulo5.auditorias_suministros
          FOR EACH ROW EXECUTE FUNCTION modulo5.sellar_auditoria_m05();
        CREATE FUNCTION modulo5.impedir_modificacion_auditoria_m05() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          RAISE EXCEPTION USING ERRCODE='55000', MESSAGE='La bitácora es de solo lectura.';
        END;
        $$;
        CREATE TRIGGER trg_auditoria_m05_inmutable BEFORE UPDATE OR DELETE
          ON modulo5.auditorias_suministros FOR EACH ROW
          EXECUTE FUNCTION modulo5.impedir_modificacion_auditoria_m05();
    """)


def downgrade() -> None:
    # Retirar identidad de eventos ya emitidos impediría verificar su sello.
    op.execute("""
        DO $$ BEGIN
          IF EXISTS(SELECT 1 FROM modulo5.auditorias_suministros WHERE version_hash_integridad=2) THEN
            RAISE EXCEPTION 'No se puede retirar la identidad de eventos ya emitidos.';
          END IF;
        END $$;
        DROP TRIGGER trg_auditoria_m05_inmutable ON modulo5.auditorias_suministros;
        DROP TRIGGER trg_audit_hash ON modulo5.auditorias_suministros;
        CREATE TRIGGER trg_audit_hash BEFORE INSERT OR UPDATE ON modulo5.auditorias_suministros
          FOR EACH ROW EXECUTE FUNCTION modulo5.calcular_hash_integridad();
        DROP FUNCTION modulo5.impedir_modificacion_auditoria_m05();
        DROP FUNCTION modulo5.sellar_auditoria_m05();
        DROP FUNCTION modulo5.hash_evento_auditoria_m05(jsonb,integer);
        ALTER TABLE modulo5.auditorias_suministros
          DROP CONSTRAINT ck_auditorias_suministros_incompleto_causa,
          DROP CONSTRAINT ck_auditorias_suministros_version_hash,
          DROP CONSTRAINT uq_auditorias_suministros_id_evento_m05,
          DROP COLUMN version_hash_integridad,
          DROP COLUMN id_evento_m05;
    """)
