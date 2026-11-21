# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-11-07 | Leandro | INC-M05-270-G14 RF-76: alinear cantidad a numeric(10,4), conservar la vista y evitar pérdida histórica. |
"""RF-76: cuatro decimales de dosis desde el registro al ledger.

Revision ID: d2e71a4c980b
Revises: b7e2d94c1a68
Create Date: 2026-11-07

La vista impide ALTER TYPE directo. Se conserva su definición, propietario,
opciones, comentarios y privilegios (incluidas columnas y grant option).
No se actualizan registros históricos ni se modifican triggers o RLS.
"""
from alembic import op
import sqlalchemy as sa

revision = 'd2e71a4c980b'
down_revision = 'b7e2d94c1a68'
branch_labels = None
depends_on = None

_VISTA = 'modulo5.vw_m05_aplicacion_medicamentos'


def _cambiar_tipo(escala: int) -> None:
    db = op.get_bind()
    quote = db.dialect.identifier_preparer.quote
    # Protege la comprobación de datos y el cambio de tipo de escrituras concurrentes.
    db.execute(sa.text('LOCK TABLE modulo5.registros_medicamentos IN ACCESS EXCLUSIVE MODE'))
    if escala == 4:
        incompatible = db.scalar(sa.text('SELECT EXISTS (SELECT 1 FROM modulo5.registros_medicamentos WHERE abs(cantidad) >= 1000000)'))
        if incompatible:
            raise RuntimeError('RF-76: existen dosis históricas que exceden decimal(10,4); resolverlas con autorización antes de migrar.')
    else:
        incompatible = db.scalar(sa.text('SELECT EXISTS (SELECT 1 FROM modulo5.registros_medicamentos WHERE cantidad <> trunc(cantidad,3))'))
        if incompatible:
            raise RuntimeError('RF-76: downgrade bloqueado para no redondear dosis históricas con cuatro decimales.')

    vista = db.execute(sa.text("""SELECT c.oid,pg_get_viewdef(c.oid) AS definicion,
        pg_get_userbyid(c.relowner) AS propietario,c.reloptions AS opciones,
        obj_description(c.oid,'pg_class') AS comentario
        FROM pg_class c WHERE c.oid='modulo5.vw_m05_aplicacion_medicamentos'::regclass""")).mappings().one()
    extras = db.scalar(sa.text("""SELECT EXISTS(SELECT 1 FROM pg_rewrite WHERE ev_class=:oid AND rulename<>'_RETURN')
        OR EXISTS(SELECT 1 FROM pg_trigger WHERE tgrelid=:oid AND NOT tgisinternal)"""), {'oid':vista['oid']})
    if extras:
        raise RuntimeError('RF-76: la vista tiene reglas/triggers adicionales; revisar dependencias antes de migrar.')

    permisos = db.execute(sa.text("""SELECT pg_get_userbyid(a.grantor) AS otorgante,
        CASE WHEN a.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(a.grantee) END AS destinatario,
        a.grantee=0 AS publico,a.privilege_type,a.is_grantable
        FROM pg_class c CROSS JOIN LATERAL aclexplode(COALESCE(c.relacl,acldefault('r',c.relowner))) a
        WHERE c.oid=:oid"""),{'oid':vista['oid']}).mappings().all()
    columnas = db.execute(sa.text("""SELECT attname,col_description(attrelid,attnum) AS comentario
        FROM pg_attribute WHERE attrelid=:oid AND attnum>0 AND NOT attisdropped"""),{'oid':vista['oid']}).mappings().all()
    permisos_columnas = db.execute(sa.text("""SELECT c.attname,pg_get_userbyid(a.grantor) AS otorgante,
        CASE WHEN a.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(a.grantee) END AS destinatario,
        a.grantee=0 AS publico,a.privilege_type,a.is_grantable
        FROM pg_attribute c CROSS JOIN LATERAL aclexplode(c.attacl) a
        WHERE c.attrelid=:oid AND c.attnum>0 AND NOT c.attisdropped"""),{'oid':vista['oid']}).mappings().all()

    # RESTRICT (sin CASCADE): cualquier dependencia desconocida aborta la transacción.
    op.execute('DROP VIEW modulo5.vw_m05_aplicacion_medicamentos')
    op.alter_column('registros_medicamentos','cantidad',schema='modulo5',
                    existing_type=sa.Numeric(10,3 if escala==4 else 4),
                    type_=sa.Numeric(10,escala),existing_nullable=False)
    op.execute(sa.text('CREATE VIEW '+_VISTA+' AS '+vista['definicion']))
    op.execute(sa.text('ALTER VIEW '+_VISTA+' OWNER TO '+quote(vista['propietario'])))
    if vista['opciones']:
        # Opciones devueltas por PostgreSQL, no valores recibidos del cliente.
        op.execute(sa.text('ALTER VIEW '+_VISTA+' SET ('+', '.join(vista['opciones'])+')'))
    db.execute(sa.text('COMMENT ON VIEW '+_VISTA+' IS :comentario'),{'comentario':vista['comentario']})
    for columna in columnas:
        db.execute(sa.text('COMMENT ON COLUMN '+_VISTA+'.'+quote(columna['attname'])+' IS :comentario'),
                   {'comentario':columna['comentario']})

    # El CREATE puede adquirir default privileges nuevos; no se conservan grants
    # adicionales que la vista original no tenía.
    nuevos = db.execute(sa.text("""SELECT DISTINCT a.grantee,
        CASE WHEN a.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(a.grantee) END AS destinatario
        FROM pg_class c CROSS JOIN LATERAL aclexplode(c.relacl) a
        WHERE c.oid='modulo5.vw_m05_aplicacion_medicamentos'::regclass AND a.grantee<>c.relowner""")).mappings().all()
    for permiso in nuevos:
        destinatario = 'PUBLIC' if permiso['grantee']==0 else quote(permiso['destinatario'])
        op.execute(sa.text('REVOKE ALL ON '+_VISTA+' FROM '+destinatario))
    for permiso in permisos:
        _restaurar_permiso(permiso,quote)
    for permiso in permisos_columnas:
        _restaurar_permiso(permiso,quote,columna=permiso['attname'])


def _restaurar_permiso(permiso,quote,*,columna=None) -> None:
    destinatario = 'PUBLIC' if permiso['publico'] else quote(permiso['destinatario'])
    privilegio = permiso['privilege_type']
    if columna is not None:
        privilegio += ' ('+quote(columna)+')'
    sentencia = 'GRANT '+privilegio+' ON '+_VISTA+' TO '+destinatario
    if permiso['is_grantable']:
        sentencia += ' WITH GRANT OPTION'
    # PostgreSQL exige que GRANTED BY sea el rol actual. Restaurar con el
    # otorgante original conserva la cadena de grants; no se amplían permisos.
    db = op.get_bind()
    anterior = db.scalar(sa.text('SELECT current_user'))
    cambia_rol = anterior != permiso['otorgante']
    if cambia_rol:
        op.execute(sa.text('SET LOCAL ROLE '+quote(permiso['otorgante'])))
    # Si falla el GRANT, la transacción Alembic revierte SET LOCAL; no emitir
    # otra sentencia sobre una transacción abortada que oculte el error original.
    op.execute(sa.text(sentencia))
    if cambia_rol:
        op.execute(sa.text('SET LOCAL ROLE '+quote(anterior)))


def upgrade() -> None:
    _cambiar_tipo(4)


def downgrade() -> None:
    _cambiar_tipo(3)
