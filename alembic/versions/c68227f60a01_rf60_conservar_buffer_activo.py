# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-27 | Leandro | INC-M03-127-G27 RF-54/60: alinear trigger y procedimiento con buffer pendiente, bloqueo compartido y cierre tras vaciado. |
"""#682 RF-54/RF-60: conservar BUFFER_ACTIVO hasta confirmar vaciado.

No cambia tablas, permisos ni políticas. Las definiciones anteriores se conservan para downgrade.
"""
from alembic import op

revision = 'c68227f60a01'
down_revision = 'ebbb160365e5'
branch_labels = None
depends_on = None

_HEARTBEAT_ANTERIOR = r'''CREATE OR REPLACE FUNCTION modulo3.fn_procesar_heartbeat()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
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
$function$
'''
_CLASIFICAR_ANTERIOR = r'''CREATE OR REPLACE PROCEDURE modulo3.sp_clasificar_estado_dispositivo(IN p_id_dispositivo integer, IN p_margen_tolerancia_min integer DEFAULT 5, IN p_umbral_inactivo_horas integer DEFAULT 6)
 LANGUAGE plpgsql
AS $procedure$
DECLARE
    v_rec                RECORD;
    v_t_sin_contacto     INTERVAL;
    v_tiene_buffer_pend  BOOLEAN;
    v_estado_nuevo       modulo3.enum_estado_dispositivo;
    v_estado_actual      modulo3.enum_estado_dispositivo;
BEGIN
    -- Obtener la fila completa del estado actual del dispositivo
    SELECT edi.estado_actual,
           edi.fecha_ultimo_contacto,
           edi.id_ultimo_heardbeat
    INTO v_rec
    FROM modulo3.estados_dispositivos_iot edi
    WHERE edi.id_dispositivo_iot = p_id_dispositivo;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Dispositivo % no existe en estados_dispositivos_iot', p_id_dispositivo;
    END IF;

    v_estado_actual := v_rec.estado_actual;

    -- Si está en mantenimiento, no se modifica
    IF v_estado_actual = 'EN_MANTENIMIENTO'::modulo3.enum_estado_dispositivo THEN
        RETURN;
    END IF;

    -- Calcular tiempo sin contacto
    v_t_sin_contacto := NOW() - COALESCE(v_rec.fecha_ultimo_contacto, '1970-01-01'::TIMESTAMPTZ);

    -- Buffer pendiente según el último heartbeat del nodo (DB-03 / D10: el
    -- buffer vive en el Edge y su estado llega por heartbeat)
    SELECT COALESCE((
        SELECT h.datos_pendientes_buffer > 0
        FROM modulo3.heartbeats h
        WHERE h.id_dispositivo_iot = p_id_dispositivo
        ORDER BY h.fecha_recepcion DESC, h.id_heartbeat DESC
        LIMIT 1
    ), FALSE) INTO v_tiene_buffer_pend;

    -- Determinar nuevo estado según reglas de negocio
    IF v_t_sin_contacto <= INTERVAL '10 minutes' THEN        -- frecuencia de heartbeat típica
        v_estado_nuevo := 'ACTIVO'::modulo3.enum_estado_dispositivo;
    ELSIF v_tiene_buffer_pend THEN
        v_estado_nuevo := 'BUFFER_ACTIVO'::modulo3.enum_estado_dispositivo;
    ELSIF v_t_sin_contacto <= MAKE_INTERVAL(mins => p_margen_tolerancia_min) THEN
        v_estado_nuevo := 'SIN_SEÑAL'::modulo3.enum_estado_dispositivo;
    ELSIF v_t_sin_contacto > MAKE_INTERVAL(hours => p_umbral_inactivo_horas) THEN
        v_estado_nuevo := 'INACTIVO'::modulo3.enum_estado_dispositivo;
    ELSE
        v_estado_nuevo := 'SIN_SEÑAL'::modulo3.enum_estado_dispositivo;
    END IF;

    -- Actualizar si cambió
    IF v_estado_nuevo IS DISTINCT FROM v_estado_actual THEN
        UPDATE modulo3.estados_dispositivos_iot
        SET estado_actual              = v_estado_nuevo,
            tiempo_sin_contacto        = EXTRACT(EPOCH FROM v_t_sin_contacto)::INTEGER / 60,
            fecha_ultima_actualizacion = NOW()
        WHERE id_dispositivo_iot = p_id_dispositivo;
    END IF;
END;
$procedure$
'''
_HEARTBEAT_ACTUAL = r'''CREATE OR REPLACE FUNCTION modulo3.fn_procesar_heartbeat()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
DECLARE
    v_estado_actual   modulo3.enum_estado_dispositivo;
    v_estado_nuevo    modulo3.enum_estado_dispositivo := 'ACTIVO';
    v_ultimo_heartbeat integer := NEW.id_heartbeat;
BEGIN
    -- Mismo bloqueo que el evaluador y el worker, antes de resolver el reporte vigente.
    PERFORM pg_advisory_xact_lock(3505, NEW.id_dispositivo_iot);
    SELECT estado_actual INTO v_estado_actual
    FROM   modulo3.estados_dispositivos_iot
    WHERE  id_dispositivo_iot = NEW.id_dispositivo_iot;

    IF NOT FOUND THEN
        v_estado_nuevo := CASE WHEN NEW.estado_local_buffer::text IN ('A','L')
                                  AND NEW.datos_pendientes_buffer > 0
                              THEN 'BUFFER_ACTIVO'::modulo3.enum_estado_dispositivo
                              ELSE 'ACTIVO'::modulo3.enum_estado_dispositivo END;
        INSERT INTO modulo3.estados_dispositivos_iot (
            id_dispositivo_iot, estado_actual, fecha_ultimo_contacto,
            id_ultimo_heardbeat, tiempo_sin_contacto, fecha_ultima_actualizacion, causa_primaria
        ) VALUES (
            NEW.id_dispositivo_iot, v_estado_nuevo, NEW.fecha_recepcion,
            NEW.id_heartbeat, 0, now(),
            CASE WHEN v_estado_nuevo='BUFFER_ACTIVO' THEN 'FALLO_CONECTIVIDAD'::modulo3.enum_causa_inactividad ELSE NULL END
        );
        RETURN NEW;
    END IF;

    -- EN_MANTENIMIENTO no se cambia automáticamente
    IF v_estado_actual = 'EN_MANTENIMIENTO' THEN
        v_estado_nuevo := 'EN_MANTENIMIENTO';
    ELSE
        -- Una recepción anterior que termina más tarde no reemplaza el último reporte.
        SELECT CASE WHEN h.datos_pendientes_buffer > 0
                          AND (h.estado_local_buffer::text IN ('A','L') OR v_estado_actual='BUFFER_ACTIVO')
                    THEN 'BUFFER_ACTIVO'::modulo3.enum_estado_dispositivo
                    ELSE 'ACTIVO'::modulo3.enum_estado_dispositivo END
        , h.id_heartbeat INTO v_estado_nuevo, v_ultimo_heartbeat FROM modulo3.heartbeats h
        WHERE h.id_dispositivo_iot=NEW.id_dispositivo_iot
        ORDER BY h.fecha_recepcion DESC,h.id_heartbeat DESC LIMIT 1;
    END IF;

    UPDATE modulo3.estados_dispositivos_iot SET
        estado_actual              = v_estado_nuevo,
        fecha_ultimo_contacto      = GREATEST(COALESCE(fecha_ultimo_contacto,'1970-01-01'), NEW.fecha_recepcion),
        id_ultimo_heardbeat        = v_ultimo_heartbeat,
        tiempo_sin_contacto        = 0,
        causa_primaria             = CASE WHEN v_estado_nuevo='BUFFER_ACTIVO'
                                             THEN 'FALLO_CONECTIVIDAD'::modulo3.enum_causa_inactividad ELSE NULL END,
        id_usuario                 = NULL,
        causas_secundarias         = NULL,
        fecha_ultima_actualizacion = now()
    WHERE id_dispositivo_iot = NEW.id_dispositivo_iot;

    -- Si venía de estado de fallo → registrar reconexión y cerrar período
    IF v_estado_nuevo='ACTIVO' AND v_estado_actual IN ('SIN_SEÑAL','INACTIVO','BUFFER_ACTIVO') THEN
        UPDATE modulo3.periodos_inactividad SET
            fecha_fin    = now(),
            duracion_min = EXTRACT(EPOCH FROM (now() - fecha_inicio))::integer / 60
        WHERE  id_dispositivo_iot = NEW.id_dispositivo_iot AND fecha_fin IS NULL;
    END IF;

    RETURN NEW;
END;
$function$
'''
_CLASIFICAR_ACTUAL = r'''CREATE OR REPLACE PROCEDURE modulo3.sp_clasificar_estado_dispositivo(IN p_id_dispositivo integer, IN p_margen_tolerancia_min integer DEFAULT 5, IN p_umbral_inactivo_horas integer DEFAULT 6)
 LANGUAGE plpgsql
AS $procedure$
DECLARE
    v_rec                RECORD;
    v_t_sin_contacto     INTERVAL;
    v_tiene_buffer_pend  BOOLEAN;
    v_estado_nuevo       modulo3.enum_estado_dispositivo;
    v_estado_actual      modulo3.enum_estado_dispositivo;
BEGIN
    PERFORM pg_advisory_xact_lock(3505, p_id_dispositivo);
    -- Obtener la fila completa del estado actual del dispositivo
    SELECT edi.estado_actual,
           edi.fecha_ultimo_contacto,
           edi.id_ultimo_heardbeat
    INTO v_rec
    FROM modulo3.estados_dispositivos_iot edi
    WHERE edi.id_dispositivo_iot = p_id_dispositivo;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Dispositivo % no existe en estados_dispositivos_iot', p_id_dispositivo;
    END IF;

    v_estado_actual := v_rec.estado_actual;

    -- Si está en mantenimiento, no se modifica
    IF v_estado_actual = 'EN_MANTENIMIENTO'::modulo3.enum_estado_dispositivo THEN
        RETURN;
    END IF;

    -- Calcular tiempo sin contacto
    v_t_sin_contacto := NOW() - COALESCE(v_rec.fecha_ultimo_contacto, '1970-01-01'::TIMESTAMPTZ);

    -- Buffer pendiente según el último heartbeat del nodo (DB-03 / D10: el
    -- buffer vive en el Edge y su estado llega por heartbeat)
    SELECT COALESCE((
        SELECT h.datos_pendientes_buffer > 0
               AND (h.estado_local_buffer::text IN ('A','L') OR v_estado_actual='BUFFER_ACTIVO')
        FROM modulo3.heartbeats h
        WHERE h.id_dispositivo_iot = p_id_dispositivo
        ORDER BY h.fecha_recepcion DESC, h.id_heartbeat DESC
        LIMIT 1
    ), v_estado_actual='BUFFER_ACTIVO') INTO v_tiene_buffer_pend;

    -- Determinar nuevo estado según reglas de negocio
    IF v_tiene_buffer_pend THEN
        v_estado_nuevo := 'BUFFER_ACTIVO'::modulo3.enum_estado_dispositivo;
    ELSIF v_t_sin_contacto <= INTERVAL '10 minutes' THEN
        v_estado_nuevo := 'ACTIVO'::modulo3.enum_estado_dispositivo;
    ELSIF v_t_sin_contacto <= MAKE_INTERVAL(mins => p_margen_tolerancia_min) THEN
        v_estado_nuevo := 'SIN_SEÑAL'::modulo3.enum_estado_dispositivo;
    ELSIF v_t_sin_contacto > MAKE_INTERVAL(hours => p_umbral_inactivo_horas) THEN
        v_estado_nuevo := 'INACTIVO'::modulo3.enum_estado_dispositivo;
    ELSE
        v_estado_nuevo := 'SIN_SEÑAL'::modulo3.enum_estado_dispositivo;
    END IF;

    -- Actualizar si cambió
    IF v_estado_nuevo IS DISTINCT FROM v_estado_actual THEN
        UPDATE modulo3.estados_dispositivos_iot
        SET estado_actual              = v_estado_nuevo,
            causa_primaria = CASE WHEN v_estado_nuevo IN ('BUFFER_ACTIVO','SIN_SEÑAL','INACTIVO')
                                 THEN 'FALLO_CONECTIVIDAD'::modulo3.enum_causa_inactividad ELSE NULL END,
            tiempo_sin_contacto        = EXTRACT(EPOCH FROM v_t_sin_contacto)::INTEGER / 60,
            fecha_ultima_actualizacion = NOW()
        WHERE id_dispositivo_iot = p_id_dispositivo;
    END IF;
END;
$procedure$
'''


def upgrade():
    op.execute(_HEARTBEAT_ACTUAL)
    op.execute(_CLASIFICAR_ACTUAL)


def downgrade():
    op.execute(_HEARTBEAT_ANTERIOR)
    op.execute(_CLASIFICAR_ANTERIOR)
