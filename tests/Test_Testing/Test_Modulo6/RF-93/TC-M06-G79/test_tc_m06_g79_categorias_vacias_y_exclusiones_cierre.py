"""
TC-M06-G79 (RF-93 CA-6, CA-8, FA-3, FA-4, CU-07/CU-08) - "Categorías sin
registros y activos excluidos del cierre."

Construido 2026-11-07 contra el código real de RF-93 (implementado
2026-11-04/05 por Arekkazu). Primera ronda, código nunca antes probado.

Código bajo prueba:
    src/financial_valuation/application/services/reportes.py (ConstructorEstadoResultados)
    src/financial_valuation/domain/services/consolidacion.py (estado_resultados)
    src/financial_valuation/application/use_cases/reportes/generar_estado_resultados_use_case.py

Ficha: "una categoría sin registros se presenta con valor 0.0000 e indicador
'sin actividad en el período' sin error; y los activos excluidos del cierre
con autorización del Contador quedan fuera del estado con todos sus
componentes, se listan explícitamente con sus montos y la ecuación sigue
cuadrando." Nota de la ficha: "Excluir un activo de ingresos pero no de
costos descuadraría la conciliación."

CORREGIDO 2026-11-12 (INC-M06-359-G79, commit `d2d9dbad`): los dos HALLAZGO
originales de este archivo ya están resueltos en el código real. Se deja la
evidencia histórica abajo y se reescriben las pruebas para confirmar el estado
actual.

HISTÓRICO -- lo que fallaba hasta el 2026-11-11: `GenerarEstadoResultadosUseCase.
generar()` obtenía la lista real de excluidos (`ejecucion.get("activos_excluidos")`)
y se la pasaba a `ConstructorEstadoResultados.guardar(..., excluidos)` -- pero
`guardar()` solo la usaba para decorar la salida; `calcular(self, id_periodo_contable,
filtros)` tenía exactamente 2 parámetros y nunca recibía `excluidos`, así que
`reportes.movimientos(...)`/`costos.del_periodo(...)` traían TODAS las líneas del
período, incluidas las de los activos "excluidos" -- la exclusión era cosmética.

CORRECCIÓN REAL CONFIRMADA (`reportes.py`, commit `d2d9dbad`):
`calcular(self, id_periodo_contable, filtros, excluir_activos=())` ahora SÍ recibe
la lista y la agrega a la consulta real (`{**filtros, "excluir_activos": ...}`);
`guardar()` ahora extrae los ids de `excluidos` (lista de dicts con
`id_activo_biologico`) y los reenvía a `calcular()`. Además cada activo excluido
ahora se lista con sus `montos_excluidos` reales (vía `_con_montos()`), y todos los
montos se serializan con `q4()` a 4 decimales ("0.0000", no "0").

(a) Categoría sin registros -> 0.0000 + indicador, sin error -- CORREGIDO: ahora
    `calcular()` aplica `q4()` antes de convertir a texto, así que un componente sin
    movimientos serializa "0.0000", no "0".
(b)-(h) Activos excluidos quedan fuera con todos sus componentes -- CORREGIDO: ver
    arriba, `excluir_activos` ya llega hasta la consulta real.

Cómo se prueba: pytest de unidad sobre `ConstructorEstadoResultados`/
`estado_resultados()` con repos mockeados, más inspección de firma
(`inspect.signature`) para confirmar que `calcular()` ahora sí recibe un parámetro
de exclusión, y que `guardar()`/`generar()` lo reenvían hasta la consulta real
(verificado con `assert_called_once_with` sobre el mock del repositorio).

Como correrlo (Windows necesita el stub de fcntl):
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    $env:SECRET_KEY = "test"
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    python -m pytest <ruta>\\test_tc_m06_g79_categorias_vacias_y_exclusiones_cierre.py -v \\
        --html=<ruta>\\resultados\\resultado_TC-M06-G79.html --self-contained-html
"""
from __future__ import annotations

import inspect
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from src.financial_valuation.application.services.reportes import ConstructorEstadoResultados
from src.financial_valuation.application.use_cases.reportes.generar_estado_resultados_use_case import (
    GenerarEstadoResultadosUseCase,
)
from src.financial_valuation.domain.entities.contabilidad import Periodo
from src.financial_valuation.domain.services.consolidacion import MovimientoResultado, estado_resultados
from src.financial_valuation.domain.value_objects.nic41 import Sentido, TipoHecho


def _periodo():
    import datetime
    return Periodo(id_periodo_contable=93, numero_id_tributaria="900123456", tipo_cierre="MENSUAL",
                   fecha_inicio=datetime.date(2026, 10, 1), fecha_fin=datetime.date(2026, 10, 31), estado="CERRADO")


class TestSubCasoAUnaCategoriaSinRegistrosQuedaEnCeroSinError:
    def test_un_componente_sin_movimientos_queda_en_decimal_cero_sin_lanzar_error(self):
        er = estado_resultados([MovimientoResultado(TipoHecho.VARIACION_VR_TB.value, Sentido.GANANCIA.value, Decimal('10.00'))], [])
        assert er.componentes['ingresos_productos_agricolas'] == Decimal('0')

    def test_el_indicador_sin_actividad_si_existe_y_lista_los_componentes_vacios(self):
        reportes = MagicMock()
        reportes.movimientos.return_value = [
            {'tipo_hecho': 'VARIACION_VR_TB', 'sentido': 'GANANCIA', 'valor': '10.00', 'es_reverso': False},
        ]
        costos = MagicMock()
        costos.del_periodo.return_value = []
        constructor = ConstructorEstadoResultados(reportes=reportes, costos=costos)
        resultado = constructor.calcular(id_periodo_contable=93, filtros={})
        assert 'ingresos_productos_agricolas' in resultado['sin_actividad']
        assert 'ganancia_transformacion_biologica' not in resultado['sin_actividad']

    def test_el_valor_serializado_ahora_si_es_0_0000_corregido(self):
        """CORREGIDO (commit d2d9dbad, INC-M06-359-G79): calcular() ahora aplica q4()
        antes de convertir a texto, asi que un componente sin actividad serializa
        '0.0000' (4 decimales), como pide la ficha -- antes salia '0'."""
        reportes = MagicMock()
        reportes.movimientos.return_value = []
        costos = MagicMock()
        costos.del_periodo.return_value = []
        constructor = ConstructorEstadoResultados(reportes=reportes, costos=costos)
        resultado = constructor.calcular(id_periodo_contable=93, filtros={})
        assert resultado['componentes']['ingresos_productos_agricolas'] == '0.0000'


class TestSubCasoBHLosActivosExcluidosAhoraSiSeExcluyenCorregido:
    def test_calcular_ahora_si_tiene_un_parametro_de_exclusion(self):
        """CORREGIDO (commit d2d9dbad): calcular() ahora acepta excluir_activos."""
        firma = inspect.signature(ConstructorEstadoResultados.calcular)
        assert 'excluir_activos' in firma.parameters

    def test_guardar_pasa_los_ids_excluidos_como_filtro_real_a_la_consulta(self):
        """CORREGIDO: guardar() extrae los ids de 'excluidos' (lista de dicts con
        id_activo_biologico, el formato real que entrega el cierre) y calcular() los
        agrega a la consulta real de movimientos/costos -- ya no es solo metadato."""
        reportes = MagicMock()
        reportes.movimientos.return_value = [
            {'tipo_hecho': 'VARIACION_VR_TB', 'sentido': 'GANANCIA', 'valor': '100.00', 'es_reverso': False},
        ]
        reportes.siguiente_version_estado.return_value = 1
        reportes.agregar_estado.return_value = 1
        costos = MagicMock()
        costos.del_periodo.return_value = []
        constructor = ConstructorEstadoResultados(reportes=reportes, costos=costos)
        excluidos = [{'id_activo_biologico': 555}, {'id_activo_biologico': 777}]
        constructor.guardar(id_periodo_contable=93, filtros={}, id_usuario=1, excluidos=excluidos)
        # La primera llamada (el calculo principal) ya incluye el filtro de exclusion real.
        primera_llamada = reportes.movimientos.call_args_list[0]
        assert primera_llamada.args == (93, {'excluir_activos': [555, 777]})

    def test_generar_reenvia_los_excluidos_reales_del_cierre_hasta_la_consulta(self):
        """CORREGIDO: generar() obtiene los excluidos reales del cierre (lista de dicts
        con id_activo_biologico, como los entrega periodos.ultima_ejecucion() de verdad)
        y ahora SI llegan como filtro real hasta reportes.movimientos()."""
        periodos = MagicMock()
        periodos.obtener.return_value = _periodo()
        periodos.ultima_ejecucion.return_value = {'activos_excluidos': [{'id_activo_biologico': 42}]}
        reportes = MagicMock()
        reportes.movimientos.return_value = [
            {'tipo_hecho': 'BAJA_ACTIVO', 'sentido': 'UNICO', 'valor': '250.00', 'es_reverso': False},
        ]
        reportes.siguiente_version_estado.return_value = 2
        reportes.agregar_estado.return_value = 2
        costos = MagicMock()
        costos.del_periodo.return_value = []
        constructor = ConstructorEstadoResultados(reportes=reportes, costos=costos)
        uc = GenerarEstadoResultadosUseCase(db=MagicMock(), periodos=periodos, reportes=reportes,
                                            constructor=constructor, auditoria=MagicMock())
        resultado = uc.generar(id_periodo_contable=93, filtros={}, id_usuario=1)
        assert resultado['activos_excluidos_cierre'][0]['id_activo_biologico'] == 42  # se lista
        primera_llamada = reportes.movimientos.call_args_list[0]
        assert primera_llamada.args == (93, {'excluir_activos': [42]})  # y ahora tambien se filtra
