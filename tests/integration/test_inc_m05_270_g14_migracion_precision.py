# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-11-07 | Leandro | INC-M05-270-G14 RF-76: verificar migración reversible, metadatos y bloqueos sin pérdida de dosis. |
"""DDL únicamente en la base local exclusiva, bajo rollback exterior."""
from decimal import Decimal as D
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.operations import Operations
from alembic.migration import MigrationContext

from tests.integration.test_inc_m05_270_g14_precision_dosis_integration import montar,escenario,medicamento

pytestmark=pytest.mark.integration


@pytest.fixture(autouse=True)
def exclusiva(integration_engine):
    if (integration_engine.url.host not in ('localhost','127.0.0.1','::1')
            or integration_engine.url.database!='sgpmp_inc954_test'):
        pytest.skip('El DDL requiere la base local exclusiva sgpmp_inc954_test.')


def revision():
    return ScriptDirectory.from_config(Config('alembic.ini')).get_revision('d2e71a4c980b').module


def ejecutar(db,accion):
    with Operations.context(MigrationContext.configure(db.connection())):
        getattr(revision(),accion)()


def escala(db):
    return db.execute(text("SELECT numeric_precision,numeric_scale FROM information_schema.columns WHERE table_schema='modulo5' AND table_name='registros_medicamentos' AND column_name='cantidad'")).one()


def vista(db):
    return db.execute(text("""SELECT pg_get_viewdef(c.oid),c.relowner,c.reloptions,obj_description(c.oid,'pg_class'),
        (SELECT jsonb_agg(jsonb_build_array(a.attname,col_description(a.attrelid,a.attnum)) ORDER BY a.attnum)
           FROM pg_attribute a WHERE a.attrelid=c.oid AND a.attnum>0 AND NOT a.attisdropped),
        (SELECT jsonb_agg(jsonb_build_array(p.grantor,p.grantee,p.privilege_type,p.is_grantable)
           ORDER BY p.grantor,p.grantee,p.privilege_type) FROM aclexplode(c.relacl) p),
        (SELECT jsonb_agg(jsonb_build_array(a.attname,p.grantor,p.grantee,p.privilege_type,p.is_grantable)
           ORDER BY a.attname,p.grantor,p.grantee,p.privilege_type)
           FROM pg_attribute a CROSS JOIN LATERAL aclexplode(a.attacl) p WHERE a.attrelid=c.oid)
        FROM pg_class c WHERE c.oid='modulo5.vw_m05_aplicacion_medicamentos'::regclass""")).one()


def protecciones(db):
    return db.execute(text("""SELECT relowner,relrowsecurity,relforcerowsecurity,
        (SELECT array_agg(pg_get_triggerdef(t.oid) ORDER BY tgname) FROM pg_trigger t WHERE tgrelid=c.oid AND NOT tgisinternal),
        (SELECT array_agg(pg_get_constraintdef(t.oid) ORDER BY conname) FROM pg_constraint t WHERE conrelid=c.oid)
        FROM pg_class c WHERE oid='modulo5.registros_medicamentos'::regclass""")).one()


def test_roundtrip_conserva_historico_vista_owner_opciones_y_grants(client,db_session,escenario):
    db=db_session;e=escenario
    r=client.post('/suministros/medicamentos',headers=e['vet'],json=medicamento(e,retiro=0)|{'dosis_aplicada':'.001'})
    assert r.status_code==201,r.text
    db.execute(text('ALTER VIEW modulo5.vw_m05_aplicacion_medicamentos OWNER TO sgpmp_owner'))
    db.execute(text('ALTER VIEW modulo5.vw_m05_aplicacion_medicamentos SET (security_barrier=true)'))
    db.execute(text("COMMENT ON COLUMN modulo5.vw_m05_aplicacion_medicamentos.cantidad_dosis IS 'Precision de dosis de prueba'"))
    db.execute(text('GRANT USAGE ON SCHEMA modulo5 TO sgpmp_owner'))
    db.execute(text('SET LOCAL ROLE sgpmp_owner'))
    db.execute(text('GRANT SELECT ON modulo5.vw_m05_aplicacion_medicamentos TO sgpmp_app WITH GRANT OPTION'))
    db.execute(text('GRANT SELECT (cantidad_dosis) ON modulo5.vw_m05_aplicacion_medicamentos TO rol_app'))
    db.execute(text('RESET ROLE'))
    # Un default privilege nuevo no debe ampliar la exposición de la vista al recrearla.
    db.execute(text('ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA modulo5 GRANT SELECT ON TABLES TO PUBLIC'))
    original=vista(db);seguridad=protecciones(db)
    aud=db.execute(text('SELECT datos_nuevos,hash_integridad FROM modulo5.auditorias_suministros ORDER BY id_auditoria_suministro')).all()
    ejecutar(db,'downgrade')
    assert escala(db)==(10,3) and vista(db)==original and protecciones(db)==seguridad
    ejecutar(db,'upgrade')
    assert escala(db)==(10,4) and vista(db)==original and protecciones(db)==seguridad
    assert db.execute(text('SELECT cantidad FROM modulo5.registros_medicamentos')).scalar_one()==D('.001')
    assert db.execute(text('SELECT costo_registro FROM modulo5.registro_suministro')).scalar_one()==D('.5')
    assert db.execute(text('SELECT datos_nuevos,hash_integridad FROM modulo5.auditorias_suministros ORDER BY id_auditoria_suministro')).all()==aud
    assert db.execute(text("SELECT EXISTS(SELECT 1 FROM pg_class c CROSS JOIN LATERAL aclexplode(c.relacl) a WHERE c.oid='modulo5.vw_m05_aplicacion_medicamentos'::regclass AND a.grantee=0 AND a.privilege_type='SELECT')")).scalar_one() is False


def test_downgrade_bloquea_redondeo_de_dosis_ya_registrada(client,db_session,escenario):
    db=db_session;e=escenario
    r=client.post('/suministros/medicamentos',headers=e['vet'],json=medicamento(e,retiro=0)|{'dosis_aplicada':'.0001'})
    assert r.status_code==201,r.text
    original=vista(db)
    with pytest.raises(RuntimeError,match='downgrade bloqueado'):
        with db.begin_nested():ejecutar(db,'downgrade')
    assert escala(db)==(10,4) and vista(db)==original
    assert db.execute(text('SELECT cantidad FROM modulo5.registros_medicamentos')).scalar_one()==D('.0001')


def test_upgrade_bloquea_historico_fuera_del_rango_sin_truncarlo(db_session,escenario):
    db=db_session;e=escenario
    ejecutar(db,'downgrade')
    # Activo histórico sin fase: la BD de origen permitía dosis de siete enteros.
    activo=db.execute(text("""INSERT INTO modulo2.activos_biologicos(id_especie,id_infraestructura,tipo,identificador,
        fecha_inicio_ciclo,id_estado,descripcion,origen_financiero,costo_adquisicion,atributos_dinamicos,
        id_usuario,fecha_creacion,soporte_documental,detalles_procedencia)
        SELECT id_especie,id_infraestructura,tipo,'HISTORICO-PRECISION',fecha_inicio_ciclo,id_estado,descripcion,
        origen_financiero,costo_adquisicion,atributos_dinamicos,id_usuario,fecha_creacion,soporte_documental,detalles_procedencia
        FROM modulo2.activos_biologicos WHERE id_activo_biologico=:a RETURNING id_activo_biologico"""),{'a':e['individual']['activo']}).scalar_one()
    db.execute(text("""INSERT INTO modulo5.registros_medicamentos(id_activo_biologico,nombre_medicamento,
        descripcion_clinica,unidad_dosis,cantidad,fecha_aplicacion,costo_unitario_medicamento,id_usuario)
        VALUES(:a,'Historico','Descripcion clinica','ml',1000000,:fecha,.0001,:u)"""),{'a':activo,'fecha':e['hoy'],'u':e['vet_id']})
    original=vista(db)
    with pytest.raises(RuntimeError,match='exceden decimal'):
        with db.begin_nested():ejecutar(db,'upgrade')
    assert escala(db)==(10,3) and vista(db)==original
    assert db.execute(text('SELECT cantidad FROM modulo5.registros_medicamentos')).scalar_one()==D('1000000')


def test_dependencia_no_prevista_aborta_sin_cascade_ni_cambios(db_session,escenario):
    db=db_session
    db.execute(text('CREATE VIEW modulo5.vw_inc954_dependencia AS SELECT cantidad_dosis FROM modulo5.vw_m05_aplicacion_medicamentos'))
    original=vista(db)
    with pytest.raises(DBAPIError) as exc:
        with db.begin_nested():ejecutar(db,'downgrade')
    assert exc.value.orig.pgcode=='2BP01'
    assert escala(db)==(10,4) and vista(db)==original
    assert db.execute(text("SELECT to_regclass('modulo5.vw_inc954_dependencia') IS NOT NULL")).scalar_one()
