# | Fecha      | Nombre  | Que se hizo |
# |------------|---------|-------------|
# | 2026-10-22 | Leandro | DEV-47 RF-63: verifica hash incidentes y contrato HTTP |
# | 2026-10-25 | Arekkazu | INC-M03-137-G179 RF-63 E8: sin componente la retención es la de NIC41 |
# | 2026-10-26 | Leandro | INC-M03-125-G12 RF-53/63: verificar clasificación de fallas con contexto seguro de solicitud. |
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.telemetry.application.use_cases.auditoria.evidencia_iot import registrar_evidencia
from src.telemetry.application.use_cases.auditoria.registrar_evento_auditoria_iot_use_case import _calcular_hash
from src.telemetry.application.use_cases.auditoria.verificar_integridad_bitacora_use_case import VerificarIntegridadBitacoraUseCase, hash_coincide
from src.telemetry.domain.entities.evento_auditoria_iot import ComponenteOrigen as C, TipoResultado as R


class Memoria:
    def __init__(self):
        self.eventos = []

    def registrar(self, evento):
        nuevo = replace(evento, id_evento=uuid4())
        self.eventos.append(nuevo)
        return nuevo

    def obtener(self, identificador):
        return next(e for e in self.eventos if e.id_evento == identificador)

    def listar_todos_para_verificacion(self, *args):
        return list(self.eventos)

    def bloquear_integridad(self, *args):
        pass

    def buscar_incidente(self, clave):
        return next((e for e in self.eventos if (e.accion_detallada or {}).get('compromiso') == clave), None)

    def aviso_confirmado(self, identificador):
        return any((e.accion_detallada or {}).get('aviso_incidente') == str(identificador) for e in self.eventos)


def fuente(repo):
    return registrar_evidencia(repo, 'TELEMETRIA_VALIDADA', C.RF53, detalle={'id_telemetria': 17})


def test_evidencia_usa_hash_oficial_sin_commit():
    repo = Memoria()
    evento = fuente(repo)
    assert evento.hash_integridad == _calcular_hash(evento)
    assert evento.clasificacion_registro == 'NIC41' and evento.retencion_aplicable == 5


def test_fallo_de_escritura_no_simula_evidencia():
    repo = Mock()
    repo.registrar.side_effect = lambda e: e
    with pytest.raises(RuntimeError, match='evidencia obligatoria'):
        fuente(repo)


def test_integridad_valida_no_crea_incidentes():
    repo = Memoria(); fuente(repo)
    r = VerificarIntegridadBitacoraUseCase(Mock(), repo).execute()
    assert r.comprometidos == 0 and len(repo.eventos) == 1


@pytest.mark.parametrize('campo,valor', [('descripcion', 'alterado'), ('resultado', R.FALLIDO),
                                        ('accion_detallada', {'alterado': True})])
def test_alteracion_de_campos_cubiertos_crea_un_incidente(campo, valor):
    repo = Memoria(); original = fuente(repo)
    setattr(original, campo, valor)
    copia = deepcopy(original)
    caso = VerificarIntegridadBitacoraUseCase(Mock(), repo)
    primero = caso.execute(); segundo = caso.execute()
    assert primero.incidentes_creados == 1 and segundo.incidentes_creados == 0
    assert segundo.ids_comprometidos == [str(original.id_evento)]
    assert original == copia
    incidente = repo.eventos[-1]
    assert incidente.severidad_log == 'CRITICAL' and hash_coincide(incidente)
    # E8: sin RF emisor identificable la clasificación es ambigua → NIC41, 5 años.
    assert incidente.componente_origen is None and incidente.retencion_aplicable == 5


def test_offset_equivalente_no_es_alteracion():
    repo = Memoria(); original = fuente(repo)
    original.fecha_hora = original.fecha_hora.astimezone(timezone(timedelta(hours=-5)))
    assert hash_coincide(original)


def test_sin_hash_e_incompleto_se_distinguen_de_hash_alterado():
    repo = Memoria(); original = fuente(repo)
    original.hash_integridad = ''; original.registro_incompleto = True
    r = VerificarIntegridadBitacoraUseCase(Mock(), repo).execute()
    assert r.comprometidos == 0
    assert r.ids_sin_hash == r.ids_incompletos == [str(original.id_evento)]


def test_aviso_confirmado_no_se_repite_y_no_genera_recursion():
    repo = Memoria(); original = fuente(repo); original.hash_integridad = '0' * 64
    avisos = Mock(); avisos.notificar.return_value = 2
    caso = VerificarIntegridadBitacoraUseCase(Mock(), repo, avisos)
    assert caso.execute().notificaciones_pendientes == 0
    assert caso.execute().incidentes_creados == 0
    assert avisos.notificar.call_count == 1 and len(repo.eventos) == 3


def test_fallo_aviso_conserva_incidente_y_permite_recuperacion():
    repo = Memoria(); original = fuente(repo); original.hash_integridad = '0' * 64
    avisos = Mock(); avisos.notificar.side_effect = RuntimeError('sin red')
    db = Mock(); caso = VerificarIntegridadBitacoraUseCase(db, repo, avisos)
    assert caso.execute().notificaciones_pendientes == 1
    assert len(repo.eventos) == 2 and db.commit.called and db.rollback.called
    avisos.notificar.side_effect = None; avisos.notificar.return_value = 1
    assert caso.execute().notificaciones_pendientes == 0
    assert len(repo.eventos) == 3


def test_error_infraestructura_no_se_presenta_como_compromiso():
    repo = Mock(); repo.listar_todos_para_verificacion.side_effect = RuntimeError('sin BD')
    with pytest.raises(RuntimeError, match='sin BD'):
        VerificarIntegridadBitacoraUseCase(Mock(), repo).execute()
    repo.registrar.assert_not_called()


@pytest.mark.parametrize('metodo', ['get', 'post'])
def test_endpoint_estatico_get_post_y_rbac_sin_permiso(monkeypatch, metodo):
    from types import SimpleNamespace
    from src.shared.database import get_db
    from src.shared.error_handlers import register_error_handlers
    from src.shared import rbac
    from src.identity_access.infrastructure.dependencies import get_current_user
    from src.telemetry.infrastructure.routers.auditoria_iot_router import router
    app = FastAPI(); register_error_handlers(app); app.include_router(router)
    app.dependency_overrides[get_db] = lambda: Mock()
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id_estado_cuenta=2, id_rol=777)
    # La autorización real consulta este puerto; no se altera el endpoint.
    monkeypatch.setattr(rbac, 'tiene_permiso', lambda *a, **k: False)
    with TestClient(app, raise_server_exceptions=False) as client:
        respuesta = getattr(client, metodo)('/iot/auditoria/verificar-integridad')
    assert respuesta.status_code == 403, respuesta.text


@pytest.mark.parametrize('clase,esperado', [('negocio', None), ('infraestructura', 'FALLA_PERSISTENCIA'),
                                         ('sql', 'FALLA_PERSISTENCIA'), ('desconocido', None)])
def test_error_de_negocio_no_se_reclasifica_como_fallo_de_persistencia(monkeypatch, clase, esperado):
    from sqlalchemy.exc import SQLAlchemyError
    from src.shared.errors import ValidationError, InfrastructureError
    from src.shared.error_handlers import register_error_handlers
    from src.telemetry.infrastructure.routers import ruta_ingesta_auditada as modulo
    from fastapi import APIRouter
    registro = Mock()
    monkeypatch.setattr(modulo, '_registrar_error', registro)
    errores = {
        'negocio': ValidationError(code='ERROR_UNIDAD', message='Unidad incompatible.'),
        'infraestructura': InfrastructureError(code='BD_ERROR', message='Sin persistencia.',
                                              original_error=SQLAlchemyError('detalle interno')),
        'sql': SQLAlchemyError('detalle interno'), 'desconocido': RuntimeError('otro error'),
    }
    errores['negocio'].original_error = SQLAlchemyError('regla funcional')
    router = APIRouter(route_class=modulo.RutaIngestaAuditada)

    @router.post('/iot/telemetria')
    def endpoint():
        raise errores[clase]

    app = FastAPI(); register_error_handlers(app); app.include_router(router)
    with TestClient(app, raise_server_exceptions=False) as client:
        client.post('/iot/telemetria', json={})
    if esperado:
        registro.assert_called_once()
        ruta, tipo, detalle = registro.call_args.args
        assert (ruta, tipo) == ('/iot/telemetria', esperado)
        assert 'id_correlacion' in detalle and 'hash_solicitud' in detalle
    else:
        registro.assert_not_called()
