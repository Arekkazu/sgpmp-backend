# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-11-12 | Leandro | INC-M05-354-G39 RF-80: completar y validar el contexto de emisión antes de sellar la bitácora. |
# | 2026-11-12 | Arekkazu | Lote M05/M06 11-12 RF-80: campos faltantes con nombres legibles y sin repetir los de la app |
"""RF-80: completar la auditoría DML de M05 y proteger las nuevas emisiones."""

from alembic import op

revision = "a107980ae001"
down_revision = "603631775892"
branch_labels = None
depends_on = None

_EMISORES = (
    ("consumo_alimento", "registros_consumo_alimentos"),
    ("medicamento", "registros_medicamentos"),
    ("costos_productivos", "costos_productivos"),
    ("resultado_ica", "resultado_ica"),
)
_ORIGEN_LEDGER = {"consumo_alimento": "id_registro_rf75", "medicamento": "id_registro_rf76"}


def _contexto_emisor(emisor: str) -> str:
    if emisor in _ORIGEN_LEDGER:
        origen = _ORIGEN_LEDGER[emisor]
        return f"""
            SELECT min(s.id_ciclo_productivo), min(s.id_gestion_fases)
              INTO v_ciclo, v_fase
              FROM modulo5.registro_suministro AS s
             WHERE s.{origen} = NEW.{origen}
               AND s.id_activo_biologico = NEW.id_activo_biologico
               AND s.tipo_operacion = 'REGISTRO'
            HAVING count(*) = 1;
        """
    if emisor == "resultado_ica":
        return """
            SELECT f.id_ciclo_productiva, f.id_gestion_fases
              INTO v_ciclo, v_fase
              FROM modulo2.gestiones_fases AS f
             WHERE f.id_gestion_fases = NEW.id_gestion_fases
               AND f.id_activo_biologico = NEW.id_activo_biologico;
        """
    return "v_ciclo := NEW.id_ciclo_productivo;"


def _reemplazar_emisores(*, con_contexto: bool) -> None:
    for emisor, entidad in _EMISORES:
        columnas = ""
        valores = ""
        if con_contexto:
            columnas = ", fecha_emision, id_activo_biologico, id_ciclo_productivo, id_gestion_fases"
            valores = ", clock_timestamp(), NEW.id_activo_biologico, v_ciclo, v_fase"
        elif emisor == "resultado_ica":
            columnas = ", id_activo_biologico"
            valores = ", COALESCE(NEW.id_activo_biologico, OLD.id_activo_biologico)"

        actor = "COALESCE(NEW.id_usuario, OLD.id_usuario)"
        if emisor == "resultado_ica":
            actor = "COALESCE(NEW.id_usuario, OLD.id_usuario, 1)"
        elif emisor == "costos_productivos":
            actor = "NEW.id_usuario"

        op.execute(f"""
            CREATE OR REPLACE FUNCTION modulo5.fn_trg_auditoria_{emisor}()
            RETURNS trigger LANGUAGE plpgsql AS $$
            DECLARE
                v_tipo_op modulo5.enum_auditoria_suministro_tipo_operacion := TG_OP;
                v_antes json;
                v_ciclo integer;
                v_fase integer;
            BEGIN
                IF TG_OP = 'UPDATE' THEN
                    v_antes := row_to_json(OLD);
                END IF;
                {_contexto_emisor(emisor) if con_contexto else ""}
                INSERT INTO modulo5.auditorias_suministros (
                    entidad_afectada, tipo_operacion, datos_anteriores, datos_nuevos,
                    id_usuario, ip_origen, fecha_evento, resultado{columnas}
                ) VALUES (
                    '{entidad}', v_tipo_op, v_antes, row_to_json(NEW),
                    {actor}, NULL, now(), 'EXITOSO'{valores}
                );
                RETURN NULL;
            END;
            $$;
        """)


def _sellar(*, con_contexto: bool) -> None:
    completar = """
        -- El rechazo por falta de campos base se mantiene en los constraints.
        -- Una emisión ya marcada como incompleta debe aportar su propia causa.
        -- El detalle sale en la bitácora y en su Excel/PDF: los campos se nombran como los ve el
        -- usuario, igual que EventoAuditoriaSuministro; si la app ya los listó, no se repiten.
        IF NEW.registro_incompleto IS NOT TRUE OR NULLIF(btrim(NEW.detalle_causa), '') IS NOT NULL THEN
            IF strpos(COALESCE(NEW.detalle_causa, ''), 'Campos faltantes:') = 0 THEN
                IF NEW.id_activo_biologico IS NULL THEN
                    v_faltantes := array_append(v_faltantes, 'activo biológico');
                END IF;
                IF NEW.id_ciclo_productivo IS NULL THEN
                    v_faltantes := array_append(v_faltantes, 'ciclo productivo');
                END IF;
            END IF;
            IF cardinality(v_faltantes) > 0 THEN
                NEW.detalle_causa := concat_ws(
                    '. ', NULLIF(rtrim(btrim(NEW.detalle_causa), '.'), ''),
                    'Campos faltantes: ' || array_to_string(v_faltantes, ', ') || '.'
                );
            END IF;
            IF NEW.id_activo_biologico IS NULL OR NEW.id_ciclo_productivo IS NULL THEN
                NEW.registro_incompleto := true;
            END IF;
        END IF;
    """
    op.execute(f"""
        CREATE OR REPLACE FUNCTION modulo5.fn_sellar_auditoria_m05()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
            v_faltantes text[] := ARRAY[]::text[];
        BEGIN
            {completar if con_contexto else ""}
            NEW.version_hash_integridad := 2;
            NEW.hash_integridad := modulo5.fn_hash_evento_auditoria_m05(to_jsonb(NEW), 2);
            RETURN NEW;
        END;
        $$;
    """)


def _ordenar_auditoria_ledger(*, despues_del_ledger: bool) -> None:
    for emisor, entidad in _EMISORES[:2]:
        anterior = f"trg_auditoria_{emisor}"
        posterior = f"trg_registrar_auditoria_{emisor}"
        origen, destino = (anterior, posterior) if despues_del_ledger else (posterior, anterior)
        op.execute(f"ALTER TRIGGER {origen} ON modulo5.{entidad} RENAME TO {destino}")


def upgrade() -> None:
    # RF-38 calcula el ICA antes de cerrar la fase. Capturar ese vínculo en el
    # INSERT permite auditar futuras actualizaciones del resultado ya histórico.
    op.execute("""
        ALTER TABLE modulo5.resultado_ica ADD COLUMN id_gestion_fases integer;
        CREATE FUNCTION modulo5.fn_asignar_fase_resultado_ica()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            SELECT min(f.id_gestion_fases)
              INTO NEW.id_gestion_fases
              FROM modulo2.gestiones_fases AS f
             WHERE f.id_activo_biologico = NEW.id_activo_biologico AND f.es_activa
            HAVING count(*) = 1;
            RETURN NEW;
        END;
        $$;
        CREATE TRIGGER trg_antes_insertar_fase_resultado_ica
        BEFORE INSERT ON modulo5.resultado_ica
        FOR EACH ROW EXECUTE FUNCTION modulo5.fn_asignar_fase_resultado_ica();
    """)
    # PostgreSQL ejecuta los triggers AFTER del mismo tipo en orden alfabético.
    # En RF-75/76 se audita después de poblar el ledger para leer el vínculo exacto.
    _ordenar_auditoria_ledger(despues_del_ledger=True)
    _reemplazar_emisores(con_contexto=True)
    _sellar(con_contexto=True)
    op.execute("""
        ALTER TABLE modulo5.auditorias_suministros
          ADD CONSTRAINT ck_auditorias_suministros_fecha_emision
            CHECK (fecha_emision IS NOT NULL) NOT VALID,
          ADD CONSTRAINT ck_auditorias_suministros_contexto_incompleto
            CHECK ((id_activo_biologico IS NOT NULL AND id_ciclo_productivo IS NOT NULL)
                   OR registro_incompleto IS TRUE) NOT VALID;
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE modulo5.auditorias_suministros
          DROP CONSTRAINT ck_auditorias_suministros_contexto_incompleto,
          DROP CONSTRAINT ck_auditorias_suministros_fecha_emision;
    """)
    _sellar(con_contexto=False)
    _reemplazar_emisores(con_contexto=False)
    _ordenar_auditoria_ledger(despues_del_ledger=False)
    op.execute("""
        DROP TRIGGER trg_antes_insertar_fase_resultado_ica ON modulo5.resultado_ica;
        DROP FUNCTION modulo5.fn_asignar_fase_resultado_ica();
        ALTER TABLE modulo5.resultado_ica DROP COLUMN id_gestion_fases;
    """)
