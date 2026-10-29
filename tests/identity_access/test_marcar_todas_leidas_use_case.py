"""T-08 (reporte UAT 07/10/2026): marcar todas las notificaciones propias como leídas."""
from __future__ import annotations

import pytest

from src.identity_access.application.use_cases.notificaciones.marcar_todas_leidas_use_case import (
    MarcarTodasLeidasUseCase,
)


class _Db:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class _Repo:
    def __init__(self, falla: bool = False) -> None:
        self.falla = falla
        self.usuarios: list[int] = []

    def marcar_todas_leidas(self, id_usuario: int) -> int:
        if self.falla:
            raise RuntimeError('fallo simulado')
        self.usuarios.append(id_usuario)
        return 7


def test_marca_solo_las_del_usuario_y_confirma() -> None:
    db, repo = _Db(), _Repo()
    assert MarcarTodasLeidasUseCase(repo, db).execute(42) == 7
    assert repo.usuarios == [42]
    assert db.commits == 1


def test_si_falla_revierte() -> None:
    db = _Db()
    with pytest.raises(RuntimeError):
        MarcarTodasLeidasUseCase(_Repo(falla=True), db).execute(42)
    assert db.rollbacks == 1 and db.commits == 0
