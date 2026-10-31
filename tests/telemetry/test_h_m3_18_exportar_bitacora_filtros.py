# | Fecha      | Nombre   | Que se hizo                                                        |
# |------------|----------|--------------------------------------------------------------------|
# | 2026-10-29 | Arekkazu | H-M3-18/19 RF-63: la exportación respeta filtros y alcance         |
# | 2026-10-31 | Arekkazu | USAB-M03-M04 M3-14 RF-63: la clasificación se resuelve por permiso |
"""H-M3-18/19: el CSV/JSON exportado conserva los filtros de la pantalla y el alcance por finca."""
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.identity_access.infrastructure.dependencies import get_current_user
from src.shared.database import get_db
from src.telemetry.infrastructure.routers import auditoria_iot_router as modulo


def test_exportar_pasa_entidad_severidad_resultado_y_fincas(monkeypatch):
    capturado = {}

    class _UseCase:
        def __init__(self, **_):
            pass

        def listar(self, **kwargs):
            capturado.update(kwargs)
            return [], 0

    monkeypatch.setattr(modulo, 'ConsultarBitacoraIotUseCase', _UseCase)
    monkeypatch.setattr(modulo, '_fincas_de_la_bitacora', lambda db, usuario: [7])
    # M3-14: la clasificación pedida pasa tal cual para quien tiene datos técnicos.
    monkeypatch.setattr(modulo, '_clasificacion_de_la_bitacora', lambda db, usuario, pedida: pedida)
    app = FastAPI()
    app.include_router(modulo.router)
    app.dependency_overrides[get_db] = lambda: object()
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id_usuario=1, id_rol=1)
    for ruta in modulo.router.routes:
        for dep in ruta.dependencies:
            app.dependency_overrides[dep.dependency] = lambda: None
    ruta = next(r.path for r in modulo.router.routes if r.path.endswith('/exportar'))
    respuesta = TestClient(app).get(ruta, params={
        'entidad_afectada_id': '14499', 'severidad_log': 'WARNING', 'resultado': 'FALLIDO', 'formato': 'csv'})
    assert respuesta.status_code == 200, respuesta.text
    assert capturado['entidad_afectada_id'] == '14499'
    assert capturado['severidad_log'] == 'WARNING' and capturado['resultado'] == 'FALLIDO'
    assert capturado['ids_fincas_permitidas'] == [7]
