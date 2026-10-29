# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-27 | Leandro | INC-M03-130-G16 RF-53/62: corregir frecuencia lenta y conservar muestreo aplicado en la funcion comun. |
"""RF-53 E13: marcar frecuencia lenta y conservar el intervalo aplicado.

Revision ID: c685130a0260
Revises: ebbb160365e5

Parche reversible de la definicion vigente. Preserva firma, propietario,
privilegios, validaciones, snapshot RF-24 y contexto multiespecie.
El drift permanece en RF-62 y no se actualizan lecturas inmutables.
"""
from alembic import op
import sqlalchemy as sa

revision = 'c685130a0260'
down_revision = 'ebbb160365e5'
branch_labels = None
depends_on = None

FN = (
    'modulo3.fn_ingesta_telemetria(integer, integer, integer, numeric, character varying, '
    'timestamp with time zone, timestamp with time zone, modulo3.enum_telemetria_origen, '
    'modulo3.enum_telemetria_categoria_variable, modulo3.enum_telemetria_tipo_dato, boolean, '
    'integer, numeric, numeric, numeric, numeric, numeric, boolean, jsonb)'
)
_BLOQUE_ANTERIOR = """            -- >>> RFC053_B_INICIO
            ----------------------------------------------------------------------------
            -- FASE 8.5: FRECUENCIA ANOMALA (E13, G-07)
            -- Solo MARCA, no rechaza. Anomala = existe otra lectura del mismo sensor/variable
            -- a menos de 0.5 x frecuencia_muestreo (M09, minutos), antes o despues
            -- (los datos buferizados pueden llegar desordenados). Se acota la busqueda a esa ventana
            -- para usar el indice unico (id_sensor, id_variable, timestamp_captura) y podar particiones.
            -- Los EVENTO_EDGE no son periodicos: no se evaluan.
            ----------------------------------------------------------------------------
            v_frecuencia_anomala := FALSE;
            IF NOT (v_tipo_dato = 'EVENTO_EDGE') THEN
                SELECT cg.frecuencia_muestreo INTO v_frecuencia_esp
                FROM modulo9.configuraciones_globales cg
                WHERE cg.es_activo = TRUE
                LIMIT 1;

                IF v_frecuencia_esp IS NOT NULL AND v_frecuencia_esp > 0 THEN
                    v_frecuencia_anomala := EXISTS (
                        SELECT 1
                        FROM modulo3.telemetrias t_frec
                        WHERE t_frec.id_sensor = p_id_sensor
                          AND t_frec.id_variable = p_id_variable
                          AND t_frec.timestamp_captura > p_timestamp_captura - ((v_frecuencia_esp * 30)::DOUBLE PRECISION * INTERVAL '1 second')
                          AND t_frec.timestamp_captura < p_timestamp_captura + ((v_frecuencia_esp * 30)::DOUBLE PRECISION * INTERVAL '1 second')
                          AND t_frec.timestamp_captura <> p_timestamp_captura
                    );
                END IF;
            END IF;
            -- <<< RFC053_B_FIN

"""
_BLOQUE_NUEVO = """            -- >>> G31_FRECUENCIA_INICIO
            -- RF-53 E13: intervalo al vecino cronologico mas cercano del mismo
            -- sensor/variable. Conserva el limite inferior existente (0.5x)
            -- y usa el limite superior de consistencia temporal RF-62 (2x).
            -- Solo marca la nueva lectura: no rechaza ni modifica el historial.
            -- Dos busquedas LIMIT 1 aprovechan el indice sensor/variable/captura
            -- y permiten recibir BUFFER_LOCAL fuera de orden.
            v_frecuencia_anomala := FALSE;
            IF NOT (v_tipo_dato = 'EVENTO_EDGE') THEN
                SELECT cg.frecuencia_muestreo INTO v_frecuencia_esp
                FROM modulo9.configuraciones_globales cg
                WHERE cg.es_activo = TRUE
                LIMIT 1;

                IF v_frecuencia_esp IS NOT NULL AND v_frecuencia_esp > 0 THEN
                    SELECT COALESCE(
                        MIN(vecinos.intervalo_segundos) < v_frecuencia_esp::NUMERIC * 30
                        OR MIN(vecinos.intervalo_segundos) > v_frecuencia_esp::NUMERIC * 120,
                        FALSE
                    ) INTO v_frecuencia_anomala
                    FROM (
                        (SELECT EXTRACT(EPOCH FROM (p_timestamp_captura - t.timestamp_captura)) AS intervalo_segundos
                         FROM modulo3.telemetrias t
                         WHERE t.id_sensor = p_id_sensor AND t.id_variable = p_id_variable
                           AND t.tipo_dato <> 'EVENTO_EDGE'
                           AND t.timestamp_captura < p_timestamp_captura
                         ORDER BY t.timestamp_captura DESC LIMIT 1)
                        UNION ALL
                        (SELECT EXTRACT(EPOCH FROM (t.timestamp_captura - p_timestamp_captura)) AS intervalo_segundos
                         FROM modulo3.telemetrias t
                         WHERE t.id_sensor = p_id_sensor AND t.id_variable = p_id_variable
                           AND t.tipo_dato <> 'EVENTO_EDGE'
                           AND t.timestamp_captura > p_timestamp_captura
                         ORDER BY t.timestamp_captura ASC LIMIT 1)
                    ) vecinos;
                END IF;
            END IF;
            -- <<< G31_FRECUENCIA_FIN

"""
_FRECUENCIA_ANTERIOR = 'NULL, -- frecuencia_muestreo_min (fijo en nulo por ahora)'
_FRECUENCIA_NUEVA = 'v_frecuencia_esp, -- G31_FRECUENCIA_SNAPSHOT'


def _reemplazar_una_vez(src, anterior, nuevo):
    if src.count(anterior) != 1:
        raise RuntimeError('G31: la funcion vigente no tiene el bloque esperado; revisar antes de migrar.')
    return src.replace(anterior, nuevo, 1)


def _transformar(src, *, revertir=False):
    anterior, nuevo = (_BLOQUE_NUEVO, _BLOQUE_ANTERIOR) if revertir else (_BLOQUE_ANTERIOR, _BLOQUE_NUEVO)
    resultado = _reemplazar_una_vez(src, anterior, nuevo)
    anterior, nuevo = ((_FRECUENCIA_NUEVA, _FRECUENCIA_ANTERIOR) if revertir
                       else (_FRECUENCIA_ANTERIOR, _FRECUENCIA_NUEVA))
    return _reemplazar_una_vez(resultado, anterior, nuevo)


def _actualizar(*, revertir=False):
    bind = op.get_bind()
    actual = bind.execute(sa.text('SELECT pg_get_functiondef(CAST(:firma AS regprocedure))'),
                          {'firma': FN}).scalar_one()
    nueva = _transformar(actual, revertir=revertir)
    # No reinterpretar los casts :: ni las asignaciones := como binds.
    op.execute(sa.text(nueva.replace(':', r'\:')))


def upgrade():
    _actualizar()


def downgrade():
    _actualizar(revertir=True)
