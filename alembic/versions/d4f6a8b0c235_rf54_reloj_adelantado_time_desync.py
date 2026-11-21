# | Fecha      | Nombre | Que se hizo                                                                   |
# |------------|--------|-------------------------------------------------------------------------------|
# | 2026-10-31 | Claude | INC-M03-238-G30 RF-53/54: lectura con reloj adelantado y sin sincronizar entra TIME_DESYNC |
"""rf54: captura futura con reloj_sincronizado=false se guarda TIME_DESYNC

Revision ID: d4f6a8b0c235
Revises: c3e5f7a9b124
Create Date: 2026-10-31

INC-M03-238-G30 (#877, TC-M03-049). Con el reloj del dispositivo atrasado, las
lecturas del buffer se aceptan y quedan TIME_DESYNC (sin aptitud para IA ni NIC 41).
Con el reloj adelantado, `fn_ingesta_telemetria` las rechazaba con ERROR_TIEMPO
("timestamp_captura futuro") antes de considerar la marca de reloj, y se perdían.

Ahora, si la lectura misma declara `reloj_sincronizado = false`, una captura futura
no se rechaza: sigue el flujo normal y el bloque G33 la marca TIME_DESYNC. Sin esa
declaración el rechazo se conserva (un reloj que dice estar sincronizado y fecha en
el futuro sigue siendo un dato inválido). Tope: 72 h hacia adelante, simétrico al
límite de antigüedad del buffer; más allá sigue siendo ERROR_TIEMPO.

Mismo patrón que c687132a0270: se reescribe solo la condición, sobre la definición
vigente, sin cambiar firma ni atributos de la función.

El trigger `trg_rf53_01_validar_timestamp` (BEFORE INSERT) repetía el rechazo sobre la
fila: `fn_validar_timestamp_telemetria` acepta ahora la captura futura solo si la fila
llega con `reloj_desincronizado = TRUE` (lo fija el bloque G33) y dentro de 72 h.

`chk_timestamp_coherencia` (captura <= procesamiento) admite la misma excepción. Se
conserva su nombre (no se renombra retroactivamente, ver convención de BD).
"""
import re

import sqlalchemy as sa
from alembic import op

revision = 'd4f6a8b0c235'
down_revision = 'c3e5f7a9b124'
branch_labels = None
depends_on = None

FN = (
    'modulo3.fn_ingesta_telemetria(integer, integer, integer, numeric, character varying, '
    'timestamp with time zone, timestamp with time zone, modulo3.enum_telemetria_origen, '
    'modulo3.enum_telemetria_categoria_variable, modulo3.enum_telemetria_tipo_dato, boolean, '
    'integer, numeric, numeric, numeric, numeric, numeric, boolean, jsonb)'
)
_ORIGINAL = 'IF p_timestamp_captura > v_ts_procesamiento THEN'
# COALESCE: sin la clave, la comparación JSON es NULL y NOT NULL dejaría pasar la captura futura.
_NUEVA = """IF p_timestamp_captura > v_ts_procesamiento -- G30B_RELOJ_FUTURO
               AND NOT COALESCE(v_metadatos->'reloj_sincronizado' = 'false'::jsonb
                        AND p_timestamp_captura <= v_ts_procesamiento + INTERVAL '72 hours', FALSE) THEN"""


def _transformar(src: str, revertir: bool = False) -> str:
    origen, destino = (_NUEVA, _ORIGINAL) if revertir else (_ORIGINAL, _NUEVA)
    if src.count(origen) != 1:
        raise RuntimeError('G30B: la función vigente no tiene una única validación de captura futura esperada.')
    nueva = src.replace(origen, destino, 1)
    # v_metadatos debe estar asignado antes de la validación (FASE 3).
    if not revertir and not re.search(r"v_metadatos\s*:=\s*COALESCE\(p_metadatos", nueva[:nueva.index(destino)]):
        raise RuntimeError('G30B: v_metadatos no está disponible antes de la validación temporal.')
    return nueva


def _actualizar(revertir: bool = False) -> None:
    bind = op.get_bind()
    actual = bind.execute(sa.text('SELECT pg_get_functiondef(CAST(:firma AS regprocedure))'),
                          {'firma': FN}).scalar_one()
    op.execute(sa.text(_transformar(actual, revertir).replace(':', r'\:')))


_TRIGGER_ORIGINAL = """
CREATE OR REPLACE FUNCTION modulo3.fn_validar_timestamp_telemetria()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN
    IF NEW.timestamp_captura > now() THEN
        RAISE EXCEPTION
            'RF-53 [ERROR_TIEMPO]: timestamp_captura (%) es posterior a la hora actual. Dato rechazado.',
            NEW.timestamp_captura
            USING ERRCODE = 'P0001';
    END IF;
    RETURN NEW;
END;
$function$
"""

_TRIGGER_NUEVO = """
CREATE OR REPLACE FUNCTION modulo3.fn_validar_timestamp_telemetria()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN
    -- G30B (RF-54 E9): un reloj declarado sin sincronizar puede ir adelantado; la
    -- fila llega marcada TIME_DESYNC y sin aptitud. Más de 72 h sigue siendo inválido.
    IF NEW.timestamp_captura > now()
       AND NOT (NEW.reloj_desincronizado IS TRUE
                AND NEW.timestamp_captura <= now() + INTERVAL '72 hours') THEN
        RAISE EXCEPTION
            'RF-53 [ERROR_TIEMPO]: timestamp_captura (%) es posterior a la hora actual. Dato rechazado.',
            NEW.timestamp_captura
            USING ERRCODE = 'P0001';
    END IF;
    RETURN NEW;
END;
$function$
"""


def _coherencia(condicion: str) -> None:
    op.execute('ALTER TABLE modulo3.telemetrias DROP CONSTRAINT IF EXISTS chk_timestamp_coherencia')
    # NOT VALID + VALIDATE: no bloquea escrituras mientras revisa las filas existentes.
    op.execute(f'ALTER TABLE modulo3.telemetrias ADD CONSTRAINT chk_timestamp_coherencia CHECK ({condicion}) NOT VALID')
    op.execute('ALTER TABLE modulo3.telemetrias VALIDATE CONSTRAINT chk_timestamp_coherencia')


def upgrade() -> None:
    _actualizar()
    op.execute(_TRIGGER_NUEVO)
    _coherencia('timestamp_captura <= timestamp_procesamiento OR reloj_desincronizado IS TRUE')


def downgrade() -> None:
    _coherencia('timestamp_captura <= timestamp_procesamiento')
    op.execute(_TRIGGER_ORIGINAL)
    _actualizar(revertir=True)
