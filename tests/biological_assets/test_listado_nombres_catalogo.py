"""M2-04 (reporte UAT 07/10/2026): el listado mostraba "Especie #4" en vez del nombre."""
from __future__ import annotations

from types import SimpleNamespace

from src.biological_assets.infrastructure.routers import activo_biologico_router as router_module


class _DbFake:
    def execute(self, *_args, **_kwargs):
        filas = [
            SimpleNamespace(tipo='E', id=4, nombre='Cachama Blanca'),
            SimpleNamespace(tipo='I', id=6, nombre='Piscina-Cam-01'),
        ]
        return SimpleNamespace(fetchall=lambda: filas)


def test_completa_nombre_de_especie_e_infraestructura() -> None:
    activo = SimpleNamespace(id_especie=4, id_infraestructura=6, nombre_especie=None, nombre_infraestructura=None)

    router_module._completar_nombres_catalogo(_DbFake(), [activo])

    assert activo.nombre_especie == 'Cachama Blanca'
    assert activo.nombre_infraestructura == 'Piscina-Cam-01'
