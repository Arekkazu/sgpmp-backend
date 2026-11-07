# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-30 | Leandro | INC-M04-221-G032 RF-68: verificar downgrade/upgrade transaccional, backfill, trigger, owner y RLS del perfil. |
"""DDL solo en PostgreSQL local exclusivo de pruebas y bajo rollback exterior del fixture."""
from pathlib import Path
import importlib.util

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text

pytestmark=pytest.mark.integration


def test_migracion_perfil_conserva_datos_historia_y_protecciones(integration_engine,db_session,crear_usuario_db):
    if integration_engine.url.host not in ('localhost','127.0.0.1','::1'):
        pytest.skip('El roundtrip DDL requiere una base local exclusiva de pruebas.')
    path=Path(__file__).resolve().parents[2]/'alembic/versions/c31f8a6d920e_rf68_perfil_calculo_mvp.py'
    spec=importlib.util.spec_from_file_location('migration_inc856',path)
    migration=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    db=db_session
    usuario=crear_usuario_db(id_rol=1)
    from src.shared.database import declarar_identidad
    nombre_rol=db.execute(text("SELECT nombre_rol FROM modulo1.roles WHERE id_rol=:id"), {"id":usuario["id_rol"]}).scalar_one()
    declarar_identidad(db,usuario["id_usuario"],nombre_rol)
    ident=db.execute(text("""INSERT INTO modulo4.configuraciones_motor_ia(tipo_modelo,umbral_riesgo_alto,
        umbral_alerta_critica,ventana_temporal_min,modo_ejecucion,id_usuario_responsable)
        VALUES('MODELO_RIESGO_CONTAGIO',.7,.8,10,'SERVIDOR',:u) RETURNING id_configuracion_motor"""),{'u':usuario['id_usuario']}).scalar_one()
    db.execute(text('UPDATE modulo4.configuraciones_motor_ia SET config_version=2 WHERE id_configuracion_motor=:id'),{'id':ident})
    estado=lambda:db.execute(text("""SELECT relname,relrowsecurity,relforcerowsecurity,relowner FROM pg_class
        WHERE oid IN ('modulo4.configuraciones_motor_ia'::regclass,'modulo4.configuracion_ia_log'::regclass)
        ORDER BY relname""")).all()
    original=estado()
    owner=db.execute(text("SELECT proowner FROM pg_proc WHERE oid='modulo4.fn_rf65_log_configuracion_motor()'::regprocedure")).scalar_one()
    with Operations.context(MigrationContext.configure(db.connection())):
        migration.downgrade()
    assert db.execute(text("SELECT count(*) FROM information_schema.columns WHERE table_schema='modulo4' AND table_name IN ('configuraciones_motor_ia','configuracion_ia_log') AND column_name='perfil_calculo_contagio'")).scalar_one()==0
    db.execute(text('UPDATE modulo4.configuraciones_motor_ia SET config_version=3 WHERE id_configuracion_motor=:id'),{'id':ident})
    assert db.execute(text('SELECT count(*) FROM modulo4.configuracion_ia_log WHERE id_configuracion_motor=:id'),{'id':ident}).scalar_one()==2
    with Operations.context(MigrationContext.configure(db.connection())):
        migration.upgrade()
    assert db.execute(text('SELECT perfil_calculo_contagio FROM modulo4.configuraciones_motor_ia WHERE id_configuracion_motor=:id'),{'id':ident}).scalar_one()=='ESTANDAR'
    assert db.execute(text('SELECT perfil_calculo_contagio FROM modulo4.configuracion_ia_log WHERE id_configuracion_motor=:id ORDER BY config_version'),{'id':ident}).scalars().all()==['ESTANDAR','ESTANDAR']
    db.execute(text("UPDATE modulo4.configuraciones_motor_ia SET config_version=4,perfil_calculo_contagio='MVP' WHERE id_configuracion_motor=:id"),{'id':ident})
    db.execute(text("UPDATE modulo4.configuraciones_motor_ia SET config_version=5,perfil_calculo_contagio='ESTANDAR' WHERE id_configuracion_motor=:id"),{'id':ident})
    assert db.execute(text('SELECT perfil_calculo_contagio FROM modulo4.configuracion_ia_log WHERE id_configuracion_motor=:id AND config_version=4'),{'id':ident}).scalar_one()=='MVP'
    assert estado()==original
    assert db.execute(text("SELECT proowner FROM pg_proc WHERE oid='modulo4.fn_rf65_log_configuracion_motor()'::regprocedure")).scalar_one()==owner
    assert db.execute(text("SELECT proconfig FROM pg_proc WHERE oid='modulo4.fn_rf65_log_configuracion_motor()'::regprocedure")).scalar_one()==['search_path=pg_catalog, pg_temp']
    assert db.execute(text("SELECT prosecdef FROM pg_proc WHERE oid='modulo4.fn_rf65_log_configuracion_motor()'::regprocedure")).scalar_one() is True
