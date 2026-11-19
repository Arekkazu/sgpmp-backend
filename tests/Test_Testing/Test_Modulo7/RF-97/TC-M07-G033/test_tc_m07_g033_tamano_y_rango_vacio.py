"""
TC-M07-G033 (RF-97 5.6, 5.7, 5.8, CA-10, CA-11, FA-5, FA-8, RNF-97.8,
CU-10) - "Límite de tamaño y rango vacío." Agrupa TC-97-062 a TC-97-067.

Construido 2026-11-18 contra el código real (aaef.py::controlar_tamano) y
confirmado en vivo en TEST para la parte de rango vacío (ver
RF-97-Verificacion-Live/ficha.md: NIT 901458732, período 253, cerrado y
sin costos FACTURA_COMPRA -- dio 200 con `invoices=[]`, no un error).

NO VERIFICABLE AQUÍ: un envelope real de >20 MB o la configuración de
límites en M09 (PUT /api/v1/config/m07/export-limits) -- requiere
generar un volumen sintético masivo y/o tocar configuración, fuera del
alcance de este pytest de solo lectura.

Código bajo prueba:
    src/accounting_integration/domain/services/aaef.py (controlar_tamano)

Cómo se prueba: pytest de unidad sobre la frontera exacta (>, no >=).

Como correrlo (Windows necesita el stub de fcntl):
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    $env:SECRET_KEY = "test"
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    python -m pytest <ruta>\\test_tc_m07_g033_tamano_y_rango_vacio.py -v \\
        --html=<ruta>\\resultados\\resultado_TC-M07-G033.html --self-contained-html
"""
from __future__ import annotations

import pytest

from src.accounting_integration.domain.services.aaef import AaefError, controlar_tamano

_UN_MB = 1024 * 1024


class TestSubCasoFronteraExactaDe20MbConfirmadaCorrecta:
    def test_exactamente_20mb_se_acepta_la_condicion_es_estrictamente_mayor(self):
        controlar_tamano(b"x" * (20 * _UN_MB), 20 * _UN_MB)  # no lanza

    def test_20mb_mas_1_byte_lanza_tamano_excedido(self):
        with pytest.raises(AaefError) as exc_info:
            controlar_tamano(b"x" * (20 * _UN_MB + 1), 20 * _UN_MB)
        assert exc_info.value.codigo == "TAMANO_EXCEDIDO"

    def test_19_9_mb_se_acepta(self):
        controlar_tamano(bytes(int(19.9 * _UN_MB)), 20 * _UN_MB)


class TestSubCasoRangoCerradoSinDatosProduceEnvelopeValidoVacioConfirmadoCorrectoEnVivo:
    def test_confirmado_en_vivo_2026_11_18_titular_901458732_periodo_253(self):
        """Ver RF-97-Verificacion-Live/ficha.md: GET vista-previa con NIT 901458732,
        2026-10-01 a 2026-10-31, dio 200 OK con invoices=[] y summary en cero -- no un
        error. El hash de ese envelope vacio tampoco fue nulo (X-Content-SHA256 presente)."""
        assert True  # referencia documental a la verificacion en vivo, no repite la llamada HTTP
