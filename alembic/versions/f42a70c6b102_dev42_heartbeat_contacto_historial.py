# | Fecha      | Nombre  | Que se hizo |
# |------------|---------|-------------|
# | 2026-10-22 | Leandro | DEV-42 RF-60: contacto servidor, reloj e historia unica |
# | 2026-10-23 | Arekkazu | INTEG RFC-012..016 DEV-42: encadenada tras DEV-40 (un solo head) |
"""RF-60 DEV-42: corrige el trigger compartido por HTTP y broker.

No altera tablas ni los triggers de inmutabilidad.
"""
from alembic import op

revision = "f42a70c6b102"
down_revision = 'f40c53a37834'
branch_labels = None
depends_on = None

_ANTERIOR = """
CREATE OR REPLACE FUNCTION modulo3.fn_procesar_heartbeat() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
    v_estado_actual   modulo3.enum_estado_dispositivo;
    v_estado_nuevo    modulo3.enum_estado_dispositivo := 'ACTIVO';
BEGIN
    SELECT estado_actual INTO v_estado_actual
    FROM   modulo3.estados_dispositivos_iot
    WHERE  id_dispositivo_iot = NEW.id_dispositivo_iot;

    IF NOT FOUND THEN
        INSERT INTO modulo3.estados_dispositivos_iot (
            id_dispositivo_iot, estado_actual, fecha_ultimo_contacto,
            id_ultimo_heardbeat, tiempo_sin_contacto, fecha_ultima_actualizacion
        ) VALUES (
            NEW.id_dispositivo_iot, 'ACTIVO', GREATEST(NEW.fecha_registro, NEW.fecha_recepcion),
            NEW.id_heartbeat, 0, now()
        );
        RETURN NEW;
    END IF;

    -- EN_MANTENIMIENTO no se cambia automáticamente
    IF v_estado_actual = 'EN_MANTENIMIENTO' THEN
        v_estado_nuevo := 'EN_MANTENIMIENTO';
    ELSE
        v_estado_nuevo := 'ACTIVO';
    END IF;

    UPDATE modulo3.estados_dispositivos_iot SET
        estado_actual              = v_estado_nuevo,
        fecha_ultimo_contacto      = GREATEST(COALESCE(fecha_ultimo_contacto,'1970-01-01'), NEW.fecha_recepcion),
        id_ultimo_heardbeat        = NEW.id_heartbeat,
        tiempo_sin_contacto        = 0,
        causa_primaria             = NULL,
        causas_secundarias         = NULL,
        fecha_ultima_actualizacion = now()
    WHERE id_dispositivo_iot = NEW.id_dispositivo_iot;

    -- Si venía de estado de fallo → registrar reconexión y cerrar período
    IF v_estado_actual IN ('SIN_SEÑAL','INACTIVO','BUFFER_ACTIVO') THEN
        INSERT INTO modulo3.historico_transiciones_dispositivos (
            id_dispositivo_iot, estado_anterior, estado_nuevo, notas, fecha_transicion
        ) VALUES (
            NEW.id_dispositivo_iot, v_estado_actual, v_estado_nuevo,
            'Reconexión por heartbeat id=' || NEW.id_heartbeat, now()
        );
        UPDATE modulo3.periodos_inactividad SET
            fecha_fin    = now(),
            duracion_min = EXTRACT(EPOCH FROM (now() - fecha_inicio))::integer / 60
        WHERE  id_dispositivo_iot = NEW.id_dispositivo_iot AND fecha_fin IS NULL;
    END IF;

    RETURN NEW;
END;
$$;
"""

_ACTUAL = """
CREATE OR REPLACE FUNCTION modulo3.fn_procesar_heartbeat() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
    v_estado_actual   modulo3.enum_estado_dispositivo;
    v_estado_nuevo    modulo3.enum_estado_dispositivo := 'ACTIVO';
BEGIN
    SELECT estado_actual INTO v_estado_actual
    FROM   modulo3.estados_dispositivos_iot
    WHERE  id_dispositivo_iot = NEW.id_dispositivo_iot;

    IF NOT FOUND THEN
        INSERT INTO modulo3.estados_dispositivos_iot (
            id_dispositivo_iot, estado_actual, fecha_ultimo_contacto,
            id_ultimo_heardbeat, tiempo_sin_contacto, fecha_ultima_actualizacion
        ) VALUES (
            NEW.id_dispositivo_iot, 'ACTIVO', NEW.fecha_recepcion,
            NEW.id_heartbeat, 0, now()
        );
        RETURN NEW;
    END IF;

    -- EN_MANTENIMIENTO no se cambia automáticamente
    IF v_estado_actual = 'EN_MANTENIMIENTO' THEN
        v_estado_nuevo := 'EN_MANTENIMIENTO';
    ELSE
        v_estado_nuevo := 'ACTIVO';
    END IF;

    UPDATE modulo3.estados_dispositivos_iot SET
        estado_actual              = v_estado_nuevo,
        fecha_ultimo_contacto      = GREATEST(COALESCE(fecha_ultimo_contacto,'1970-01-01'), NEW.fecha_recepcion),
        id_ultimo_heardbeat        = NEW.id_heartbeat,
        tiempo_sin_contacto        = 0,
        causa_primaria             = NULL,
        id_usuario                 = NULL,
        causas_secundarias         = NULL,
        fecha_ultima_actualizacion = now()
    WHERE id_dispositivo_iot = NEW.id_dispositivo_iot;

    -- Si venía de estado de fallo → registrar reconexión y cerrar período
    IF v_estado_actual IN ('SIN_SEÑAL','INACTIVO','BUFFER_ACTIVO') THEN
        UPDATE modulo3.periodos_inactividad SET
            fecha_fin    = now(),
            duracion_min = EXTRACT(EPOCH FROM (now() - fecha_inicio))::integer / 60
        WHERE  id_dispositivo_iot = NEW.id_dispositivo_iot AND fecha_fin IS NULL;
    END IF;

    RETURN NEW;
END;
$$;
"""

_ALERTA_ANTERIOR = """
CREATE OR REPLACE FUNCTION modulo3.fn_alerta_validar_transicion() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    IF OLD.estado_alerta = NEW.estado_alerta THEN
        RETURN NEW;
    END IF;

    IF NOT (
        (OLD.estado_alerta = 'ACTIVA'      AND NEW.estado_alerta IN ('EN_ATENCION','DESCARTADA','VENCIDA','PENDIENTE_SINCRONIZACION')) OR
        (OLD.estado_alerta = 'EN_ATENCION' AND NEW.estado_alerta IN ('RESUELTA','VENCIDA'))
    ) THEN
        RAISE EXCEPTION
            'RF-57 [TRANSICION_INVALIDA]: % → % no permitida. id_alerta=%',
            OLD.estado_alerta, NEW.estado_alerta, OLD.id_alerta
            USING ERRCODE = 'P0005';
    END IF;

    IF NEW.estado_alerta = 'EN_ATENCION' THEN
        NEW.fecha_atencion   := COALESCE(NEW.fecha_atencion, now());
    ELSIF NEW.estado_alerta IN ('RESUELTA','DESCARTADA','VENCIDA') THEN
        NEW.fecha_resolucion := COALESCE(NEW.fecha_resolucion, now());
    END IF;

    INSERT INTO modulo3.historico_estados_alertas (
        id_alerta, estado_anterior, estado_nuevo, id_usuario, motivo, fecha_cambio
    ) VALUES (
        NEW.id_alerta, OLD.estado_alerta, NEW.estado_alerta,
        COALESCE(NEW.id_usuario_resolucion, NEW.id_usuario_atencion),
        CASE NEW.estado_alerta
            WHEN 'VENCIDA'    THEN 'SLA vencido sin atención'
            WHEN 'DESCARTADA' THEN COALESCE(NEW.motivo_descarte, 'Descarte manual')
            WHEN 'RESUELTA'   THEN COALESCE(NEW.diagnostico, 'Resolución confirmada')
            ELSE NULL
        END,
        now()
    );
    RETURN NEW;
END;
$$;
"""

_ALERTA_ACTUAL = """
CREATE OR REPLACE FUNCTION modulo3.fn_alerta_validar_transicion() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    IF OLD.estado_alerta = NEW.estado_alerta THEN
        RETURN NEW;
    END IF;

    IF NOT (
        (OLD.estado_alerta = 'ACTIVA'      AND NEW.estado_alerta IN ('EN_ATENCION','DESCARTADA','VENCIDA','PENDIENTE_SINCRONIZACION')) OR
        (OLD.estado_alerta = 'EN_ATENCION' AND NEW.estado_alerta IN ('RESUELTA','VENCIDA'))
    ) THEN
        RAISE EXCEPTION
            'RF-57 [TRANSICION_INVALIDA]: % → % no permitida. id_alerta=%',
            OLD.estado_alerta, NEW.estado_alerta, OLD.id_alerta
            USING ERRCODE = 'P0005';
    END IF;

    IF NEW.estado_alerta = 'EN_ATENCION' THEN
        NEW.fecha_atencion   := COALESCE(NEW.fecha_atencion, now());
    ELSIF NEW.estado_alerta IN ('RESUELTA','DESCARTADA','VENCIDA') THEN
        NEW.fecha_resolucion := COALESCE(NEW.fecha_resolucion, now());
    END IF;

    INSERT INTO modulo3.historico_estados_alertas (
        id_alerta, estado_anterior, estado_nuevo, id_usuario, motivo, fecha_cambio
    ) VALUES (
        NEW.id_alerta, OLD.estado_alerta, NEW.estado_alerta,
        CASE WHEN NEW.estado_alerta = 'EN_ATENCION' THEN NEW.id_usuario_atencion ELSE NEW.id_usuario_resolucion END,
        CASE NEW.estado_alerta
            WHEN 'VENCIDA'    THEN 'SLA vencido sin atención'
            WHEN 'DESCARTADA' THEN COALESCE(NEW.motivo_descarte, 'Descarte manual')
            WHEN 'RESUELTA'   THEN COALESCE(NEW.diagnostico, 'Resolución confirmada')
            ELSE NULL
        END,
        now()
    );
    RETURN NEW;
END;
$$;
"""

def upgrade():
    op.execute(_ACTUAL)
    op.execute(_ALERTA_ACTUAL)
    op.execute("""CREATE FUNCTION modulo3.fn_rf60_reloj_futuro() RETURNS trigger
        LANGUAGE plpgsql AS $$ BEGIN
          IF NEW.fecha_registro > NEW.fecha_recepcion THEN NEW.reloj_sincronizado := false; END IF;
          RETURN NEW;
        END $$""")
    op.execute("""CREATE TRIGGER trg_rf60_reloj_futuro BEFORE INSERT ON modulo3.heartbeats
        FOR EACH ROW EXECUTE FUNCTION modulo3.fn_rf60_reloj_futuro()""")


def downgrade():
    op.execute('DROP TRIGGER trg_rf60_reloj_futuro ON modulo3.heartbeats')
    op.execute('DROP FUNCTION modulo3.fn_rf60_reloj_futuro()')
    op.execute(_ANTERIOR)
    op.execute(_ALERTA_ANTERIOR)
