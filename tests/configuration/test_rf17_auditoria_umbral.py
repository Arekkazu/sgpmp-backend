"""RF-17 / INC-M09-30-G30 (TC-M09-64) — Auditoría de umbrales consultable.

Verifica con fakes (sin BD; modulo9 no existe en la base `pruebas`):
- consultar la auditoría de un umbral existente devuelve el historial;
- consultar la de un umbral inexistente devuelve 404 tipado;
- el historial se correlaciona con el id_umbral_ambiental pedido.
"""
from __future__ import annotations

import datetime

import pytest

from src.configuration.application.use_cases.umbrales.consultar_auditoria_umbral_use_case import (
    ConsultarAuditoriaUmbralUseCase,
)
from src.configuration.domain.entities.auditoria_umbral import AuditoriaUmbral
from src.shared.errors import NotFoundError

FECHA = datetime.datetime(2026, 9, 6, 12, 0, 0, tzinfo=datetime.timezone.utc)


def _registro(id_aud: int, id_umbral: int, op: str) -> AuditoriaUmbral:
    return AuditoriaUmbral(
        id_auditoria_umbral=id_aud,
        id_umbral_ambiental=id_umbral,
        id_usuario=1,
        tipo_operacion=op,
        valores_anteriores=None if op == 'CREATE' else {'valor_min': '1'},
        valores_nuevos={'valor_min': '2', 'valor_max': '70'},
        fecha_gestion=FECHA,
    )


class AuditoriaRepoFake:
    def __init__(self, filas: list[AuditoriaUmbral]) -> None:
        self._filas = filas
        self.consultas = 0

    def registrar(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        raise AssertionError("consultar no debe escribir")

    def listar_por_umbral(self, id_umbral_ambiental: int) -> list[AuditoriaUmbral]:
        self.consultas += 1
        return [f for f in self._filas if f.id_umbral_ambiental == id_umbral_ambiental]


class UmbralRepoFake:
    def __init__(self, existe: bool) -> None:
        self._existe = existe

    def obtener_por_id(self, id_umbral_ambiental: int) -> object | None:
        return object() if self._existe else None


def test_la_auditoria_de_un_umbral_existente_se_correlaciona_con_su_id() -> None:
    filas = [_registro(1, 11, 'CREATE'), _registro(2, 11, 'UPDATE'), _registro(3, 99, 'CREATE')]
    auditoria = AuditoriaRepoFake(filas)
    use_case = ConsultarAuditoriaUmbralUseCase(
        auditoria_repo=auditoria,
        umbral_repo=UmbralRepoFake(existe=True),
    )

    resultado = use_case.execute(11)

    assert [r.id_auditoria_umbral for r in resultado] == [1, 2]
    assert all(r.id_umbral_ambiental == 11 for r in resultado)
    assert auditoria.consultas == 1


def test_umbral_inexistente_devuelve_404() -> None:
    use_case = ConsultarAuditoriaUmbralUseCase(
        auditoria_repo=AuditoriaRepoFake([]),
        umbral_repo=UmbralRepoFake(existe=False),
    )

    with pytest.raises(NotFoundError) as excinfo:
        use_case.execute(12345)

    assert excinfo.value.code == 'UMBRAL_NO_ENCONTRADO'
