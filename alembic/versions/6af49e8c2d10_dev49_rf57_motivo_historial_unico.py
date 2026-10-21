# | Fecha      | Nombre  | Que se hizo                                          |
# |------------|---------|------------------------------------------------------|
# | 2026-10-21 | Leandro | DEV-49 RF-57: conserva motivo en el historial unico  |
"""Conservar el motivo manual al delegar el historial al trigger de RF-57.

Revision ID: 6af49e8c2d10
Revises: e5a3c9b17d42

No cambia estados, tablas ni permisos. El contexto local evita perder el motivo
de EN_ATENCION/RESUELTA que antes solo guardaba el INSERT redundante de Python.
"""
from alembic import op
import sqlalchemy as sa

revision = "6af49e8c2d10"
down_revision = "e5a3c9b17d42"
branch_labels = None
depends_on = None

_MOTIVO_ANTERIOR = """CASE NEW.estado_alerta
            WHEN 'VENCIDA' THEN 'SLA vencido sin atención'
            WHEN 'DESCARTADA' THEN COALESCE(NEW.motivo_descarte, 'Descarte manual')
            WHEN 'RESUELTA' THEN COALESCE(NEW.diagnostico, 'Resolución confirmada')
            ELSE NULL
        END"""


def _funcion(motivo):
    return f"""
CREATE OR REPLACE FUNCTION modulo3.fn_alerta_validar_transicion()
RETURNS trigger LANGUAGE plpgsql AS $function$
BEGIN
    IF OLD.estado_alerta = NEW.estado_alerta THEN
        RETURN NEW;
    END IF;
    IF NOT (
        (OLD.estado_alerta = 'ACTIVA' AND NEW.estado_alerta IN ('EN_ATENCION','DESCARTADA','VENCIDA','PENDIENTE_SINCRONIZACION')) OR
        (OLD.estado_alerta = 'EN_ATENCION' AND NEW.estado_alerta IN ('RESUELTA','VENCIDA'))
    ) THEN
        RAISE EXCEPTION 'RF-57 [TRANSICION_INVALIDA]: % → % no permitida. id_alerta=%',
            OLD.estado_alerta, NEW.estado_alerta, OLD.id_alerta USING ERRCODE = 'P0005';
    END IF;
    IF NEW.estado_alerta = 'EN_ATENCION' THEN
        NEW.fecha_atencion := COALESCE(NEW.fecha_atencion, now());
    ELSIF NEW.estado_alerta IN ('RESUELTA','DESCARTADA','VENCIDA') THEN
        NEW.fecha_resolucion := COALESCE(NEW.fecha_resolucion, now());
    END IF;
    INSERT INTO modulo3.historico_estados_alertas (
        id_alerta, estado_anterior, estado_nuevo, id_usuario, motivo, fecha_cambio
    ) VALUES (
        NEW.id_alerta, OLD.estado_alerta, NEW.estado_alerta,
        COALESCE(NEW.id_usuario_resolucion, NEW.id_usuario_atencion),
        {motivo}, now()
    );
    RETURN NEW;
END;
$function$;
"""


def upgrade():
    motivo = "COALESCE(NULLIF(current_setting('app.rf57_motivo_transicion', true), ''), " + _MOTIVO_ANTERIOR + ")"
    op.execute(sa.text(_funcion(motivo)))
    motivo_inicial = """COALESCE(
        CASE WHEN NEW.tipo_alerta = 'TECNICA' THEN NULLIF(NEW.metadato_evento->>'motivo_generacion', '') END,
        'Alerta creada · origen=' || NEW.origen_evento::text)"""
    op.execute(sa.text(_funcion_inicial(motivo_inicial)))


def downgrade():
    op.execute(sa.text(_funcion(_MOTIVO_ANTERIOR)))
    op.execute(sa.text(_funcion_inicial("'Alerta creada · origen=' || NEW.origen_evento::text")))


def _funcion_inicial(motivo):
    return f"""
CREATE OR REPLACE FUNCTION modulo3.fn_alerta_historico_inicial()
RETURNS trigger LANGUAGE plpgsql AS $function$
BEGIN
    INSERT INTO modulo3.historico_estados_alertas (
        id_alerta, estado_anterior, estado_nuevo, motivo, fecha_cambio
    ) VALUES (
        NEW.id_alerta, NEW.estado_alerta, NEW.estado_alerta, {motivo}, now()
    );
    RETURN NEW;
END;
$function$;
"""
