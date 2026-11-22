# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-26 | Leandro | INC-M03-123-G167 RF-53/RF-62: conservar ganancia y offset aplicados en el INSERT de telemetria. |
"""Conservar el snapshot de calibración utilizado por la ingesta común.

Revision ID: 8d13c7e9a624
Revises: 30168ab97bd4

Se modifica únicamente el INSERT de la función vigente: mantiene firma,
validaciones RF-53, contexto multiespecie, propietario y privilegios. No se
reconstruyen snapshots históricos desde calibraciones actuales.
"""
import re

from alembic import op
import sqlalchemy as sa


revision = '8d13c7e9a624'
down_revision = '30168ab97bd4'
branch_labels = None
depends_on = None

FN = (
    'modulo3.fn_ingesta_telemetria(integer, integer, integer, numeric, character varying, '
    'timestamp with time zone, timestamp with time zone, modulo3.enum_telemetria_origen, '
    'modulo3.enum_telemetria_categoria_variable, modulo3.enum_telemetria_tipo_dato, boolean, '
    'integer, numeric, numeric, numeric, numeric, numeric, boolean, jsonb)'
)
_INSERT = (
    r'(INSERT INTO modulo3\.telemetrias\s*\()(.*?)'
    r'(\)\s*VALUES\s*\()(.*?)(\)\s*RETURNING)'
)
_COLUMNA = 'parametros_calibracion, -- G167_SNAPSHOT_COLUMNA'
_VALOR = (
    "CASE WHEN v_calibrado THEN jsonb_build_object('ganancia', v_ganancia, "
    "'offset', v_offset) ELSE NULL END, -- G167_SNAPSHOT_VALOR"
)


def _una_vez(patron, src, reemplazo, *, flags=0):
    nuevo, cantidad = re.subn(patron, reemplazo, src, flags=flags)
    if cantidad != 1:
        raise RuntimeError(f'G167: se esperaba una coincidencia y se encontraron {cantidad}.')
    return nuevo


def _transformar(src: str, *, revertir: bool = False) -> str:
    def cambiar_insert(match):
        columnas, valores = match.group(2), match.group(4)
        if revertir:
            columnas = _una_vez(
                r'^[ \t]*' + re.escape(_COLUMNA) + r'\r?\n', columnas, '', flags=re.MULTILINE,
            )
            valores = _una_vez(
                r'^[ \t]*' + re.escape(_VALOR) + r'\r?\n', valores, '', flags=re.MULTILINE,
            )
        else:
            if re.search(r'\bparametros_calibracion\b', columnas):
                raise RuntimeError('G167: el INSERT ya contiene parametros_calibracion; revisar su implementación.')
            columnas = _una_vez(
                r'(?m)^([ \t]*)calibrado,[ \t]*(\r?\n)', columnas,
                lambda m: m.group(0) + m.group(1) + _COLUMNA + m.group(2),
            )
            valores = _una_vez(
                r'(?m)^([ \t]*)v_calibrado,[ \t]*(\r?\n)', valores,
                lambda m: m.group(0) + m.group(1) + _VALOR + m.group(2),
            )
        return match.group(1) + columnas + match.group(3) + valores + match.group(5)

    return _una_vez(_INSERT, src, cambiar_insert, flags=re.DOTALL)


def _actualizar(*, revertir: bool = False) -> None:
    bind = op.get_bind()
    tipo = bind.execute(sa.text("""
        SELECT data_type FROM information_schema.columns
        WHERE table_schema='modulo3' AND table_name='telemetrias'
          AND column_name='parametros_calibracion'
    """)).scalar_one_or_none()
    if tipo != 'jsonb':
        raise RuntimeError('G167: se requiere telemetrias.parametros_calibracion de tipo jsonb.')
    actual = bind.execute(
        sa.text('SELECT pg_get_functiondef(CAST(:firma AS regprocedure))'), {'firma': FN},
    ).scalar_one()
    nueva = _transformar(actual, revertir=revertir)
    # Igual que RF-53: evitar que SQLAlchemy interprete los :: y := como binds.
    op.execute(sa.text(nueva.replace(':', r'\:')))


def upgrade() -> None:
    _actualizar()


def downgrade() -> None:
    _actualizar(revertir=True)
