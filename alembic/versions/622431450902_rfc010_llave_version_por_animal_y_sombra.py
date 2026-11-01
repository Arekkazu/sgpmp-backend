# | Fecha      | Nombre   | Que se hizo                                                        |
# |------------|----------|--------------------------------------------------------------------|
# | 2026-10-31 | Arekkazu | RFC-010 RF-69: llave por animal, estado SOMBRA y fuente_datos      |
"""rfc010: versión de modelo por animal, estado SOMBRA y fuente de datos (RF-69)

Revision ID: 622431450902
Revises: 90fd5bff3519
Create Date: 2026-10-31

RFC-010 (ESCALAMIENTO_C1-C8_ET02_v5 §C1, puntos 1 y 2). ET-02 entrena un modelo
INDIVIDUAL por animal, y RF-69 solo admitía una versión ACTIVO por
``(tipo_modelo, componente)``: la segunda vaca reemplazaba a la primera. Además
los modelos entrenados con datos sintéticos tienen que correr en sombra (calculan
y se registran, pero no alertan) y RF-69 no tenía ese estado.

- ``enum_estado_version_modelo`` + ``SOMBRA``.
- ``enum_tipo_evento_auditoria_m04`` + ``VERSION_EN_SOMBRA`` (RF-73).
- Nuevo ``enum_version_modelo_fuente_datos`` (REAL, SINTETICA, EXTERNA, MIXTA) y
  columna ``fuente_datos`` (NOT NULL, default REAL: las versiones existentes vienen
  del pipeline RF-71 con datos reales).
- Columna ``id_activo_biologico`` (FK a ``modulo2.activos_biologicos``).
- ``ck_version_modelo_llave_paradigma``: INDIVIDUAL no lleva componente; POBLACIONAL
  y META no llevan animal. Que un INDIVIDUAL nuevo traiga animal lo exige el registro
  (422 ACTIVO_BIOLOGICO_REQUERIDO) y no el CHECK: las versiones INDIVIDUAL ya
  registradas no tienen animal y un CHECK, aun ``NOT VALID``, se evalúa en cada UPDATE;
  no se podrían deprecar nunca. ``NOT VALID`` por si algún ambiente tiene filas viejas
  fuera de la regla.
- La unicidad pasa a «una versión ACTIVO y una SOMBRA por llave»
  ``(tipo_modelo, componente, id_activo_biologico)``: reemplaza a
  ``uq_version_modelo_activa_tipo_componente``.
- ``trg_fn_versiones_modelos_unicidad_produccion`` agrega el animal a la llave; sin
  esto, activar el modelo de un animal sacaba de producción el de otro.

No cambia ``nombre_version varchar(40)`` (H2): el nombre lo arma el backend y cabe
con el id del animal; el nombre largo de ET-02 no se guarda ahí.
"""
from typing import Sequence, Union

from alembic import op


revision: str = '622431450902'
down_revision: Union[str, Sequence[str], None] = '90fd5bff3519'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TIPOS_INDIVIDUAL = "('MODELO_ESPECIES_MEDIANAS', 'MODELO_ESPECIES_GRANDES')"

_UNICIDAD_PRODUCCION = """
CREATE OR REPLACE FUNCTION modulo4.trg_fn_versiones_modelos_unicidad_produccion()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
        BEGIN
            IF NEW.esta_produccion = true THEN
                UPDATE modulo4.versiones_modelos
                SET    esta_produccion = false
                WHERE  tipo_modelo         IS NOT DISTINCT FROM NEW.tipo_modelo
                  AND  componente          IS NOT DISTINCT FROM NEW.componente
                  {filtro_animal}
                  AND  esta_produccion     = true
                  AND  id_version_modelo   <> NEW.id_version_modelo;
            END IF;

            RETURN NEW;
        END;
        $function$
"""


def upgrade() -> None:
    # Un valor nuevo de enum no se puede usar en la misma transacción que lo crea, y el
    # índice parcial de abajo filtra por SOMBRA.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE modulo4.enum_estado_version_modelo ADD VALUE IF NOT EXISTS 'SOMBRA'")
        op.execute(
            "ALTER TYPE modulo4.enum_tipo_evento_auditoria_m04 ADD VALUE IF NOT EXISTS 'VERSION_EN_SOMBRA'"
        )

    op.execute(
        "CREATE TYPE modulo4.enum_version_modelo_fuente_datos AS ENUM "
        "('REAL', 'SINTETICA', 'EXTERNA', 'MIXTA')"
    )
    op.execute(
        """ALTER TABLE modulo4.versiones_modelos
            ADD COLUMN id_activo_biologico integer,
            ADD COLUMN fuente_datos modulo4.enum_version_modelo_fuente_datos NOT NULL DEFAULT 'REAL'"""
    )
    op.execute(
        """ALTER TABLE modulo4.versiones_modelos
            ADD CONSTRAINT versiones_modelos_id_activo_biologico_fkey
            FOREIGN KEY (id_activo_biologico) REFERENCES modulo2.activos_biologicos (id_activo_biologico)
            ON DELETE RESTRICT ON UPDATE RESTRICT"""
    )
    op.execute(
        f"""ALTER TABLE modulo4.versiones_modelos
            ADD CONSTRAINT ck_version_modelo_llave_paradigma CHECK (
                CASE WHEN tipo_modelo IN {_TIPOS_INDIVIDUAL}
                     THEN componente IS NULL
                     ELSE id_activo_biologico IS NULL
                END
            ) NOT VALID"""
    )
    op.execute("DROP INDEX modulo4.uq_version_modelo_activa_tipo_componente")
    op.execute(
        """CREATE UNIQUE INDEX uq_version_modelo_tipo_componente_activo_estado
            ON modulo4.versiones_modelos (
                tipo_modelo, COALESCE(componente, ''), COALESCE(id_activo_biologico, 0), estado_version
            )
            WHERE estado_version IN ('ACTIVO', 'SOMBRA')"""
    )
    op.execute(
        _UNICIDAD_PRODUCCION.format(
            filtro_animal="AND  id_activo_biologico IS NOT DISTINCT FROM NEW.id_activo_biologico"
        )
    )


def downgrade() -> None:
    op.execute(_UNICIDAD_PRODUCCION.format(filtro_animal=""))
    op.execute("DROP INDEX modulo4.uq_version_modelo_tipo_componente_activo_estado")
    # Falla si quedaron dos ACTIVO de animales distintos con la misma llave vieja: hay que
    # deprecar uno antes de bajar, porque la llave vieja no los distingue.
    op.execute(
        """CREATE UNIQUE INDEX uq_version_modelo_activa_tipo_componente
            ON modulo4.versiones_modelos (tipo_modelo, COALESCE(componente, ''))
            WHERE estado_version = 'ACTIVO'"""
    )
    op.execute("ALTER TABLE modulo4.versiones_modelos DROP CONSTRAINT ck_version_modelo_llave_paradigma")
    op.execute(
        "ALTER TABLE modulo4.versiones_modelos DROP CONSTRAINT versiones_modelos_id_activo_biologico_fkey"
    )
    op.execute(
        "ALTER TABLE modulo4.versiones_modelos DROP COLUMN fuente_datos, DROP COLUMN id_activo_biologico"
    )
    op.execute("DROP TYPE modulo4.enum_version_modelo_fuente_datos")
    # SOMBRA y VERSION_EN_SOMBRA se quedan: Postgres no quita valores de un enum (mismo
    # criterio que 67e33de11180). Las versiones en SOMBRA siguen siendo filas válidas.
