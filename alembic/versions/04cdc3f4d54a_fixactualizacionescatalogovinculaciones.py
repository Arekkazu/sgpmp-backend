# | Fecha      | Nombre  | Que se hizo |
# |------------|---------|-------------|
# | 2026-10-22 | Leandro | DEV-44 RF-61: preserva vistas dependientes al aplicar DB-13 |
# | 2026-10-23 | Arekkazu | INTEG RFC-012..016 DB-13: cadena lineal y owner del enum solo si existe sgpmp_owner |
"""FixActualizacionesCatalogoVinculaciones

Revision ID: 04cdc3f4d54a
Revises: 60bf7fe3d775
Create Date: 2026-10-21 23:41:33.266806

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '04cdc3f4d54a'
down_revision: Union[str, Sequence[str], None] = '60bf7fe3d775'
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
    vistas = _retirar_vistas_dependientes()
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
    # Sin el rol (BD construida desde cero: pruebas, CI) el tipo queda con el owner de la migración.
    op.execute(f"""DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sgpmp_owner') THEN
            ALTER TYPE {ENUM} OWNER TO sgpmp_owner;
        END IF;
    END $$""")

    _recrear_dependencias(confirmado, pendientes, comentario_ck)
    _restaurar_vistas(vistas,confirmado)


def _retirar_vistas_dependientes():
    """Sin CASCADE: preserva definiciones, owner, opciones, comentarios y grants."""
    conn=op.get_bind()
    vistas=[dict(f) for f in conn.execute(sa.text('''WITH RECURSIVE dependientes AS (
        SELECT c.oid,1 profundidad FROM pg_depend d JOIN pg_rewrite r ON r.oid=d.objid
          JOIN pg_class c ON c.oid=r.ev_class
          WHERE d.refobjid='modulo3.vinculaciones_lecturas'::regclass AND c.relkind IN ('v','m')
        UNION ALL
        SELECT c.oid,p.profundidad+1 FROM dependientes p JOIN pg_depend d ON d.refobjid=p.oid
          JOIN pg_rewrite r ON r.oid=d.objid JOIN pg_class c ON c.oid=r.ev_class
          WHERE c.oid<>p.oid AND c.relkind IN ('v','m') AND p.profundidad<50)
        SELECT c.oid,n.nspname,c.relname,c.relkind,c.reloptions,pg_get_userbyid(c.relowner) propietario,
          pg_get_viewdef(c.oid,true) definicion,obj_description(c.oid,'pg_class') comentario,max(p.profundidad) profundidad
        FROM dependientes p JOIN pg_class c ON c.oid=p.oid JOIN pg_namespace n ON n.oid=c.relnamespace
        GROUP BY c.oid,n.nspname ORDER BY profundidad,c.oid''')).mappings()]
    for v in vistas:
        if v['relkind']!='v':
            raise RuntimeError('DB-13 requiere plan explicito para una vista materializada dependiente.')
        v['grants']=[dict(f) for f in conn.execute(sa.text('''SELECT x.grantee,pg_get_userbyid(x.grantee) rol,
            x.privilege_type,x.is_grantable FROM pg_class c,
            LATERAL aclexplode(COALESCE(c.relacl,acldefault('r',c.relowner))) x WHERE c.oid=:oid'''),{'oid':v['oid']}).mappings()]
        v['columnas']=[dict(f) for f in conn.execute(sa.text('''SELECT attname,attacl,
            col_description(attrelid,attnum) comentario FROM pg_attribute
            WHERE attrelid=:oid AND attnum>0 AND NOT attisdropped'''),{'oid':v['oid']}).mappings()]
        if any(c['attacl'] is not None for c in v['columnas']):
            raise RuntimeError('DB-13 requiere conservar grants por columna antes de reemplazar esta vista.')
    q=conn.dialect.identifier_preparer.quote
    for v in reversed(vistas):
        conn.execute(sa.text('DROP VIEW '+q(v['nspname'])+'.'+q(v['relname'])))
    return vistas


def _restaurar_vistas(vistas,confirmado):
    conn=op.get_bind()
    q=conn.dialect.identifier_preparer.quote
    def literal(valor):
        return conn.execute(sa.select(sa.func.quote_literal(valor))).scalar_one()
    for v in vistas:
        nombre=q(v['nspname'])+'.'+q(v['relname'])
        opciones=' WITH ('+', '.join(v['reloptions'])+')' if v['reloptions'] else ''
        definicion=v['definicion']
        mapeo={'VINCULADA':'CONFIRMADA','CORREGIDA':'SUPERADA'} if confirmado=='CONFIRMADA' else {
            'CONFIRMADA':'VINCULADA','SUPERADA':'CORREGIDA','PENDIENTE_REVISION':'AMBIGUA'}
        for viejo,nuevo in mapeo.items():
            definicion=definicion.replace("'"+viejo+"'::"+ENUM,"'"+nuevo+"'::"+ENUM)
        conn.execute(sa.text('CREATE VIEW '+nombre+opciones+' AS '+definicion))
        conn.execute(sa.text('ALTER VIEW '+nombre+' OWNER TO '+q(v['propietario'])))
        # El creador puede tener default privileges distintos al owner original.
        actuales=conn.execute(sa.text('''SELECT DISTINCT x.grantee,pg_get_userbyid(x.grantee) rol
            FROM pg_class c,LATERAL aclexplode(COALESCE(c.relacl,acldefault('r',c.relowner))) x
            WHERE c.oid=to_regclass(:nombre)'''),{'nombre':nombre}).mappings().all()
        for permiso in actuales:
            rol='PUBLIC' if permiso['grantee']==0 else q(permiso['rol'])
            conn.execute(sa.text('REVOKE ALL ON '+nombre+' FROM '+rol))
        for permiso in v['grants']:
            rol='PUBLIC' if permiso['grantee']==0 else q(permiso['rol'])
            conn.execute(sa.text('GRANT '+permiso['privilege_type']+' ON '+nombre+' TO '+rol+
                (' WITH GRANT OPTION' if permiso['is_grantable'] else '')))
        if v['comentario'] is not None:
            conn.execute(sa.text('COMMENT ON VIEW '+nombre+' IS '+literal(v['comentario'])))
        for columna in v['columnas']:
            if columna['comentario'] is not None:
                conn.execute(sa.text('COMMENT ON COLUMN '+nombre+'.'+q(columna['attname'])+' IS '+literal(columna['comentario'])))


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
    _actualizar_procedimiento_correccion(True)

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
    _actualizar_procedimiento_correccion(False)


def _actualizar_procedimiento_correccion(nuevo):
    """El procedimiento publicado tambien contiene literales del enum anterior."""
    conn=op.get_bind()
    definiciones=conn.execute(sa.text('''SELECT pg_get_functiondef(p.oid) FROM pg_proc p
        JOIN pg_namespace n ON n.oid=p.pronamespace
        WHERE n.nspname='modulo3' AND p.proname='sp_corregir_vinculacion' AND p.prokind='p' ''')).scalars().all()
    mapeo={'VINCULADA':'CONFIRMADA','CORREGIDA':'SUPERADA'} if nuevo else {'CONFIRMADA':'VINCULADA','SUPERADA':'CORREGIDA'}
    for definicion in definiciones:
        for antes,despues in mapeo.items():
            definicion=definicion.replace("'"+antes+"'","'"+despues+"'")
        conn.execute(sa.text(definicion))
