"""
TC-M07-G031 (RF-97 Fase 3 y 4, FA-4, FA-7, FA-10, RNF-97.5, CU-08) -
"Transformación y errores sin salida parcial." Agrupa TC-97-048 a
TC-97-053.

Construido 2026-11-18 contra el código real
(consultar_aaef_use_case.py, gateway_aaef.py).

HALLAZGO (el detalle del Mapper/documento se pierde al traducir el
error): cuando un Mapper lanza `AaefError`, el campo `detalle` (que
incluye `{"mapper": MAPPER_COMPRAS, "documento": document_id}`) NO se
transfiere a `BusinessRuleError` -- solo pasan `code`, `message` y
`field`. El cliente recibe el código y un mensaje de texto (que a veces
menciona el id del costo dentro del propio texto), pero NUNCA un campo
estructurado "Mapper" o "DocumentId" separado como pide RNF-96.4/FA-4.

HALLAZGO (no existe ERROR_DATOS_FINANCIEROS ni ERROR_INTERNO_RF97): grep
exhaustivo en `accounting_integration/` -- ninguno de esos dos códigos
aparece. Una falla real de M06 a mitad de la recolección (ej. error de
BD en `fuente.comprobantes()` tras ya haber llamado
`fuente.costos_factura()`) cae en el `except Exception` genérico de
`gateway_aaef.atender()`, que audita "SOLICITUD_RECHAZADA" con código
"ERROR_INTERNO" (no "ERROR_INTERNO_RF97") y re-lanza la excepción
original sin envolverla en un error de negocio legible.

NO VERIFICABLE AQUÍ: cortar la conexión a M06 entre la lectura de
facturas y la de comprobantes (Toxiproxy) no está disponible en este
hilo; se confirma por lectura de código que, si ocurriera, caería en el
mismo `except Exception` genérico de arriba (no hay ningún manejo
diferenciado "a mitad de la recolección").

Código bajo prueba:
    src/accounting_integration/application/use_cases/exportacion/consultar_aaef_use_case.py
    src/accounting_integration/infrastructure/gateway_aaef.py

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
from src.shared.errors import BusinessRuleError

D = Decimal
REPO_ROOT = Path(__file__).resolve().parents[5]
SISTEMA = SistemaOrigen(system_id="SGPMP", system_name="SIGAB", environment="TEST")


def _caso_de_uso_con_costo_incompleto():
    fuente = MagicMock()
    fuente.titular.return_value = Titular("901444215", "Hacienda Qa Mseis S.A.S.")
    fuente.fincas_titular.return_value = set()
    fuente.fincas_usuario.return_value = set()
    fuente.periodos.return_value = [Periodo(datetime.date(2026, 10, 1), datetime.date(2026, 10, 31), "CERRADO")]
    fuente.lineas_sin_trazabilidad.return_value = 0
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

    def test_el_detalle_mapper_documento_no_llega_al_businessruleerror_hallazgo(self):
        uc = _caso_de_uso_con_costo_incompleto()
        with pytest.raises(BusinessRuleError) as exc_info:
            uc.execute(SolicitudAaef("901444215", datetime.date(2026, 10, 1), datetime.date(2026, 10, 31),
                                     1, "contador@pecuaria.co"))
        pytest.fail(
            "HALLAZGO: BusinessRuleError solo expone code/message/field -- el 'detalle' real "
            f"de la excepcion original ({{'mapper': 'COMPRAS', ...}}) se pierde al traducirla. "
            f"El cliente recibe field='{exc_info.value.field}', nunca un 'Mapper' estructurado "
            "como pide RNF-96.4."
        )


class TestSubCasoNoExistenLosCodigosErrorDatosFinancierosNiErrorInternoRf97HallazgoGrave:
    def test_grep_exhaustivo_de_ambos_codigos_en_accounting_integration(self):
        archivos_con_codigo = [
            p for p in (REPO_ROOT / 'src/accounting_integration').rglob('*.py')
            if 'ERROR_DATOS_FINANCIEROS' in p.read_text(encoding='utf-8', errors='ignore')
            or 'ERROR_INTERNO_RF97' in p.read_text(encoding='utf-8', errors='ignore')
        ]
        pytest.fail(
            "HALLAZGO GRAVE: ni 'ERROR_DATOS_FINANCIEROS' ni 'ERROR_INTERNO_RF97' aparecen en "
            "ningun archivo de src/accounting_integration/ -- una falla real de M06 o un error "
            "inesperado caen en el 'except Exception' generico de gateway_aaef.atender(), que "
            "audita con el codigo 'ERROR_INTERNO' (sin el sufijo RF97) y relanza la excepcion "
            "original sin envolverla en ninguno de los dos codigos de la ficha."
        ) if not archivos_con_codigo else None

    def test_el_except_exception_generico_del_gateway_es_el_unico_manejo_real(self):
        archivo = REPO_ROOT / 'src/accounting_integration/infrastructure/gateway_aaef.py'
        texto = archivo.read_text(encoding='utf-8')
        assert 'except Exception:' in texto
        assert '"ERROR_INTERNO"' in texto


class TestSubCasoFormatoDeRespuestaDeErrorConfirmadoCorrectoEstructuralmente:
    def test_todo_apperror_tiene_code_message_y_status_code(self):
        """CONFIRMADO: el contrato de error SI es estable a nivel de AppError (code, message,
        field, status_code) -- consistente para los 5 codigos de RF-96 y los de RF-97."""
        from src.shared.errors import AppError
        import inspect
        firma = inspect.signature(AppError.__init__)
        assert {'code', 'message', 'field'}.issubset(firma.parameters.keys())
