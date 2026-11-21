"""
TC-M07-G028 (RF-97 Fase 2, FA-3, Precondiciones, CU-05) - "Validación de
trazabilidad con RF-91." Agrupa TC-97-030 a TC-97-034.

Construido 2026-11-18, actualizado 2026-11-20 tras el merge de
origin/dev (PR #1202, TC-M07-379 por LuisfNarvaez01). El código real de
TRAZABILIDAD_INCOMPLETA SÍ usa ese código literal.

ARREGLADO (2026-11-20, TC-M07-379): el hallazgo de este TC ("el detalle
no identifica los hechos afectados") ya se corrigió. `lineas_sin_trazabilidad()`
ahora devuelve una lista de dicts (`tipo_hecho`, `activo`, `fecha_hecho`,
`id_activo_biologico`), y `_trazabilidad_incompleta()` nombra los primeros
5 hechos en el mensaje y los trae TODOS en `detalle.hechos` -- justo la
solución que habíamos propuesto.

Dato real confirmado en vivo en TEST (NIT 901444215, período 627,
2026-11-17/18): el costo COS-4486 (VP-342, servicio veterinario,
SERVICIO_TERCERO) SÍ se exportó sin bloqueo -- el período completo
respondió 200 con sus 3 documentos, confirmando en código real que un
costo sin línea de asiento propia no bloquea la trazabilidad del rango.

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


def _hecho(tipo_hecho: str = "VARIACION_VR_TB", activo: str = "F2",
          fecha_hecho: datetime.date = datetime.date(2026, 10, 15)) -> dict:
    return {"id_linea_asiento_nic41": 1, "tipo_hecho": tipo_hecho, "id_activo_biologico": 1,
            "activo": activo, "fecha_hecho": fecha_hecho}


def _caso_de_uso(hechos_sin_traza: list[dict]):
    fuente = MagicMock()
    fuente.titular.return_value = Titular("901444215", "Hacienda Qa Mseis S.A.S.")
    fuente.fincas_titular.return_value = set()
    fuente.fincas_usuario.return_value = set()
    fuente.periodos.return_value = [Periodo(datetime.date(2026, 10, 1), datetime.date(2026, 10, 31), "CERRADO")]
    fuente.lineas_sin_trazabilidad.return_value = hechos_sin_traza
    fuente.linetypes_catalogados.return_value = (frozenset({"VETERINARIO"}), frozenset())
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
    def test_sin_hechos_pendientes_no_lanza_ninguna_excepcion(self):
        uc = _caso_de_uso(hechos_sin_traza=[])
        resultado = uc.execute(SolicitudAaef("901444215", datetime.date(2026, 10, 1), datetime.date(2026, 10, 31),
                                             1, "contador@pecuaria.co"))
        assert resultado.documentos == 1


class TestSubCasoUnoSinTrazabilidadBloqueaConfirmadoCorrecto:
    def test_un_asiento_sin_trazabilidad_lanza_trazabilidad_incompleta(self):
        """CONFIRMADO: a diferencia de la mayoria de codigos de RF-96/RF-97,
        'TRAZABILIDAD_INCOMPLETA' SI es el codigo literal real."""
        uc = _caso_de_uso(hechos_sin_traza=[_hecho()])
        with pytest.raises(BusinessRuleError) as exc_info:
            uc.execute(SolicitudAaef("901444215", datetime.date(2026, 10, 1), datetime.date(2026, 10, 31),
                                     1, "contador@pecuaria.co"))
        assert exc_info.value.code == "TRAZABILIDAD_INCOMPLETA"

    def test_el_mensaje_ahora_si_identifica_los_hechos_afectados_arreglado(self):
        """ARREGLADO (2026-11-20, TC-M07-379): el mensaje ya nombra el hecho, el activo y la
        fecha, y el detalle estructurado trae todos los hechos -- ya no es solo un conteo."""
        hechos = [_hecho(activo="F2", fecha_hecho=datetime.date(2026, 10, 15)),
                 _hecho(activo="F3", fecha_hecho=datetime.date(2026, 10, 20)),
                 _hecho(activo="F1", fecha_hecho=datetime.date(2026, 10, 22))]
        uc = _caso_de_uso(hechos_sin_traza=hechos)
        with pytest.raises(BusinessRuleError) as exc_info:
            uc.execute(SolicitudAaef("901444215", datetime.date(2026, 10, 1), datetime.date(2026, 10, 31),
                                     1, "contador@pecuaria.co"))
        assert "3 asientos" in exc_info.value.message
        assert "F2" in exc_info.value.message and "2026-10-15" in exc_info.value.message
        assert exc_info.value.detalle is not None
        assert len(exc_info.value.detalle["hechos"]) == 3
        assert {h["activo"] for h in exc_info.value.detalle["hechos"]} == {"F2", "F3", "F1"}

    def test_el_mensaje_trunca_a_5_hechos_nombrados_y_cuenta_el_resto(self):
        hechos = [_hecho(activo=f"F{i}") for i in range(7)]
        uc = _caso_de_uso(hechos_sin_traza=hechos)
        with pytest.raises(BusinessRuleError) as exc_info:
            uc.execute(SolicitudAaef("901444215", datetime.date(2026, 10, 1), datetime.date(2026, 10, 31),
                                     1, "contador@pecuaria.co"))
        assert "y 2 más" in exc_info.value.message
        assert len(exc_info.value.detalle["hechos"]) == 7  # el detalle SI trae los 7, aunque el mensaje solo nombre 5


class TestSubCasoServicioTerceroSinLineaDeAsientoNoBloqueaConfirmadoCorrectoConDatosReales:
    def test_un_costo_servicio_tercero_sin_linea_propia_no_impide_la_exportacion(self):
        """Confirmado en vivo en TEST (2026-11-17/18): el periodo 627 de NIT 901444215
        incluye COS-4486 (VP-342, SERVICIO_TERCERO, servicio veterinario) y exporto sus 3
        documentos sin ningun error de trazabilidad -- la Fase 2 no exige una linea de
        asiento propia por cada costo de compra, solo por los hechos de RF-86."""
        uc = _caso_de_uso(hechos_sin_traza=[])  # el costo de servicio_tercero no cuenta aqui
        resultado = uc.execute(SolicitudAaef("901444215", datetime.date(2026, 10, 1), datetime.date(2026, 10, 31),
                                             1, "contador@pecuaria.co"))
        assert resultado.documentos == 1  # el 02 del servicio veterinario SI se genero
