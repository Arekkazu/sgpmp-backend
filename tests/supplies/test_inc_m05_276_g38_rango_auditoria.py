# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-11-08 | Leandro | INC-M05-276-G38 RF-80: reproducir y validar filtros temporales antes de consultar la bitácora. |
"""Regresiones de dominio y contrato HTTP con un puerto de lectura falso."""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock
from zoneinfo import ZoneInfo

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.identity_access.domain.entities.cuenta import Cuenta
from src.identity_access.infrastructure.dependencies import get_current_user
from src.shared.database import get_db
from src.shared.error_handlers import register_error_handlers
from src.shared.errors import ValidationError
from src.supplies.application.use_cases.auditoria.consultar_auditoria_suministros_use_case import (
    ConsultarAuditoriaSuministrosUseCase,
)
from src.supplies.application.use_cases.auditoria.exportar_auditoria_suministros_use_case import (
    ExportarAuditoriaSuministrosUseCase,
)
from src.supplies.domain.repositories.auditoria_suministro_read_port import (
    AuditoriaSuministroReadPort, FiltrosAuditoriaSuministro,
)
from src.supplies.infrastructure.routers import auditoria_suministros_router as rutas


@pytest.fixture
def contrato(monkeypatch):
    puerto = Mock(spec=AuditoriaSuministroReadPort)
    puerto.consultar.return_value = ([], 0)
    consultar = Mock(return_value=ConsultarAuditoriaSuministrosUseCase(puerto))
    exportar = Mock(return_value=ExportarAuditoriaSuministrosUseCase(puerto))
    monkeypatch.setattr(rutas, 'build_consultar_auditoria_use_case', consultar)
    monkeypatch.setattr(rutas, 'build_exportar_auditoria_use_case', exportar)
    # Autorización simulada solo aquí; JWT/RBAC reales se verifican en integración.
    monkeypatch.setattr('src.shared.rbac.tiene_permiso', lambda *args: True)
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(rutas.router)
    app.dependency_overrides[get_db] = lambda: Mock()
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id_usuario=7, id_rol=1, id_estado_cuenta=Cuenta.ESTADO_ACTIVO,
    )
    with TestClient(app) as client:
        yield SimpleNamespace(client=client, puerto=puerto, consultar=consultar, exportar=exportar, app=app)


def test_rango_invertido_es_error_y_no_consulta_el_repositorio(contrato):
    r = contrato.client.get('/suministros/auditoria', params={
        'fecha_desde': '2026-11-08T18:00:00Z', 'fecha_hasta': '2026-11-07T18:00:00Z',
    })
    assert r.status_code == 400, r.text
    assert r.json()['error_code'] == 'VAL_ENTRADA'
    contrato.puerto.consultar.assert_not_called()


@pytest.mark.parametrize('desde,hasta', [
    ('2026-11-02T10:00:00+00:00', '2026-11-01T10:00:00+00:00'),
    ('2026-11-01T10:00:00-05:00', '2026-11-01T11:00:00+00:00'),
    ('2026-11-02T10:00:00', '2026-11-01T10:00:00+00:00'),
    ('2026-11-02T10:00:00+00:00', '2026-11-01T10:00:00'),
])
def test_filtros_rechazan_inversion_por_instante(desde, hasta):
    with pytest.raises(ValidationError) as error:
        FiltrosAuditoriaSuministro(fecha_desde=datetime.fromisoformat(desde), fecha_hasta=datetime.fromisoformat(hasta))
    assert error.value.code == 'VAL_ENTRADA'
    assert 'Corrige las fechas' in error.value.message


@pytest.mark.parametrize('desde,hasta', [
    (None, None),
    ('2026-11-01T10:00:00', None),
    (None, '2026-11-01T10:00:00'),
    ('2026-11-01T10:00:00+00:00', '2026-11-01T10:00:00+00:00'),
    ('2026-11-01T05:00:00-05:00', '2026-11-01T11:00:00+01:00'),
    ('2026-11-01T10:00:00', '2026-11-01T10:00:00+00:00'),
    ('2026-11-01T10:00:00+00:00', '2026-11-01T10:00:00'),
])
def test_filtros_admiten_igualdad_y_extremos_opcionales(desde, hasta):
    a = datetime.fromisoformat(desde) if desde else None
    b = datetime.fromisoformat(hasta) if hasta else None
    filtros = FiltrosAuditoriaSuministro(fecha_desde=a, fecha_hasta=b)
    assert filtros.fecha_desde == a and filtros.fecha_hasta == b


@pytest.mark.parametrize('formato', ['csv', 'xlsx', 'pdf'])
def test_exportacion_no_lee_ni_genera_archivo_con_rango_invertido(contrato, formato):
    r = contrato.client.get('/suministros/auditoria/exportar', params={
        'fecha_desde': '2026-11-08T18:00:00Z', 'fecha_hasta': '2026-11-07T18:00:00Z', 'formato': formato,
    })
    assert r.status_code == 400 and r.json()['error_code'] == 'VAL_ENTRADA', r.text
    contrato.puerto.consultar.assert_not_called()
    contrato.exportar.assert_not_called()
    assert 'content-disposition' not in r.headers


@pytest.mark.parametrize('ruta', ['/suministros/auditoria', '/suministros/auditoria/exportar'])
@pytest.mark.parametrize('campo', ['fecha_desde', 'fecha_hasta'])
def test_formato_invalido_no_consulta_el_puerto(contrato, ruta, campo):
    r = contrato.client.get(ruta, params={campo: 'fecha-invalida'})
    assert r.status_code == 400 and r.json()['error_code'] == 'VAL_ENTRADA', r.text
    contrato.puerto.consultar.assert_not_called()


def test_consulta_valida_vacia_conserva_200_y_filtros_normalizados(contrato):
    r = contrato.client.get('/suministros/auditoria', params={
        'fecha_desde': '2026-11-01T05:00:00-05:00', 'fecha_hasta': '2026-11-01T10:00:00Z',
    })
    assert r.status_code == 200 and r.json()['items'] == [] and r.json()['total'] == 0, r.text
    filtros = contrato.puerto.consultar.call_args.args[0]
    assert filtros.fecha_desde == filtros.fecha_hasta == datetime(2026, 11, 1, 10, tzinfo=timezone.utc)


def test_openapi_documenta_400_en_consulta_y_exportacion(contrato):
    esquema = contrato.app.openapi()
    for ruta in ('/suministros/auditoria', '/suministros/auditoria/exportar'):
        assert '400' in esquema['paths'][ruta]['get']['responses']


def test_hora_repetida_por_cambio_de_zona_se_compara_en_utc():
    zona = ZoneInfo('America/New_York')
    # 01:30 de la segunda ocurrencia es posterior a 01:45 de la primera.
    with pytest.raises(ValidationError):
        FiltrosAuditoriaSuministro(
            fecha_desde=datetime(2026, 11, 1, 1, 30, tzinfo=zona, fold=1),
            fecha_hasta=datetime(2026, 11, 1, 1, 45, tzinfo=zona, fold=0),
        )
