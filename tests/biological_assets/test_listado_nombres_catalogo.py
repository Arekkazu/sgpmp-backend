# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-14 | Arekkazu | FILTRO-FINCA RF-35: el listado también trae la finca de cada activo |
"""M2-04 (reporte UAT 07/10/2026): el listado mostraba "Especie #4" en vez del nombre."""
from __future__ import annotations

from types import SimpleNamespace

from src.biological_assets.infrastructure.routers import activo_biologico_router as router_module


class _DbFake:
    def execute(self, sql, *_args, **_kwargs):
        if 'modulo9.especies' in str(sql):
            filas = [(4, 'Cachama Blanca')]
        else:
            filas = [SimpleNamespace(id_infraestructura=6, nombre='Piscina-Cam-01', id_finca=3, finca='La Esperanza')]
        return SimpleNamespace(fetchall=lambda: filas)


def test_completa_nombre_de_especie_infraestructura_y_finca() -> None:
    activo = SimpleNamespace(id_especie=4, id_infraestructura=6, nombre_especie=None, nombre_infraestructura=None,
                             id_finca=None, nombre_finca=None)

    router_module._completar_nombres_catalogo(_DbFake(), [activo])

    assert activo.nombre_especie == 'Cachama Blanca'
    assert activo.nombre_infraestructura == 'Piscina-Cam-01'
    assert (activo.id_finca, activo.nombre_finca) == (3, 'La Esperanza')
