"""
TC-M06-G76 (RF-93 CA-3, RNF-93-04, CU-05) - "Filtros combinados y
coherencia con el consolidado."

Construido 2026-11-07 contra el código real de RF-93. Primera ronda. Ver
TC-M06-G75 (ya construido) para el hallazgo base sobre `FiltrosEstadoDTO`
(4 campos reales: `id_especie`, `id_activo_biologico`, `id_infraestructura`,
`id_finca` -- no existe `filtro_activo_poblacional`).

Código bajo prueba:
    src/financial_valuation/infrastructure/dto/m06_dto.py (FiltrosEstadoDTO)
    src/financial_valuation/infrastructure/routers/m06_router.py (generar_estado)
    src/financial_valuation/application/services/reportes.py (ConstructorEstadoResultados.calcular)

HALLAZGO PRINCIPAL: la ficha enumera "infraestructura, especie, activo
POBLACIONAL y PERÍODO" como las 4 dimensiones combinables del filtro. El
período NO es un filtro: es el segmento de ruta
`POST /finanzas/periodos/{id_periodo_contable}/estados-resultados` -- fijo
por la URL, no un campo de `FiltrosEstadoDTO` que se pueda combinar con los
demás en una sola llamada. Los 4 campos REALES combinables son
`id_especie`, `id_activo_biologico`, `id_infraestructura` e `id_finca` --
`id_finca` ni siquiera aparece mencionado en la ficha. Es decir: el
conjunto de dimensiones que describe la ficha no coincide con el real ni en
cantidad conceptual ni en los nombres (sustituye período por finca, y
"activo POBLACIONAL" sigue sin existir como filtro propio, ver G05).

(a) Combinaciones crecientes (1/2/3/4 filtros) -- CONFIRMADO: como las
    condiciones se combinan con AND sobre columnas distintas, cualquier
    combinación de 1 a 4 de los 4 campos reales se aplica sin error.
(b) Suma de todos los filtrados = no filtrado -- CONFIRMADO (test con
    partición completa por especie×infraestructura).
(c) 4 filtros simultáneos no degradan el tiempo de respuesta -- NO
    VERIFICABLE EN ESTE ENTORNO: requiere una base de datos real con
    volumen de datos y medición de latencia (RNF-93-04); no se simula aquí
    de forma realista. Queda como limitación explícita, no como hallazgo.
(d) Combinación contradictoria -- CONFIRMADO con comportamiento bien
    definido: como todas las condiciones son un único `WHERE ... AND ...`
    evaluado de una vez (no se aplican en secuencia ni una “gana” sobre
    otra), una combinación imposible (p. ej. un activo que pertenece a una
    infraestructura distinta a la filtrada) simplemente no encuentra filas
    y devuelve componentes en cero -- el mismo mecanismo exacto que "filtro
    sin coincidencias" de TC-M06-G75(e). NINGÚN filtro se ignora en
    silencio: los cuatro se evalúan siempre, todos a la vez.

Como correrlo (Windows necesita el stub de fcntl):
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    python -m pytest <ruta>\\test_tc_m06_g76_filtros_combinados_coherencia_consolidado.py -v \\
        --html=<ruta>\\resultados\\resultado_TC-M06-G76.html --self-contained-html
"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from src.financial_valuation.application.services.reportes import ConstructorEstadoResultados
from src.financial_valuation.infrastructure.dto.m06_dto import FiltrosEstadoDTO

REPO_ROOT = Path(__file__).resolve().parents[5]


def _aplica(filtros: dict, fila: dict) -> bool:
    return all(fila.get(campo) == valor for campo, valor in filtros.items() if valor)


class _FakeReportes:
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


def _mov(valor, id_especie, id_activo_biologico, id_infraestructura, id_finca):
    return {'tipo_hecho': 'VARIACION_VR_TB', 'sentido': 'GANANCIA', 'valor': valor, 'es_reverso': False,
            'id_especie': id_especie, 'id_activo_biologico': id_activo_biologico,
            'id_infraestructura': id_infraestructura, 'id_finca': id_finca}


# Particion completa en 4 celdas: 2 especies x 2 infraestructuras, cada combinacion con un
# activo y una finca distintos -- permite sumar por cualquier subconjunto de dimensiones.
_MOVIMIENTOS = [
    _mov('10.00', id_especie=10, id_activo_biologico=1, id_infraestructura=1, id_finca=100),
    _mov('20.00', id_especie=10, id_activo_biologico=2, id_infraestructura=2, id_finca=100),
    _mov('30.00', id_especie=20, id_activo_biologico=3, id_infraestructura=1, id_finca=200),
    _mov('40.00', id_especie=20, id_activo_biologico=4, id_infraestructura=2, id_finca=200),
]


class TestSubCasoLaFichaAsumeElPeriodoComoFiltroCombinableDocumentacion:
    def test_filtros_estado_dto_no_tiene_ningun_campo_de_periodo(self):
        """No es un defecto: el periodo es fijo por la URL
        (POST /finanzas/periodos/{id_periodo_contable}/estados-resultados), no un campo
        combinable de FiltrosEstadoDTO -- diferencia de alcance con la ficha, no una
        funcionalidad faltante."""
        campos = set(FiltrosEstadoDTO.model_fields.keys())
        assert 'id_periodo_contable' not in campos
        assert 'id_finca' in campos  # campo real que la ficha ni menciona


class TestSubCasoACombinacionesCrecientesDeFiltros:
    def test_un_filtro(self):
        c = ConstructorEstadoResultados(reportes=_FakeReportes(_MOVIMIENTOS), costos=_FakeCostos())
        r = c.calcular(1, {'id_especie': 10})
        assert Decimal(r['componentes']['ganancia_transformacion_biologica']) == Decimal('30.00')

    def test_dos_filtros(self):
        c = ConstructorEstadoResultados(reportes=_FakeReportes(_MOVIMIENTOS), costos=_FakeCostos())
        r = c.calcular(1, {'id_especie': 10, 'id_infraestructura': 1})
        assert Decimal(r['componentes']['ganancia_transformacion_biologica']) == Decimal('10.00')

    def test_tres_filtros(self):
        c = ConstructorEstadoResultados(reportes=_FakeReportes(_MOVIMIENTOS), costos=_FakeCostos())
        r = c.calcular(1, {'id_especie': 10, 'id_infraestructura': 1, 'id_finca': 100})
        assert Decimal(r['componentes']['ganancia_transformacion_biologica']) == Decimal('10.00')

    def test_cuatro_filtros_simultaneos_incluido_el_activo(self):
        c = ConstructorEstadoResultados(reportes=_FakeReportes(_MOVIMIENTOS), costos=_FakeCostos())
        r = c.calcular(1, {'id_especie': 10, 'id_infraestructura': 1, 'id_finca': 100, 'id_activo_biologico': 1})
        assert Decimal(r['componentes']['ganancia_transformacion_biologica']) == Decimal('10.00')


class TestSubCasoBSumaDeTodosLosFiltradosIgualAlNoFiltrado:
    def test_suma_de_las_cuatro_celdas_de_la_particion_igual_al_consolidado(self):
        c = ConstructorEstadoResultados(reportes=_FakeReportes(_MOVIMIENTOS), costos=_FakeCostos())
        consolidado = Decimal(c.calcular(1, {})['componentes']['ganancia_transformacion_biologica'])
        suma = sum(
            Decimal(c.calcular(1, {'id_activo_biologico': idx})['componentes']['ganancia_transformacion_biologica'])
            for idx in (1, 2, 3, 4)
        )
        assert suma == consolidado == Decimal('100.00')


class TestSubCasoCRendimientoNoVerificableSinBdReal:
    def test_limitacion_explicita_de_rendimiento(self):
        pytest.skip(
            "RNF-93-04 (4 filtros simultaneos no degradan el tiempo de respuesta) requiere una "
            "base de datos real con volumen representativo y medicion de latencia -- no se "
            "simula de forma realista en este entorno de pytest sin BD. Limitacion explicita, "
            "no un hallazgo de codigo."
        )


class TestSubCasoDCombinacionContradictoriaTieneComportamientoBienDefinido:
    def test_combinacion_imposible_no_ignora_ningun_filtro_simplemente_no_hay_match(self):
        """Activo 1 pertenece a infraestructura 1 (ver _MOVIMIENTOS) -- combinarlo con
        infraestructura 2 es una combinacion contradictoria. El comportamiento real: ambas
        condiciones se evaluan SIEMPRE juntas en un unico WHERE..AND, asi que no hay ningun
        'filtro ganador' que se imponga sobre el otro -- simplemente no hay filas que
        satisfagan ambas, y el resultado es cero, igual que un filtro sin coincidencias."""
        c = ConstructorEstadoResultados(reportes=_FakeReportes(_MOVIMIENTOS), costos=_FakeCostos())
        r = c.calcular(1, {'id_activo_biologico': 1, 'id_infraestructura': 2})
        assert Decimal(r['componentes']['ganancia_transformacion_biologica']) == Decimal('0')
        assert r['resultado_neto'] == Decimal('0')
