"""INC-M09-21-G125-02 — Límite de tasa en memoria (`src/shared/rate_limit.py`).

El pentest reportó que `POST /configuracion/dispositivos-iot` no aplicaba
ningún control de tasa: 50 registros concurrentes se procesaron enteros sin
un solo 429. Verifica que la dependencia `rate_limit` corta al usuario tras
el límite configurado, dentro de la ventana, y que un usuario distinto no
comparte el contador.
"""
from __future__ import annotations

import pytest

from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import TooManyRequestsError
from src.shared.rate_limit import rate_limit


def _usuario(id_usuario: int) -> UsuarioActual:
    return UsuarioActual(id_usuario=id_usuario, id_token=1, id_rol=1)


def test_permite_hasta_el_limite_y_luego_corta_con_429() -> None:
    dependencia = rate_limit(3, 60, alcance="test_burst_1")
    for _ in range(3):
        dependencia(request=None, usuario_actual=_usuario(101))

    with pytest.raises(TooManyRequestsError) as exc:
        dependencia(request=None, usuario_actual=_usuario(101))
    assert exc.value.code == "LIMITE_TASA_EXCEDIDO"
    assert exc.value.status_code == 429


def test_usuarios_distintos_no_comparten_contador() -> None:
    dependencia = rate_limit(1, 60, alcance="test_burst_2")
    dependencia(request=None, usuario_actual=_usuario(201))

    with pytest.raises(TooManyRequestsError):
        dependencia(request=None, usuario_actual=_usuario(201))

    # Otro usuario, mismo alcance: no debe verse afectado por el límite anterior.
    dependencia(request=None, usuario_actual=_usuario(202))


if __name__ == "__main__":
    test_permite_hasta_el_limite_y_luego_corta_con_429()
    test_usuarios_distintos_no_comparten_contador()
    print("OK")
