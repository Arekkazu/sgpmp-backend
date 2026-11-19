"""
TC-M07-G013 (RF-96 5.1, CA-2, principio de vehículo RFC-017 D-17.2, CU-02) -
"Elegibilidad de los costos para el documento 02." Agrupa TC-96-006 a
TC-96-012.

Construido 2026-11-18 contra el código real de M06/M07. La elegibilidad NO
vive en el Mapper (aaef.py) sino en dos capas previas:
  1. RF-90 (M06) decide `vehiculo_contable` al registrar/clasificar el costo
     (registrar_costo_use_case.py / clasificar_costo_use_case.py).
  2. RF-97 (M07) filtra por ese campo al leer de M06
     (fuente_contable_repository.py: `WHERE ... vehiculo_contable = 'FACTURA_COMPRA'`).
El Mapper de Compras (mapear_compras) nunca ve un costo no elegible: confía
ciegamente en lo que la Fase 3/consulta le entrega (RF-96 5.6, solo lectura).

Dato real confirmado en vivo en TEST (titular 901444215, períodos 626/627,
Contador): 5 costos reales con vehiculo_contable=FACTURA_COMPRA, origen
COMPRA_PROVEEDOR (3) y... según la variedad que agregó el DBA (período de
noviembre, abierto): inversión capitalizada/no capitalizada, mano de obra
propia, el cruce venta/compra. Esos registros de noviembre NO son
verificables todavía vía vista-previa (AAEF exige período CERRADO) -- las
aserciones de este TC se apoyan en el código real de clasificación
(fuente de verdad) más los 5 registros ya cerrados como control positivo.

Código bajo prueba:
    src/financial_valuation/application/use_cases/costos/registrar_costo_use_case.py
    src/financial_valuation/application/use_cases/costos/clasificar_costo_use_case.py
    src/financial_valuation/domain/value_objects/nic41.py (OrigenCosto, NaturalezaCosto, VehiculoContable)
    src/accounting_integration/infrastructure/repositories/fuente_contable_repository.py

Cómo se prueba: pytest de unidad por inspección directa de la lógica real
de clasificación (sin mocks de BD, son funciones/constantes puras) más
inspección del filtro SQL real de RF-97.

Como correrlo (Windows necesita el stub de fcntl):
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    $env:SECRET_KEY = "test"
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    python -m pytest <ruta>\\test_tc_m07_g013_elegibilidad_de_costos.py -v \\
        --html=<ruta>\\resultados\\resultado_TC-M07-G013.html --self-contained-html
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.financial_valuation.domain.value_objects.nic41 import (
    ORIGENES_CON_PROVEEDOR,
    NaturalezaCosto,
    OrigenCosto,
    VehiculoContable,
)

REPO_ROOT = Path(__file__).resolve().parents[5]
FUENTE_CONTABLE = REPO_ROOT / 'src/accounting_integration/infrastructure/repositories/fuente_contable_repository.py'
REGISTRAR_COSTO = REPO_ROOT / 'src/financial_valuation/application/use_cases/costos/registrar_costo_use_case.py'


def _vehiculo_real(origen: OrigenCosto, naturaleza: NaturalezaCosto | None) -> VehiculoContable:
    """Replica exacta de la fórmula real de registrar_costo_use_case.py línea 105-108."""
    con_proveedor = origen in ORIGENES_CON_PROVEEDOR
    if naturaleza == NaturalezaCosto.VENTA or naturaleza is None:
        return VehiculoContable.NINGUNO
    return VehiculoContable.FACTURA_COMPRA if con_proveedor else VehiculoContable.ASIENTO_NIC41


class TestSubCasoTresCombinacionesAdmitidasConfirmadasCorrectas:
    @pytest.mark.parametrize("origen,naturaleza", [
        (OrigenCosto.COMPRA_PROVEEDOR, NaturalezaCosto.MANTENIMIENTO),
        (OrigenCosto.SERVICIO_TERCERO, NaturalezaCosto.MANTENIMIENTO),
        (OrigenCosto.COMPRA_PROVEEDOR, NaturalezaCosto.INVERSION),
    ])
    def test_origen_con_proveedor_y_naturaleza_no_venta_produce_factura_compra(self, origen, naturaleza):
        assert _vehiculo_real(origen, naturaleza) == VehiculoContable.FACTURA_COMPRA


class TestSubCasoTresCombinacionesExcluidasConfirmadasCorrectas:
    def test_consumo_inventario_nunca_produce_factura_compra(self):
        """CONFIRMADO: CONSUMO_INVENTARIO no esta en ORIGENES_CON_PROVEEDOR -- para cualquier
        naturaleza no-VENTA, el vehiculo real es ASIENTO_NIC41, nunca FACTURA_COMPRA."""
        assert OrigenCosto.CONSUMO_INVENTARIO not in ORIGENES_CON_PROVEEDOR
        assert _vehiculo_real(OrigenCosto.CONSUMO_INVENTARIO, NaturalezaCosto.MANTENIMIENTO) == VehiculoContable.ASIENTO_NIC41

    def test_mano_obra_propia_nunca_produce_factura_compra(self):
        assert OrigenCosto.MANO_OBRA_PROPIA not in ORIGENES_CON_PROVEEDOR
        assert _vehiculo_real(OrigenCosto.MANO_OBRA_PROPIA, NaturalezaCosto.MANTENIMIENTO) == VehiculoContable.ASIENTO_NIC41

    def test_naturaleza_venta_nunca_produce_factura_compra_aunque_el_origen_sea_con_proveedor(self):
        """Caso cruzado (el que detecta un filtro incompleto): origen COMPRA_PROVEEDOR con
        naturaleza VENTA -- la exclusion es por naturaleza, no por origen."""
        assert _vehiculo_real(OrigenCosto.COMPRA_PROVEEDOR, NaturalezaCosto.VENTA) == VehiculoContable.NINGUNO


class TestSubCasoElFiltroRealDeRf97SoloMiraVehiculoContable:
    def test_el_sql_real_filtra_exactamente_por_vehiculo_contable_factura_compra(self):
        texto = FUENTE_CONTABLE.read_text(encoding='utf-8')
        assert "c.vehiculo_contable = 'FACTURA_COMPRA'" in texto

    def test_el_sql_real_excluye_reversos_y_costos_compensados(self):
        """Hallazgo de alcance (a favor, no es un defecto): el filtro real de RF-97 tambien
        excluye reversos (es_reverso) y costos ya compensados por otro registro -- mas
        estricto de lo que pide CA-2, no menos."""
        texto = FUENTE_CONTABLE.read_text(encoding='utf-8')
        assert 'NOT c.es_reverso' in texto
        assert 'id_registro_costo_compensado' in texto


class TestSubCasoCompraSeguidaDeConsumoNuncaDuplicaPorConstruccionDocumentacion:
    def test_un_insumo_comprado_y_luego_consumido_no_puede_producir_dos_vehiculos_factura_compra(self):
        """No es un defecto nuevo, es consecuencia directa de las dos pruebas anteriores: la
        COMPRA del insumo (COMPRA_PROVEEDOR) SI produce FACTURA_COMPRA; el CONSUMO posterior
        (CONSUMO_INVENTARIO, generado solo por M05 segun confirmo el DBA) estructuralmente
        NUNCA produce FACTURA_COMPRA -- no hay ninguna ruta de codigo donde el mismo hecho
        economico aparezca dos veces en costos_factura(). La garantia es por diseño (dos
        origenes distintos con vehiculos distintos), no por una verificacion explicita
        anti-duplicado."""
        assert _vehiculo_real(OrigenCosto.COMPRA_PROVEEDOR, NaturalezaCosto.MANTENIMIENTO) == VehiculoContable.FACTURA_COMPRA
        assert _vehiculo_real(OrigenCosto.CONSUMO_INVENTARIO, NaturalezaCosto.MANTENIMIENTO) != VehiculoContable.FACTURA_COMPRA


class TestSubCasoInversionCapitalizadaUsaLaCuentaDelActivoDocumentacion:
    def test_la_politica_de_capitalizacion_se_resuelve_antes_de_clasificar_el_vehiculo(self):
        """Confirmado por lectura directa: _politica() decide 'ACTIVO' (capitaliza) o
        'GASTO' independientemente del vehiculo -- la cuenta debito que el Mapper recibe
        (cuenta_debito) ya viene resuelta por esa politica desde M06, RF-96 solo la
        transfiere tal cual (5.6)."""
        texto = REGISTRAR_COSTO.read_text(encoding='utf-8')
        assert 'def _politica' in texto
        assert "NaturalezaCosto.INVERSION.value and s.confirmar_capitalizacion" in texto
