# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-27 | Leandro | INC-M03-132-G30 RF-53/54/62: calcular snapshot TIME_DESYNC en la funcion comun sin cambiar firma ni historicos. |
"""RF-54 E9: snapshot de reloj antes de insertar la telemetria inmutable.

Revision ID: c687132a0270
Revises: ebbb160365e5

Conserva firma, atributos y otras correcciones de la funcion vigente.
No reconstruye estados historicos ni actualiza lecturas existentes.
"""
import re
from alembic import op
import sqlalchemy as sa

revision = 'c687132a0270'
down_revision = 'ebbb160365e5'
branch_labels = None
depends_on = None
FN = (
    'modulo3.fn_ingesta_telemetria(integer, integer, integer, numeric, character varying, '
    'timestamp with time zone, timestamp with time zone, modulo3.enum_telemetria_origen, '
    'modulo3.enum_telemetria_categoria_variable, modulo3.enum_telemetria_tipo_dato, boolean, '
    'integer, numeric, numeric, numeric, numeric, numeric, boolean, jsonb)'
)
_DECLARACIONES = """            v_reloj_sincronizado BOOLEAN; -- G33_RELOJ_DECL
            v_reloj_desincronizado BOOLEAN := FALSE; -- G33_RELOJ_DECL
            v_fuente_reloj TEXT := 'SIN_EVIDENCIA'; -- G33_RELOJ_DECL
            v_id_heartbeat_reloj INTEGER; -- G33_RELOJ_DECL
            v_fecha_heartbeat_reloj TIMESTAMPTZ; -- G33_RELOJ_DECL
"""
_BLOQUE = """            -- >>> G33_RELOJ_INICIO
            -- La evidencia de captura prevalece. El heartbeat es solamente el
            -- ultimo estado conocido al ingerir, no una reconstruccion historica.
            IF v_metadatos ? 'reloj_sincronizado'
               AND jsonb_typeof(v_metadatos->'reloj_sincronizado') NOT IN ('boolean', 'null') THEN
                INSERT INTO modulo3.bitacora_ingest (
                    id_dispositivo_iot, id_sensor, estado_calidad, descripcion_text,
                    payload_recibido, fecha_evento, fecha_captura_dato
                ) VALUES (
                    p_id_dispositivo, p_id_sensor,
                    'ERROR_ESTRUCTURA'::modulo3.enum_bitacora_ingest_estado_calidad,
                    'ERROR_ESTRUCTURA: reloj_sincronizado debe ser booleano.',
                    jsonb_build_object('campo', 'reloj_sincronizado'),
                    v_ts_procesamiento, p_timestamp_captura
                );
                RETURN QUERY SELECT NULL::INTEGER,
                    NULL::modulo3.enum_telemetria_estado_calidad,
                    'ERROR_ESTRUCTURA: reloj_sincronizado debe ser booleano.'::TEXT;
                RETURN;
            END IF;

            IF jsonb_typeof(v_metadatos->'reloj_sincronizado') = 'boolean' THEN
                v_reloj_sincronizado := (v_metadatos->>'reloj_sincronizado')::BOOLEAN;
                v_fuente_reloj := 'LECTURA';
            ELSE
                SELECT h.reloj_sincronizado, h.id_heartbeat, h.fecha_recepcion
                INTO v_reloj_sincronizado, v_id_heartbeat_reloj, v_fecha_heartbeat_reloj
                FROM modulo3.heartbeats h
                WHERE h.id_dispositivo_iot = p_id_dispositivo
                  AND h.fecha_recepcion <= v_ts_procesamiento
                ORDER BY h.fecha_recepcion DESC, h.id_heartbeat DESC
                LIMIT 1;
                IF FOUND THEN
                    v_fuente_reloj := 'HEARTBEAT';
                END IF;
            END IF;

            v_reloj_desincronizado := v_reloj_sincronizado IS FALSE;
            v_metadatos := v_metadatos || jsonb_build_object('rf53_reloj', jsonb_build_object(
                'reloj_sincronizado', v_reloj_sincronizado,
                'reloj_desincronizado', v_reloj_desincronizado,
                'codigo', CASE WHEN v_reloj_desincronizado THEN 'TIME_DESYNC' ELSE NULL END,
                'fuente', v_fuente_reloj,
                'id_heartbeat', v_id_heartbeat_reloj,
                'fecha_recepcion_heartbeat', v_fecha_heartbeat_reloj,
                'instante_decision', v_ts_procesamiento,
                'alcance', CASE v_fuente_reloj
                    WHEN 'LECTURA' THEN 'CAPTURA_REPORTADA'
                    WHEN 'HEARTBEAT' THEN 'ESTADO_CONOCIDO_AL_INGERIR'
                    ELSE 'SIN_EVIDENCIA' END
            ));
            -- <<< G33_RELOJ_FIN

"""
_COLUMNA = 'reloj_desincronizado, -- G33_RELOJ_COLUMNA'
_VALOR = 'v_reloj_desincronizado, -- G33_RELOJ_VALOR'
_INSERT = r'(INSERT INTO modulo3\.telemetrias\s*\()(.*?)(\)\s*VALUES\s*\()(.*?)(\)\s*RETURNING)'


def _una_vez(patron, src, reemplazo, *, flags=0):
    nuevo, cantidad = re.subn(patron, reemplazo, src, flags=flags)
    if cantidad != 1:
        raise RuntimeError('G33: la funcion vigente no tiene una unica version del bloque esperado.')
    return nuevo


def _transformar(src, *, revertir=False):
    if revertir:
        if src.count(_BLOQUE) != 1 or src.count(_DECLARACIONES) != 1:
            raise RuntimeError('G33: no se encontro el snapshot de reloj esperado.')
        src = src.replace(_BLOQUE, '', 1).replace(_DECLARACIONES, '', 1)
    else:
        if 'G33_RELOJ_' in src:
            raise RuntimeError('G33: la funcion ya contiene el snapshot de reloj.')
        src = _una_vez(r'(v_metadatos[ \t]+JSONB;\r?\n)', src,
                       lambda m: m.group(0) + _DECLARACIONES)
        src = _una_vez(r'([ \t]*-{10,}[ \t]*\r?\n[ \t]*-- FASE 9: PERSISTENCIA FINAL EN TELEMETRIAS)',
                       src, lambda m: _BLOQUE + m.group(0))

    def cambiar_insert(m):
        columnas, valores = m.group(2), m.group(4)
        if revertir:
            columnas = _una_vez(r'(?m)^[ \t]*'+re.escape(_COLUMNA)+r'\r?\n',columnas,'')
            valores = _una_vez(r'(?m)^[ \t]*'+re.escape(_VALOR)+r'\r?\n',valores,'')
        else:
            if re.search(r'\breloj_desincronizado\b', columnas):
                raise RuntimeError('G33: el INSERT ya contiene reloj_desincronizado; revisar su implementacion.')
            columnas = _una_vez(r'(?m)^([ \t]*)calidad_senal_snr,[ \t]*(\r?\n)', columnas,
                lambda x: x.group(0)+x.group(1)+_COLUMNA+x.group(2))
            valores = _una_vez(r'(?m)^([ \t]*)v_snr,[ \t]*(\r?\n)', valores,
                lambda x: x.group(0)+x.group(1)+_VALOR+x.group(2))
        return m.group(1)+columnas+m.group(3)+valores+m.group(5)

    return _una_vez(_INSERT, src, cambiar_insert, flags=re.DOTALL)


def _actualizar(*, revertir=False):
    bind = op.get_bind()
    actual = bind.execute(sa.text('SELECT pg_get_functiondef(CAST(:firma AS regprocedure))'),
                          {'firma': FN}).scalar_one()
    nueva = _transformar(actual, revertir=revertir)
    op.execute(sa.text(nueva.replace(':', r'\:')))


def upgrade():
    _actualizar()


def downgrade():
    _actualizar(revertir=True)
