"""INC-M02-96-G94 — GET /{id_activo}/datos-consolidados no aplicaba ningun
limitador de tasa (RF-50 exige 100 solicitudes/minuto). Verifica que el
limitador esta realmente conectado a la ruta y que corta con 429 al superar
el limite configurado, en el mismo estilo que
tests/shared/test_inc_m09_21_g125_02_rate_limit.py.
"""
from __future__ import annotations

import pytest

from src.biological_assets.infrastructure.routers.activo_biologico_router import (
    _LIMITE_DATOS_CONSOLIDADOS,
    router,
)
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import TooManyRequestsError


def _usuario(id_usuario: int) -> UsuarioActual:
    return UsuarioActual(id_usuario=id_usuario, id_token=1, id_rol=1)


def test_ruta_datos_consolidados_declara_el_limitador() -> None:
    ruta = next(
        r for r in router.routes
        if getattr(r, "path", None) == "/activos-biologicos/{id_activo}/datos-consolidados"
    )
    dependencias = {d.call for d in ruta.dependant.dependencies}
    assert _LIMITE_DATOS_CONSOLIDADOS in dependencias
    assert 429 in ruta.responses


def test_limitador_corta_tras_100_solicitudes_por_minuto() -> None:
    for _ in range(100):
        _LIMITE_DATOS_CONSOLIDADOS(request=None, usuario_actual=_usuario(9001))

    with pytest.raises(TooManyRequestsError) as exc:
        _LIMITE_DATOS_CONSOLIDADOS(request=None, usuario_actual=_usuario(9001))
    assert exc.value.code == "LIMITE_TASA_EXCEDIDO"
    assert exc.value.status_code == 429


if __name__ == "__main__":
    test_ruta_datos_consolidados_declara_el_limitador()
    test_limitador_corta_tras_100_solicitudes_por_minuto()
    print("OK")
