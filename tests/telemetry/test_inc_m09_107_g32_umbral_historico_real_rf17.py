"""INC-M09-107-G32 (#298): el semáforo histórico (RF-59) debe consumir el umbral RF-17 real.

Cubre `SemaforoCalculator.calcular_por_niveles` y `ConsultarHistorialUseCase._semaforo_historico`
contra un `UmbralHistoricoPort` fake. El adaptador real (`UmbralHistoricoM09Adapter`) delega en
`SqlAlchemyUmbralAmbientalRepository`, ya cubierto por sus propias pruebas de módulo 9.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from src.telemetry.domain.entities.monitoreo import (
    FiltrosHistorial,
    LecturaHistorica,
    SemaforoCalculator,
)
from src.telemetry.application.use_cases.monitoreo.consultar_historial_use_case import (
    ConsultarHistorialUseCase,
)

_NIVELES_TILAPIA_TEMP = [
    {"nivel": "normal", "limite_inferior": Decimal("18.00"), "limite_superior": Decimal("21.00")},
    {"nivel": "precaucion", "limite_inferior": Decimal("21.00"), "limite_superior": Decimal("24.00")},
    {"nivel": "critico", "limite_inferior": Decimal("24.00"), "limite_superior": Decimal("27.00")},
]


class _UmbralPortFake:
    def __init__(self, umbral: Optional[dict]) -> None:
        self.umbral = umbral
        self.llamadas: list[dict] = []

    def obtener_umbral_vigente(self, id_variable_ambiental, id_especie, timestamp) -> Optional[dict]:
        self.llamadas.append({
            "id_variable_ambiental": id_variable_ambiental,
            "id_especie": id_especie,
            "timestamp": timestamp,
        })
        return self.umbral


class _HistorialRepoFake:
    def __init__(self, lecturas: list[LecturaHistorica]) -> None:
        self.lecturas = lecturas

    def consultar(self, filtros):
        return self.lecturas, len(self.lecturas)

    def calcular_estadisticas(self, filtros):
        return []


def _lectura(*, id_especie: Optional[int], valor: Optional[Decimal], id_variable: int = 1) -> LecturaHistorica:
    return LecturaHistorica(
        id_telemetria=1,
        id_sensor=101,
        nombre_sensor="Sensor Temp A1",
        id_variable=id_variable,
        tipo_variable="TEMPERATURA_AMBIENTAL",
        categoria_variable="AMBIENTAL",
        valor=valor,
        valor_ajustado=None,
        unidad_medida="°C",
        timestamp_captura=datetime(2026, 9, 13, 2, 16, 45, tzinfo=timezone.utc),
        estado_calidad="LECTURA_VALIDA",
        estado_semaforo_historico="GRIS",
        origen_dato="TIEMPO_REAL",
        id_infraestructura=1,
        infraestructura="Galpón A",
        finca="Finca El Pinar",
        id_activo_biologico=55,
        especie="Tilapia Roja",
        id_especie=id_especie,
        id_alerta=None,
        nivel_bateria_pct=None,
        calidad_senal_rssi=None,
        calidad_senal_snr=None,
    )


def _filtros() -> FiltrosHistorial:
    return FiltrosHistorial(fecha_inicio=date(2026, 9, 1), fecha_fin=date(2026, 9, 13))


class TestSemaforoCalculatorPorNiveles:
    def test_valor_en_banda_normal_es_verde(self) -> None:
        assert SemaforoCalculator.calcular_por_niveles(Decimal("19.5"), _NIVELES_TILAPIA_TEMP) == "VERDE"

    def test_valor_en_banda_precaucion_es_amarillo(self) -> None:
        assert SemaforoCalculator.calcular_por_niveles(Decimal("22.0"), _NIVELES_TILAPIA_TEMP) == "AMARILLO"

    def test_valor_en_banda_critica_es_rojo(self) -> None:
        assert SemaforoCalculator.calcular_por_niveles(Decimal("25.0"), _NIVELES_TILAPIA_TEMP) == "ROJO"

    def test_valor_fuera_de_todas_las_bandas_es_rojo(self) -> None:
        assert SemaforoCalculator.calcular_por_niveles(Decimal("30.0"), _NIVELES_TILAPIA_TEMP) == "ROJO"
        assert SemaforoCalculator.calcular_por_niveles(Decimal("5.0"), _NIVELES_TILAPIA_TEMP) == "ROJO"


class TestSemaforoHistoricoConsumeUmbralReal:
    def test_sin_especie_resuelta_no_consulta_el_puerto_y_queda_gris(self) -> None:
        lectura = _lectura(id_especie=None, valor=Decimal("19.5"))
        port = _UmbralPortFake(umbral=None)
        caso_uso = ConsultarHistorialUseCase(
            historial_repo=_HistorialRepoFake([lectura]),
            umbral_port=port,
        )

        lecturas, _stats, _total, _meta = caso_uso.execute(_filtros())

        assert lecturas[0].estado_semaforo_historico == "GRIS"
        assert port.llamadas == []

    def test_sin_valor_queda_gris(self) -> None:
        lectura = _lectura(id_especie=39, valor=None)
        caso_uso = ConsultarHistorialUseCase(
            historial_repo=_HistorialRepoFake([lectura]),
            umbral_port=_UmbralPortFake(umbral=None),
        )

        lecturas, _stats, _total, _meta = caso_uso.execute(_filtros())

        assert lecturas[0].estado_semaforo_historico == "GRIS"

    def test_sin_umbral_configurado_queda_gris(self) -> None:
        lectura = _lectura(id_especie=39, valor=Decimal("19.5"))
        caso_uso = ConsultarHistorialUseCase(
            historial_repo=_HistorialRepoFake([lectura]),
            umbral_port=_UmbralPortFake(umbral=None),
        )

        lecturas, _stats, _total, _meta = caso_uso.execute(_filtros())

        assert lecturas[0].estado_semaforo_historico == "GRIS"
        assert lecturas[0].id_umbral_ambiental is None

    def test_umbral_configurado_calcula_semaforo_real_y_expone_identificacion(self) -> None:
        lectura = _lectura(id_especie=39, valor=Decimal("22.0"))
        version = datetime(2026, 9, 10, 12, 0, 0, tzinfo=timezone.utc)
        port = _UmbralPortFake(umbral={
            "id_umbral_ambiental": 39,
            "umbral_min": Decimal("18.00"),
            "umbral_max": Decimal("27.00"),
            "niveles": _NIVELES_TILAPIA_TEMP,
            "version": version,
        })
        caso_uso = ConsultarHistorialUseCase(
            historial_repo=_HistorialRepoFake([lectura]),
            umbral_port=port,
        )

        lecturas, _stats, _total, _meta = caso_uso.execute(_filtros())
        resultado = lecturas[0]

        assert resultado.estado_semaforo_historico == "AMARILLO"
        assert resultado.id_umbral_ambiental == 39
        assert resultado.valor_min_umbral == Decimal("18.00")
        assert resultado.valor_max_umbral == Decimal("27.00")
        assert resultado.version_umbral == version
        assert port.llamadas == [{
            "id_variable_ambiental": 1,
            "id_especie": 39,
            "timestamp": lectura.timestamp_captura,
        }]
