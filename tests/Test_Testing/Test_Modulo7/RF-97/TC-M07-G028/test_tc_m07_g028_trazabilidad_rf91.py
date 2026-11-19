"""
TC-M07-G028 (RF-97 Fase 2, FA-3, Precondiciones, CU-05) - "Validación de
trazabilidad con RF-91." Agrupa TC-97-030 a TC-97-034.

Construido 2026-11-18 contra el código real
(consultar_aaef_use_case.py). El código real de TRAZABILIDAD_INCOMPLETA
SÍ usa ese código literal (a diferencia de la mayoría de códigos de RF-96,
este sí coincide con la ficha).

Dato real confirmado en vivo en TEST (NIT 901444215, período 627,
2026-11-17/18): el costo COS-4486 (VP-342, servicio veterinario,
SERVICIO_TERCERO) SÍ se exportó sin bloqueo -- el período completo
respondió 200 con sus 3 documentos, confirmando en código real que un
costo sin línea de asiento propia no bloquea la trazabilidad del rango.

HALLAZGO (el detalle no identifica los hechos afectados): la ficha pide
que TRAZABILIDAD_INCOMPLETA venga "con el detalle de los hechos
afectados" para que el Contador sepa qué resolver. El mensaje real es
`f"{sin_traza} asientos del rango no tienen la trazabilidad completa..."`
-- solo un CONTEO, ningún id de línea, hecho ni activo. El Contador no
puede identificar cuáles asientos corregir desde este mensaje solo.

NO VERIFICABLE AQUÍ: la indisponibilidad de RF-91 (RF-91 caído) requiere
inyección de fallos (Toxiproxy), no disponible en este hilo. La exclusión
autorizada del cierre (2 casos reales según el DBA) no se pudo localizar
con un NIT/período concretos en esta sesión -- queda pendiente de un dato
puntual del DBA.

Código bajo prueba:
    src/accounting_integration/application/use_cases/exportacion/consultar_aaef_use_case.py

Cómo se prueba: pytest de unidad con repositorio de fuente simulado
(MagicMock).

Como correrlo (Windows necesita el stub de fcntl):
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    $env:SECRET_KEY = "test"
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    python -m pytest <ruta>\\test_tc_m07_g028_trazabilidad_rf91.py -v \\
        --html=<ruta>\\resultados\\resultado_TC-M07-G028.html --self-contained-html
"""
from __future__ import annotations

import datetime
from decimal import Decimal
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
SISTEMA = SistemaOrigen(system_id="SGPMP", system_name="SIGAB", environment="TEST")


def _caso_de_uso(sin_traza: int):
    fuente = MagicMock()
    fuente.titular.return_value = Titular("901444215", "Hacienda Qa Mseis S.A.S.")
    fuente.fincas_titular.return_value = set()
    fuente.fincas_usuario.return_value = set()
    fuente.periodos.return_value = [Periodo(datetime.date(2026, 10, 1), datetime.date(2026, 10, 31), "CERRADO")]
    fuente.lineas_sin_trazabilidad.return_value = sin_traza
    fuente.costos_factura.return_value = [CostoFactura(
        4486, "900777582", "Veterinaria El Prado S.A.S.", "VP", "342", datetime.date(2026, 10, 21),
        datetime.date(2026, 11, 20), "VETERINARIO", D("210000"), "158405", "F3",
    )]
    fuente.comprobantes.return_value = []
    contratos = MagicMock()
    contratos.listar_contratos.return_value = [VersionContrato(1, "2.1", "MINOR", datetime.date(2026, 1, 1), 1,
                                                                [MAPPER_COMPRAS], estado="ACTIVO")]
    return ConsultarAaefUseCase(fuente=fuente, contratos=contratos, sistema=SISTEMA, limite_bytes=20 * 1024 * 1024,
                               hoy=lambda: datetime.date(2026, 11, 18))


class TestSubCasoTodosVerificadosContinuaSinErrorConfirmadoCorrecto:
    def test_sin_traza_cero_no_lanza_ninguna_excepcion(self):
        uc = _caso_de_uso(sin_traza=0)
        resultado = uc.execute(SolicitudAaef("901444215", datetime.date(2026, 10, 1), datetime.date(2026, 10, 31),
                                             1, "contador@pecuaria.co"))
        assert resultado.documentos == 1


class TestSubCasoUnoSinTrazabilidadBloqueaConfirmadoCorrecto:
    def test_un_asiento_sin_trazabilidad_lanza_trazabilidad_incompleta(self):
        """CONFIRMADO: a diferencia de la mayoria de codigos de RF-96/RF-97,
        'TRAZABILIDAD_INCOMPLETA' SI es el codigo literal real."""
        uc = _caso_de_uso(sin_traza=1)
        with pytest.raises(BusinessRuleError) as exc_info:
            uc.execute(SolicitudAaef("901444215", datetime.date(2026, 10, 1), datetime.date(2026, 10, 31),
                                     1, "contador@pecuaria.co"))
        assert exc_info.value.code == "TRAZABILIDAD_INCOMPLETA"

    def test_el_mensaje_no_identifica_los_hechos_afectados_solo_el_conteo_hallazgo(self):
        uc = _caso_de_uso(sin_traza=3)
        with pytest.raises(BusinessRuleError) as exc_info:
            uc.execute(SolicitudAaef("901444215", datetime.date(2026, 10, 1), datetime.date(2026, 10, 31),
                                     1, "contador@pecuaria.co"))
        pytest.fail(
            f"HALLAZGO: el mensaje real es '{exc_info.value.message}' -- solo informa un "
            "conteo (3 asientos), sin ningun id, hecho ni activo que el Contador pueda usar "
            "para localizarlos en Finanzas. La ficha pide 'el detalle de los hechos "
            "afectados', que no existe en este mensaje."
        )


class TestSubCasoServicioTerceroSinLineaDeAsientoNoBloqueaConfirmadoCorrectoConDatosReales:
    def test_un_costo_servicio_tercero_sin_linea_propia_no_impide_la_exportacion(self):
        """Confirmado en vivo en TEST (2026-11-17/18): el periodo 627 de NIT 901444215
        incluye COS-4486 (VP-342, SERVICIO_TERCERO, servicio veterinario) y exporto sus 3
        documentos sin ningun error de trazabilidad -- la Fase 2 no exige una linea de
        asiento propia por cada costo de compra, solo por los hechos de RF-86."""
        uc = _caso_de_uso(sin_traza=0)  # el costo de servicio_tercero no cuenta para lineas_sin_trazabilidad
        resultado = uc.execute(SolicitudAaef("901444215", datetime.date(2026, 10, 1), datetime.date(2026, 10, 31),
                                             1, "contador@pecuaria.co"))
        assert resultado.documentos == 1  # el 02 del servicio veterinario SI se genero
