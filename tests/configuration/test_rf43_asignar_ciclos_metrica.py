"""[RF-43 E-04] Habilitar una métrica como producto en ciclos productivos."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.configuration.application.use_cases.metricas.asignar_ciclos_metrica_use_case import (
    AsignarCiclosMetricaUseCase,
)
from src.configuration.domain.entities.ciclo_metrica import CicloMetrica
from src.shared.errors import BusinessRuleError, NotFoundError


class _Db:
    commits = rollbacks = 0

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


class _Metricas:
    def __init__(self, metrica):
        self.metrica = metrica

    def obtener_por_id(self, _id):
        return self.metrica


class _Ciclos:
    def __init__(self):
        self.habilitados: set[int] = set()

    def listar_por_metrica(self, _id_metrica, id_especie):
        assert id_especie == 4
        return [CicloMetrica(c, f'Ciclo {c}', c in self.habilitados) for c in (4, 7)]

    def reemplazar(self, _id_metrica, ids):
        self.habilitados = set(ids)


def _uc(metrica):
    db, ciclos = _Db(), _Ciclos()
    return AsignarCiclosMetricaUseCase(db, _Metricas(metrica), ciclos), db, ciclos


ACTIVA = SimpleNamespace(id_especie=4, es_activo=True)


def test_habilita_solo_los_ciclos_pedidos() -> None:
    uc, db, ciclos = _uc(ACTIVA)
    resultado = uc.execute(17, [7, 7])
    assert [(c.id_ciclo_productivo, c.habilitada) for c in resultado] == [(4, False), (7, True)]
    assert db.commits == 1


def test_rechaza_ciclos_de_otra_especie() -> None:
    uc, db, _ = _uc(ACTIVA)
    with pytest.raises(BusinessRuleError) as exc:
        uc.execute(17, [4, 99])
    assert exc.value.code == 'CICLO_DE_OTRA_ESPECIE'
    assert db.commits == 0


def test_rechaza_metrica_inactiva_o_inexistente() -> None:
    with pytest.raises(BusinessRuleError):
        _uc(SimpleNamespace(id_especie=4, es_activo=False))[0].execute(17, [4])
    with pytest.raises(NotFoundError):
        _uc(None)[0].execute(17, [4])
