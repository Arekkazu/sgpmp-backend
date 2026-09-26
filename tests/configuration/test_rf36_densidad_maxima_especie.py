"""RF-36: configuración M09 de densidad máxima por especie."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError as PydanticValidationError

from src.configuration.application.use_cases.especies.editar_especie_use_case import (
    EditarEspecieUseCase,
)
from src.configuration.application.use_cases.especies.registrar_especie_use_case import (
    RegistrarEspecieUseCase,
)
from src.configuration.domain.entities.especie import Especie
from src.configuration.domain.value_objects.nombre_especie import NombreEspecie
from src.configuration.infrastructure.dto.editar_especie_dto import EditarEspecieDTO
from src.configuration.infrastructure.dto.registrar_especie_dto import RegistrarEspecieDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual


class DbFake:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class EspecieRepoFake:
    def __init__(self, especie: Especie | None = None) -> None:
        self.especie = especie

    def obtener_por_nombre(self, _nombre):
        return None

    def obtener_por_id(self, _id_especie: int):
        return self.especie

    def guardar(self, especie: Especie) -> Especie:
        especie.id_especie = 4
        self.especie = especie
        return especie

    def actualizar(self, especie: Especie) -> Especie:
        self.especie = especie
        return especie


class AuditoriaFake:
    def __init__(self) -> None:
        self.registros: list[dict] = []

    def registrar(self, **datos) -> None:
        self.registros.append(datos)


def _usuario() -> UsuarioActual:
    return UsuarioActual(id_usuario=1, id_token=1, id_rol=1)


def _especie(densidad: Decimal | None) -> Especie:
    fecha = datetime(2026, 9, 20, tzinfo=timezone.utc)
    return Especie(
        id_especie=4,
        nombre=NombreEspecie('Cachama Blanca'),
        descripcion='Especie de prueba',
        densidad_maxima_por_especie=densidad,
        es_activo=True,
        fecha_creacion=fecha,
        fecha_actualizacion=fecha,
    )


@pytest.mark.parametrize('valor', [Decimal('0'), Decimal('-0.1')])
def test_dto_rechaza_densidad_no_positiva(valor: Decimal) -> None:
    with pytest.raises(PydanticValidationError):
        RegistrarEspecieDTO(
            nombre='Cachama Blanca',
            densidad_maxima_por_especie=valor,
        )


def test_registro_persiste_y_audita_densidad_maxima() -> None:
    db = DbFake()
    repo = EspecieRepoFake()
    auditoria = AuditoriaFake()
    caso_uso = RegistrarEspecieUseCase(db, repo, auditoria)

    especie = caso_uso.execute(
        RegistrarEspecieDTO(
            nombre='Cachama Blanca',
            descripcion='Especie de prueba',
            densidad_maxima_por_especie=Decimal('12.5000'),
        ),
        _usuario(),
    )

    assert especie.densidad_maxima_por_especie == Decimal('12.5000')
    assert auditoria.registros[0]['valores_nuevos']['densidad_maxima_por_especie'] == '12.5000'
    assert db.commits == 1


def test_edicion_omitida_conserva_densidad_existente() -> None:
    existente = _especie(Decimal('12.5'))
    repo = EspecieRepoFake(existente)
    caso_uso = EditarEspecieUseCase(DbFake(), repo, AuditoriaFake())

    actualizada = caso_uso.execute(
        4,
        EditarEspecieDTO(
            nombre='Cachama Blanca',
            descripcion='Descripción actualizada',
            fecha_actualizacion=existente.fecha_actualizacion,
        ),
        _usuario(),
    )

    assert actualizada.densidad_maxima_por_especie == Decimal('12.5')


def test_edicion_actualiza_y_audita_densidad() -> None:
    existente = _especie(Decimal('12.5'))
    db = DbFake()
    auditoria = AuditoriaFake()
    caso_uso = EditarEspecieUseCase(db, EspecieRepoFake(existente), auditoria)

    actualizada = caso_uso.execute(
        4,
        EditarEspecieDTO(
            nombre='Cachama Blanca',
            descripcion=existente.descripcion,
            densidad_maxima_por_especie=Decimal('8.7500'),
            fecha_actualizacion=existente.fecha_actualizacion,
        ),
        _usuario(),
    )

    assert actualizada.densidad_maxima_por_especie == Decimal('8.7500')
    registro = auditoria.registros[0]
    assert registro['valores_anteriores']['densidad_maxima_por_especie'] == '12.5'
    assert registro['valores_nuevos']['densidad_maxima_por_especie'] == '8.7500'
    assert db.commits == 1
