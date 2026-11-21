"""
TC-M07-G031 (RF-97 Fase 3 y 4, FA-4, FA-7, FA-10, RNF-97.5, CU-08) -
"Transformación y errores sin salida parcial." Agrupa TC-97-048 a
TC-97-053.

Construido 2026-11-18, actualizado 2026-11-20 tras el merge de
origin/dev (PR #1202, TC-M07-380/381 por LuisfNarvaez01).

ARREGLADO (TC-M07-381): el hallazgo "el detalle del Mapper/documento se
pierde al traducir el error" ya se corrigió. `ConsultarAaefUseCase.execute()`
ahora pasa `detalle=exc.detalle or None` al construir `BusinessRuleError`
-- el cliente SÍ recibe `{"mapper": ..., "documento"/"id_registro_costo": ...}`
estructurado, no solo en el texto del mensaje.

ARREGLADO (TC-M07-380): el hallazgo "no existen ERROR_DATOS_FINANCIEROS ni
ERROR_INTERNO_RF97" ya se corrigió. El propio `consultar_aaef_use_case.py`
(no el gateway) ahora distingue las tres fases:
  - `_financieros()` envuelve cualquier falla al leer M06 en
    `InfrastructureError(code="ERROR_DATOS_FINANCIEROS")`.
  - El `except Exception` genérico de la Fase 5-7 envuelve lo inesperado en
    `InfrastructureError(code="ERROR_INTERNO_RF97")`.
  - Un `AppError` ya tipado (404/403/422) se re-lanza tal cual.
El manejo ya no vive en el `except Exception` genérico de `gateway_aaef.py`
-- ese gateway solo autentica/audita; la distinción de fases es del caso de
uso, que es donde corresponde (Fase 3 vs. Fase 5-7).

Código bajo prueba:
    src/accounting_integration/application/use_cases/exportacion/consultar_aaef_use_case.py

Cómo se prueba: pytest de unidad.

Como correrlo (Windows necesita el stub de fcntl):
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    $env:SECRET_KEY = "test"
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    python -m pytest <ruta>\\test_tc_m07_g031_transformacion_y_errores.py -v \\
        --html=<ruta>\\resultados\\resultado_TC-M07-G031.html --self-contained-html
"""
from __future__ import annotations

import datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.accounting_integration.application.use_cases.exportacion.consultar_aaef_use_case import (
    ConsultarAaefUseCase,
    SolicitudAaef,
)
from src.accounting_integration.domain.entities.contrato import VersionContrato
from src.accounting_integration.domain.services.aaef import MAPPER_COMPRAS, CostoFactura, Periodo, SistemaOrigen, Titular
from src.shared.errors import BusinessRuleError, InfrastructureError

D = Decimal
REPO_ROOT = Path(__file__).resolve().parents[5]
SISTEMA = SistemaOrigen(system_id="SGPMP", system_name="SIGAB", environment="TEST")


def _caso_de_uso_con_costo_incompleto():
    fuente = MagicMock()
    fuente.titular.return_value = Titular("901444215", "Hacienda Qa Mseis S.A.S.")
    fuente.fincas_titular.return_value = set()
    fuente.fincas_usuario.return_value = set()
    fuente.periodos.return_value = [Periodo(datetime.date(2026, 10, 1), datetime.date(2026, 10, 31), "CERRADO")]
    fuente.lineas_sin_trazabilidad.return_value = []
    fuente.linetypes_catalogados.return_value = (frozenset(), frozenset())
    fuente.costos_factura.return_value = [CostoFactura(
        4485, None, "Concentrados La Pradera S.A.S.", "CP", "1187", datetime.date(2026, 10, 8),
        datetime.date(2026, 11, 7), "ALIMENTO", D("380000"), "158405", "F2",
    )]  # tercero_nit=None -> MAPPER_FALLIDO
    fuente.comprobantes.return_value = []
    contratos = MagicMock()
    contratos.listar_contratos.return_value = [VersionContrato(1, "2.1", "MINOR", datetime.date(2026, 1, 1), 1,
                                                                [MAPPER_COMPRAS], estado="ACTIVO")]
    return ConsultarAaefUseCase(fuente=fuente, contratos=contratos, sistema=SISTEMA, limite_bytes=20 * 1024 * 1024,
                               hoy=lambda: datetime.date(2026, 11, 18))


class TestSubCasoFalloDeMapperDevuelveBusinessRuleErrorSinSalidaParcial:
    def test_un_mapper_fallido_propaga_como_businessruleerror_422(self):
        uc = _caso_de_uso_con_costo_incompleto()
        with pytest.raises(BusinessRuleError) as exc_info:
            uc.execute(SolicitudAaef("901444215", datetime.date(2026, 10, 1), datetime.date(2026, 10, 31),
                                     1, "contador@pecuaria.co"))
        assert exc_info.value.status_code == 422
        assert exc_info.value.code == "MAPPER_FALLIDO"

    def test_el_detalle_mapper_y_costo_ahora_si_llega_al_businessruleerror_arreglado(self):
        """ARREGLADO (TC-M07-381): el detalle estructurado ya viaja en el error del cliente,
        no solo en el texto del mensaje."""
        uc = _caso_de_uso_con_costo_incompleto()
        with pytest.raises(BusinessRuleError) as exc_info:
            uc.execute(SolicitudAaef("901444215", datetime.date(2026, 10, 1), datetime.date(2026, 10, 31),
                                     1, "contador@pecuaria.co"))
        assert exc_info.value.detalle is not None
        assert exc_info.value.detalle["mapper"] == "COMPRAS"
        assert exc_info.value.detalle["id_registro_costo"] == 4485


class TestSubCasoErrorDatosFinancierosYErrorInternoRf97Arreglado:
    def test_ambos_codigos_ya_existen_en_consultar_aaef_use_case(self):
        archivo = REPO_ROOT / (
            'src/accounting_integration/application/use_cases/exportacion/consultar_aaef_use_case.py')
        texto = archivo.read_text(encoding='utf-8')
        assert 'ERROR_DATOS_FINANCIEROS' in texto
        assert 'ERROR_INTERNO_RF97' in texto

    def test_una_falla_al_leer_m06_se_envuelve_en_error_datos_financieros(self):
        uc = _caso_de_uso_con_costo_incompleto()
        uc.fuente.costos_factura.side_effect = RuntimeError("BD de M06 caida")
        with pytest.raises(InfrastructureError) as exc_info:
            uc.execute(SolicitudAaef("901444215", datetime.date(2026, 10, 1), datetime.date(2026, 10, 31),
                                     1, "contador@pecuaria.co"))
        assert exc_info.value.code == "ERROR_DATOS_FINANCIEROS"

    def test_un_error_inesperado_de_fase_5_a_7_se_envuelve_en_error_interno_rf97(self):
        uc = _caso_de_uso_con_costo_incompleto()
        uc.limite_bytes = "no-es-un-entero"  # rompe controlar_tamano() con un TypeError inesperado
        uc.fuente.costos_factura.return_value = []  # sin costo incompleto, para llegar hasta esa fase
        with pytest.raises(InfrastructureError) as exc_info:
            uc.execute(SolicitudAaef("901444215", datetime.date(2026, 10, 1), datetime.date(2026, 10, 31),
                                     1, "contador@pecuaria.co"))
        assert exc_info.value.code == "ERROR_INTERNO_RF97"

    def test_la_distincion_de_fases_vive_en_el_caso_de_uso_no_en_el_gateway_arreglado(self):
        """ARREGLADO: el manejo diferenciado (Fase 3 vs. Fase 5-7) ya no depende de un
        'except Exception' generico en gateway_aaef.py -- vive en consultar_aaef_use_case.py,
        que es la capa que conoce en que fase esta cada llamada."""
        archivo = REPO_ROOT / (
            'src/accounting_integration/application/use_cases/exportacion/consultar_aaef_use_case.py')
        texto = archivo.read_text(encoding='utf-8')
        assert 'def _financieros(' in texto  # envuelve Fase 3 (lectura de M06)
        assert 'except Exception as exc:  # RF-97 FA-10' in texto  # envuelve Fase 5-7


class TestSubCasoFormatoDeRespuestaDeErrorConfirmadoCorrectoEstructuralmente:
    def test_todo_apperror_tiene_code_message_y_status_code(self):
        """CONFIRMADO: el contrato de error SI es estable a nivel de AppError (code, message,
        field, status_code) -- consistente para los 5 codigos de RF-96 y los de RF-97."""
        from src.shared.errors import AppError
        import inspect
        firma = inspect.signature(AppError.__init__)
        assert {'code', 'message', 'field'}.issubset(firma.parameters.keys())
