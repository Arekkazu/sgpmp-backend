"""inc_m02_299_parto_diagnostico_exitoso

Revision ID: 9947f4621939
Revises: 8c44765be172
Create Date: 2026-10-08 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '9947f4621939'
down_revision: Union[str, Sequence[str], None] = '8c44765be172'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_FUNCION = """
CREATE OR REPLACE FUNCTION modulo2.trg_fn_evento_reproductivo_secuencia()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
DECLARE
    v_activo_id   INTEGER;
    v_tipo_activo modulo2.enum_activo_biologico_tipo;
    v_count_previo INTEGER;
BEGIN
    SELECT a.id_activo_biologico, a.tipo
    INTO v_activo_id, v_tipo_activo
    FROM modulo2.activos_biologicos a
    JOIN modulo2.eventos_activos ev ON ev.id_activo_biologico = a.id_activo_biologico
    WHERE ev.id_eventos = NEW.id_evento_reproductivo;

    -- Para LOTE: solo se permite nacimiento
    IF v_tipo_activo = 'POBLACIONAL' AND NEW.categoria NOT IN ('nacimiento') THEN
        RAISE EXCEPTION 'TYPE_RESTRICTION: Para activos de tipo LOTE (poblacional) solo se permite el evento reproductivo nacimiento. Categoría recibida: %.', NEW.categoria
        USING ERRCODE = 'P0220';
    END IF;

    IF v_tipo_activo = 'INDIVIDUAL' THEN
        -- parto requiere diagnostico positivo previo
        IF NEW.categoria = 'parto' THEN
            SELECT COUNT(*) INTO v_count_previo
            FROM modulo2.eventos_reproductivos er
            JOIN modulo2.eventos_activos ea ON ea.id_eventos = er.id_evento_reproductivo
            WHERE ea.id_activo_biologico = v_activo_id
              AND er.categoria = 'diagnostico'
              AND {condicion_diagnostico};

            IF v_count_previo = 0 THEN
                RAISE EXCEPTION 'SEQUENCE_VIOLATION: No se puede registrar parto sin un evento previo de diagnostico positivo para el activo ID %.', v_activo_id
                USING ERRCODE = 'P0221';
            END IF;
        END IF;

        -- nacimiento requiere parto previo
        IF NEW.categoria = 'nacimiento' THEN
            SELECT COUNT(*) INTO v_count_previo
            FROM modulo2.eventos_reproductivos er
            JOIN modulo2.eventos_activos ea ON ea.id_eventos = er.id_evento_reproductivo
            WHERE ea.id_activo_biologico = v_activo_id
              AND er.categoria = 'parto';

            IF v_count_previo = 0 THEN
                RAISE EXCEPTION 'SEQUENCE_VIOLATION: No se puede registrar nacimiento sin un evento previo de parto para el activo ID %.', v_activo_id
                USING ERRCODE = 'P0221';
            END IF;
        END IF;

        -- Número de crías en parto o nacimiento debe ser >= 1
        IF NEW.categoria IN ('parto', 'nacimiento') AND NEW.numero_cria < 1 THEN
            RAISE EXCEPTION 'INVALID_VALUE: El número de crías en un evento de % debe ser mayor o igual a 1. Valor recibido: %.', NEW.categoria, NEW.numero_cria
            USING ERRCODE = 'P0222';
        END IF;
    END IF;

    RETURN NEW;
END;
$function$
"""


def upgrade() -> None:
    # Arekkazu/SGPMP-FRONT-END-PWA#299: el trigger buscaba un diagnóstico con
    # `resultado LIKE '%POSITIV%'`, pero RF-42 (y el DTO) solo admiten
    # `exitoso`/`fallido`. Ningún parto pasaba nunca: el use case lo validaba
    # bien (`resultado = 'exitoso'`) y el trigger lo rechazaba con P0221, que
    # salía como 500. Se alinea el trigger con la regla de la aplicación;
    # 'positivo' se sigue aceptando por los datos sembrados antes de RF-42.
    op.execute(_FUNCION.format(condicion_diagnostico="LOWER(er.resultado) IN ('exitoso', 'positivo')"))


def downgrade() -> None:
    op.execute(_FUNCION.format(condicion_diagnostico="UPPER(er.resultado) LIKE '%POSITIV%'"))
