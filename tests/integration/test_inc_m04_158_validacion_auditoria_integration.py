# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-27 | Leandro | INC-M04-158-G086 RF-73: validar E1, enums, savepoints, rollback y RBAC en PostgreSQL real. |
# | 2026-10-29 | Arekkazu | QA-M04-27-10 CU09 H-04 RF-73: consultas globales sin HISTORIAL_CONSULTADO |
"""PostgreSQL exclusivo de pruebas; repositorio bajo sgpmp_app sin BYPASSRLS."""
from __future__ import annotations

import logging
import uuid

import pytest
from sqlalchemy import text

from src.prediction.domain.services.validacion_auditoria_m04 import TipoEventoM04
from src.prediction.infrastructure.repositories import evento_auditoria_m04_repository as modulo_repo
from src.prediction.infrastructure.repositories.evento_auditoria_m04_repository import SqlAlchemyEventoAuditoriaM04Repository
from src.shared.database import declarar_identidad
from tests.prediction.test_inc_m04_158_validacion_auditoria import INVALIDOS, Respaldo, evento


@pytest.fixture(autouse=True)
def montar_router_auditoria(integration_app):
    from src.prediction.infrastructure.routers.auditoria_m04_router import router
    integration_app.include_router(router)


@pytest.fixture
def app_db(db_session, crear_usuario_db):
    usuario = crear_usuario_db(id_rol=1)
    db_session.execute(text('SET LOCAL ROLE sgpmp_app'))
    declarar_identidad(db_session, usuario['id_usuario'], 'Administrador')
    assert db_session.execute(text('SELECT current_user')).scalar_one() == 'sgpmp_app'
    yield db_session, usuario['id_usuario']
    db_session.execute(text('RESET ROLE'))


def filas(db, correlacion):
    return db.execute(text('SELECT * FROM modulo4.eventos_auditoria_m04 WHERE correlacion_id=:c ORDER BY fecha_evento'), {'c':correlacion}).mappings().all()


@pytest.mark.parametrize('cambios,campo', INVALIDOS)
def test_rechazos_qa_e1_con_rol_real(app_db, cambios, campo):
    db, _ = app_db
    correlacion = uuid.uuid4()
    respaldo = Respaldo()
    resultado = SqlAlchemyEventoAuditoriaM04Repository(db, respaldo).registrar(**evento(correlacion_id=correlacion, **cambios))
    assert not resultado.aceptado and campo in resultado.campos_invalidos
    db.commit()  # El commit pertenece al emisor, nunca al repositorio.
    registros = filas(db, correlacion)
    assert len(registros) == 1
    rechazo = registros[0]
    assert rechazo['tipo_evento'] == 'AUDITORIA_EVENTO_INVALIDO'
    assert rechazo['id_usuario'] is None and rechazo['id_sistema']
    assert rechazo['id_referencia'] == rechazo['payload_evento']['id_intento']
    assert rechazo['severidad_evento'] == 'ERROR' and rechazo['resultado_operacion'] == 'FALLIDO'
    assert respaldo.eventos == []
    assert db.execute(text('SELECT 1')).scalar_one() == 1


def test_enum_de_dominio_coincide_con_el_catalogo_real(app_db):
    db, _ = app_db
    valores = set(db.execute(text("SELECT e.enumlabel FROM pg_enum e JOIN pg_type t ON t.oid=e.enumtypid JOIN pg_namespace n ON n.oid=t.typnamespace WHERE n.nspname='modulo4' AND t.typname='enum_tipo_evento_auditoria_m04'")).scalars())
    assert valores == {t.value for t in TipoEventoM04}


@pytest.mark.parametrize('actor', ['USUARIO', 'SISTEMA', 'DISPOSITIVO_EDGE'])
def test_evento_valido_se_persiste_y_no_crea_incidente(app_db, actor):
    db, usuario = app_db
    correlacion = uuid.uuid4()
    resultado = SqlAlchemyEventoAuditoriaM04Repository(db).registrar(**evento(
        correlacion_id=correlacion, tipo_actor=actor, id_usuario=usuario if actor=='USUARIO' else None,
        id_sistema=None if actor=='USUARIO' else 'M04',
    ))
    assert resultado.aceptado
    registro, = filas(db, correlacion)
    assert registro['tipo_evento'] == 'HISTORIAL_CONSULTADO'
    assert registro['id_referencia'] == 'consulta-1'


@pytest.mark.parametrize('fallo', ['tipo_evento', 'tipo_actor', 'actor'])
def test_defensa_bd_real_aisla_el_rechazo_y_conserva_sesion(app_db, monkeypatch, fallo):
    db, usuario = app_db
    correlacion = uuid.uuid4()
    respaldo = Respaldo()
    # Se omite SOLO el validador de aplicación para ejercer enum/CHECK reales.
    monkeypatch.setattr(modulo_repo, 'validar_evento', lambda **_kw: ())
    if fallo=='tipo_evento':
        monkeypatch.setattr(modulo_repo, '_campos_requeridos', lambda *_a: [])
        cambios = {'tipo_evento':'EVENTO_INVENTADO'}
    elif fallo=='tipo_actor':
        cambios = {'tipo_actor':'OTRO'}
    else:
        cambios = {'id_usuario':usuario}
    resultado = SqlAlchemyEventoAuditoriaM04Repository(db, respaldo).registrar(**evento(correlacion_id=correlacion, **cambios))
    assert not resultado.aceptado and resultado.campos_invalidos == (fallo,)
    assert db.execute(text('SELECT current_user')).scalar_one() == 'sgpmp_app'
    db.commit()
    registro, = filas(db, correlacion)
    assert registro['tipo_evento'] == 'AUDITORIA_EVENTO_INVALIDO'
    assert respaldo.eventos == []  # El inválido nunca queda pendiente de reintentar.


def test_rechazo_no_hace_commit_y_rollback_conserva_evidencia_tecnica(app_db, caplog):
    db, _ = app_db
    correlacion = uuid.uuid4()
    with caplog.at_level(logging.ERROR):
        SqlAlchemyEventoAuditoriaM04Repository(db).registrar(**evento(correlacion_id=correlacion, payload_evento={}))
    assert len(filas(db, correlacion)) == 1
    db.rollback()
    assert filas(db, correlacion) == []  # No hay commit oculto ni transacción autónoma.
    assert str(correlacion) in caplog.text and 'AUDITORIA_EVENTO_INVALIDO' in caplog.text


def test_no_se_insertan_eventos_parcialmente_antes_de_validar(app_db):
    db, _ = app_db
    correlacion = uuid.uuid4()
    repo = SqlAlchemyEventoAuditoriaM04Repository(db)
    resultado = repo.registrar(**evento(correlacion_id=correlacion, id_referencia=None))
    assert not resultado.aceptado
    assert repo.registrar(**evento(correlacion_id=correlacion)).aceptado
    db.commit()
    assert [f['tipo_evento'] for f in filas(db, correlacion)] == ['AUDITORIA_EVENTO_INVALIDO', 'HISTORIAL_CONSULTADO']


@pytest.mark.parametrize('rol,codigo', [(1,200), (3,200), (2,403), (4,403), (5,403)])
def test_consulta_http_con_jwt_y_rbac(client, db_session, crear_usuario_db, crear_auth_headers, rol, codigo):
    usuario = crear_usuario_db(id_rol=rol)
    respuesta = client.get('/prediccion/auditoria', headers=crear_auth_headers(usuario))
    assert respuesta.status_code == codigo, respuesta.text
    if codigo == 200:
        # La consulta global deja una referencia propia correlacionada.
        registro = db_session.execute(text("SELECT correlacion_id,id_referencia FROM modulo4.eventos_auditoria_m04 WHERE id_usuario=:u AND tipo_evento='HISTORIAL_CONSULTADO' ORDER BY fecha_evento DESC LIMIT 1"), {'u':usuario['id_usuario']}).one()
        assert str(registro.correlacion_id) == registro.id_referencia


def test_http_exige_autenticacion(client):
    assert client.get('/prediccion/auditoria').status_code == 401


def test_conflicto_clinico_emite_actor_valido_con_constraint_real(app_db):
    """Solo la auditoría usa PostgreSQL; los otros puertos son fakes explícitos."""
    from datetime import datetime, timedelta, timezone
    from types import SimpleNamespace
    from unittest.mock import Mock
    from src.prediction.application.use_cases.retroalimentacion.registrar_retroalimentacion_use_case import RegistrarRetroalimentacionUseCase
    from src.prediction.infrastructure.dto.registrar_retroalimentacion_dto import RegistrarRetroalimentacionDTO
    db, usuario = app_db
    resultado = uuid.uuid4()
    resultados, clinica, patologias, parametros = Mock(), Mock(), Mock(), Mock()
    resultados.obtener_por_id.return_value = {'fecha_inferencia':datetime.now(timezone.utc)-timedelta(days=1), 'id_activo_biologico':876}
    clinica.obtener_por_resultado_y_usuario.return_value = None
    clinica.listar_por_resultado.return_value = [SimpleNamespace(estado_retroalimentacion='CORRECTO',id_usuario_veterinario=-1)]
    def guardar(entidad):
        entidad.id_retroalimentacion = uuid.uuid4()
        return entidad
    clinica.guardar.side_effect = guardar
    patologias.obtener_por_id.return_value = SimpleNamespace(es_activo=True)
    parametros.obtener.return_value = {'ventana_retroalimentacion_dias':SimpleNamespace(valor=90,minimo=None,maximo=None)}
    respaldo = Respaldo()
    RegistrarRetroalimentacionUseCase(db=db,repo=clinica,resultado_port=resultados,patologia_repo=patologias,
        auditoria_repo=SqlAlchemyEventoAuditoriaM04Repository(db,respaldo),parametros_port=parametros).execute(
        RegistrarRetroalimentacionDTO(id_resultado_inferencia=resultado,id_activo_biologico=876,
            estado_retroalimentacion='INCORRECTO',diagnosticos_reales=[1]),id_usuario_veterinario=usuario)
    conflicto = db.execute(text("SELECT tipo_actor::text,id_usuario,id_sistema FROM modulo4.eventos_auditoria_m04 WHERE tipo_evento='CONFLICTO_RETROALIMENTACION' AND id_referencia=:r"),{'r':str(resultado)}).one()
    assert tuple(conflicto) == ('USUARIO',usuario,None)
    assert respaldo.eventos == []


def test_consultas_globales_y_exportacion_preservan_eventos(app_db):
    from src.prediction.application.use_cases.versiones_modelo.consultar_versiones_use_case import ConsultarVersionesUseCase
    from src.prediction.application.use_cases.ota.listar_despliegues_use_case import ListarDesplieguesUseCase
    from src.prediction.application.use_cases.auditoria.exportar_auditoria_m04_use_case import ExportarAuditoriaM04UseCase
    from unittest.mock import Mock
    db, usuario = app_db
    auditoria = SqlAlchemyEventoAuditoriaM04Repository(db,Respaldo())
    versiones, ota = Mock(), Mock()
    versiones.listar.return_value = ([],0)
    ota.listar.return_value = ([],0)
    ConsultarVersionesUseCase(repo=versiones).listar()
    ListarDesplieguesUseCase(repo=ota,version_port=Mock()).execute(
        id_version=None,id_dispositivo=None,estado=None,limit=20,offset=0)
    ExportarAuditoriaM04UseCase(db,auditoria).exportar(tipo_evento=None,fecha_desde=None,fecha_hasta=None,
        id_usuario=None,id_sistema=None,id_referencia=None,severidad_evento=None,formato='json',id_usuario_exportador=usuario)
    registros = db.execute(text('SELECT tipo_evento::text,correlacion_id,id_referencia FROM modulo4.eventos_auditoria_m04 WHERE id_usuario=:u ORDER BY fecha_evento'),{'u':usuario}).all()
    # CU09 H-04: consultar versiones y despliegues no deja evento; exportar sí.
    assert [r[0] for r in registros] == ['EXPORTACION_GENERADA']
    assert all(str(r[1]) == r[2] for r in registros)


def test_reporte_integrity_ok_conserva_auditoria_valida(app_db):
    """RF-70: puertos OTA en memoria y bitácora/constraints reales."""
    from tests.prediction.test_dev15_orquestador_ota import _distribuida
    db, _ = app_db
    ctx, (canary, *_) = _distribuida()
    respaldo = Respaldo()
    ctx.auditoria = SqlAlchemyEventoAuditoriaM04Repository(db,respaldo)
    ctx.reportar(canary,'integrity_ok')
    db.commit()
    registro = db.execute(text("SELECT tipo_actor::text,payload_evento FROM modulo4.eventos_auditoria_m04 WHERE tipo_evento='MODELO_DISTRIBUIDO_EDGE' AND id_referencia=:r"),{'r':str(canary)}).one()
    assert registro[0] == 'DISPOSITIVO_EDGE'
    assert registro[1]['hash_verificado'] is True
    assert registro[1]['device_id'] == ctx.despliegues.filas[canary].id_dispositivo_iot
    assert registro[1]['id_version'] == ctx.despliegues.filas[canary].id_version_modelo
    assert respaldo.eventos == []
