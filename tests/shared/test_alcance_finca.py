"""Tests del adaptador de alcance por finca (RF-25)."""
from __future__ import annotations

from typing import Any

from src.shared.alcance_finca_adapter import AlcanceFincaAdapter


class _Fila:
    def __init__(self, id_finca: int) -> None:
        self.id_finca = id_finca


class _Resultado:
    def __init__(self, ids: list[int], protegido: bool) -> None:
        self._ids = ids
        self._protegido = protegido

    def fetchall(self) -> list[_Fila]:
        return [_Fila(i) for i in self._ids]

    def scalar(self) -> bool:
        return self._protegido


class _DbFake:
    def __init__(self, fincas_ids: list[int], protegido: bool) -> None:
        self._fincas_ids = fincas_ids
        self._protegido = protegido

    def execute(self, _sql: Any, _params: Any) -> _Resultado:
        return _Resultado(self._fincas_ids, self._protegido)


def _adapter(ids: list[int], protegido: bool = False) -> AlcanceFincaAdapter:
    return AlcanceFincaAdapter(_DbFake(ids, protegido))  # type: ignore[arg-type]


def test_administrador_es_global() -> None:
    # RF-19: el rol protegido (Administrador del sistema) ve todas las fincas.
    assert _adapter([], protegido=True).es_global(1) is True


def test_administrador_lista_sin_restriccion_aunque_tenga_fincas() -> None:
    assert _adapter([1, 2], protegido=True).listar_ids_fincas_permitidas(400, 1) is None


def test_rol_no_protegido_no_es_global() -> None:
    assert _adapter([20]).es_global(2) is False


def test_restringido_lista_sus_fincas() -> None:
    assert _adapter([20]).listar_ids_fincas_permitidas(401, 2) == [20]


def test_sin_fincas_devuelve_vacio() -> None:
    assert _adapter([]).listar_ids_fincas_permitidas(401, 2) == []
