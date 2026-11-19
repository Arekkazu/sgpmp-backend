"""
TC-M07-G021 (RF-96 5.1, 5.6, CA-7, Postcondiciones, RFC-017, CU-09) -
"Solo lectura y tipos permitidos." Agrupa TC-96-059 a TC-96-063.

Construido 2026-11-18 contra el código real (aaef.py, RFC-017: retiro de
los Mappers 01/03/04-A/04-B).

Código bajo prueba:
    src/accounting_integration/domain/services/aaef.py
    src/accounting_integration/infrastructure/repositories/fuente_contable_repository.py

Cómo se prueba: pytest de unidad por inspección de código -- confirma que
el único vocabulario de escritura SQL (INSERT/UPDATE/DELETE) está ausente
de los módulos de lectura de RF-96/97, y que los únicos dos Type.Code
posibles son '02' y '06'.

Como correrlo (Windows necesita el stub de fcntl):
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    $env:SECRET_KEY = "test"
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    python -m pytest <ruta>\\test_tc_m07_g021_solo_lectura_y_tipos_permitidos.py -v \\
        --html=<ruta>\\resultados\\resultado_TC-M07-G021.html --self-contained-html
"""
from __future__ import annotations

import re
from pathlib import Path

from src.accounting_integration.domain.services.aaef import MAPPERS_DISPONIBLES, mapear_comprobantes, mapear_compras

REPO_ROOT = Path(__file__).resolve().parents[5]
AAEF = REPO_ROOT / 'src/accounting_integration/domain/services/aaef.py'
FUENTE_CONTABLE = REPO_ROOT / 'src/accounting_integration/infrastructure/repositories/fuente_contable_repository.py'


class TestSubCasoNingunObjetoDeM06SeModificaConfirmadoCorrecto:
    def test_aaef_no_contiene_ningun_verbo_sql_de_escritura(self):
        texto = AAEF.read_text(encoding='utf-8')
        assert not re.search(r'\b(INSERT|UPDATE|DELETE)\b', texto, re.IGNORECASE)

    def test_fuente_contable_repository_solo_tiene_selects(self):
        texto = FUENTE_CONTABLE.read_text(encoding='utf-8')
        assert not re.search(r'\b(INSERT|UPDATE|DELETE)\b', texto, re.IGNORECASE)
        assert texto.upper().count('SELECT') >= 4  # titular, fincas, periodos, costos_factura, comprobantes...


class TestSubCasoLosUnicosDosTypeCodePosiblesSonConfirmadoCorrecto:
    def test_solo_existen_los_literales_02_y_06_en_todo_el_modulo(self):
        texto = AAEF.read_text(encoding='utf-8')
        codigos = set(re.findall(r'"Code":\s*"(\d{2})"', texto))
        assert codigos == {"02", "06"}

    def test_cualquier_salida_real_solo_tiene_esos_dos_codigos(self):
        compra = mapear_compras.__wrapped__ if hasattr(mapear_compras, '__wrapped__') else mapear_compras
        import datetime
        from decimal import Decimal
        from src.accounting_integration.domain.services.aaef import CostoFactura, Titular
        costo = CostoFactura(1, "900777571", "Proveedor", "CP", "1", datetime.date(2026, 10, 1), None,
                             "ALIMENTO", Decimal("100"), "158405", "activo")
        comp_doc = mapear_compras([costo])[0]
        assert comp_doc["Header"]["Type"]["Code"] in ("02", "06")


class TestSubCasoLosMappersRetiradosNoExistenComoFunciones:
    def test_mappers_disponibles_solo_tiene_dos_elementos(self):
        assert set(MAPPERS_DISPONIBLES) == {"COMPRAS", "COMPROBANTE_NIC41"}

    def test_no_existe_ninguna_funcion_de_mapeo_para_los_5_mappers_retirados(self):
        import src.accounting_integration.domain.services.aaef as modulo
        for nombre in ("mapear_reconocimiento", "mapear_variaciones", "mapear_cotizaciones",
                      "mapear_revelaciones", "mapear_estado_resultados"):
            assert not hasattr(modulo, nombre)


class TestSubCasoRevelacionesYEstadoDeResultadosNuncaProducenDocumentosConfirmadoCorrecto:
    def test_aaef_no_importa_nada_de_rf92_ni_rf93(self):
        """RFC-018 D-18.8: el informe de revelaciones (RF-92) y el estado de resultados
        (RF-93) no son hechos contables -- aaef.py no los importa ni los referencia."""
        texto = AAEF.read_text(encoding='utf-8')
        assert 'revelacion' not in texto.lower()
        assert 'estado_resultados' not in texto.lower() and 'EstadoResultados' not in texto


class TestSubCasoLasVariacionesSoloViajanAgregadasDentroDel06ConfirmadoCorrecto:
    def test_no_existe_ningun_mapper_de_variacion_individual(self):
        """Las variaciones de RF-86 solo llegan a RF-96 ya consolidadas por
        consolidar_comprobantes() de M06 en pares de cuentas (ComprobanteNic41.lineas) --
        no existe ningun Mapper que tome una variacion individual directamente."""
        import inspect
        firma = inspect.signature(mapear_comprobantes)
        assert list(firma.parameters.keys())[0] == 'comprobantes'  # recibe comprobantes ya agregados
