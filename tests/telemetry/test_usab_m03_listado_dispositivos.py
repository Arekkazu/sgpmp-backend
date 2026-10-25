# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-24 | Arekkazu | USAB-M03 M3-10 RF-60: el listado usa el alcance de finca del usuario |
"""M3-10: GET /iot/dispositivos lista con el alcance de finca del usuario."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared.database import get_db
from src.shared.error_handlers import register_error_handlers
from src.shared.rbac import require_permission
from src.telemetry.domain.entities.dispositivo_con_estado import DispositivoConEstado
from src.telemetry.infrastructure.routers import infraestructura_iot_router as r


def test_listado_pasa_las_fincas_del_usuario_y_el_filtro(monkeypatch):
    llamadas = {}

    class Repo:
        def __init__(self, _db): pass

        def listar_con_estado(self, fincas, estado=None):
            llamadas['args'] = (fincas, estado)
            return [DispositivoConEstado(7, 'EDGE-QA-02', None, 3, 'Área QA 01', 'El Remanso', 'SIN_SEÑAL')]

    class Alcance:
        def __init__(self, _db): pass

        def listar_ids_fincas_permitidas(self, _u, _r): return [1]

    monkeypatch.setattr(r, 'SqlAlchemyEstadoDispositivoIoTRepository', Repo)
    monkeypatch.setattr(r, 'AlcanceFincaAdapter', Alcance)
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(r.router)
    app.dependency_overrides[get_db] = lambda: None
    app.dependency_overrides[get_current_user] = lambda: UsuarioActual(id_usuario=9, id_rol=4, id_token='t')
    for dep in r.router.routes:
        for d in getattr(dep, 'dependencies', []):
            app.dependency_overrides[d.dependency] = lambda: None

    res = TestClient(app).get('/iot/dispositivos', params={'estado': 'SIN_SEÑAL'})

    assert res.status_code == 200, res.text
    assert llamadas['args'] == ([1], 'SIN_SEÑAL')
    assert res.json()[0]['nombre_infraestructura'] == 'Área QA 01'
