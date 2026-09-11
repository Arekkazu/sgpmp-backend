"""RF-33: snapshot inicial (Evento 0) y código HTTP del flujo de costo inválido.

- El registro exitoso debe dejar un snapshot version=1/tipo_evento=CREACION en
  historial_activos.
- "costo_adquisicion inválido para el origen" debe rechazarse con
  BusinessRuleError (422), no con un ValueError de Pydantic (400).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

import pytest

from src.biological_assets.application.use_cases.registro.registrar_activo_use_case import (
    RegistrarActivoBiologicoUseCase,
    _validar_origen_financiero,
)
from src.biological_assets.domain.entities.activo_biologico import ActivoBiologico, HistorialActivo
from src.biological_assets.domain.repositories.especie_consulta_port import EspecieConsulta
from src.biological_assets.domain.repositories.infraestructura_consulta_port import InfraestructuraConsulta
from src.biological_assets.domain.repositories.parametros_especie_port import ParametroEspecie
from src.biological_assets.infrastructure.dto.registrar_activo_dto import RegistrarActivoBiologicoDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import BusinessRuleError


class DbFake:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class ActivoRepoFake:
    def __init__(self) -> None:
        self.historial: list[HistorialActivo] = []
        self.guardados = 0
        self._next_id = 100

    def existe_identificador(self, identificador: str) -> bool:
        return False

    def guardar(self, activo: ActivoBiologico) -> ActivoBiologico:
        self.guardados += 1
        activo.id_activo_biologico = self._next_id
        return activo

    def registrar_historial(self, historial: HistorialActivo) -> HistorialActivo:
        historial.id_historial_activo = len(self.historial) + 1
        self.historial.append(historial)
        return historial


class EspecieFake:
    def obtener_activa(self, id_especie: int):
        return EspecieConsulta(id_especie=id_especie, nombre='Bovino', es_activo=True)


class InfraFake:
    def obtener_activa(self, id_infraestructura: int):
        return InfraestructuraConsulta(
            id_infraestructura=id_infraestructura, nombre='Potrero 1', tipo='potrero', es_activo=True,
        )


class ParametrosFake:
    def __init__(self, parametros: list[ParametroEspecie] | None = None) -> None:
        self.parametros = parametros or []

    def listar_por_especie(self, id_especie: int, tipo_activo: str):
        return self.parametros


def _usuario() -> UsuarioActual:
    return UsuarioActual(id_usuario=7, id_token=1, id_rol=2)


def _dto(**overrides) -> RegistrarActivoBiologicoDTO:
    base = dict(
        tipo_activo='INDIVIDUAL',
        id_especie=1,
        fecha_inicio_ciclo=date(2024, 1, 1),
        origen_financiero='compra',
        costo_adquisicion=100,
        soporte_documental='factura.pdf',
        id_infraestructura=1,
        identificador='BOV-100',
        raza='Angus',
        sexo='M',
        fecha_nacimiento=datetime(2023, 1, 1),
    )
    base.update(overrides)
    return RegistrarActivoBiologicoDTO(**base)


def _use_case(
    repo: ActivoRepoFake,
    db: DbFake,
    parametros: list[ParametroEspecie] | None = None,
) -> RegistrarActivoBiologicoUseCase:
    return RegistrarActivoBiologicoUseCase(
        db=db,
        repo=repo,
        especie_port=EspecieFake(),
        infra_port=InfraFake(),
        parametros_port=ParametrosFake(parametros),
    )


def test_registro_exitoso_deja_snapshot_evento_0() -> None:
    db = DbFake()
    repo = ActivoRepoFake()
    uc = _use_case(repo, db)

    activo = uc.execute(_dto(), _usuario())

    assert len(repo.historial) == 1
    snapshot = repo.historial[0]
    assert snapshot.id_activo_biologico == activo.id_activo_biologico
    assert snapshot.version == 1
    assert snapshot.tipo_evento == 'CREACION'
    assert snapshot.snapshot['identificador'] == 'BOV-100'
    assert snapshot.snapshot['detalle_individual']['raza'] == 'Angus'
    assert snapshot.snapshot['detalle_individual']['sexo'] == 'M'
    assert db.commits == 1
    assert db.rollbacks == 0


def test_registro_poblacional_snapshot_incluye_cantidades_y_peso_inicial() -> None:
    # INC-M02-46-G13 / INC-M02-G08: el snapshot inicial de un lote debe
    # conservar cantidad_inicial, cantidad_actual y peso_promedio_inicial.
    db = DbFake()
    repo = ActivoRepoFake()
    uc = _use_case(repo, db)
    dto = _dto(
        tipo_activo='POBLACIONAL',
        identificador=None,
        raza=None,
        sexo=None,
        fecha_nacimiento=None,
        cantidad_inicial=10,
        peso_promedio_inicial=Decimal('2.5'),
    )

    uc.execute(dto, _usuario())

    snapshot = repo.historial[0].snapshot
    assert snapshot['detalle_poblacional']['cantidad_inicial'] == 10
    assert snapshot['detalle_poblacional']['cantidad_actual'] == 10
    assert snapshot['detalle_poblacional']['peso_promedio_inicial'] == '2.5'


@dataclass
class _OrigenFinancieroPayload:
    """Sustituto mínimo del DTO para probar `_validar_origen_financiero` en aislamiento."""

    origen_financiero: str
    costo_adquisicion: Optional[Decimal] = None
    soporte_documental: Optional[str] = None


def test_costo_adquisicion_invalido_para_nacimiento_es_422() -> None:
    # nacimiento no admite costo_adquisicion — el propio DTO ya no lo bloquea
    # en Pydantic (movido al use case), así que se simula el payload aquí.
    payload = _OrigenFinancieroPayload(origen_financiero='nacimiento', costo_adquisicion=Decimal('100'))

    with pytest.raises(BusinessRuleError) as exc_info:
        _validar_origen_financiero(payload)

    assert exc_info.value.status_code == 422
    assert exc_info.value.code == 'COSTO_ADQUISICION_INVALIDO'


def test_soporte_documental_requerido_para_compra_es_422() -> None:
    payload = _OrigenFinancieroPayload(
        origen_financiero='compra', costo_adquisicion=Decimal('100'), soporte_documental=None,
    )

    with pytest.raises(BusinessRuleError) as exc_info:
        _validar_origen_financiero(payload)

    assert exc_info.value.status_code == 422
    assert exc_info.value.code == 'SOPORTE_DOCUMENTAL_REQUERIDO'


def test_costo_adquisicion_invalido_para_origen_bloquea_antes_de_persistir() -> None:
    db = DbFake()
    repo = ActivoRepoFake()
    uc = _use_case(repo, db)
    dto = _dto(origen_financiero='donacion', costo_adquisicion=None, soporte_documental='acta.pdf')

    with pytest.raises(BusinessRuleError) as exc_info:
        uc.execute(dto, _usuario())

    assert exc_info.value.status_code == 422
    assert repo.historial == []
    assert db.commits == 0


def _parametro_requerido(**overrides) -> ParametroEspecie:
    base = {
        'nombre': 'Peso de ingreso G17',
        'tipo_medicion': 'PESO',
        'aplica_a_tipo_activo': 'INDIVIDUAL',
        'tipo_dato': 'NUMERICO',
        'es_obligatorio': True,
        'valor_min': Decimal('0.1'),
        'valor_max': Decimal('500'),
    }
    base.update(overrides)
    return ParametroEspecie(**base)


@pytest.mark.parametrize(
    'atributos',
    [None, {}, {'Peso de ingreso G17': None}],
)
def test_tc_m02_187_rechaza_atributo_obligatorio_omitido_o_null_sin_persistir(
    atributos,
) -> None:
    db = DbFake()
    repo = ActivoRepoFake()
    uc = _use_case(repo, db, [_parametro_requerido()])

    with pytest.raises(BusinessRuleError) as exc_info:
        uc.execute(_dto(atributos_dinamicos=atributos), _usuario())

    assert exc_info.value.status_code == 422
    assert exc_info.value.code == 'ATRIBUTO_REQUERIDO'
    assert repo.guardados == 0
    assert repo.historial == []
    assert db.commits == 0


@pytest.mark.parametrize('valor_invalido', ['12.5', True, [12.5]])
def test_tc_m02_188_rechaza_tipo_distinto_al_configurado_sin_persistir(
    valor_invalido,
) -> None:
    db = DbFake()
    repo = ActivoRepoFake()
    uc = _use_case(repo, db, [_parametro_requerido()])

    with pytest.raises(BusinessRuleError) as exc_info:
        uc.execute(
            _dto(atributos_dinamicos={'Peso de ingreso G17': valor_invalido}),
            _usuario(),
        )

    assert exc_info.value.status_code == 422
    assert exc_info.value.code == 'ATRIBUTO_TIPO_INVALIDO'
    assert repo.guardados == 0
    assert repo.historial == []
    assert db.commits == 0


def test_atributo_dinamico_valido_se_persiste_normalmente() -> None:
    db = DbFake()
    repo = ActivoRepoFake()
    uc = _use_case(repo, db, [_parametro_requerido()])

    activo = uc.execute(
        _dto(atributos_dinamicos={'Peso de ingreso G17': 12.5}),
        _usuario(),
    )

    assert activo.atributos_dinamicos == {'Peso de ingreso G17': 12.5}
    assert repo.guardados == 1
    assert len(repo.historial) == 1
    assert db.commits == 1
