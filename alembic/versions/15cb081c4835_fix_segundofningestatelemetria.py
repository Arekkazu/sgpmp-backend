"""fix_segundoFnIngestaTelemetria

Revision ID: 15cb081c4835
Revises: e5a3c9b17d42
Create Date: 2026-10-21 22:07:13.078248

"""
from typing import Sequence, Union

import logging
import re

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '15cb081c4835'
down_revision: Union[str, Sequence[str], None] = 'e5a3c9b17d42'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


log = logging.getLogger("alembic.runtime.migration")

FN = (
    "modulo3.fn_ingesta_telemetria(integer, integer, integer, numeric, character varying, "
    "timestamp with time zone, timestamp with time zone, modulo3.enum_telemetria_origen, "
    "modulo3.enum_telemetria_categoria_variable, modulo3.enum_telemetria_tipo_dato, boolean, "
    "integer, numeric, numeric, numeric, numeric, numeric, boolean, jsonb)"
)
TABLA_TEL = "modulo3.telemetrias"
UQ_DUPLICADO = "uq_sensor_variable_timepo_captura_origen"
UQ_VIGENTE = "uq_telemetria_sensor_variable_captura_origen"

# E13: una lectura es anómala si hay otra del mismo sensor/variable a menos de
# FACTOR_FRECUENCIA_MIN x frecuencia_muestreo (M09, en minutos). Solo marca, no rechaza.
FACTOR_FRECUENCIA_MIN = 0.5
SEG_UMBRAL_POR_MINUTO = int(60 * FACTOR_FRECUENCIA_MIN)


# --------------------------------------------------------------------------
# Helpers de ejecución
# --------------------------------------------------------------------------
def _fetch(sql: str, **params):
    return op.get_bind().execute(sa.text(sql), params).all()


def _sql(sql: str) -> None:
    # Se escapan todos los ':' para que text() no los interprete como bind params (::, :=, 'X: ...').
    op.execute(sa.text(sql.replace(":", r"\:")))


def _definicion_actual() -> str:
    # Se parcha la definición VIGENTE (no un texto fijo): conserva lo que haya reescrito DB-06.
    return op.get_bind().execute(
        sa.text("SELECT pg_get_functiondef(CAST(:f AS regprocedure))"), {"f": FN}
    ).scalar_one()


# --------------------------------------------------------------------------
# DDL: constraint único duplicado
# --------------------------------------------------------------------------
def _def_constraint(nombre: str) -> str | None:
    f = _fetch(
        "SELECT pg_get_constraintdef(c.oid) FROM pg_constraint c "
        "WHERE c.conrelid = CAST(:t AS regclass) AND c.conname = :n",
        t=TABLA_TEL, n=nombre,
    )
    return f[0][0] if f else None


def _quitar_constraint_duplicado() -> None:
    dup, ok = _def_constraint(UQ_DUPLICADO), _def_constraint(UQ_VIGENTE)
    if dup is None:
        log.info("RF-53: %s ya no existe; nada que quitar.", UQ_DUPLICADO)
        return
    if ok is None:
        raise RuntimeError(f"{UQ_VIGENTE} no existe: quitar {UQ_DUPLICADO} dejaría la tabla sin unicidad")
    if dup != ok:
        raise RuntimeError(f"Los constraints no son equivalentes: {dup} vs {ok}")
    usados = _fetch(
        "SELECT p.oid::regproc::text FROM pg_proc p "
        "WHERE p.prosrc ILIKE :pat AND p.pronamespace NOT IN "
        "(SELECT oid FROM pg_namespace WHERE nspname IN ('pg_catalog', 'information_schema'))",
        pat=f"%{UQ_DUPLICADO}%",
    )
    if usados:
        raise RuntimeError(f"Funciones que referencian {UQ_DUPLICADO} (ON CONFLICT ON CONSTRAINT): {usados}")
    op.execute(f"ALTER TABLE {TABLA_TEL} DROP CONSTRAINT IF EXISTS {UQ_DUPLICADO}")


def _recrear_constraint_duplicado() -> None:
    if _def_constraint(UQ_DUPLICADO) is not None:
        return
    ok = _def_constraint(UQ_VIGENTE)
    if ok is None:
        raise RuntimeError(f"{UQ_VIGENTE} no existe: no se puede derivar la definición de {UQ_DUPLICADO}")
    # Misma definición que el vigente (UNIQUE (id_sensor, id_variable, timestamp_captura, origen)).
    op.execute(f"ALTER TABLE {TABLA_TEL} ADD CONSTRAINT {UQ_DUPLICADO} {ok}")


# --------------------------------------------------------------------------
# Preflight de columnas que usa la función nueva
# --------------------------------------------------------------------------
def _columnas(esquema: str, tabla: str) -> set[str]:
    return {
        r[0] for r in _fetch(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = :e AND table_name = :t", e=esquema, t=tabla,
        )
    }


def _preflight() -> str:
    asoc = _columnas("modulo9", "sensores_areas_asociadas")
    if "es_activo" not in asoc:
        raise RuntimeError("modulo9.sensores_areas_asociadas no existe o no tiene es_activo")
    col_sensor = next((c for c in ("id_sensor", "id_sensores") if c in asoc), None)
    if col_sensor is None:
        raise RuntimeError("modulo9.sensores_areas_asociadas no tiene id_sensor ni id_sensores")
    extra = asoc & {"fecha_fin", "estado_asociacion"}
    if extra:
        log.warning("RF-53: sensores_areas_asociadas tiene %s; el predicado usa solo es_activo = TRUE. Revísalo.", sorted(extra))
    if "estado_operativo" not in _columnas("modulo9", "dispositivos_iot"):
        raise RuntimeError("modulo9.dispositivos_iot no tiene estado_operativo")
    if "frecuencia_muestreo" not in _columnas("modulo9", "configuraciones_globales"):
        raise RuntimeError("modulo9.configuraciones_globales no tiene frecuencia_muestreo")
    return col_sensor


# --------------------------------------------------------------------------
# Bloques PL/pgSQL (delimitados por marcadores para poder revertirlos exactamente)
# --------------------------------------------------------------------------
def _bloque_a(col_sensor: str) -> str:
    def rechazo(motivo: str, mensaje: str, extra: str = "") -> str:
        return f"""                INSERT INTO modulo3.bitacora_ingest (
                    id_dispositivo_iot,
                    id_sensor,
                    estado_calidad,
                    descripcion_text,
                    payload_recibido,
                    fecha_evento,
                    fecha_captura_dato
                )
                VALUES (
                    p_id_dispositivo,
                    p_id_sensor,
                    'ERROR_AUTENTICACION'::modulo3.enum_bitacora_ingest_estado_calidad,
                    '{mensaje}',
                    jsonb_build_object(
                        'id_dispositivo_recibido', p_id_dispositivo,
                        'id_sensor_recibido', p_id_sensor,
                        'valor_crudo', p_valor_crudo,
                        'motivo', '{motivo}'{extra}
                    ),
                    v_ts_procesamiento,
                    p_timestamp_captura
                );

                RETURN QUERY SELECT NULL::INTEGER,
                                    NULL::modulo3.enum_telemetria_estado_calidad,
                                    '{mensaje}'::TEXT;
                RETURN;
"""

    return f"""            -- >>> RFC053_A_INICIO
            ----------------------------------------------------------------------------
            -- FASE 2.5: MANTENIMIENTO Y ASOCIACION A UNIDAD PRODUCTIVA (RF-60, G-05/G-07)
            -- Se reutiliza el prefijo ERROR_AUTENTICACION del contrato D2 (E1): el broker no cambia.
            ----------------------------------------------------------------------------
            IF EXISTS (
                SELECT 1
                FROM modulo9.dispositivos_iot d_mto
                WHERE d_mto.id_dispositivo_iot = p_id_dispositivo
                  AND d_mto.estado_operativo::text = 'EN_MANTENIMIENTO'
            ) THEN
{rechazo('EN_MANTENIMIENTO', 'ERROR_AUTENTICACION: Dispositivo en mantenimiento.')}            END IF;

            IF NOT EXISTS (
                SELECT 1
                FROM modulo9.sensores_areas_asociadas saa
                WHERE saa.{col_sensor} = p_id_sensor
                  AND saa.es_activo = TRUE
            ) THEN
{rechazo('SENSOR_SIN_ASOCIACION', 'ERROR_AUTENTICACION: Sensor no asociado a una unidad productiva.')}            END IF;
            -- <<< RFC053_A_FIN

"""


def _bloque_b() -> str:
    ventana = f"((v_frecuencia_esp * {SEG_UMBRAL_POR_MINUTO})::DOUBLE PRECISION * INTERVAL '1 second')"
    return f"""            -- >>> RFC053_B_INICIO
            ----------------------------------------------------------------------------
            -- FASE 8.5: FRECUENCIA ANOMALA (E13, G-07)
            -- Solo MARCA, no rechaza. Anomala = existe otra lectura del mismo sensor/variable
            -- a menos de {FACTOR_FRECUENCIA_MIN} x frecuencia_muestreo (M09, minutos), antes o despues
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
                          AND t_frec.timestamp_captura > p_timestamp_captura - {ventana}
                          AND t_frec.timestamp_captura < p_timestamp_captura + {ventana}
                          AND t_frec.timestamp_captura <> p_timestamp_captura
                    );
                END IF;
            END IF;
            -- <<< RFC053_B_FIN

"""


LINEA_LATENCIA_ORIGINAL = "v_latencia_ms   := EXTRACT(EPOCH FROM (v_ts_procesamiento - p_timestamp_envio))::INTEGER * 1000;"
# E4: contra timestamp_captura. Se acota a +-2147483 s (~24.8 dias) para que *1000 no desborde INTEGER:
# con captura (no con envio) una lectura antigua o futura abortaria la ingesta en vez de rechazarse limpiamente.
LINEA_LATENCIA_NUEVA = (
    "v_latencia_ms   := LEAST(GREATEST(ROUND(EXTRACT(EPOCH FROM (v_ts_procesamiento - p_timestamp_captura))), "
    "-2147483), 2147483)::INTEGER * 1000;  -- RFC053_LAT"
)

ANCLA_FASE_3 = r"[ \t]*-{10,}[ \t]*\r?\n[ \t]*-- FASE 3: COHERENCIA TEMPORAL"
ANCLA_FASE_9 = r"[ \t]*-{10,}[ \t]*\r?\n[ \t]*-- FASE 9: PERSISTENCIA FINAL EN TELEMETRIAS"


def _una_vez(patron: str, src: str, reemplazo, flags: int = 0) -> str:
    repl = reemplazo if callable(reemplazo) else (lambda _m: reemplazo)
    nuevo, n = re.subn(patron, repl, src, flags=flags)
    if n != 1:
        raise RuntimeError(f"Parche RF-53 aplicó {n} veces (esperado 1): {patron[:70]}")
    return nuevo


def _insertar_antes(src: str, patron: str, bloque: str) -> str:
    ms = list(re.finditer(patron, src))
    if len(ms) != 1:
        raise RuntimeError(f"Ancla RF-53 encontrada {len(ms)} veces (esperado 1): {patron[:70]}")
    i = ms[0].start()
    return src[:i] + bloque + src[i:]


def _aplicar(src: str, col_sensor: str) -> str:
    if "RFC053_" in src:
        raise RuntimeError("fn_ingesta_telemetria ya contiene la versión RF-53")
    s = _una_vez(
        r"v_latencia_ms\s*:=\s*EXTRACT\(EPOCH FROM \(v_ts_procesamiento - p_timestamp_envio\)\)::INTEGER\s*\*\s*1000;",
        src, LINEA_LATENCIA_NUEVA,
    )
    s = _una_vez(
        r"(v_frecuencia_esp\s+INTEGER\s*:=\s*NULL;)",
        s,
        lambda m: m.group(1) + "\n            v_frecuencia_anomala  BOOLEAN := FALSE;  -- RFC053_DECL",
    )
    s = _insertar_antes(s, ANCLA_FASE_3, _bloque_a(col_sensor))
    s = _insertar_antes(s, ANCLA_FASE_9, _bloque_b())
    s = _una_vez(r"FALSE,\s*--\s*frecuencia_anomala", s, "v_frecuencia_anomala, -- frecuencia_anomala RFC053_INS")
    return s


def _revertir(src: str) -> str:
    for marca in ("RFC053_A_INICIO", "RFC053_B_INICIO", "RFC053_DECL", "RFC053_INS", "RFC053_LAT"):
        if marca not in src:
            raise RuntimeError(f"fn_ingesta_telemetria no contiene la marca {marca}: no es la versión RF-53")
    s = src
    for bloque in ("A", "B"):
        s = _una_vez(
            rf"[ \t]*-- >>> RFC053_{bloque}_INICIO.*?-- <<< RFC053_{bloque}_FIN[ \t]*\r?\n\r?\n",
            s, "", flags=re.DOTALL,
        )
    s = _una_vez(r"\r?\n[ \t]*v_frecuencia_anomala[^\n]*RFC053_DECL", s, "")
    s = _una_vez(r"v_frecuencia_anomala,\s*--\s*frecuencia_anomala RFC053_INS", s, "FALSE, -- frecuencia_anomala")
    s = _una_vez(r"v_latencia_ms\s*:=[^\n]*--\s*RFC053_LAT", s, LINEA_LATENCIA_ORIGINAL)
    if "RFC053_" in s:
        raise RuntimeError("Quedaron marcas RFC053 tras revertir")
    return s


# --------------------------------------------------------------------------
# Migración
# --------------------------------------------------------------------------
def upgrade() -> None:
    col_sensor = _preflight()
    _quitar_constraint_duplicado()
    _sql(_aplicar(_definicion_actual(), col_sensor))


def downgrade() -> None:
    _sql(_revertir(_definicion_actual()))
    _recrear_constraint_duplicado()