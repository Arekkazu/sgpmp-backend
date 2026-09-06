"""RF-34: fecha_referencia, 404 sin asociación activa, sensores_en_infraestructura, advertencia_integridad."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.biological_assets.application.use_cases.registro.consultar_asociacion_use_case import (
    ConsultarAsociacionUseCase,
)
from src.biological_assets.domain.entities.activo_biologico import HistorialInfraestructura, SensorEnInfraestructura
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import NotFoundError, ValidationError


class DbFake:
    def __init__(self) -> None:
        self.commits = 0

    def commit(self) -> None:
        self.commits += 1


class ActivoRepoFake:
    def __init__(
        self,
        activo=object(),
        asociacion_activa=None,
        historial=None,
        asociacion_en_fecha=None,
    ) -> None:
        self.activo = activo
        self.asociacion_activa = asociacion_activa
        self.historial = historial or []
        self.asociacion_en_fecha = asociacion_en_fecha

    def obtener_por_id(self, _id: int):
        return self.activo

    def obtener_asociacion_activa(self, _id: int):
        return self.asociacion_activa

    def obtener_asociacion_en_fecha(self, _id: int, _fecha):
        return self.asociacion_en_fecha

    def obtener_historial_infraestructura(self, _id: int):
        return self.historial


class InfraPortFake:
    def __init__(self, sensores=None) -> None:
        self.sensores = sensores or []
        self.consultas: list[int] = []

    def listar_sensores_activos(self, id_infraestructura: int):
        self.consultas.append(id_infraestructura)
        return self.sensores


def _usuario() -> UsuarioActual:
    return UsuarioActual(id_usuario=7, id_token=1, id_rol=2)


def _historial(id_historial: int, inicio: datetime, fin: datetime | None, id_infra: int = 5):
    return HistorialInfraestructura(
        id_historial=id_historial,
        id_activo_biologico=10,
        id_infraestructura=id_infra,
        nombre_infraestructura=f'Infra {id_infra}',
        tipo_infraestructura='CORRAL',
        fecha_inicio=inicio,
        fecha_fin=fin,
    )


def test_tipo_consulta_invalido_lanza_validation_error() -> None:
    uc = ConsultarAsociacionUseCase(db=DbFake(), repo=ActivoRepoFake())
    with pytest.raises(ValidationError) as exc:
        uc.execute(10, 'OTRO')
    assert exc.value.code == 'TIPO_CONSULTA_INVALIDO'


def test_activo_no_encontrado_lanza_404() -> None:
    uc = ConsultarAsociacionUseCase(db=DbFake(), repo=ActivoRepoFake(activo=None))
    with pytest.raises(NotFoundError) as exc:
        uc.execute(10, 'ACTIVA')
    assert exc.value.code == 'ACTIVO_NO_ENCONTRADO'


def test_activa_sin_asociacion_activa_lanza_404_con_alerta_tecnica() -> None:
    """Corrige el flujo alterno E2: antes retornaba 200 con asociacion_activa=None."""
    uc = ConsultarAsociacionUseCase(db=DbFake(), repo=ActivoRepoFake(asociacion_activa=None))
    with pytest.raises(NotFoundError) as exc:
        uc.execute(10, 'ACTIVA')
    assert exc.value.code == 'ASOCIACION_INFRAESTRUCTURA_NO_ENCONTRADA'


def test_activa_con_asociacion_incluye_sensores_en_infraestructura() -> None:
    asociacion = _historial(1, datetime(2026, 1, 1, tzinfo=timezone.utc), None, id_infra=5)
    sensor = SensorEnInfraestructura(
        id_sensor=99, nombre='Sensor Temp', id_dispositivo_iot=3, punto_instalacion='Entrada',
    )
    infra_port = InfraPortFake(sensores=[sensor])
    uc = ConsultarAsociacionUseCase(
        db=DbFake(),
        repo=ActivoRepoFake(asociacion_activa=asociacion, historial=[asociacion]),
        infra_port=infra_port,
    )
    resultado = uc.execute(10, 'ACTIVA', usuario=_usuario())

    assert resultado.asociacion_activa is asociacion
    assert resultado.sensores_en_infraestructura == [sensor]
    assert infra_port.consultas == [5]


def test_fecha_referencia_retorna_asociacion_vigente_en_esa_fecha() -> None:
    fecha_pasada = _historial(1, datetime(2025, 1, 1, tzinfo=timezone.utc), datetime(2025, 6, 1, tzinfo=timezone.utc))
    uc = ConsultarAsociacionUseCase(
        db=DbFake(),
        repo=ActivoRepoFake(asociacion_en_fecha=fecha_pasada, historial=[fecha_pasada]),
        infra_port=InfraPortFake(),
    )
    resultado = uc.execute(10, 'ACTIVA', fecha_referencia=datetime(2025, 3, 1, tzinfo=timezone.utc))

    assert resultado.asociacion_activa is fecha_pasada


def test_fecha_referencia_sin_asociacion_en_esa_fecha_lanza_404() -> None:
    uc = ConsultarAsociacionUseCase(db=DbFake(), repo=ActivoRepoFake(asociacion_en_fecha=None))
    with pytest.raises(NotFoundError) as exc:
        uc.execute(10, 'ACTIVA', fecha_referencia=datetime(2020, 1, 1, tzinfo=timezone.utc))
    assert exc.value.code == 'ASOCIACION_INFRAESTRUCTURA_NO_ENCONTRADA'


def test_fecha_referencia_con_tipo_historial_lanza_validation_error() -> None:
    uc = ConsultarAsociacionUseCase(db=DbFake(), repo=ActivoRepoFake())
    with pytest.raises(ValidationError) as exc:
        uc.execute(10, 'HISTORIAL', fecha_referencia=datetime(2025, 1, 1, tzinfo=timezone.utc))
    assert exc.value.code == 'FECHA_REFERENCIA_INVALIDA'


def test_historial_sin_solapamiento_no_agrega_advertencia() -> None:
    h1 = _historial(1, datetime(2025, 1, 1, tzinfo=timezone.utc), datetime(2025, 6, 1, tzinfo=timezone.utc))
    h2 = _historial(2, datetime(2025, 6, 1, tzinfo=timezone.utc), None)
    uc = ConsultarAsociacionUseCase(db=DbFake(), repo=ActivoRepoFake(historial=[h1, h2]))

    resultado = uc.execute(10, 'HISTORIAL')

    assert resultado.historial == [h1, h2]
    assert resultado.advertencia_integridad is None


def test_historial_con_solapamiento_agrega_advertencia_integridad() -> None:
    h1 = _historial(1, datetime(2025, 1, 1, tzinfo=timezone.utc), datetime(2025, 6, 1, tzinfo=timezone.utc))
    # h2 empieza antes de que h1 termine → solapamiento
    h2 = _historial(2, datetime(2025, 5, 1, tzinfo=timezone.utc), None)
    uc = ConsultarAsociacionUseCase(db=DbFake(), repo=ActivoRepoFake(historial=[h1, h2]))

    resultado = uc.execute(10, 'HISTORIAL')

    assert resultado.advertencia_integridad is not None
    assert '1' in resultado.advertencia_integridad and '2' in resultado.advertencia_integridad


def test_advertencia_integridad_se_calcula_tambien_para_tipo_activa() -> None:
    h1 = _historial(1, datetime(2025, 1, 1, tzinfo=timezone.utc), datetime(2025, 6, 1, tzinfo=timezone.utc))
    h2 = _historial(2, datetime(2025, 5, 1, tzinfo=timezone.utc), None)
    uc = ConsultarAsociacionUseCase(
        db=DbFake(),
        repo=ActivoRepoFake(asociacion_activa=h2, historial=[h1, h2]),
        infra_port=InfraPortFake(),
    )

    resultado = uc.execute(10, 'ACTIVA')

    assert resultado.advertencia_integridad is not None
