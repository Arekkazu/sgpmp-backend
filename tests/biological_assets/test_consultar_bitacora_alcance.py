"""RF-52 CA-8: alcance diferenciado de la bitácora por rol y propiedad."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.biological_assets.application.use_cases.gestion.consultar_bitacora_use_case import (
    ConsultarBitacoraUseCase,
)
from src.biological_assets.infrastructure.dto.consultar_bitacora_dto import ConsultarBitacoraDTO
from src.biological_assets.infrastructure.routers import activo_biologico_router as router_module
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared.database import get_db
from src.shared.error_handlers import register_error_handlers
from src.shared.errors import AuthorizationError


class DbFake:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class BitacoraRepoFake:
    def __init__(self, activos_propios: set[int] | None = None) -> None:
        self.activos_propios = activos_propios or set()
        self.registrados = []
        self.consulta = None

    def activo_pertenece_a_usuario(self, id_activo: int, _id_usuario: int) -> bool:
        return id_activo in self.activos_propios

    def registrar(self, evento) -> None:
        self.registrados.append(evento)

    def consultar(self, **filtros):
        self.consulta = filtros
        return [], 0


class RolRepoFake:
    def __init__(self, nombre_rol: str) -> None:
        self.rol = SimpleNamespace(nombre_rol=nombre_rol)

    def obtener_por_id(self, _id_rol: int):
        return self.rol


def _usuario(id_usuario: int = 35, id_rol: int = 2) -> UsuarioActual:
    return UsuarioActual(
        id_usuario=id_usuario,
        id_token=1,
        id_rol=id_rol,
        id_estado_cuenta=2,
    )


def _caso(nombre_rol: str, repo: BitacoraRepoFake | None = None):
    db = DbFake()
    repo = repo or BitacoraRepoFake()
    caso = ConsultarBitacoraUseCase(db, repo, RolRepoFake(nombre_rol))
    return caso, db, repo


def test_productor_recibe_403_y_registra_intento_sobre_acceso_datos_ajeno() -> None:
    caso, db, repo = _caso('Productor')
    dto = ConsultarBitacoraDTO(
        id_activo_biologico=240,
        clasificacion_biologica='ACCESO_DATOS',
    )

    with pytest.raises(AuthorizationError) as capturada:
        caso.execute(dto, _usuario())

    assert capturada.value.status_code == 403
    assert capturada.value.code == 'ALCANCE_BITACORA_DENEGADO'
    assert repo.consulta is None
    assert db.commits == 1
    assert len(repo.registrados) == 1
    intento = repo.registrados[0]
    assert intento.tipo_evento == 'ACCESO_NO_AUTORIZADO'
    assert intento.resultado == 'RECHAZADO'
    assert intento.id_activo_biologico == 240
    assert intento.id_usuario_responsable == 35


def test_productor_consulta_acceso_datos_de_activo_propio() -> None:
    caso, _db, repo = _caso('Productor', BitacoraRepoFake({240}))

    registros, total = caso.execute(
        ConsultarBitacoraDTO(
            id_activo_biologico=240,
            clasificacion_biologica='ACCESO_DATOS',
        ),
        _usuario(),
    )

    assert (registros, total) == ([], 0)
    assert repo.consulta['id_propietario_acceso_datos'] == 35
    assert repo.registrados == []


def test_productor_sin_clasificacion_no_recibe_accesos_de_activos_ajenos() -> None:
    caso, _db, repo = _caso('Productor')

    caso.execute(ConsultarBitacoraDTO(), _usuario())

    assert repo.consulta['id_propietario_acceso_datos'] == 35


@pytest.mark.parametrize('clasificacion', ['GESTION_OPERATIVA', 'CONTROL_ESTADO'])
def test_contador_recibe_403_y_registra_clasificacion_no_permitida(
    clasificacion: str,
) -> None:
    caso, db, repo = _caso('Contador')

    with pytest.raises(AuthorizationError) as capturada:
        caso.execute(
            ConsultarBitacoraDTO(
                id_activo_biologico=240,
                clasificacion_biologica=clasificacion,
            ),
            _usuario(id_usuario=9, id_rol=5),
        )

    assert capturada.value.status_code == 403
    assert repo.consulta is None
    assert db.commits == 1
    assert repo.registrados[0].tipo_evento == 'ACCESO_NO_AUTORIZADO'
    assert repo.registrados[0].detalle_tecnico['clasificacion_solicitada'] == clasificacion


@pytest.mark.parametrize('clasificacion', ['TRANSFORMACION_BIOLOGICA', 'SANITARIO'])
def test_contador_conserva_acceso_a_clasificaciones_autorizadas(
    clasificacion: str,
) -> None:
    caso, _db, repo = _caso('Contador')

    caso.execute(
        ConsultarBitacoraDTO(clasificacion_biologica=clasificacion),
        _usuario(id_usuario=9, id_rol=5),
    )

    assert repo.consulta['clasificaciones_permitidas'] == {
        'TRANSFORMACION_BIOLOGICA',
        'SANITARIO',
    }


def test_contador_sin_filtro_solo_recibe_clasificaciones_autorizadas() -> None:
    caso, _db, repo = _caso('Contador')

    caso.execute(ConsultarBitacoraDTO(), _usuario(id_usuario=9, id_rol=5))

    assert repo.consulta['clasificaciones_permitidas'] == {
        'TRANSFORMACION_BIOLOGICA',
        'SANITARIO',
    }


def test_administrador_conserva_consulta_global_sin_filtros_adicionales() -> None:
    caso, _db, repo = _caso('Administrador')

    caso.execute(ConsultarBitacoraDTO(), _usuario(id_usuario=1, id_rol=1))

    assert repo.consulta['clasificaciones_permitidas'] is None
    assert repo.consulta['id_propietario_acceso_datos'] is None


def test_fallo_al_registrar_intento_no_habilita_la_consulta() -> None:
    class RepoConFallo(BitacoraRepoFake):
        def registrar(self, _evento) -> None:
            raise RuntimeError('bitácora no disponible')

    caso, db, repo = _caso('Contador', RepoConFallo())

    with pytest.raises(AuthorizationError):
        caso.execute(
            ConsultarBitacoraDTO(clasificacion_biologica='CONTROL_ESTADO'),
            _usuario(id_usuario=9, id_rol=5),
        )

    assert repo.consulta is None
    assert db.commits == 0
    assert db.rollbacks == 1


@pytest.fixture
def cliente_productor_ajeno(monkeypatch: pytest.MonkeyPatch):
    db = DbFake()
    repo = BitacoraRepoFake()
    monkeypatch.setattr(router_module, 'SqlAlchemyBitacoraAuditoriaRepository', lambda _db: repo)
    monkeypatch.setattr(router_module, 'SqlAlchemyRolRepository', lambda _db: RolRepoFake('Productor'))

    app = FastAPI()
    register_error_handlers(app)
    app.include_router(router_module.router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = _usuario

    ruta = next(
        ruta
        for ruta in app.routes
        if ruta.path == '/activos-biologicos/auditoria' and 'GET' in ruta.methods
    )
    for dependencia in ruta.dependant.dependencies:
        if dependencia.call not in {get_db, get_current_user}:
            app.dependency_overrides[dependencia.call] = lambda: None

    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, repo

    app.dependency_overrides.clear()


def test_endpoint_reproduce_tc_m02_266_con_http_403(cliente_productor_ajeno) -> None:
    client, repo = cliente_productor_ajeno

    respuesta = client.get(
        '/activos-biologicos/auditoria',
        params={
            'id_activo_biologico': 240,
            'clasificacion_biologica': 'ACCESO_DATOS',
            'page_size': 10,
        },
    )

    assert respuesta.status_code == 403, respuesta.text
    assert respuesta.json()['error_code'] == 'ALCANCE_BITACORA_DENEGADO'
    assert repo.consulta is None
    assert repo.registrados[0].tipo_evento == 'ACCESO_NO_AUTORIZADO'
