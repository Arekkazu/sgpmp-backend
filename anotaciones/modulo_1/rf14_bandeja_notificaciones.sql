-- RF-14: indice para la bandeja de notificaciones internas por usuario.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM modulo1.notificaciones_canal
        WHERE id_notificacion_canal = 2
          AND upper(btrim(nombre)) = 'INTERNO'
    ) THEN
        RAISE EXCEPTION
            'RF-14: id_notificacion_canal=2 no corresponde al canal INTERNO';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'modulo1'
          AND table_name = 'notificaciones'
          AND column_name = 'es_leido'
          AND data_type = 'boolean'
    ) THEN
        RAISE EXCEPTION
            'RF-14: modulo1.notificaciones.es_leido no existe o no es boolean';
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS ix_notificaciones_bandeja_usuario
ON modulo1.notificaciones (
    id_usuario,
    fecha_envio DESC,
    id_notificacion DESC
)
WHERE id_notificacion_canal = 2;

COMMIT;
