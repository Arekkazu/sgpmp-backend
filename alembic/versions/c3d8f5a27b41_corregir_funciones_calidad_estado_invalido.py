# | Fecha      | Nombre     | Que se hizo                                                           |
# |------------|------------|-----------------------------------------------------------------------|
# | 2026-10-30 | SamuelPR21 | CARGA-FREC RF-62: corrige funciones que comparaban valores fuera del enum |
"""rf62: fn_calcular_indice_calidad y sp_evaluar_calidad_dato ya no fallan siempre

Revision ID: c3d8f5a27b41
Revises: b7c2e4f19a30
Create Date: 2026-10-30

Ambas filtraban `estado_calidad NOT IN ('ERROR_SENSOR','ERROR_AUTENTICACION')`, pero
esos valores no existen en `enum_telemetria_estado_calidad`: la consulta fallaba con
InvalidTextRepresentation en cada llamada. El filtro no aportaba nada, porque una
lectura rechazada nunca llega a `telemetrias` (RF-53), así que se retira.

`fn_calcular_indice_calidad` tenía además otro defecto: con la serie vacía
`array_length` da NULL, `NULL < 5` no es verdadero y seguía calculando como si
hubiera datos. Ahora responde INDETERMINADA.

Se edita el cuerpo vigente en lugar de reescribirlo para no pisar otros cambios, y
falla si el texto esperado no aparece. La app no llama estas funciones: RF-62 corre
en Python. Se corrigen para que quien las use obtenga un resultado.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'c3d8f5a27b41'
down_revision: Union[str, Sequence[str], None] = 'b7c2e4f19a30'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_FILTRO = "AND estado_calidad NOT IN (''ERROR_SENSOR'',''ERROR_AUTENTICACION'')"
_NOTA = '-- RF-53: las lecturas rechazadas no llegan a telemetrias'
_LONGITUD = 'v_n_real := array_length(v_serie, 1);'
_LONGITUD_SEGURA = 'v_n_real := COALESCE(array_length(v_serie, 1), 0);'


def _reemplazar(nombre: str, pares: tuple) -> None:
    cambios = ''.join(
        f"""
            IF position('{viejo}' IN v_def) = 0 THEN
                RAISE EXCEPTION 'No se encontró el texto esperado en modulo3.{nombre}';
            END IF;
            v_def := replace(v_def, '{viejo}', '{nuevo}');"""
        for viejo, nuevo in pares
    )
    op.execute(
        f"""
        DO $migracion$
        DECLARE v_def text;
        BEGIN
            SELECT pg_get_functiondef(p.oid) INTO STRICT v_def
            FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
            WHERE n.nspname = 'modulo3' AND p.proname = '{nombre}';
            {cambios}
            EXECUTE v_def;
        END
        $migracion$
        """
    )


def upgrade() -> None:
    _reemplazar('fn_calcular_indice_calidad', ((_FILTRO, _NOTA), (_LONGITUD, _LONGITUD_SEGURA)))
    _reemplazar('sp_evaluar_calidad_dato', ((_FILTRO, _NOTA),))


def downgrade() -> None:
    _reemplazar('sp_evaluar_calidad_dato', ((_NOTA, _FILTRO),))
    _reemplazar('fn_calcular_indice_calidad', ((_LONGITUD_SEGURA, _LONGITUD), (_NOTA, _FILTRO)))
