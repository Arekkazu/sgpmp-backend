"""descripciones_roles_integracion_sin_codigos

Revision ID: 00c60ae92735
Revises: 2672a752c041
Create Date: 2026-10-08 21:00:00.000000

Las descripciones de los roles técnicos 'Integración M04' / 'Integración M06'
nombraban los módulos por código («módulo 4», «M02», «RF-50», «INC-…»), que
no le dicen nada al administrador que las lee en Roles y permisos. Se reescriben
con el nombre de cada módulo.

Solo cambia `descripcion`. El `nombre_rol` NO se toca: `resolver_modulo_consumidor`
(consultar_datos_consolidados_use_case.py) deduce el módulo consumidor
parseándolo con `^integraci[oó]n\\s+m0*(\\d+)$`, y de eso dependen la auditoría
de RF-50/RF-52, el límite de tasa por módulo y la consistencia fuerte de M06.

Busca por nombre y no por id porque los ids difieren entre ambientes. Es
idempotente: donde el rol no existe no hace nada.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "00c60ae92735"
down_revision: Union[str, Sequence[str], None] = "2672a752c041"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_NUEVAS = {
    "integración m04": (
        "Identidad técnica de solo lectura para que Predicción IA consuma los "
        "datos consolidados e indicadores de Activos biológicos."
    ),
    "integración m06": (
        "Identidad técnica de solo lectura para que Finanzas (valoración NIC-41) "
        "consuma los datos consolidados de Activos biológicos."
    ),
}

_ANTERIORES = {
    "integración m04": (
        "Identidad técnica de solo lectura para que el módulo 4 (analítica/predicción) "
        "consuma los endpoints analíticos de M02 (RF-50 datos-consolidados, RF-51 "
        "indicadores). Creado para INC-M02-90-G92, aplicado en INC-M02-92-G93."
    ),
    "integración m06": (
        "Identidad técnica de solo lectura para que el módulo 6 (valoración financiera / "
        "NIC-41) consuma los endpoints analíticos de M02 (RF-50 datos-consolidados). "
        "Creado para INC-M02-93-G93."
    ),
}


def _actualizar(descripciones: dict[str, str]) -> None:
    for nombre, descripcion in descripciones.items():
        op.execute(
            f"""
            UPDATE modulo1.roles
            SET descripcion = $${descripcion}$$,
                fecha_actualizacion = now()
            WHERE lower(btrim(nombre_rol)) = $${nombre}$$
              AND descripcion IS DISTINCT FROM $${descripcion}$$
            """
        )


def upgrade() -> None:
    _actualizar(_NUEVAS)


def downgrade() -> None:
    _actualizar(_ANTERIORES)
