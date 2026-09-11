"""Tests del adaptador de alcance por finca (RF-25)."""
from __future__ import annotations

from typing import Any

import pytest

from src.shared import alcance_finca_adapter as modulo
from src.shared.alcance_finca_adapter import AlcanceFincaAdapter


class _Fila:
    def __init__(self, id_finca: int) -> None:
        self.id_finca = id_finca


class _Resultado:
    def __init__(self, ids: list[int]) -> None:
        self._ids = ids

    def fetchall(self) -> list[_Fila]:
        return [_Fila(i) for i in self._ids]


class _DbFake:
    def __init__(self, fincas_ids: list[int]) -> None:
        self._fincas_ids = fincas_ids

    def execute(self, _sql: Any, _params: Any) -> _Resultado:
        return _Resultado(self._fincas_ids)


def _permisos(monkeypatch: pytest.MonkeyPatch, permitidas: set[tuple[int, int, int]]) -> None:
    monkeypatch.setattr(
        modulo,
        "tiene_permiso",
        lambda _db, id_rol, id_recurso, id_accion: (id_rol, id_recurso, id_accion) in permitidas,
    )


def _adapter(ids: list[int]) -> AlcanceFincaAdapter:
    return AlcanceFincaAdapter(_DbFake(ids))  # type: ignore[arg-type]


def test_es_global_con_permiso_de_actualizar(monkeypatch: pytest.MonkeyPatch) -> None:
    _permisos(monkeypatch, {(7, 9, 3)})
    assert _adapter([]).es_global(7) is True


def test_es_global_con_permiso_de_desactivar(monkeypatch: pytest.MonkeyPatch) -> None:
    _permisos(monkeypatch, {(7, 9, 4)})
    assert _adapter([]).es_global(7) is True


def test_rol_solo_lectura_no_es_global(monkeypatch: pytest.MonkeyPatch) -> None:
    _permisos(monkeypatch, {(2, 9, 2)})
    assert _adapter([]).es_global(2) is False


def test_global_devuelve_none(monkeypatch: pytest.MonkeyPatch) -> None:
    _permisos(monkeypatch, {(7, 9, 3)})
    assert _adapter([1, 2, 3]).listar_ids_fincas_permitidas(400, 7) is None


def test_restringido_lista_sus_fincas(monkeypatch: pytest.MonkeyPatch) -> None:
    _permisos(monkeypatch, {(2, 9, 2)})
    assert _adapter([20]).listar_ids_fincas_permitidas(401, 2) == [20]


def test_restringido_sin_fincas_devuelve_vacio(monkeypatch: pytest.MonkeyPatch) -> None:
    _permisos(monkeypatch, {(2, 9, 2)})
    assert _adapter([]).listar_ids_fincas_permitidas(401, 2) == []
