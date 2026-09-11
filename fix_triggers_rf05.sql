-- =============================================================================
-- Fix: Corrección de triggers en modulo1 para RF-05 (Edición de perfil)
-- Problema 1: fn_correo_a_pendiente usaba id_estado_cuenta = 2 (Activo)
--             en lugar de 1 (Pendiente).
-- Problema 2: trg_fn_validar_transicion_estado no permitía Activo → Pendiente,
--             transición necesaria cuando el correo electrónico es modificado.
-- =============================================================================

BEGIN;

-- -----------------------------------------------------------------------------
-- Fix 1: fn_correo_a_pendiente
-- Cuando el correo cambia, la cuenta debe quedar en estado Pendiente (1),
-- no en Activo (2) como estaba incorrectamente definido.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION modulo1.fn_correo_a_pendiente()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.correo_electronico IS DISTINCT FROM NEW.correo_electronico THEN
        UPDATE modulo1.cuentas_usuarios
        SET id_estado_cuenta = 1
        WHERE id_usuario = NEW.id_usuario;
    END IF;
    RETURN NEW;
END;
$$;

-- -----------------------------------------------------------------------------
-- Fix 2: trg_fn_validar_transicion_estado
-- Se agrega la transición Activo → Pendiente a la matriz de transiciones
-- permitidas, requerida por el flujo de verificación de correo en RF-05.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION modulo1.trg_fn_validar_transicion_estado()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
    v_estado_origen  VARCHAR(55);
    v_estado_destino VARCHAR(55);
BEGIN
    IF NEW.id_estado_cuenta = OLD.id_estado_cuenta THEN
        RETURN NEW;
    END IF;

    SELECT nombre INTO v_estado_origen
    FROM modulo1.estados_cuentas WHERE id_estado_cuenta = OLD.id_estado_cuenta;

    SELECT nombre INTO v_estado_destino
    FROM modulo1.estados_cuentas WHERE id_estado_cuenta = NEW.id_estado_cuenta;

    IF v_estado_origen = 'Eliminado' THEN
        RAISE EXCEPTION 'INVALID_TRANSITION: Una cuenta Eliminada no puede cambiar a %.', v_estado_destino
            USING ERRCODE = 'P0003';
    END IF;

    IF NOT (
        (v_estado_origen = 'Pendiente' AND v_estado_destino IN ('Activo', 'Eliminado'))
        OR (v_estado_origen = 'Activo'    AND v_estado_destino IN ('Pendiente', 'Inactivo', 'Bloqueado', 'Eliminado'))
        OR (v_estado_origen = 'Inactivo'  AND v_estado_destino IN ('Activo', 'Eliminado'))
        OR (v_estado_origen = 'Bloqueado' AND v_estado_destino IN ('Activo', 'Inactivo', 'Eliminado'))
    ) THEN
        RAISE EXCEPTION 'INVALID_TRANSITION: Transición no permitida (% → %).', v_estado_origen, v_estado_destino
            USING ERRCODE = 'P0003';
    END IF;

    NEW.fecha_cambio_estado := now();
    RETURN NEW;
END;
$$;

COMMIT;
