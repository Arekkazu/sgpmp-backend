"""rf40 corrige unidad gr vs g y gaps de validacion en evento de crecimiento

Revision ID: 543cddec52a7
Revises: f19e0ca62445
Create Date: 2026-09-02 00:00:00.000000

RF-40 (anotaciones/modulo_2/estado_M02.md) — `trg_fn_evento_crecimiento_tipo_activo`
estaba desincronizado con el contrato real del sistema
(`RegistrarEventoCrecimientoDTO._UNIDADES_POR_TIPO`) en tres puntos:

1. Para PESO, el DTO acepta 'gr' como unidad valida pero el trigger solo
   aceptaba ('kg', 'g', 'lb') — 'g', no 'gr'. Un request que pasa Pydantic y
   el use case (contrato valido segun el propio sistema) era rechazado por
   el trigger en el INSERT, y por el gap de traduccion de errores de RF-39
   (`raise_from_db_error` no reconoce el ERRCODE P0218 propio del trigger)
   se convertia en HTTP 500 en vez de un 400 claro.
2. El trigger no validaba ninguna unidad para BIOMASA, dejando esa segunda
   capa de defensa incompleta frente al DTO (que exige 'kg/m2').
3. La rama que exige `tipo_agregacion` obligatorio para activos POBLACIONAL
   comparaba contra el literal `'poblacional'` (minuscula), pero
   `modulo2.enum_activo_biologico_tipo` solo tiene los valores 'INDIVIDUAL'
   y 'POBLACIONAL' (mayuscula) — esa rama nunca se ejecutaba. No era visible
   al usuario porque Python ya validaba correctamente antes, pero dejaba la
   regla sin reforzar a nivel de base de datos.

Se corrigen los tres puntos en la misma funcion. `downgrade()` restaura la
definicion previa (con los tres bugs) byte a byte igual a como existia en
la base de datos, incluidos los acentos de los mensajes originales.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '543cddec52a7'
down_revision: Union[str, Sequence[str], None] = 'f19e0ca62445'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
CREATE OR REPLACE FUNCTION modulo2.trg_fn_evento_crecimiento_tipo_activo()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
DECLARE
    v_tipo_activo   modulo2.enum_activo_biologico_tipo;
    v_tipo_medicion VARCHAR(55);
    v_unidad        VARCHAR(5);
BEGIN
    SELECT a.tipo INTO v_tipo_activo
    FROM modulo2.activos_biologicos a
    JOIN modulo2.eventos_activos ev ON ev.id_activo_biologico = a.id_activo_biologico
    WHERE ev.id_eventos = NEW.id_evento;

    v_tipo_medicion := UPPER(TRIM(NEW.tipo_medicion));
    v_unidad        := LOWER(TRIM(NEW.unidad_medida));

    -- Validar tipo_agregacion según tipo de activo
    IF v_tipo_activo = 'INDIVIDUAL' THEN
        IF NEW.tipo_agregacion IS NOT NULL AND TRIM(NEW.tipo_agregacion) <> '' THEN
            RAISE EXCEPTION 'INVALID_FIELD: Para activos INDIVIDUALES el campo tipo_agregacion debe ser nulo o vacío.'
            USING ERRCODE = 'P0216';
        END IF;
    ELSIF v_tipo_activo = 'POBLACIONAL' THEN
        IF NEW.tipo_agregacion IS NULL OR TRIM(NEW.tipo_agregacion) = '' THEN
            RAISE EXCEPTION 'MISSING_FIELD: Para activos LOTE (poblacional) el campo tipo_agregacion es obligatorio.'
            USING ERRCODE = 'P0216';
        END IF;
    END IF;

    -- Validar valor positivo
    IF NEW.valor_medicion <= 0 THEN
        RAISE EXCEPTION 'INVALID_VALUE: El valor de medición debe ser positivo y mayor a cero. Valor recibido: %.', NEW.valor_medicion
        USING ERRCODE = 'P0217';
    END IF;

    -- Validar coherencia unidad / tipo de medición (alineado con
    -- RegistrarEventoCrecimientoDTO._UNIDADES_POR_TIPO)
    IF v_tipo_medicion = 'PESO' AND v_unidad NOT IN ('kg', 'gr', 'lb') THEN
        RAISE EXCEPTION 'UNIT_MISMATCH: Para medición de PESO solo se permiten unidades: kg, gr, lb. Unidad recibida: %.', NEW.unidad_medida
        USING ERRCODE = 'P0218';
    END IF;

    IF v_tipo_medicion IN ('TALLA', 'LONGITUD', 'ALTURA') AND v_unidad NOT IN ('cm', 'm') THEN
        RAISE EXCEPTION 'UNIT_MISMATCH: Para medición de TALLA/LONGITUD/ALTURA solo se permiten unidades: cm, m. Unidad recibida: %.', NEW.unidad_medida
        USING ERRCODE = 'P0218';
    END IF;

    IF v_tipo_medicion = 'BIOMASA' AND v_unidad NOT IN ('kg/m2') THEN
        RAISE EXCEPTION 'UNIT_MISMATCH: Para medición de BIOMASA solo se permite la unidad: kg/m2. Unidad recibida: %.', NEW.unidad_medida
        USING ERRCODE = 'P0218';
    END IF;

    RETURN NEW;
END;
$function$
"""
    )


def downgrade() -> None:
    # Restaura la definición previa, con los tres bugs descritos arriba,
    # byte a byte igual a como existía en la base de datos.
    op.execute(
        """
CREATE OR REPLACE FUNCTION modulo2.trg_fn_evento_crecimiento_tipo_activo()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
DECLARE
    v_tipo_activo   modulo2.enum_activo_biologico_tipo;
    v_tipo_medicion VARCHAR(55);
    v_unidad        VARCHAR(5);
BEGIN
    SELECT a.tipo INTO v_tipo_activo
    FROM modulo2.activos_biologicos a
    JOIN modulo2.eventos_activos ev ON ev.id_activo_biologico = a.id_activo_biologico
    WHERE ev.id_eventos = NEW.id_evento;

    v_tipo_medicion := UPPER(TRIM(NEW.tipo_medicion));
    v_unidad        := LOWER(TRIM(NEW.unidad_medida));

    -- Validar tipo_agregacion según tipo de activo
    IF v_tipo_activo = 'INDIVIDUAL' THEN
        IF NEW.tipo_agregacion IS NOT NULL AND TRIM(NEW.tipo_agregacion) <> '' THEN
            RAISE EXCEPTION 'INVALID_FIELD: Para activos INDIVIDUALES el campo tipo_agregacion debe ser nulo o vacío.'
            USING ERRCODE = 'P0216';
        END IF;
    ELSIF v_tipo_activo = 'poblacional' THEN
        IF NEW.tipo_agregacion IS NULL OR TRIM(NEW.tipo_agregacion) = '' THEN
            RAISE EXCEPTION 'MISSING_FIELD: Para activos LOTE (poblacional) el campo tipo_agregacion es obligatorio.'
            USING ERRCODE = 'P0216';
        END IF;
    END IF;

    -- Validar valor positivo
    IF NEW.valor_medicion <= 0 THEN
        RAISE EXCEPTION 'INVALID_VALUE: El valor de medición debe ser positivo y mayor a cero. Valor recibido: %.', NEW.valor_medicion
        USING ERRCODE = 'P0217';
    END IF;

    -- Validar coherencia unidad / tipo de medición
    IF v_tipo_medicion = 'PESO' AND v_unidad NOT IN ('kg', 'g', 'lb') THEN
        RAISE EXCEPTION 'UNIT_MISMATCH: Para medición de PESO solo se permiten unidades: kg, g, lb. Unidad recibida: %.', NEW.unidad_medida
        USING ERRCODE = 'P0218';
    END IF;

    IF v_tipo_medicion IN ('TALLA', 'LONGITUD', 'ALTURA') AND v_unidad NOT IN ('cm', 'm') THEN
        RAISE EXCEPTION 'UNIT_MISMATCH: Para medición de TALLA/LONGITUD/ALTURA solo se permiten unidades: cm, m. Unidad recibida: %.', NEW.unidad_medida
        USING ERRCODE = 'P0218';
    END IF;

    RETURN NEW;
END;
$function$
"""
    )
