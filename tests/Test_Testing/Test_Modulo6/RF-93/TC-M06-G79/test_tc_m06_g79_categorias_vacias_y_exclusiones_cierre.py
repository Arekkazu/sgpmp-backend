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

HALLAZGO PRINCIPAL (grave): los activos excluidos del cierre NO se excluyen
realmente del estado de resultados. `GenerarEstadoResultadosUseCase.generar()`
obtiene la lista real de excluidos (`ejecucion.get("activos_excluidos")`,
desde `periodos.ultima_ejecucion()`) y se la pasa a
`ConstructorEstadoResultados.guardar(..., excluidos)` -- pero `guardar()`
SOLO la usa para decorar la salida:
```python
def guardar(self, id_periodo_contable, filtros, id_usuario, excluidos):
    calculo = self.calcular(id_periodo_contable, filtros)   # <- excluidos NO se pasa aqui
    componentes = {**calculo["componentes"], "activos_excluidos_cierre": excluidos}
    ...
```
`calcular(self, id_periodo_contable, filtros)` tiene exactamente 2
parámetros -- NUNCA recibe `excluidos`. Por lo tanto
`self.reportes.movimientos(...)` y `self.costos.del_periodo(...)` traen
TODAS las líneas/costos del período, incluidos los de los activos
"excluidos". El JSON de salida sí lista `activos_excluidos_cierre` (eso
parte de la ficha se cumple: "se listan explícitamente"), pero sus montos
NUNCA se restan de ningún componente -- la ficha exige que "queden fuera
del estado con todos sus componentes", y eso es falso: siguen sumando
exactamente igual que cualquier otro activo. Como consecuencia, "la
ecuación sigue cuadrando" se cumple trivialmente (nunca se excluye nada),
no por un diseño que reste ingresos y gastos de forma simétrica como
advierte la nota de la ficha.

(a) Categoría sin registros -> 0.0000 + indicador, sin error -- CONFIRMADO
    EN LO ESENCIAL, CON UN MATIZ: `estado_resultados()` inicializa
    `comp = {c: CERO for c in INGRESOS + GASTOS}`, así que un componente sin
    movimientos queda en `Decimal('0')` sin lanzar ningún error, y
    `ConstructorEstadoResultados.calcular()` sí expone un indicador real:
    `"sin_actividad": [k for k, v in er.componentes.items() if v == 0]`
    (una lista de los nombres de componentes en cero). PERO el valor
    serializado es `str(Decimal('0'))` = `"0"`, NO `"0.0000"` como pide la
    ficha -- no hay ningún `quantize` a 4 decimales antes de convertir a
    texto.
(b)-(h) Activos excluidos quedan fuera con todos sus componentes -- HALLAZGO
    GRAVE (ver arriba): la exclusión es cosmética, no funcional.

Cómo se prueba: pytest de unidad sobre `ConstructorEstadoResultados`/
`estado_resultados()` con repos mockeados, más inspección de firma
(`inspect.signature`) para confirmar que `calcular()` no recibe `excluidos`.

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

    def test_el_valor_serializado_es_0_no_0_0000_hallazgo_menor(self):
        reportes = MagicMock()
        reportes.movimientos.return_value = []
        costos = MagicMock()
        costos.del_periodo.return_value = []
        constructor = ConstructorEstadoResultados(reportes=reportes, costos=costos)
        resultado = constructor.calcular(id_periodo_contable=93, filtros={})
        pytest.fail(
            f"HALLAZGO MENOR: el valor serializado de un componente sin actividad es "
            f"'{resultado['componentes']['ingresos_productos_agricolas']}' -- la ficha pide "
            f"'0.0000' (4 decimales); el codigo real no aplica quantize antes de str(), asi que "
            f"siempre sale '0'."
        ) if resultado['componentes']['ingresos_productos_agricolas'] == '0' else None


class TestSubCasoBHLosActivosExcluidosNuncaSeExcluyenRealmenteHallazgoGrave:
    def test_calcular_no_tiene_ningun_parametro_de_exclusion(self):
        firma = inspect.signature(ConstructorEstadoResultados.calcular)
        pytest.fail(
            f"HALLAZGO GRAVE CONFIRMADO: ConstructorEstadoResultados.calcular{firma} no tiene "
            f"ningun parametro de exclusion de activos -- la lista de 'activos_excluidos' del "
            f"cierre nunca llega a la consulta real de movimientos/costos."
        ) if 'excluidos' not in firma.parameters and 'excluir' not in firma.parameters else None

    def test_guardar_pasa_excluidos_solo_como_metadato_decorativo_no_como_filtro(self):
        reportes = MagicMock()
        reportes.movimientos.return_value = [
            {'tipo_hecho': 'VARIACION_VR_TB', 'sentido': 'GANANCIA', 'valor': '100.00', 'es_reverso': False},
        ]
        reportes.siguiente_version_estado.return_value = 1
        reportes.agregar_estado.return_value = 1
        costos = MagicMock()
        costos.del_periodo.return_value = []
        constructor = ConstructorEstadoResultados(reportes=reportes, costos=costos)
        resultado = constructor.guardar(id_periodo_contable=93, filtros={}, id_usuario=1, excluidos=[555, 777])
        # reportes.movimientos se llamo SOLO con (id_periodo, filtros) -- sin rastro de excluidos.
        reportes.movimientos.assert_called_once_with(93, {})
        pytest.fail(
            f"HALLAZGO GRAVE CONFIRMADO: pese a pasar excluidos=[555, 777], "
            f"reportes.movimientos() se invoco sin ningun filtro de exclusion -- el monto de "
            f"100.00 del activo supuestamente excluido SIGUE sumando en "
            f"ganancia_transformacion_biologica={resultado['componentes']['ganancia_transformacion_biologica']}. "
            f"'activos_excluidos_cierre' en la salida es solo metadato: {resultado['activos_excluidos_cierre']!r}, "
            f"no afecta ningun componente numerico."
        ) if resultado['componentes']['ganancia_transformacion_biologica'] == '100.00' else None

    def test_generar_obtiene_los_excluidos_reales_del_cierre_pero_el_resultado_final_sigue_sin_filtrarlos(self):
        periodos = MagicMock()
        periodos.obtener.return_value = _periodo()
        periodos.ultima_ejecucion.return_value = {'activos_excluidos': [42]}
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
        assert resultado['activos_excluidos_cierre'] == [42]  # se lista (parte que SI cumple la ficha)
        pytest.fail(
            "HALLAZGO GRAVE: aunque el activo 42 esta en 'activos_excluidos_cierre' (se lista "
            "correctamente), su monto de 250.00 SIGUE sumando en bajas_activos "
            f"(={resultado['componentes']['bajas_activos']}) -- no queda fuera del estado como "
            "exige la ficha."
        ) if resultado['componentes']['bajas_activos'] == '250.00' else None
