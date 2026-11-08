"""
TC-M06-G02 (RF-93 Proceso 3b, CU-03) - "Integración de los componentes de
GASTOS."

Construido 2026-11-07 contra el código real de RF-93 (implementado
2026-11-04/05). Primera ronda, código nunca antes probado.

Código bajo prueba:
    src/financial_valuation/domain/services/consolidacion.py (estado_resultados, GASTOS, _COMPONENTE_LINEA)
    src/financial_valuation/application/use_cases/valoracion/procesar_eventos_m02_use_case.py (_baja)

HALLAZGO PRINCIPAL (grave, relacionado con G01): la ficha pide que
"pérdidas por bajas sin valor de recuperación de RF-45" sea el componente de
gasto por bajas, "con imputación correcta de las recuperaciones parciales".
El código real hace exactamente lo contrario de lo que el nombre sugiere:
```
sentido = Sentido.UNICO.value if tipo_baja in _BAJAS_DE_VENTA else Sentido.PERDIDA.value
```
`_BAJAS_DE_VENTA = ("venta", "sacrificio")`. Es decir:
- Una baja por VENTA/SACRIFICIO (que SÍ tiene valor de recuperación: el
  dinero de la venta) se asienta con `sentido=UNICO`, que SÍ está mapeado a
  `bajas_activos` (GASTOS) en `_COMPONENTE_LINEA`.
- Una baja SIN venta (muerte, pérdida real, sin ningún valor de
  recuperación -- justo lo que la ficha describe) se asienta con
  `sentido=PERDIDA`, que NO TIENE NINGÚN MAPEO en `_COMPONENTE_LINEA` --
  la línea se genera y se persiste en BD, pero `estado_resultados()` la
  ignora por completo (`nombre = _COMPONENTE_LINEA.get(...); if nombre is
  not None: ...`): una pérdida real por baja sin recuperación NO APARECE EN
  NINGÚN LADO del estado de resultados.
No existe ningún concepto de "recuperación parcial" distinto del valor en
libros: `valor = truncar2(valor_libros * proporcion)`, donde `proporcion`
es la fracción de cantidad afectada (para activos POBLACIONALES), no un
valor de rescate/recuperación.

HALLAZGO SECUNDARIO: "costos de mantenimiento... desglosados en alimento,
medicamentos y mano de obra" -- el estado de resultados real NO desglosa:
`estado_resultados()` suma TODO costo con `naturaleza == 'MANTENIMIENTO'`
(alimento, medicamento, mano de obra Y servicio veterinario, ver
`NATURALEZA_POR_SUBTIPO` en `value_objects/nic41.py`) en un único número,
`costos_mantenimiento`. El desglose por `subtipo_costo` existe en los
registros de costo individuales (`GET /finanzas/costos?subtipo_costo=...`),
pero NO en el estado de resultados.

(a)/(b) Pérdida transformación/precio -- CONFIRMADO: existen
    (`perdida_transformacion_biologica`, `perdida_precio_mercado`), fuente
    real VARIACION_VR_TB/PERDIDA y VARIACION_VR_PM/PERDIDA.
(c) Costos de mantenimiento desglosados -- HALLAZGO: un único total, sin
    desglose por subtipo (ver arriba).
(d) Pérdidas por bajas con recuperación parcial -- HALLAZGO GRAVE (ver
    arriba): el componente real (`bajas_activos`) es alimentado por VENTAS,
    no por pérdidas; las pérdidas reales (sentido PERDIDA) se pierden sin
    aparecer en ningún componente.
(e) Total_Gastos -- CONFIRMADO: suma literal de los 9 componentes reales de
    `GASTOS` (la ficha solo describe 4 conceptuales).

Cómo se prueba: pytest de unidad sobre `estado_resultados()` y sobre la
lógica de `_baja()` (via inspección de código, dado que requiere una
sesión de BD real para ejecutarse end-to-end).

Como correrlo (Windows necesita el stub de fcntl):
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    python -m pytest <ruta>\\test_tc_m06_g02_integracion_componentes_gastos.py -v \\
        --html=<ruta>\\resultados\\resultado_TC-M06-G02.html --self-contained-html
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


class TestSubCasoCCostosDeMantenimientoNoSeDesglosanHallazgo:
    def test_alimento_medicamento_y_mano_de_obra_caen_en_un_unico_total(self):
        costos = [
            CostoPeriodo(naturaleza='MANTENIMIENTO', politica=None, monto=Decimal('100.00')),  # alimento
            CostoPeriodo(naturaleza='MANTENIMIENTO', politica=None, monto=Decimal('50.00')),   # medicamento
            CostoPeriodo(naturaleza='MANTENIMIENTO', politica=None, monto=Decimal('30.00')),   # mano de obra
        ]
        er = estado_resultados([], costos)
        pytest.fail(
            f"HALLAZGO (c): los 3 subtipos (alimento, medicamento, mano de obra) se suman en un "
            f"UNICO componente 'costos_mantenimiento'={er.componentes['costos_mantenimiento']} -- "
            f"el estado de resultados no desglosa por subtipo, al contrario de lo que pide la ficha."
        ) if er.componentes['costos_mantenimiento'] == Decimal('180.00') else None

    def test_alimento_medicamento_mano_obra_y_veterinario_son_todos_mantenimiento(self):
        assert NATURALEZA_POR_SUBTIPO['ALIMENTO'].value == 'MANTENIMIENTO'
        assert NATURALEZA_POR_SUBTIPO['MEDICAMENTO'].value == 'MANTENIMIENTO'
        assert NATURALEZA_POR_SUBTIPO['MANO_OBRA'].value == 'MANTENIMIENTO'
        assert NATURALEZA_POR_SUBTIPO['VETERINARIO'].value == 'MANTENIMIENTO'


class TestSubCasoDBajasActivosEsVentasNoPerdidasHallazgoGrave:
    def test_una_baja_por_venta_sigue_cayendo_en_bajas_activos(self):
        venta = MovimientoResultado(TipoHecho.BAJA_ACTIVO.value, Sentido.UNICO.value, Decimal('500.00'))
        er = estado_resultados([venta], [])
        assert er.componentes['bajas_activos'] == Decimal('500.00')

    def test_una_baja_por_perdida_real_sin_recuperacion_no_aparece_en_ningun_componente(self):
        """HALLAZGO GRAVE: una perdida real (sentido=PERDIDA, exactamente lo que la ficha
        describe como 'bajas sin valor de recuperacion') NO tiene mapeo en
        _COMPONENTE_LINEA -- la linea existe en BD pero el estado de resultados la ignora
        por completo. No reduce bajas_activos, no reduce ningun otro componente, no
        aparece en ningun lado."""
        perdida_real = MovimientoResultado(TipoHecho.BAJA_ACTIVO.value, Sentido.PERDIDA.value, Decimal('800.00'))
        er = estado_resultados([perdida_real], [])
        total_en_todos_los_componentes = sum(er.componentes.values())
        pytest.fail(
            "HALLAZGO GRAVE CONFIRMADO: una baja con sentido=PERDIDA (perdida real sin "
            "recuperacion, el caso que la ficha pide probar) no contribuye a NINGUN componente "
            "del estado de resultados -- la suma de todos los componentes sigue en 0 pese a "
            "haber una perdida de 800.00 registrada. 'bajas_activos' solo recoge VENTAS "
            "(sentido=UNICO), no perdidas."
        ) if total_en_todos_los_componentes == 0 else None

    def test_no_existe_ningun_concepto_de_recuperacion_parcial_distinto_del_valor_en_libros(self):
        archivo = REPO_ROOT / 'src/financial_valuation/application/use_cases/valoracion/procesar_eventos_m02_use_case.py'
        texto = archivo.read_text(encoding='utf-8')
        pytest.fail(
            "HALLAZGO: no existe ningun campo o calculo de 'valor de recuperacion' distinto del "
            "valor en libros * proporcion -- _baja() solo calcula 'valor = truncar2(valor_libros * "
            "proporcion)', sin ningun concepto de recuperacion parcial que la ficha exige probar."
        ) if 'recuperacion' not in texto.lower() and 'recupera' not in texto.lower() else None


class TestSubCasoETotalGastosEsLaSumaDeLosComponentesReales:
    def test_gastos_tiene_nueve_componentes_reales_no_cuatro(self):
        pytest.fail(
            f"HALLAZGO: GASTOS tiene {len(GASTOS)} componentes reales {GASTOS!r} -- la ficha "
            f"solo describe 4 conceptuales (perdida transformacion, perdida precio, costos de "
            f"mantenimiento, bajas)."
        ) if len(GASTOS) != 4 else None

    def test_total_gastos_es_la_suma_exacta_de_los_componentes(self):
        movimientos = [
            MovimientoResultado(TipoHecho.VARIACION_VR_TB.value, Sentido.PERDIDA.value, Decimal('10.00')),
            MovimientoResultado(TipoHecho.BAJA_ACTIVO.value, Sentido.UNICO.value, Decimal('5.00')),
        ]
        costos = [CostoPeriodo(naturaleza='MANTENIMIENTO', politica=None, monto=Decimal('3.00'))]
        er = estado_resultados(movimientos, costos)
        assert er.total_gastos == Decimal('18.00')
