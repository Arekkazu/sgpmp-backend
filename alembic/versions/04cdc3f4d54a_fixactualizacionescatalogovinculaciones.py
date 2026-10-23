"""FixActualizacionesCatalogoVinculaciones

Revision ID: 04cdc3f4d54a
Revises: e5a3c9b17d42
Create Date: 2026-10-21 23:41:33.266806

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '04cdc3f4d54a'
down_revision: Union[str, Sequence[str], None] = 'e5a3c9b17d42'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLA = "modulo3.vinculaciones_lecturas"
ENUM = "modulo3.enum_estado_vinculacion"


# ---------------------------------------------------------------------------
# Funciones de trigger (CREATE OR REPLACE conserva owner y GRANTs)
# ---------------------------------------------------------------------------
FN_UNICIDAD_NUEVA = r"""
CREATE OR REPLACE FUNCTION modulo3.fn_validar_unicidad_vinculacion_individual()
    RETURNS trigger
    LANGUAGE 'plpgsql'
    COST 100
    VOLATILE NOT LEAKPROOF
AS $BODY$
DECLARE v_conflicto INTEGER;
BEGIN
    IF NEW.modelo_manejo <> 'INDIVIDUAL'::modulo3.enum_modelo_manejo THEN
        RETURN NEW;
    END IF;

    SELECT COUNT(*) INTO v_conflicto
    FROM   modulo3.vinculaciones_lecturas
    WHERE  id_telemetria        = NEW.id_telemetria
      AND  modelo_manejo        = 'INDIVIDUAL'::modulo3.enum_modelo_manejo
      AND  estado_vinculacion   = 'CONFIRMADA'::modulo3.enum_estado_vinculacion
      AND  id_vinculacion_lectura <> COALESCE(NEW.id_vinculacion_lectura, -1)
      AND  fecha_inicio_vinculacion < COALESCE(NEW.fecha_fin_vinculacion, 'infinity'::timestamptz)
      AND  COALESCE(fecha_fin_vinculacion,'infinity'::timestamptz) > NEW.fecha_inicio_vinculacion;

    IF v_conflicto > 0 THEN
        RAISE EXCEPTION
            'RF-61 [UNICIDAD]: Ya existe vinculación INDIVIDUAL activa para id_telemetria=% en ese período.',
            NEW.id_telemetria USING ERRCODE = 'P0012';
    END IF;
    RETURN NEW;
END;
$BODY$;
"""

FN_UNICIDAD_ORIGINAL = FN_UNICIDAD_NUEVA.replace("'CONFIRMADA'", "'VINCULADA'")

FN_CERRAR_NUEVA = r"""
CREATE OR REPLACE FUNCTION modulo3.fn_cerrar_vinculacion_reemplazada()
    RETURNS trigger
    LANGUAGE 'plpgsql'
    COST 100
    VOLATILE NOT LEAKPROOF
AS $BODY$
BEGIN
    UPDATE modulo3.vinculaciones_lecturas SET
        fecha_fin_vinculacion = NEW.fecha_inicio_vinculacion,
        estado_vinculacion    = 'SUPERADA'::modulo3.enum_estado_vinculacion
    WHERE  id_vinculacion_lectura = NEW.id_vinculacion_remplazada
      AND  fecha_fin_vinculacion IS NULL;

    IF NOT FOUND THEN
        RAISE WARNING 'RF-61: Vinculación a reemplazar id=% no existe o ya está cerrada.',
            NEW.id_vinculacion_remplazada;
    END IF;
    RETURN NEW;
END;
$BODY$;
"""

FN_CERRAR_ORIGINAL = FN_CERRAR_NUEVA.replace("'SUPERADA'", "'CORREGIDA'")


# ---------------------------------------------------------------------------
# Helpers para el cambio de enum
# ---------------------------------------------------------------------------
def _soltar_dependencias() -> None:
    """Objetos que dependen del enum y bloquean el ALTER COLUMN ... TYPE."""
    op.execute(f"ALTER TABLE {TABLA} ALTER COLUMN estado_vinculacion DROP DEFAULT")
    op.execute(f"ALTER TABLE {TABLA} DROP CONSTRAINT ck_vinculacion_lectura_modelo_manejo")
    op.execute("DROP INDEX modulo3.idx_vinculaciones_activo_biologico")
    op.execute("DROP INDEX modulo3.idx_vinculaciones_pendientes")


def _recrear_dependencias(confirmado: str, pendientes: list[str], comentario_ck: str) -> None:
    pend = ", ".join(f"'{e}'::{ENUM}" for e in pendientes)

    op.execute(
        f"""
        ALTER TABLE {TABLA} ALTER COLUMN estado_vinculacion
            SET DEFAULT '{confirmado}'::{ENUM}
        """
    )
    op.execute(
        f"""
        ALTER TABLE {TABLA} ADD CONSTRAINT ck_vinculacion_lectura_modelo_manejo CHECK (
            modelo_manejo <> 'INDIVIDUAL'::modulo3.enum_modelo_manejo
            OR estado_vinculacion <> '{confirmado}'::{ENUM}
            OR id_activo_biologico IS NOT NULL
        )
        """
    )
    op.execute(
        f"COMMENT ON CONSTRAINT ck_vinculacion_lectura_modelo_manejo ON {TABLA} "
        f"IS '{comentario_ck}'"
    )
    op.execute(
        f"""
        CREATE INDEX idx_vinculaciones_activo_biologico
            ON {TABLA} USING btree
            (id_activo_biologico ASC NULLS LAST, fecha_inicio_vinculacion DESC NULLS FIRST)
            WITH (fillfactor=100, deduplicate_items=True)
            WHERE estado_vinculacion = '{confirmado}'::{ENUM}
        """
    )
    op.execute(
        f"""
        CREATE INDEX idx_vinculaciones_pendientes
            ON {TABLA} USING btree (estado_vinculacion ASC NULLS LAST)
            WITH (fillfactor=100, deduplicate_items=True)
            WHERE estado_vinculacion = ANY (ARRAY[{pend}])
        """
    )


def _cambiar_enum(
    valores: str, mapeo: str, confirmado: str, pendientes: list[str], comentario_ck: str
) -> None:
    op.execute(f"CREATE TYPE {ENUM}_tmp AS ENUM ({valores})")
    _soltar_dependencias()

    # El USING reescribe la tabla sin disparar triggers (a diferencia de un
    # UPDATE, que chocaría con trg_rf61_01_vinculacion_inmutable).
    op.execute(
        f"""
        ALTER TABLE {TABLA} ALTER COLUMN estado_vinculacion
            TYPE {ENUM}_tmp
            USING (CASE estado_vinculacion::text {mapeo}
                   ELSE estado_vinculacion::text END)::{ENUM}_tmp
        """
    )

    op.execute(f"DROP TYPE {ENUM}")
    op.execute(f"ALTER TYPE {ENUM}_tmp RENAME TO enum_estado_vinculacion")
    op.execute(f"ALTER TYPE {ENUM} OWNER TO sgpmp_owner")

    _recrear_dependencias(confirmado, pendientes, comentario_ck)


# ---------------------------------------------------------------------------
# upgrade / downgrade
# ---------------------------------------------------------------------------
def upgrade() -> None:
    # Paso A: enum nuevo + traducción de los datos existentes
    _cambiar_enum(
        valores="'CONFIRMADA','AMBIGUA','SIN_VINCULAR','PENDIENTE_REVISION','SUPERADA'",
        mapeo="WHEN 'VINCULADA' THEN 'CONFIRMADA' WHEN 'CORREGIDA' THEN 'SUPERADA'",
        confirmado="CONFIRMADA",
        pendientes=["SIN_VINCULAR", "AMBIGUA", "PENDIENTE_REVISION"],
        comentario_ck=(
            "RF-61: una vinculación INDIVIDUAL CONFIRMADA apunta a su activo; "
            "SIN_VINCULAR/AMBIGUA/PENDIENTE_REVISION/SUPERADA pueden no tenerlo "
            "y una POBLACIONAL puede apuntar a su lote (INC-M09-64-G31)."
        ),
    )

    # Funciones de trigger con los literales nuevos
    op.execute(FN_UNICIDAD_NUEVA)
    op.execute(FN_CERRAR_NUEVA)

    # Paso B: columnas nuevas
    op.add_column(
        "vinculaciones_lecturas",
        sa.Column("causa", sa.String(50), nullable=True),
        schema="modulo3",
    )
    op.create_check_constraint(
        "ck_vinculacion_lectura_causa",
        "vinculaciones_lecturas",
        "causa IN ('CONFIGURACION_INCOMPLETA', 'SIN_ACTIVOS_EN_ESTRUCTURA')",
        schema="modulo3",
    )
    op.add_column(
        "vinculaciones_lecturas",
        sa.Column("contexto_activo", postgresql.JSONB(), nullable=True),
        schema="modulo3",
    )

    op.execute(
        f"COMMENT ON COLUMN {TABLA}.causa IS "
        "'RF-61 E1/E2: causa de una vinculación no confirmada "
        "(CONFIGURACION_INCOMPLETA | SIN_ACTIVOS_EN_ESTRUCTURA).'"
    )
    op.execute(
        f"COMMENT ON COLUMN {TABLA}.contexto_activo IS "
        "'RF-61 Fase A4: contexto del activo al momento de vincular "
        "(fase, edad, peso, estado sanitario).'"
    )


def downgrade() -> None:
    # Columnas nuevas (se pierde su contenido)
    op.drop_constraint(
        "ck_vinculacion_lectura_causa",
        "vinculaciones_lecturas",
        type_="check",
        schema="modulo3",
    )
    op.drop_column("vinculaciones_lecturas", "contexto_activo", schema="modulo3")
    op.drop_column("vinculaciones_lecturas", "causa", schema="modulo3")

    # Enum de vuelta al original.
    # PENDIENTE_REVISION no existe en el enum viejo: se degrada a AMBIGUA.
    _cambiar_enum(
        valores="'VINCULADA','SIN_VINCULAR','AMBIGUA','CORREGIDA'",
        mapeo=(
            "WHEN 'CONFIRMADA' THEN 'VINCULADA' "
            "WHEN 'SUPERADA' THEN 'CORREGIDA' "
            "WHEN 'PENDIENTE_REVISION' THEN 'AMBIGUA'"
        ),
        confirmado="VINCULADA",
        pendientes=["SIN_VINCULAR", "AMBIGUA"],
        comentario_ck=(
            "RF-61: una vinculación INDIVIDUAL VINCULADA apunta a su activo; "
            "SIN_VINCULAR/AMBIGUA pueden no tenerlo y una POBLACIONAL puede "
            "apuntar a su lote (INC-M09-64-G31)."
        ),
    )

    # Funciones de trigger con los literales originales
    op.execute(FN_UNICIDAD_ORIGINAL)
    op.execute(FN_CERRAR_ORIGINAL)