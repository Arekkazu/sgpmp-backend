"""RF-51 (INC-M02-99-G97): el rango solicitado debe estar dentro del ciclo de
vida real del activo (nacimiento/inicio de ciclo como cota inferior, fecha de
baja o cierre como cota superior); si no, se rechaza con 400 antes de calcular.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from src.biological_assets.application.use_cases.gestion.consultar_indicadores_use_case import (
    ConsultarIndicadoresUseCase,
)
from src.biological_assets.domain.entities.activo_biologico import (
    ActivoBiologico,
    DetalleIndividual,
    HistoricoEstado,
    IndicadorZootecnico,
    ResultadoIndicadores,
)
from src.biological_assets.domain.value_objects.estado_activo import EstadoActivo
from src.biological_assets.infrastructure.dto.consultar_indicadores_dto import ConsultarIndicadoresDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import BusinessRuleError, ValidationError


class ActivoRepoFake:
    def __init__(self, activo: ActivoBiologico) -> None:
        self.activo = activo

    def obtener_por_id(self, _id: int, *, ids_fincas_permitidas=None):
        return self.activo


class IndicadoresRepoFake:
    def __init__(self) -> None:
        self.llamado = False

    def calcular_indicadores(self, **kwargs) -> ResultadoIndicadores:
        self.llamado = True
        return ResultadoIndicadores(id_activo_biologico=kwargs['id_activo'], tipo_activo=kwargs['tipo_activo'])


class HistoricoRepoFake:
    def __init__(self, ultimo_cambio: HistoricoEstado | None = None) -> None:
        self.ultimo_cambio = ultimo_cambio

    def obtener_ultimo_cambio(self, _id_activo: int):
        return self.ultimo_cambio


def _usuario() -> UsuarioActual:
    return UsuarioActual(id_usuario=7, id_token=1, id_rol=2)


def _activo_individual(*, nacimiento: date, inicio_ciclo: date | None = None, id_estado=EstadoActivo.ACTIVO):
    return ActivoBiologico(
        id_especie=1,
        tipo='INDIVIDUAL',
        origen_financiero='compra',
        id_infraestructura=1,
        id_estado=id_estado,
        id_usuario=1,
        id_activo_biologico=279,
        fecha_inicio_ciclo=inicio_ciclo,
        detalle_individual=DetalleIndividual(
            raza='raza', sexo='M', fecha_nacimiento=datetime(nacimiento.year, nacimiento.month, nacimiento.day, tzinfo=timezone.utc)
        ),
    )


def _uc(activo, historico=None):
    return ConsultarIndicadoresUseCase(
        db=None,
        activo_repo=ActivoRepoFake(activo),
        indicadores_repo=IndicadoresRepoFake(),
        historico_repo=historico or HistoricoRepoFake(),
        bitacora_repo=None,
    )


def test_rechaza_fecha_inicio_anterior_al_nacimiento():
    activo = _activo_individual(nacimiento=date(2026, 1, 15), inicio_ciclo=date(2026, 6, 1))
    uc = _uc(activo)
    dto = ConsultarIndicadoresDTO(fecha_inicio=date(2025, 12, 1), fecha_fin=date(2026, 9, 10))

    with pytest.raises(ValidationError) as exc:
        uc.execute(279, dto, _usuario())

    assert exc.value.field == 'fecha_inicio'


def test_rechaza_fecha_fin_posterior_a_la_baja():
    activo = _activo_individual(
        nacimiento=date(2025, 1, 1), inicio_ciclo=date(2026, 6, 1), id_estado=EstadoActivo.BAJA
    )
    historico = HistoricoRepoFake(
        HistoricoEstado(
            id_activo_biologico=286, id_estado_anterior=EstadoActivo.ACTIVO, id_estado_nuevo=EstadoActivo.BAJA,
            fecha_cambio=datetime(2026, 8, 31, tzinfo=timezone.utc), modulo_origen='RF-45', id_usuario=1,
        )
    )
    uc = _uc(activo, historico)
    dto = ConsultarIndicadoresDTO(fecha_inicio=date(2026, 7, 1), fecha_fin=date(2026, 9, 5))

    with pytest.raises(ValidationError) as exc:
        uc.execute(279, dto, _usuario())

    assert exc.value.field == 'fecha_fin'


def test_acepta_rango_dentro_del_ciclo_de_vida():
    activo = _activo_individual(nacimiento=date(2026, 1, 15), inicio_ciclo=date(2026, 6, 1))
    uc = _uc(activo)
    dto = ConsultarIndicadoresDTO(fecha_inicio=date(2026, 6, 1), fecha_fin=date(2026, 9, 10))

    resultado = uc.execute(279, dto, _usuario())

    assert resultado.id_activo_biologico == 279


def test_activo_dado_de_baja_sin_historico_no_bloquea_por_falta_de_dato():
    activo = _activo_individual(
        nacimiento=date(2025, 1, 1), inicio_ciclo=date(2026, 6, 1), id_estado=EstadoActivo.BAJA
    )
    uc = _uc(activo, HistoricoRepoFake(None))
    dto = ConsultarIndicadoresDTO(fecha_inicio=date(2026, 6, 1), fecha_fin=date(2026, 9, 10))

    resultado = uc.execute(279, dto, _usuario())

    assert resultado.id_activo_biologico == 279


def test_produccion_no_aplica_a_activo_individual_macho():
    activo = _activo_individual(nacimiento=date(2025, 1, 1), inicio_ciclo=date(2026, 1, 1))
    activo.detalle_individual.sexo = 'Macho'
    uc = _uc(activo)
    dto = ConsultarIndicadoresDTO(tipo_indicador='PRODUCCION')

    with pytest.raises(ValidationError) as exc:
        uc.execute(279, dto, _usuario())

    assert exc.value.field == 'tipo_indicador'


class IndicadoresRepoDisponibleFake:
    def calcular_indicadores(self, **kwargs) -> ResultadoIndicadores:
        return ResultadoIndicadores(
            id_activo_biologico=kwargs['id_activo'],
            tipo_activo=kwargs['tipo_activo'],
            indicadores=[
                IndicadorZootecnico(
                    tipo='produccion_promedio', valor=1, unidad='unidades/dia',
                    fecha_calculo=datetime.now(timezone.utc), disponible=True,
                    variables_usadas={},
                )
            ],
        )


def test_produccion_si_aplica_a_activo_individual_hembra():
    activo = _activo_individual(nacimiento=date(2025, 1, 1), inicio_ciclo=date(2026, 1, 1))
    activo.detalle_individual.sexo = 'Hembra'
    uc = ConsultarIndicadoresUseCase(
        db=None,
        activo_repo=ActivoRepoFake(activo),
        indicadores_repo=IndicadoresRepoDisponibleFake(),
        historico_repo=HistoricoRepoFake(),
        bitacora_repo=None,
    )
    dto = ConsultarIndicadoresDTO(tipo_indicador='PRODUCCION')

    resultado = uc.execute(279, dto, _usuario())

    assert resultado.id_activo_biologico == 279


class IndicadoresRepoNoDisponibleFake:
    def calcular_indicadores(self, **kwargs) -> ResultadoIndicadores:
        return ResultadoIndicadores(
            id_activo_biologico=kwargs['id_activo'],
            tipo_activo=kwargs['tipo_activo'],
            indicadores=[
                IndicadorZootecnico(
                    tipo='ganancia_peso', unidad='kg/dia', fecha_calculo=datetime.now(timezone.utc),
                    disponible=False, variables_usadas={'registros_disponibles': 1},
                )
            ],
            advertencias=['DATOS_INSUFICIENTES: ganancia_peso requiere al menos 2 mediciones de peso.'],
        )


def test_tipo_indicador_especifico_sin_datos_responde_422():
    activo = _activo_individual(nacimiento=date(2025, 1, 1), inicio_ciclo=date(2026, 1, 1))
    uc = ConsultarIndicadoresUseCase(
        db=None,
        activo_repo=ActivoRepoFake(activo),
        indicadores_repo=IndicadoresRepoNoDisponibleFake(),
        historico_repo=HistoricoRepoFake(),
        bitacora_repo=None,
    )
    dto = ConsultarIndicadoresDTO(tipo_indicador='CRECIMIENTO')

    with pytest.raises(BusinessRuleError) as exc:
        uc.execute(279, dto, _usuario())

    assert exc.value.code == 'INDICADOR_NO_DISPONIBLE'


def test_tipo_indicador_todos_sin_datos_no_lanza_422():
    activo = _activo_individual(nacimiento=date(2025, 1, 1), inicio_ciclo=date(2026, 1, 1))
    uc = ConsultarIndicadoresUseCase(
        db=None,
        activo_repo=ActivoRepoFake(activo),
        indicadores_repo=IndicadoresRepoNoDisponibleFake(),
        historico_repo=HistoricoRepoFake(),
        bitacora_repo=None,
    )
    dto = ConsultarIndicadoresDTO(tipo_indicador='TODOS')

    resultado = uc.execute(279, dto, _usuario())

    assert resultado.indicadores[0].disponible is False
