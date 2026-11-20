# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-11-19 | Leandro | INC-M07-371-G58 RF-102: crear archivo inmutable y traslado protegido por retención. |
"""RF-102. Conservación y traslado transaccional de auditoría M07."""

from alembic import op

revision = "f11651020001"
down_revision = "a7c3e91f5b20"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        LOCK TABLE modulo7.eventos_integracion IN SHARE ROW EXCLUSIVE MODE;
        CREATE TABLE modulo7.eventos_integracion_archivados (
            LIKE modulo7.eventos_integracion INCLUDING ALL,
            FOREIGN KEY (id_usuario) REFERENCES modulo1.usuarios (id_usuario) ON DELETE RESTRICT,
            FOREIGN KEY (id_cliente_externo) REFERENCES modulo7.clientes_externos (id_cliente_externo) ON DELETE RESTRICT
        );

        -- Reservar el UUID de por vida, también tras el traslado y ante inserciones concurrentes.
        CREATE TABLE modulo7.identidades_eventos_integracion (id_evento_integracion uuid PRIMARY KEY);
        INSERT INTO modulo7.identidades_eventos_integracion
            SELECT id_evento_integracion FROM modulo7.eventos_integracion;
        ALTER TABLE modulo7.eventos_integracion ADD FOREIGN KEY (id_evento_integracion)
            REFERENCES modulo7.identidades_eventos_integracion;
        ALTER TABLE modulo7.eventos_integracion_archivados ADD FOREIGN KEY (id_evento_integracion)
            REFERENCES modulo7.identidades_eventos_integracion;

        CREATE FUNCTION modulo7.fn_reservar_evento_integracion()
        RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
        BEGIN
            INSERT INTO modulo7.identidades_eventos_integracion VALUES (NEW.id_evento_integracion);
            RETURN NEW;
        END;
        $$;
        REVOKE ALL ON FUNCTION modulo7.fn_reservar_evento_integracion() FROM PUBLIC;
        CREATE TRIGGER trg_reservar_evento_integracion BEFORE INSERT ON modulo7.eventos_integracion
            FOR EACH ROW EXECUTE FUNCTION modulo7.fn_reservar_evento_integracion();

        CREATE FUNCTION modulo7.fn_fin_retencion_rf102(
            tipo modulo7.enum_evento_integracion_tipo_evento, ocurrio timestamptz, registrado timestamptz
        ) RETURNS timestamptz LANGUAGE sql IMMUTABLE STRICT SET search_path = pg_catalog, pg_temp AS $$
            SELECT ((GREATEST(ocurrio, registrado) AT TIME ZONE 'UTC') + CASE
                WHEN tipo IN ('PAQUETE_AAEF_CONSULTADO', 'VISTA_AAEF_GENERADA', 'CONTRATO_ACTIVADO')
                    THEN interval '10 years' ELSE interval '5 years' END) AT TIME ZONE 'UTC'
        $$;
        CREATE INDEX idx_eventos_integracion_retencion ON modulo7.eventos_integracion (
            modulo7.fn_fin_retencion_rf102(tipo_evento, fecha_evento, fecha_registro), id_evento_integracion
        );

        CREATE VIEW modulo7.v_historial_eventos_integracion WITH (security_invoker = true) AS
            SELECT * FROM modulo7.eventos_integracion
            UNION ALL
            SELECT * FROM modulo7.eventos_integracion_archivados;

        CREATE TRIGGER trg_proteger_evento_integracion_archivado
            BEFORE UPDATE OR DELETE ON modulo7.eventos_integracion_archivados
            FOR EACH ROW EXECUTE FUNCTION modulo7.fn_bloquear_modificacion_evento_integracion();
        CREATE TRIGGER trg_no_truncar_eventos_integracion_archivados
            BEFORE TRUNCATE ON modulo7.eventos_integracion_archivados
            FOR EACH STATEMENT EXECUTE FUNCTION modulo7.fn_bloquear_modificacion_evento_integracion();

        CREATE FUNCTION modulo7.fn_proteger_salida_evento_integracion()
        RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog, pg_temp AS $$
        BEGIN
            IF modulo7.fn_fin_retencion_rf102(OLD.tipo_evento, OLD.fecha_evento, OLD.fecha_registro) < statement_timestamp()
                AND EXISTS (
                    SELECT 1 FROM modulo7.eventos_integracion_archivados a
                    WHERE a.id_evento_integracion = OLD.id_evento_integracion
                      AND to_jsonb(a) = to_jsonb(OLD)
                ) THEN
                RETURN OLD;
            END IF;
            RAISE EXCEPTION '[TGR-M07-14] La auditoría de integración es inmutable (RF-102).' USING ERRCODE = 'P0001';
        END;
        $$;
        DROP TRIGGER trg_antes_modificar_evento_integracion ON modulo7.eventos_integracion;
        CREATE TRIGGER trg_antes_modificar_evento_integracion BEFORE UPDATE ON modulo7.eventos_integracion
            FOR EACH ROW EXECUTE FUNCTION modulo7.fn_bloquear_modificacion_evento_integracion();
        CREATE TRIGGER trg_proteger_salida_evento_integracion BEFORE DELETE ON modulo7.eventos_integracion
            FOR EACH ROW EXECUTE FUNCTION modulo7.fn_proteger_salida_evento_integracion();

        CREATE FUNCTION modulo7.fn_archivar_eventos_rf102(p_ids uuid[])
        RETURNS SETOF uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
        BEGIN
            IF modulo1.fn_es_usuario_servicio() IS NOT TRUE THEN
                RAISE insufficient_privilege USING MESSAGE = 'Archivado reservado al servicio de integración';
            END IF;
            IF p_ids IS NULL OR cardinality(p_ids) > 100 THEN
                RAISE invalid_parameter_value USING MESSAGE = 'Lote de archivado inválido';
            END IF;
            INSERT INTO modulo7.eventos_integracion_archivados
                SELECT e.* FROM modulo7.eventos_integracion e
                WHERE e.id_evento_integracion = ANY(p_ids)
                  AND modulo7.fn_fin_retencion_rf102(e.tipo_evento, e.fecha_evento, e.fecha_registro)
                      < statement_timestamp()
                FOR UPDATE OF e;
            RETURN QUERY DELETE FROM modulo7.eventos_integracion e
                USING modulo7.eventos_integracion_archivados a
                WHERE e.id_evento_integracion = ANY(p_ids) AND a.id_evento_integracion = e.id_evento_integracion
                RETURNING e.id_evento_integracion;
        END;
        $$;
        REVOKE ALL ON FUNCTION modulo7.fn_archivar_eventos_rf102(uuid[]) FROM PUBLIC;
        REVOKE ALL ON modulo7.eventos_integracion_archivados,
            modulo7.identidades_eventos_integracion, modulo7.v_historial_eventos_integracion FROM PUBLIC;
        DO $$
        DECLARE rol text;
        BEGIN
            FOR rol IN SELECT rolname FROM pg_roles
                WHERE rolname IN ('sgpmp_app', 'rol_app', 'rol_dev', 'rol_impl', 'rol_migracion')
            LOOP
                EXECUTE format('REVOKE ALL ON modulo7.eventos_integracion_archivados,
                    modulo7.identidades_eventos_integracion, modulo7.v_historial_eventos_integracion FROM %I', rol);
                EXECUTE format('GRANT SELECT ON modulo7.eventos_integracion_archivados,
                    modulo7.v_historial_eventos_integracion TO %I', rol);
                EXECUTE format('GRANT EXECUTE ON FUNCTION modulo7.fn_archivar_eventos_rf102(uuid[]) TO %I', rol);
            END LOOP;
        END;
        $$;
    """)


def downgrade() -> None:
    op.execute("""
        LOCK TABLE modulo7.eventos_integracion, modulo7.eventos_integracion_archivados IN ACCESS EXCLUSIVE MODE;
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM modulo7.eventos_integracion_archivados) THEN
                RAISE EXCEPTION 'RF-102: no se puede retirar un archivo que conserva eventos';
            END IF;
        END;
        $$;
        DROP FUNCTION modulo7.fn_archivar_eventos_rf102(uuid[]);
        DROP VIEW modulo7.v_historial_eventos_integracion;
        DROP TRIGGER trg_proteger_salida_evento_integracion ON modulo7.eventos_integracion;
        DROP FUNCTION modulo7.fn_proteger_salida_evento_integracion();
        DROP TRIGGER trg_antes_modificar_evento_integracion ON modulo7.eventos_integracion;
        CREATE TRIGGER trg_antes_modificar_evento_integracion BEFORE UPDATE OR DELETE ON modulo7.eventos_integracion
            FOR EACH ROW EXECUTE FUNCTION modulo7.fn_bloquear_modificacion_evento_integracion();
        DROP INDEX modulo7.idx_eventos_integracion_retencion;
        DROP FUNCTION modulo7.fn_fin_retencion_rf102(modulo7.enum_evento_integracion_tipo_evento, timestamptz, timestamptz);
        DROP TRIGGER trg_reservar_evento_integracion ON modulo7.eventos_integracion;
        DROP FUNCTION modulo7.fn_reservar_evento_integracion();
        DROP TABLE modulo7.eventos_integracion_archivados;
        ALTER TABLE modulo7.eventos_integracion DROP CONSTRAINT eventos_integracion_id_evento_integracion_fkey;
        DROP TABLE modulo7.identidades_eventos_integracion;
    """)
