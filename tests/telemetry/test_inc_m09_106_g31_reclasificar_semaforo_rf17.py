"""INC-M09-106-G31 (#297): la clasificación semafórica en tiempo real debe usar los
niveles RF-17 (normal/precaución/crítico) apenas se conoce la especie de la lectura.

Cubre `ReclasificarSemaforoUseCase` y su invocación desde `ResolverVinculacionUseCase`
y `CorregirVinculacionUseCase` (los dos puntos donde una vinculación puede resolverse
manualmente hoy, dado que la vinculación automática sigue detrás de
`ActivoBiologicoStubAdapter`).
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from src.telemetry.application.use_cases.infraestructura.corregir_vinculacion_use_case import (
    CorregirVinculacionUseCase,
)
from src.telemetry.application.use_cases.infraestructura.resolver_vinculacion_use_case import (
    ResolverVinculacionUseCase,
)
from src.telemetry.application.use_cases.monitoreo.reclasificar_semaforo_use_case import (
    ReclasificarSemaforoUseCase,
)
from src.telemetry.domain.entities.telemetria import Telemetria
from src.telemetry.domain.entities.vinculacion_lectura import VinculacionLectura
from src.telemetry.infrastructure.dto.corregir_vinculacion_dto import CorregirVinculacionDTO
from src.telemetry.infrastructure.dto.resolver_vinculacion_dto import ResolverVinculacionDTO

_NIVELES = [
    {"nivel": "normal", "limite_inferior": Decimal("37.00"), "limite_superior": Decimal("39.00")},
    {"nivel": "precaucion", "limite_inferior": Decimal("39.00"), "limite_superior": Decimal("41.00")},
    {"nivel": "critico", "limite_inferior": Decimal("41.00"), "limite_superior": Decimal("43.00")},
]


class _DbFake:
    def __init__(self) -> None:
        self.commits = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        pass


def _telemetria(*, valor_ajustado: Optional[Decimal], id_variable: int = 1) -> Telemetria:
    return Telemetria(
        id_telemetria=1,
        id_sensor=101,
        id_variable=id_variable,
        id_dispositivo_iot=5,
        valor_crudo=valor_ajustado or Decimal("0"),
        valor_ajustado=valor_ajustado,
        timestamp_captura=datetime(2026, 9, 13, 10, 37, 22, tzinfo=timezone.utc),
        timestamp_envio=None,
        timestamp_procesamiento=datetime(2026, 9, 13, 10, 37, 22, tzinfo=timezone.utc),
        origen='TIEMPO_REAL',
        estado_calidad='LECTURA_VALIDA',
        calibrado=True,
        categoria_variable='ANIMAL',
        unidad_medida='°C',
        valor_agregado=False,
        tipo_dato='CRUDO',
    )


class _TelemetriaRepoFake:
    def __init__(self, telemetria: Optional[Telemetria]) -> None:
        self.telemetria = telemetria

    def obtener_por_id(self, id_telemetria: int) -> Optional[Telemetria]:
        return self.telemetria


class _EspeciePortFake:
    def __init__(self, id_especie: Optional[int]) -> None:
        self.id_especie = id_especie
        self.llamadas: list[int] = []

    def obtener_id_especie(self, id_activo_biologico: int) -> Optional[int]:
        self.llamadas.append(id_activo_biologico)
        return self.id_especie


class _UmbralPortFake:
    def __init__(self, umbral: Optional[dict]) -> None:
        self.umbral = umbral
        self.llamadas: list[dict] = []

    def obtener_umbral_vigente(self, id_variable_ambiental, id_especie, timestamp) -> Optional[dict]:
        self.llamadas.append({
            'id_variable_ambiental': id_variable_ambiental,
            'id_especie': id_especie,
            'timestamp': timestamp,
        })
        return self.umbral


class _MonitoreoRepoFake:
    def __init__(self) -> None:
        self.llamadas: list[dict] = []

    def actualizar_estado_semaforo_si_vigente(self, id_sensor, timestamp_captura, estado_semaforo) -> None:
        self.llamadas.append({
            'id_sensor': id_sensor,
            'timestamp_captura': timestamp_captura,
            'estado_semaforo': estado_semaforo,
        })


def _use_case(
    *,
    telemetria: Optional[Telemetria],
    id_especie: Optional[int],
    umbral: Optional[dict],
) -> tuple[ReclasificarSemaforoUseCase, _MonitoreoRepoFake, _DbFake]:
    db = _DbFake()
    monitoreo_repo = _MonitoreoRepoFake()
    caso_uso = ReclasificarSemaforoUseCase(
        db=db,
        telemetria_repo=_TelemetriaRepoFake(telemetria),
        especie_port=_EspeciePortFake(id_especie),
        umbral_port=_UmbralPortFake(umbral),
        monitoreo_repo=monitoreo_repo,
    )
    return caso_uso, monitoreo_repo, db


class TestReclasificarSemaforoUseCase:
    def test_sin_activo_biologico_no_hace_nada(self) -> None:
        caso_uso, monitoreo_repo, db = _use_case(
            telemetria=_telemetria(valor_ajustado=Decimal("38.00")), id_especie=39, umbral=None,
        )

        resultado = caso_uso.execute(id_telemetria=1, id_activo_biologico=None)

        assert resultado is None
        assert monitoreo_repo.llamadas == []
        assert db.commits == 0

    def test_telemetria_inexistente_no_hace_nada(self) -> None:
        caso_uso, monitoreo_repo, _db = _use_case(telemetria=None, id_especie=39, umbral=None)

        resultado = caso_uso.execute(id_telemetria=999, id_activo_biologico=1)

        assert resultado is None
        assert monitoreo_repo.llamadas == []

    def test_sin_especie_resuelta_no_hace_nada(self) -> None:
        caso_uso, monitoreo_repo, _db = _use_case(
            telemetria=_telemetria(valor_ajustado=Decimal("38.00")), id_especie=None, umbral=None,
        )

        resultado = caso_uso.execute(id_telemetria=1, id_activo_biologico=1)

        assert resultado is None
        assert monitoreo_repo.llamadas == []

    def test_sin_umbral_configurado_no_hace_nada(self) -> None:
        caso_uso, monitoreo_repo, _db = _use_case(
            telemetria=_telemetria(valor_ajustado=Decimal("38.00")), id_especie=39, umbral=None,
        )

        resultado = caso_uso.execute(id_telemetria=1, id_activo_biologico=1)

        assert resultado is None
        assert monitoreo_repo.llamadas == []

    def test_clasifica_normal_precaucion_critico_segun_niveles_rf17(self) -> None:
        casos = [(Decimal("38.00"), "VERDE"), (Decimal("40.00"), "AMARILLO"), (Decimal("42.00"), "ROJO")]
        for valor, esperado in casos:
            caso_uso, monitoreo_repo, db = _use_case(
                telemetria=_telemetria(valor_ajustado=valor),
                id_especie=39,
                umbral={"niveles": _NIVELES},
            )

            resultado = caso_uso.execute(id_telemetria=1, id_activo_biologico=7)

            assert resultado == esperado, f"valor={valor}"
            assert monitoreo_repo.llamadas[0]['estado_semaforo'] == esperado
            assert monitoreo_repo.llamadas[0]['id_sensor'] == 101
            assert db.commits == 1


def _vinculacion(*, estado: str = 'AMBIGUA', id_activo_biologico: Optional[int] = None) -> VinculacionLectura:
    return VinculacionLectura(
        id_vinculacion_lectura=10,
        id_telemetria=1,
        modelo_manejo='INDIVIDUAL',
        id_activo_biologico=id_activo_biologico,
        id_infraestructura=1,
        fecha_inicio_vinculacion=datetime(2026, 9, 13, tzinfo=timezone.utc),
        fecha_fin_vinculacion=None,
        mecanismo_vinculacion='AUTOMATICA',
        estado_vinculacion=estado,
        id_usuario=None,
        motivo_correccion=None,
        id_vinculacion_reemplazada=None,
        fecha_creacion=datetime(2026, 9, 13, tzinfo=timezone.utc),
    )


class _VinculacionRepoFake:
    def __init__(self, vinculacion: VinculacionLectura) -> None:
        self.vinculacion = vinculacion

    def obtener_por_id(self, id_vinculacion_lectura: int) -> VinculacionLectura:
        return self.vinculacion

    def actualizar(self, vinculacion: VinculacionLectura) -> VinculacionLectura:
        self.vinculacion = vinculacion
        return vinculacion

    def guardar(self, vinculacion: VinculacionLectura) -> VinculacionLectura:
        vinculacion.id_vinculacion_lectura = 11
        return vinculacion


class _ReclasificarFake:
    def __init__(self, *, falla: bool = False) -> None:
        self.llamadas: list[dict] = []
        self.falla = falla

    def execute(self, id_telemetria: int, id_activo_biologico: Optional[int]):
        self.llamadas.append({'id_telemetria': id_telemetria, 'id_activo_biologico': id_activo_biologico})
        if self.falla:
            raise RuntimeError('boom')
        return 'AMARILLO'


class TestResolverVinculacionDisparaReclasificacion:
    def test_resolver_ambigua_reclasifica_con_el_activo_elegido(self) -> None:
        reclasificar = _ReclasificarFake()
        caso_uso = ResolverVinculacionUseCase(
            db=_DbFake(),
            vinculacion_repo=_VinculacionRepoFake(_vinculacion(estado='AMBIGUA')),
            reclasificar_semaforo_use_case=reclasificar,
        )

        caso_uso.execute(
            id_vinculacion_lectura=10,
            dto=ResolverVinculacionDTO(id_activo_biologico=7, modelo_manejo='INDIVIDUAL'),
            id_usuario=1,
        )

        assert reclasificar.llamadas == [{'id_telemetria': 1, 'id_activo_biologico': 7}]

    def test_fallo_en_reclasificacion_no_rompe_la_resolucion(self) -> None:
        caso_uso = ResolverVinculacionUseCase(
            db=_DbFake(),
            vinculacion_repo=_VinculacionRepoFake(_vinculacion(estado='AMBIGUA')),
            reclasificar_semaforo_use_case=_ReclasificarFake(falla=True),
        )

        resultado = caso_uso.execute(
            id_vinculacion_lectura=10,
            dto=ResolverVinculacionDTO(id_activo_biologico=7, modelo_manejo='INDIVIDUAL'),
            id_usuario=1,
        )

        assert resultado.estado_vinculacion == 'VINCULADA'


class TestCorregirVinculacionDisparaReclasificacion:
    def test_corregir_reclasifica_con_el_nuevo_activo(self) -> None:
        reclasificar = _ReclasificarFake()
        caso_uso = CorregirVinculacionUseCase(
            db=_DbFake(),
            vinculacion_repo=_VinculacionRepoFake(_vinculacion(estado='VINCULADA', id_activo_biologico=3)),
            reclasificar_semaforo_use_case=reclasificar,
        )

        caso_uso.execute(
            id_vinculacion_lectura=10,
            dto=CorregirVinculacionDTO(id_activo_biologico=9, modelo_manejo='INDIVIDUAL', motivo='Activo incorrecto'),
            id_usuario=1,
        )

        assert reclasificar.llamadas == [{'id_telemetria': 1, 'id_activo_biologico': 9}]

    def test_fallo_en_reclasificacion_no_rompe_la_correccion(self) -> None:
        caso_uso = CorregirVinculacionUseCase(
            db=_DbFake(),
            vinculacion_repo=_VinculacionRepoFake(_vinculacion(estado='VINCULADA', id_activo_biologico=3)),
            reclasificar_semaforo_use_case=_ReclasificarFake(falla=True),
        )

        resultado = caso_uso.execute(
            id_vinculacion_lectura=10,
            dto=CorregirVinculacionDTO(id_activo_biologico=9, modelo_manejo='INDIVIDUAL', motivo='Activo incorrecto'),
            id_usuario=1,
        )

        assert resultado.id_activo_biologico == 9
