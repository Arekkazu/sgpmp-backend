"""RF-16 / #1633 — Registrar patología por especie (unicidad por especie).

Verifica con fakes (sin BD):
- el mismo nombre puede registrarse en especies distintas;
- el nombre duplicado dentro de una especie es rechazado (409);
- la patología se crea como entidad M09 (id_patologia None) → no toca el catálogo M04;
- especie inexistente/inactiva se rechazan.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.configuration.application.use_cases.patologias.registrar_patologia_use_case import (
    RegistrarPatologiaUseCase,
)
from src.configuration.domain.entities.especie import Especie
from src.configuration.domain.entities.especie_patologia import EspeciePatologia
from src.configuration.domain.value_objects.nombre_especie import NombreEspecie
from src.configuration.infrastructure.dto.registrar_patologia_dto import RegistrarPatologiaDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import BusinessRuleError, ConflictError, NotFoundError

USUARIO = UsuarioActual(id_usuario=1, id_token=1, id_rol=1)


class DbFake:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class EspeciesRepoFake:
    def __init__(self, especies: dict[int, Especie]) -> None:
        self._especies = especies

    def obtener_por_id(self, id_especie: int):
        return self._especies.get(id_especie)


class EspeciePatologiaRepoFake:
    def __init__(self) -> None:
        self.rows: list[EspeciePatologia] = []
        self._seq = 0

    def obtener_por_especie_y_nombre(self, id_especie, nombre):
        for r in self.rows:
            if r.id_especie == id_especie and r.nombre.normalizado() == nombre.normalizado():
                return r
        return None

    def guardar(self, entidad: EspeciePatologia) -> EspeciePatologia:
        self._seq += 1
        entidad.id_especies_patologias = self._seq
        entidad.fecha_creacion = datetime.now(timezone.utc)
        self.rows.append(entidad)
        return entidad


class AuditoriaFake:
    def __init__(self) -> None:
        self.registros = []

    def registrar(self, **kwargs) -> None:
        self.registros.append(kwargs)


_NOMBRES = {1: "Bovino", 2: "Ovino", 3: "Porcino"}


def _especie(id_especie: int, activa: bool = True) -> Especie:
    esp = Especie.crear(
        nombre=NombreEspecie(_NOMBRES.get(id_especie, "Caprino")),
        descripcion=None,
        fecha_creacion=datetime(2020, 1, 1, tzinfo=timezone.utc),
    )
    esp.id_especie = id_especie
    esp.es_activo = activa
    return esp


def _use_case(especies, ep_repo):
    return RegistrarPatologiaUseCase(
        db=DbFake(),
        especie_patologia_repo=ep_repo,
        especies_repo=EspeciesRepoFake(especies),
        auditoria_repo=AuditoriaFake(),
    )


def test_mismo_nombre_en_dos_especies_permitido():
    especies = {1: _especie(1), 2: _especie(2)}
    ep_repo = EspeciePatologiaRepoFake()
    uc = _use_case(especies, ep_repo)

    r1 = uc.execute(RegistrarPatologiaDTO(id_especie=1, nombre="Mastitis"), USUARIO)
    r2 = uc.execute(RegistrarPatologiaDTO(id_especie=2, nombre="Mastitis"), USUARIO)

    assert r1.id_especie == 1 and r2.id_especie == 2
    assert r1.id_especies_patologias != r2.id_especies_patologias
    # Entidad M09: no se escribe el catálogo clínico M04.
    assert r1.id_patologia is None and r2.id_patologia is None
    assert r1.es_activo is True


def test_nombre_duplicado_en_misma_especie_conflicto():
    especies = {1: _especie(1)}
    ep_repo = EspeciePatologiaRepoFake()
    uc = _use_case(especies, ep_repo)
    uc.execute(RegistrarPatologiaDTO(id_especie=1, nombre="Mastitis"), USUARIO)

    with pytest.raises(ConflictError) as exc:
        uc.execute(RegistrarPatologiaDTO(id_especie=1, nombre="mastitis"), USUARIO)  # case-insensitive
    assert exc.value.code == "PATOLOGIA_DUPLICADA_EN_ESPECIE"


def test_especie_inexistente_not_found():
    uc = _use_case({}, EspeciePatologiaRepoFake())
    with pytest.raises(NotFoundError) as exc:
        uc.execute(RegistrarPatologiaDTO(id_especie=99, nombre="Mastitis"), USUARIO)
    assert exc.value.code == "ESPECIE_NO_ENCONTRADA"


def test_especie_inactiva_business_rule():
    uc = _use_case({1: _especie(1, activa=False)}, EspeciePatologiaRepoFake())
    with pytest.raises(BusinessRuleError) as exc:
        uc.execute(RegistrarPatologiaDTO(id_especie=1, nombre="Mastitis"), USUARIO)
    assert exc.value.code == "ESPECIE_INACTIVA"
