"""INC-M02-48-G25 / issue #394 (RF-36): densidad máxima por especie.

La primera corrección usó ``infraestructuras.capacidad_maxima`` como si fuera
el límite biológico por especie. Son conceptos distintos y, además, ese campo
está sin configurar en los ambientes compartidos. El límite contractual vive
ahora en ``modulo9.especies.densidad_maxima_por_especie``.

Al registrar un evento de crecimiento
sobre un lote poblacional, el backend recalculaba la densidad
(`cantidad_actual / superficie`) pero nunca la comparaba contra
`densidad_maxima_por_especie` (RF-36, restricción de M09) — el evento se
aceptaba (201) sin importar qué tan hacinado estuviera el lote.

RF-36 es explícito en que `cantidad_actual` "se modifica únicamente mediante
eventos de tipo BAJA o... ingresos" — nunca por un evento de crecimiento — así
que la validación usa `cantidad_actual` tal cual está, sin que
`cantidad_medida` la altere (sigue siendo solo descriptivo del muestreo).
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

import pytest

from src.biological_assets.application.use_cases.gestion.registrar_evento_crecimiento_use_case import (
    RegistrarEventoCrecimientoUseCase,
)
from src.biological_assets.domain.entities.activo_biologico import (
    ActivoBiologico,
    DetallePoblacional,
    EventoActivo,
    GestionFase,
)
from src.biological_assets.domain.repositories.infraestructura_consulta_port import InfraestructuraConsulta
from src.biological_assets.domain.repositories.parametros_especie_port import ParametroEspecie
from src.biological_assets.domain.value_objects.estado_activo import EstadoActivo
from src.biological_assets.infrastructure.dto.registrar_evento_crecimiento_dto import RegistrarEventoCrecimientoDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import BusinessRuleError, ConflictError


class DbFake:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class ActivoRepoFake:
    def __init__(self, activo: ActivoBiologico) -> None:
        self.activo = activo
        self.actualizado: Optional[ActivoBiologico] = None

    def obtener_por_id(self, _id: int, *, ids_fincas_permitidas=None):
        return self.activo

    def obtener_fase_activa(self, _id: int) -> GestionFase:
        return GestionFase(
            id_activo_biologico=self.activo.id_activo_biologico,
            id_ciclo_productiva=None,  # sin avance automático de fase en estas pruebas
            nombre_ciclo='Ciclo de prueba',
            fecha_inicio=datetime.now(timezone.utc),
            es_activa=True,
            id_usuario=1,
        )

    def actualizar_detalle_poblacional(self, activo: ActivoBiologico) -> ActivoBiologico:
        self.actualizado = activo
        return activo


class EventoRepoFake:
    def __init__(self) -> None:
        self.guardado: Optional[EventoActivo] = None

    def obtener_ultima_fecha(self, _id: int):
        return None

    def guardar(self, evento: EventoActivo) -> EventoActivo:
        self.guardado = evento
        return evento


class InfraPortFake:
    def __init__(self, superficie: Decimal, capacidad_maxima: Optional[int]) -> None:
        self.superficie = superficie
        self.capacidad_maxima = capacidad_maxima

    def obtener_activa(self, _id_infraestructura: int) -> InfraestructuraConsulta:
        return InfraestructuraConsulta(
            id_infraestructura=1,
            nombre='Alevinera-01',
            tipo='Estanque',
            es_activo=True,
            superficie=self.superficie,
            capacidad_maxima=self.capacidad_maxima,
        )


class ParametrosPortFake:
    def __init__(self, densidad_maxima: Decimal | None) -> None:
        self.densidad_maxima = densidad_maxima

    def obtener_densidad_maxima(self, _id_especie):
        return self.densidad_maxima

    def obtener_por_tipo_medicion(self, _id_especie, _tipo_medicion, _tipo_activo):
        return ParametroEspecie(
            nombre='Peso', tipo_medicion='PESO', aplica_a_tipo_activo='LOTE',
            tipo_dato='DECIMAL', es_obligatorio=True,
        )


class BitacoraRepoFake:
    def registrar(self, _evento) -> None:
        pass


def _activo_poblacional(cantidad_actual: int, id_infraestructura: int = 1) -> ActivoBiologico:
    return ActivoBiologico(
        id_especie=4,
        tipo='POBLACIONAL',
        origen_financiero='compra',
        id_infraestructura=id_infraestructura,
        id_estado=EstadoActivo.ACTIVO,
        id_usuario=1,
        id_activo_biologico=130,
        fecha_inicio_ciclo=date(2026, 1, 1),
        detalle_poblacional=DetallePoblacional(
            cantidad_inicial=cantidad_actual,
            cantidad_actual=cantidad_actual,
        ),
    )


def _usuario() -> UsuarioActual:
    return UsuarioActual(id_usuario=1, id_token=1, id_rol=2)


def _dto(**overrides) -> RegistrarEventoCrecimientoDTO:
    base = dict(
        tipo_medicion='PESO',
        valor_medicion=Decimal('50'),
        unidad_medida='kg',
        nuevo_peso_promedio=Decimal('55'),
        cantidad_medida=250,
        tipo_agregacion='PROMEDIO',
        fecha=datetime(2026, 6, 1, tzinfo=timezone.utc),
    )
    base.update(overrides)
    return RegistrarEventoCrecimientoDTO(**base)


def _uc(
    activo_repo,
    evento_repo,
    infra_port,
    db=None,
    densidad_maxima: Decimal | None = Decimal('1000'),
) -> RegistrarEventoCrecimientoUseCase:
    return RegistrarEventoCrecimientoUseCase(
        db=db or DbFake(),
        activo_repo=activo_repo,
        evento_repo=evento_repo,
        infra_port=infra_port,
        parametros_port=ParametrosPortFake(densidad_maxima),
        ciclo_port=None,
        bitacora_repo=BitacoraRepoFake(),
    )


def test_densidad_por_encima_del_maximo_es_409() -> None:
    """Reproduce el caso reportado: cantidad_actual=5, superficie=500 ->
    densidad=0.01 y límite M09=0.004."""
    activo = _activo_poblacional(cantidad_actual=5)
    activo_repo = ActivoRepoFake(activo)
    evento_repo = EventoRepoFake()
    infra_port = InfraPortFake(superficie=Decimal('500'), capacidad_maxima=None)
    uc = _uc(activo_repo, evento_repo, infra_port, densidad_maxima=Decimal('0.004'))

    with pytest.raises(ConflictError) as exc_info:
        uc.execute(130, _dto(), _usuario())

    assert exc_info.value.code == 'DENSIDAD_MAXIMA_SUPERADA'
    assert exc_info.value.message == 'La densidad del lote supera el máximo permitido para la especie.'
    assert evento_repo.guardado is None
    assert activo_repo.actualizado is None


def test_densidad_igual_al_maximo_es_aceptada() -> None:
    """Borde exacto: densidad == límite M09 (0.01), no debe rechazar."""
    activo = _activo_poblacional(cantidad_actual=5)
    activo_repo = ActivoRepoFake(activo)
    evento_repo = EventoRepoFake()
    infra_port = InfraPortFake(superficie=Decimal('500'), capacidad_maxima=None)
    uc = _uc(activo_repo, evento_repo, infra_port, densidad_maxima=Decimal('0.01'))

    resultado, _ = uc.execute(130, _dto(), _usuario())

    assert resultado is not None
    assert evento_repo.guardado is not None


def test_densidad_por_debajo_del_maximo_es_aceptada() -> None:
    activo = _activo_poblacional(cantidad_actual=5)
    activo_repo = ActivoRepoFake(activo)
    evento_repo = EventoRepoFake()
    infra_port = InfraPortFake(superficie=Decimal('500'), capacidad_maxima=None)
    uc = _uc(activo_repo, evento_repo, infra_port, densidad_maxima=Decimal('0.02'))

    resultado, _ = uc.execute(130, _dto(), _usuario())

    assert resultado is not None
    assert activo.detalle_poblacional.peso_promedio == Decimal('55')
    # cantidad_actual no cambia por un evento de crecimiento (RF-36)
    assert activo.detalle_poblacional.cantidad_actual == 5


def test_sin_densidad_maxima_configurada_rechaza_de_forma_controlada() -> None:
    """La ausencia del dato obligatorio de M09 nunca omite la regla."""
    activo = _activo_poblacional(cantidad_actual=999999)
    activo_repo = ActivoRepoFake(activo)
    evento_repo = EventoRepoFake()
    infra_port = InfraPortFake(superficie=Decimal('500'), capacidad_maxima=None)
    uc = _uc(
        activo_repo,
        evento_repo,
        infra_port,
        densidad_maxima=None,
    )

    with pytest.raises(BusinessRuleError) as exc_info:
        uc.execute(130, _dto(), _usuario())

    assert exc_info.value.code == 'DENSIDAD_MAXIMA_NO_CONFIGURADA'
    assert evento_repo.guardado is None


def test_cantidad_medida_no_afecta_la_validacion_de_densidad() -> None:
    """RF-36: cantidad_medida es solo descriptiva del muestreo. Un
    cantidad_medida grande (250) no debe disparar el rechazo si
    cantidad_actual (5) sigue bajo el máximo."""
    activo = _activo_poblacional(cantidad_actual=5)
    activo_repo = ActivoRepoFake(activo)
    evento_repo = EventoRepoFake()
    # Aunque capacidad_maxima sea menor que la población, este flujo evalúa
    # el límite biológico por especie; cantidad_medida continúa siendo muestra.
    infra_port = InfraPortFake(superficie=Decimal('500'), capacidad_maxima=2)
    uc = _uc(activo_repo, evento_repo, infra_port, densidad_maxima=Decimal('0.02'))

    resultado, _ = uc.execute(130, _dto(cantidad_medida=250), _usuario())

    assert resultado is not None
    assert evento_repo.guardado.crecimiento.cantidad_medida == 250
    assert activo.detalle_poblacional.cantidad_actual == 5
