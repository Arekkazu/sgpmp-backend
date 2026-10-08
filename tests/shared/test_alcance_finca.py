"""Tests del adaptador de alcance por finca (RF-25)."""
from __future__ import annotations

from typing import Any

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


def _adapter(ids: list[int]) -> AlcanceFincaAdapter:
    return AlcanceFincaAdapter(_DbFake(ids))  # type: ignore[arg-type]


def test_ningun_rol_es_global_ni_el_administrador() -> None:
    # Decisión del DBA (PR #485): el Administrador también ve solo sus fincas.
    assert _adapter([]).es_global(1) is False


def test_administrador_lista_solo_sus_fincas() -> None:
    assert _adapter([1, 2]).listar_ids_fincas_permitidas(400, 1) == [1, 2]


def test_restringido_lista_sus_fincas() -> None:
    assert _adapter([20]).listar_ids_fincas_permitidas(401, 2) == [20]


def test_sin_fincas_devuelve_vacio() -> None:
    assert _adapter([]).listar_ids_fincas_permitidas(401, 2) == []
