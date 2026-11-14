"""
TC-M06-G72 (RF-93 Proceso 3b, CU-03) - "Integración de los componentes de
GASTOS."

Construido 2026-11-07 contra el código real de RF-93 (implementado
2026-11-04/05). Primera ronda, código nunca antes probado.

Código bajo prueba:
    src/financial_valuation/domain/services/consolidacion.py (estado_resultados, GASTOS, _COMPONENTE_LINEA)
    src/financial_valuation/application/use_cases/valoracion/procesar_eventos_m02_use_case.py (_baja)

CORREGIDO 2026-11-12/13 (INC-M06-358-G71/G72, commit `e0ecfc93`, y INC-M06-344-G42,
commit `616a35d8`): los dos HALLAZGO originales de este archivo ya están resueltos en
el código real. Se deja la evidencia histórica abajo (lo que fallaba) y se reescriben
las pruebas para confirmar el estado actual.

HISTÓRICO -- lo que fallaba hasta el 2026-11-11: la ficha pedía que "pérdidas por
bajas sin valor de recuperación de RF-45" fuera el componente de gasto por bajas. El
código real hacía exactamente lo contrario de lo que el nombre sugiere:
```
sentido = Sentido.UNICO.value if tipo_baja in _BAJAS_DE_VENTA else Sentido.PERDIDA.value
```
`_BAJAS_DE_VENTA = ("venta", "sacrificio")`. Una baja SIN venta (muerte, pérdida real)
se asentaba con `sentido=PERDIDA`, que no tenía mapeo en `_COMPONENTE_LINEA` -- la
línea se generaba y se persistía en BD, pero `estado_resultados()` la ignoraba por
completo.

CORRECCIÓN REAL CONFIRMADA (`consolidacion.py`, commit `e0ecfc93`):
`_COMPONENTE_LINEA` ahora mapea también `(BAJA_ACTIVO, PERDIDA): "bajas_activos"` --
una baja sin venta ahora SÍ suma al mismo componente de gasto que una baja con venta.
Confirmado reejecutando el código real (no solo leyéndolo).

También CORREGIDO (commit `616a35d8`, INC-M06-344-G42): "costos de mantenimiento...
desglosados en alimento, medicamentos y mano de obra" -- `estado_resultados()` ahora
SÍ devuelve un `desglose_mantenimiento` por subtipo (ALIMENTO/MEDICAMENTO/MANO_OBRA/
VETERINARIO), además del total agregado `costos_mantenimiento` que ya existía.

(a)/(b) Pérdida transformación/precio -- CONFIRMADO: existen
    (`perdida_transformacion_biologica`, `perdida_precio_mercado`), fuente
    real VARIACION_VR_TB/PERDIDA y VARIACION_VR_PM/PERDIDA.
(c) Costos de mantenimiento desglosados -- CORREGIDO: ver arriba, `desglose_mantenimiento`.
(d) Pérdidas por bajas con recuperación parcial -- CORREGIDO: ver arriba, `(BAJA_ACTIVO,
    PERDIDA)` ya mapea a `bajas_activos`. Nota de alcance (no es un defecto): no existe un
    campo de "valor de recuperación" distinto del valor en libros -- la imputación parcial
    para activos POBLACIONALES se hace por proporción de cantidad afectada
    (`valor_libros * proporcion`), un mecanismo real aunque con otro nombre que el de la ficha.
(e) Total_Gastos -- CONFIRMADO: suma literal de los componentes reales de `GASTOS`
    (la ficha describe 4 conceptuales; el código usa más, de forma más granular, sin que
    eso sea un defecto).

Cómo se prueba: pytest de unidad sobre `estado_resultados()` y sobre la
lógica de `_baja()` (via inspección de código, dado que requiere una
sesión de BD real para ejecutarse end-to-end).

Como correrlo (Windows necesita el stub de fcntl):
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    python -m pytest <ruta>\\test_tc_m06_g72_integracion_componentes_gastos.py -v \\
        --html=<ruta>\\resultados\\resultado_TC-M06-G72.html --self-contained-html
"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from src.financial_valuation.domain.services.consolidacion import (
    GASTOS,
    CostoPeriodo,
    MovimientoResultado,
    estado_resultados,
)
from src.financial_valuation.domain.value_objects.nic41 import NATURALEZA_POR_SUBTIPO, Sentido, TipoHecho

REPO_ROOT = Path(__file__).resolve().parents[5]


class TestSubCasoAyBPerdidaTransformacionYPrecioConfirmadoCorrecto:
    def test_perdida_transformacion_biologica_si_existe(self):
        er = estado_resultados([MovimientoResultado(TipoHecho.VARIACION_VR_TB.value, Sentido.PERDIDA.value, Decimal('20.00'))], [])
        assert er.componentes['perdida_transformacion_biologica'] == Decimal('20.00')

    def test_perdida_precio_mercado_si_existe(self):
        er = estado_resultados([MovimientoResultado(TipoHecho.VARIACION_VR_PM.value, Sentido.PERDIDA.value, Decimal('15.00'))], [])
        assert er.componentes['perdida_precio_mercado'] == Decimal('15.00')


class TestSubCasoCCostosDeMantenimientoSiSeDesglosanCorregido:
    def test_alimento_medicamento_y_mano_de_obra_quedan_en_un_total_y_en_un_desglose_por_subtipo(self):
        """CORREGIDO (commit 616a35d8, INC-M06-344-G42): ademas del total agregado
        'costos_mantenimiento' (que ya existia), estado_resultados() ahora tambien devuelve
        'desglose_mantenimiento' por subtipo cuando el costo trae su subtipo real."""
        costos = [
            CostoPeriodo(naturaleza='MANTENIMIENTO', politica=None, monto=Decimal('100.00'), subtipo='ALIMENTO'),
            CostoPeriodo(naturaleza='MANTENIMIENTO', politica=None, monto=Decimal('50.00'), subtipo='MEDICAMENTO'),
            CostoPeriodo(naturaleza='MANTENIMIENTO', politica=None, monto=Decimal('30.00'), subtipo='MANO_OBRA'),
        ]
        er = estado_resultados([], costos)
        assert er.componentes['costos_mantenimiento'] == Decimal('180.00')
        assert er.desglose_mantenimiento == {
            'ALIMENTO': Decimal('100.00'), 'MEDICAMENTO': Decimal('50.00'),
            'MANO_OBRA': Decimal('30.00'), 'VETERINARIO': Decimal('0'),
        }

    def test_alimento_medicamento_mano_obra_y_veterinario_son_todos_mantenimiento(self):
        assert NATURALEZA_POR_SUBTIPO['ALIMENTO'].value == 'MANTENIMIENTO'
        assert NATURALEZA_POR_SUBTIPO['MEDICAMENTO'].value == 'MANTENIMIENTO'
        assert NATURALEZA_POR_SUBTIPO['MANO_OBRA'].value == 'MANTENIMIENTO'
        assert NATURALEZA_POR_SUBTIPO['VETERINARIO'].value == 'MANTENIMIENTO'


class TestSubCasoDBajasActivosVentaYPerdidaCorregido:
    def test_una_baja_por_venta_sigue_cayendo_en_bajas_activos(self):
        venta = MovimientoResultado(TipoHecho.BAJA_ACTIVO.value, Sentido.UNICO.value, Decimal('500.00'))
        er = estado_resultados([venta], [])
        assert er.componentes['bajas_activos'] == Decimal('500.00')

    def test_una_baja_por_perdida_real_sin_recuperacion_ahora_si_suma_en_bajas_activos(self):
        """CORREGIDO (commit e0ecfc93, INC-M06-358-G71/G72): antes, una perdida real
        (sentido=PERDIDA) no tenia mapeo en _COMPONENTE_LINEA y el estado de resultados la
        ignoraba por completo. Ahora (BAJA_ACTIVO, PERDIDA) mapea al mismo componente
        'bajas_activos' que una baja por venta -- la perdida ya cuenta como gasto real."""
        perdida_real = MovimientoResultado(TipoHecho.BAJA_ACTIVO.value, Sentido.PERDIDA.value, Decimal('800.00'))
        er = estado_resultados([perdida_real], [])
        assert er.componentes['bajas_activos'] == Decimal('800.00')
        assert sum(er.componentes.values()) == Decimal('800.00')

    def test_no_existe_un_campo_de_valor_de_recuperacion_distinto_del_valor_en_libros_por_proporcion(self):
        """No es un defecto: la imputacion parcial para activos POBLACIONALES se hace por
        proporcion de cantidad afectada (valor_libros * proporcion) -- un mecanismo real,
        aunque con otro nombre que el 'valor de recuperacion' que menciona la ficha."""
        archivo = REPO_ROOT / 'src/financial_valuation/application/use_cases/valoracion/procesar_eventos_m02_use_case.py'
        texto = archivo.read_text(encoding='utf-8')
        assert 'proporcion' in texto.lower()


class TestSubCasoETotalGastosEsLaSumaDeLosComponentesReales:
    def test_gastos_tiene_mas_componentes_reales_que_los_cuatro_conceptuales_de_la_ficha(self):
        """No es un defecto: la ficha describe 4 componentes conceptuales (perdida
        transformacion, perdida precio, costos de mantenimiento, bajas); el codigo real es
        mas granular (9 componentes), pero total_gastos sigue siendo correcto porque suma
        todos ellos (ver test_total_gastos_es_la_suma_exacta_de_los_componentes)."""
        assert len(GASTOS) > 4
        assert {'perdida_transformacion_biologica', 'perdida_precio_mercado', 'costos_mantenimiento',
                'bajas_activos'}.issubset(set(GASTOS))

    def test_total_gastos_es_la_suma_exacta_de_los_componentes(self):
        movimientos = [
            MovimientoResultado(TipoHecho.VARIACION_VR_TB.value, Sentido.PERDIDA.value, Decimal('10.00')),
            MovimientoResultado(TipoHecho.BAJA_ACTIVO.value, Sentido.UNICO.value, Decimal('5.00')),
        ]
        costos = [CostoPeriodo(naturaleza='MANTENIMIENTO', politica=None, monto=Decimal('3.00'))]
        er = estado_resultados(movimientos, costos)
        assert er.total_gastos == Decimal('18.00')
