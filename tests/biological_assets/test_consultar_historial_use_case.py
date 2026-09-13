"""RF-46 E-04: mensaje informativo cuando los filtros no encuentran eventos."""
from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.biological_assets.application.use_cases.gestion.consultar_historial_use_case import (
    ConsultarHistorialUseCase,
)
from src.biological_assets.domain.entities.activo_biologico import PaginaHistorial, RegistroHistorial
from src.biological_assets.infrastructure.dto.consultar_historial_dto import ConsultarHistorialDTO
from src.biological_assets.infrastructure.routers import activo_biologico_router as router_module
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared.database import get_db


class DbFake:
    pass


class ActivoRepoFake:
    def __init__(self, activo: object | None = object()) -> None:
        self.activo = activo

    def obtener_por_id(self, _id: int, ids_fincas_permitidas=None):
        return self.activo


class TransferenciaRepoFake:
    def __init__(self, pagina: PaginaHistorial) -> None:
        self.pagina = pagina
        self.parametros: dict | None = None

    def consultar_historial(self, **kwargs) -> PaginaHistorial:
        self.parametros = kwargs
        return self.pagina


def _usuario() -> UsuarioActual:
    return UsuarioActual(id_usuario=7, id_token=1, id_rol=2)


def _pagina(registros: list[RegistroHistorial] | None = None) -> PaginaHistorial:
    registros = registros or []
    return PaginaHistorial(
        registros=registros,
        total_registros=len(registros),
        pagina_actual=1,
        total_paginas=1,
        registros_por_pagina=20,
    )


def _ejecutar(dto: ConsultarHistorialDTO, pagina: PaginaHistorial) -> PaginaHistorial:
    return ConsultarHistorialUseCase(
        db=DbFake(),
        activo_repo=ActivoRepoFake(),
        transferencia_repo=TransferenciaRepoFake(pagina),
    ).execute(130, dto, _usuario())


@pytest.mark.parametrize(
    'dto',
    [
        ConsultarHistorialDTO(categoria_evento='BAJA'),
        ConsultarHistorialDTO(fecha_inicio=date(2030, 1, 1)),
        ConsultarHistorialDTO(fecha_fin=date(2030, 12, 31)),
    ],
)
def test_filtro_sin_resultados_informa_flujo_e04(dto: ConsultarHistorialDTO) -> None:
    resultado = _ejecutar(dto, _pagina())

    assert resultado.total_registros == 0
    assert resultado.registros == []
    assert resultado.mensaje == (
        'No se encontraron eventos para el activo 130 con los filtros aplicados. '
        'Puede ampliar el rango de fechas o cambiar la categoría de evento.'
    )


def test_historial_vacio_sin_filtros_no_aplica_flujo_e04() -> None:
    resultado = _ejecutar(ConsultarHistorialDTO(), _pagina())

    assert resultado.mensaje is None


def test_filtro_con_resultados_conserva_registros_y_no_agrega_mensaje() -> None:
    registro = RegistroHistorial(
        categoria='BAJA',
        fecha_evento=datetime(2026, 9, 1, tzinfo=timezone.utc),
        descripcion='Evento de prueba',
        detalle_especifico={},
        usuario_responsable='QA',
        modulo_origen='RF-45',
    )

    resultado = _ejecutar(ConsultarHistorialDTO(categoria_evento='BAJA'), _pagina([registro]))

    assert resultado.registros == [registro]
    assert resultado.total_registros == 1
    assert resultado.mensaje is None


@pytest.fixture
def cliente_historial(monkeypatch: pytest.MonkeyPatch):
    mensaje = (
        'No se encontraron eventos para el activo 130 con los filtros aplicados. '
        'Puede ampliar el rango de fechas o cambiar la categoría de evento.'
    )

    class UseCaseFake:
        def __init__(self, **_kwargs) -> None:
            pass

        def execute(self, *_args, **_kwargs) -> PaginaHistorial:
            return PaginaHistorial(
                registros=[],
                total_registros=0,
                pagina_actual=1,
                total_paginas=1,
                registros_por_pagina=20,
                mensaje=mensaje,
            )

    monkeypatch.setattr(router_module, 'ConsultarHistorialUseCase', UseCaseFake)
    monkeypatch.setattr(router_module, 'SqlAlchemyActivoBiologicoRepository', lambda _db: object())
    monkeypatch.setattr(router_module, 'SqlAlchemyTransferenciaRepository', lambda _db: object())
    monkeypatch.setattr(router_module, 'SqlAlchemyBitacoraAuditoriaRepository', lambda _db: object())
    monkeypatch.setattr(router_module, '_ids_fincas_alcance', lambda _db, _usuario: None)

    app = FastAPI()
    app.include_router(router_module.router)
    app.dependency_overrides[get_db] = lambda: DbFake()
    app.dependency_overrides[get_current_user] = _usuario

    ruta_historial = next(
        ruta
        for ruta in app.routes
        if ruta.path == '/activos-biologicos/{id_activo}/historial'
    )
    for dependencia in ruta_historial.dependant.dependencies:
        if dependencia.call not in {get_db, get_current_user}:
            app.dependency_overrides[dependencia.call] = lambda: None

    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, mensaje


def test_router_expone_mensaje_en_el_contrato_http(cliente_historial) -> None:
    client, mensaje = cliente_historial

    respuesta = client.get('/activos-biologicos/130/historial?categoria_evento=BAJA')

    assert respuesta.status_code == 200
    assert respuesta.json() == {
        'id_activo_biologico': 130,
        'total_registros': 0,
        'pagina_actual': 1,
        'total_paginas': 1,
        'registros_por_pagina': 20,
        'registros': [],
        'mensaje': mensaje,
    }


@pytest.mark.parametrize('metodo', ['post', 'patch', 'delete'])
def test_historial_rechaza_metodos_de_escritura(cliente_historial, metodo: str) -> None:
    client, _mensaje = cliente_historial

    respuesta = getattr(client, metodo)('/activos-biologicos/130/historial')

    assert respuesta.status_code == 405
    assert 'GET' in respuesta.headers['Allow']
    assert respuesta.json() == {'detail': 'Method Not Allowed'}
