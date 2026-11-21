"""
TC-M06-G75 (RF-93 CA-2, Entradas, CU-05) - "Filtros individuales de
generación."

Construido 2026-11-07 contra el código real de RF-93 (implementado
2026-11-04/05 por Arekkazu). Primera ronda, código nunca antes probado por
QA. Ver TC-M06-G71..G04 (ya construidos) para el resto de hallazgos sobre
el motor de cálculo; este TC se enfoca solo en los filtros de la
generación.

Código bajo prueba:
    src/financial_valuation/infrastructure/dto/m06_dto.py (FiltrosEstadoDTO)
    src/financial_valuation/infrastructure/repositories/reporte_repository.py (_FILTROS, movimientos())
    src/financial_valuation/infrastructure/repositories/costo_repository.py (del_periodo())
    src/financial_valuation/application/services/reportes.py (ConstructorEstadoResultados.calcular)

HALLAZGO PRINCIPAL: la ficha pide probar un filtro por "activo POBLACIONAL"
como si fuera un mecanismo distinto al de activo individual (su propia nota
dice "filtro_activo_poblacional reemplaza a filtro_lote en la v1.1", dando
por hecho que existe un campo con ese nombre). El DTO real
(`FiltrosEstadoDTO`, `m06_dto.py` línea 163) tiene EXACTAMENTE 4 campos:
`id_especie`, `id_activo_biologico`, `id_infraestructura`, `id_finca` --
todos enteros opcionales (`gt=0`). No existe ningún campo
`filtro_activo_poblacional`, ni booleano ni de ningún otro tipo. Filtrar un
activo POBLACIONAL no es un mecanismo distinto: se hace exactamente igual
que cualquier otro activo, pasando su `id_activo_biologico`. El concepto
"filtro_lote" que la ficha asume que existía en una versión anterior
tampoco aparece en ningún lado del código actual.

(a) Filtro por especie -- CONFIRMADO: `_FILTROS` incluye
    `l.id_especie = :id_especie`.
(b) Filtro por "activo POBLACIONAL" -- HALLAZGO: no existe como mecanismo
    propio (ver arriba); se prueba aquí como filtro normal por
    `id_activo_biologico`.
(c) Filtro por activo individual -- CONFIRMADO: mismo campo que (b),
    `id_activo_biologico`.
(d) Filtro por infraestructura -- CONFIRMADO: `_FILTROS` usa
    `a.id_infraestructura = :id_infraestructura` (join contra
    `modulo2.activos_biologicos a`, no una columna directa de la línea).
(e) Filtro sin coincidencias -> componentes en cero, no error --
    CONFIRMADO: `calcular()` no valida que `movimientos`/`costos` sea
    no-vacío; `estado_resultados([], [])` devuelve todos los componentes en
    `CERO` sin lanzar ninguna excepción.
(f) Suma de estados filtrados por especie equivale al consolidado --
    CONFIRMADO en este test con datos sintéticos (ver
    `TestSubCasoFSumaPorEspecieEquivaleAlConsolidado`).
(g) Suma de estados filtrados por infraestructura equivale al consolidado
    -- CONFIRMADO igual que (f).

Nota de alcance: no hay una BD real disponible en este entorno de pruebas,
así que el filtrado SQL real (`WHERE ... AND ...`) se reproduce aquí con un
repositorio en memoria que aplica EXACTAMENTE la misma condición de
`_FILTROS` (comparación de campo por igualdad, AND entre condiciones) sobre
una lista de movimientos sintética -- no se reinterpreta la semántica del
filtro, se usa la misma tabla de campos que el código real.

Como correrlo (Windows necesita el stub de fcntl):
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    $env:SECRET_KEY = "test"
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    python -m pytest <ruta>\\test_tc_m06_g75_filtros_individuales_generacion.py -v \\
        --html=<ruta>\\resultados\\resultado_TC-M06-G75.html --self-contained-html
"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from src.financial_valuation.application.services.reportes import ConstructorEstadoResultados
from src.financial_valuation.infrastructure.dto.m06_dto import FiltrosEstadoDTO

REPO_ROOT = Path(__file__).resolve().parents[5]

# Mismos 4 campos y misma semantica (igualdad, AND) que _FILTROS en reporte_repository.py.
_CAMPOS_FILTRO = ("id_especie", "id_activo_biologico", "id_infraestructura", "id_finca")


def _aplica(filtros: dict, fila: dict) -> bool:
    return all(fila.get(campo) == valor for campo, valor in filtros.items() if valor)


class _FakeReportes:
    """Reproduce movimientos()/siguiente_version_estado()/agregar_estado() con la MISMA
    semantica de filtro (igualdad + AND) que SqlAlchemyReporteRepository, sin BD."""

    def __init__(self, filas: list[dict]) -> None:
        self._filas = filas

    def movimientos(self, id_periodo_contable: int, filtros: dict) -> list[dict]:
        return [f for f in self._filas if _aplica(filtros, f)]

    def siguiente_version_estado(self, id_periodo_contable):
        return 1

    def agregar_estado(self, datos):
        return 1


class _FakeCostos:
    def del_periodo(self, id_periodo_contable: int, filtros: dict | None = None) -> list[dict]:
        return []


def _movimiento(valor, id_especie, id_activo_biologico, id_infraestructura, id_finca=900, es_reverso=False):
    return {'tipo_hecho': 'VARIACION_VR_TB', 'sentido': 'GANANCIA', 'valor': valor, 'es_reverso': es_reverso,
            'id_especie': id_especie, 'id_activo_biologico': id_activo_biologico,
            'id_infraestructura': id_infraestructura, 'id_finca': id_finca}


# Dos especies (10, 20), cada una con un activo en una infraestructura distinta (1, 2).
_MOVIMIENTOS = [
    _movimiento('100.00', id_especie=10, id_activo_biologico=1, id_infraestructura=1),
    _movimiento('50.00', id_especie=20, id_activo_biologico=2, id_infraestructura=2),
]


class TestSubCasoBNoExisteFiltroDeActivoPoblacionalComoMecanismoPropioDocumentacion:
    def test_filtros_estado_dto_tiene_exactamente_cuatro_campos(self):
        """No es un defecto: FiltrosEstadoDTO no tiene 'filtro_activo_poblacional' ni
        'filtro_lote' porque un activo POBLACIONAL se filtra con el mismo campo que
        cualquier otro activo (id_activo_biologico) -- diferencia de nombre con la ficha,
        no una funcionalidad faltante."""
        campos = set(FiltrosEstadoDTO.model_fields.keys())
        assert campos == {'id_especie', 'id_activo_biologico', 'id_infraestructura', 'id_finca'}


class TestSubCasoADFiltrosIndividualesConfirmadosCorrectos:
    def test_filtro_por_especie(self):
        constructor = ConstructorEstadoResultados(reportes=_FakeReportes(_MOVIMIENTOS), costos=_FakeCostos())
        r = constructor.calcular(1, {'id_especie': 10})
        assert Decimal(r['componentes']['ganancia_transformacion_biologica']) == Decimal('100.00')

    def test_filtro_por_activo_biologico_individual_o_poblacional_mismo_mecanismo(self):
        constructor = ConstructorEstadoResultados(reportes=_FakeReportes(_MOVIMIENTOS), costos=_FakeCostos())
        r = constructor.calcular(1, {'id_activo_biologico': 2})
        assert Decimal(r['componentes']['ganancia_transformacion_biologica']) == Decimal('50.00')

    def test_filtro_por_infraestructura(self):
        constructor = ConstructorEstadoResultados(reportes=_FakeReportes(_MOVIMIENTOS), costos=_FakeCostos())
        r = constructor.calcular(1, {'id_infraestructura': 1})
        assert Decimal(r['componentes']['ganancia_transformacion_biologica']) == Decimal('100.00')


class TestSubCasoEFiltroSinCoincidenciasDevuelveCeroSinError:
    def test_filtro_sin_coincidencias_no_lanza_excepcion_y_da_componentes_en_cero(self):
        constructor = ConstructorEstadoResultados(reportes=_FakeReportes(_MOVIMIENTOS), costos=_FakeCostos())
        r = constructor.calcular(1, {'id_especie': 999999})
        assert Decimal(r['componentes']['ganancia_transformacion_biologica']) == Decimal('0')
        assert r['resultado_neto'] == Decimal('0')


class TestSubCasoFSumaPorEspecieEquivaleAlConsolidado:
    def test_suma_de_estados_por_especie_igual_al_consolidado(self):
        constructor = ConstructorEstadoResultados(reportes=_FakeReportes(_MOVIMIENTOS), costos=_FakeCostos())
        consolidado = constructor.calcular(1, {})
        e10 = constructor.calcular(1, {'id_especie': 10})
        e20 = constructor.calcular(1, {'id_especie': 20})
        suma = Decimal(e10['componentes']['ganancia_transformacion_biologica']) + \
            Decimal(e20['componentes']['ganancia_transformacion_biologica'])
        assert suma == Decimal(consolidado['componentes']['ganancia_transformacion_biologica'])


class TestSubCasoGSumaPorInfraestructuraIgualAlConsolidado:
    def test_suma_de_estados_por_infraestructura_igual_al_consolidado(self):
        constructor = ConstructorEstadoResultados(reportes=_FakeReportes(_MOVIMIENTOS), costos=_FakeCostos())
        consolidado = constructor.calcular(1, {})
        i1 = constructor.calcular(1, {'id_infraestructura': 1})
        i2 = constructor.calcular(1, {'id_infraestructura': 2})
        suma = Decimal(i1['componentes']['ganancia_transformacion_biologica']) + \
            Decimal(i2['componentes']['ganancia_transformacion_biologica'])
        assert suma == Decimal(consolidado['componentes']['ganancia_transformacion_biologica'])
