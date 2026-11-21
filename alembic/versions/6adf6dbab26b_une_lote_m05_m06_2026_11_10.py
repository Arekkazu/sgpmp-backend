# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-10 | Arekkazu | Lote M05/M06 RF-74..94: une las 11 cabezas del lote antes de la RLS de modulo5 y modulo6 |
"""Une las cabezas que deja el lote de PRs de M05/M06 integrado el 2026-11-10.

Todas salen de ``b7e2d94c1a68`` y no comparten objetos (la única coincidencia son los
``ADD VALUE IF NOT EXISTS`` de ``enum_auditoria_financiera_tipo_evento``, que no dependen del orden):

- d2e71a4c980b (#962)  RF-76: dosis con cuatro decimales.
- e957a82c1107 (#966)  RF-82: grants del reconocimiento contable.
- b272bf16b1ec (#1024) RF-89: texto del trigger de inmutabilidad de precios.
- a3c5e7f9b201 (#1025) RF-82: evento ACCESO_NO_AUTORIZADO.
- d81f3a5c7e02 (#1034) RF-83: evento MEDICION_EXCLUIDA.
- d96480a11e01 (#1035) RF-80: identidad e integridad de la bitácora de suministros.
- c6e8a0b2d453 (#1036) RF-82/88: hecho de donación y alerta de valor en libros en cero.
- 024944b01b4d (#1047) RF-90: grants de las recepciones de provisiones de M05.
- df80051ec91b (#1048) RNF-05: costeo directo sin permiso de crear para Productor y Veterinario.
- c68b14c65d23 (#1067) RF-79: inmutabilidad del reporte NIC 41.
- e6a2c48f9d13 (#1069) RF-86: solicitudes de correctivo de variaciones.

La RLS de modulo5 (``f7463281b461``) y de modulo6 (``4fa0e24ea021``, #955) va después de esta
revisión y no en paralelo: con ``FORCE ROW LEVEL SECURITY`` el dueño de las tablas tampoco ve filas
sin ``app.current_user_id``, así que cualquier lectura o ajuste de datos de una revisión del lote
debe correr antes de activarla.

Revision ID: 6adf6dbab26b
Revises: d2e71a4c980b, e957a82c1107, b272bf16b1ec, a3c5e7f9b201, d81f3a5c7e02, d96480a11e01,
         c6e8a0b2d453, 024944b01b4d, df80051ec91b, c68b14c65d23, e6a2c48f9d13
Create Date: 2026-11-10 18:00:00.000000

"""
from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = '6adf6dbab26b'
down_revision: Union[str, Sequence[str], None] = (
    'd2e71a4c980b', 'e957a82c1107', 'b272bf16b1ec', 'a3c5e7f9b201', 'd81f3a5c7e02', 'd96480a11e01',
    'c6e8a0b2d453', '024944b01b4d', 'df80051ec91b', 'c68b14c65d23', 'e6a2c48f9d13',
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
