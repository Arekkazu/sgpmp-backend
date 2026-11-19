"""
TC-M07-G012 (RF-96 Fase 1, CA-3, FA-5, CU-01) - "Selección de Mappers según
la versión de contrato." Agrupa TC-96-001 a TC-96-005.

Construido 2026-11-18 contra el código real de RF-96/RF-98
(src/accounting_integration/). La selección de Mappers vive en
ConsultarAaefUseCase.execute() (RF-97), no en los Mappers mismos -- son
funciones puras que no conocen la versión del contrato.

Dato de entorno (confirmado en vivo en TEST 2026-11-17): el contrato
ACTIVO real es v2.1, con mapeadores=['COMPRAS'] -- cumple exactamente la
restricción de v3.0 (solo Compras). No existe ningún contrato v3.1 activo
(el sistema limita a 2 versiones vigentes y ya está al tope con otras
versiones de QA), así que la selección con ambos Mappers y el bloqueo
MAPPER_NO_DISPONIBLE se verifican aquí por unidad (mocks), no contra una
llamada HTTP viva -- es exactamente lo que pide la ficha ('Herramienta QA
sugerida': pytest + parametrize / pytest + fixtures, no Postman).

Código bajo prueba:
    src/accounting_integration/application/use_cases/exportacion/consultar_aaef_use_case.py (selección)
    src/accounting_integration/domain/entities/contrato.py (resolver_version)
    src/accounting_integration/application/use_cases/contratos/gestionar_contratos_use_case.py (MAPPER_NO_DISPONIBLE)

Cómo se prueba: pytest de unidad con repositorios simulados (MagicMock) --
no requiere BD viva. No se necesita ningún contrato v3.0/v3.1 real en TEST
para este TC: la lógica de selección es pura y se activa por el contenido
de VersionContrato.mapeadores, no por el número de versión en sí.

Como correrlo (Windows necesita el stub de fcntl):
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    $env:SECRET_KEY = "test"
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    python -m pytest <ruta>\\test_tc_m07_g012_seleccion_de_mappers.py -v \\
        --html=<ruta>\\resultados\\resultado_TC-M07-G012.html --self-contained-html
"""
from __future__ import annotations

import datetime
from unittest.mock import MagicMock

import pytest

from src.accounting_integration.application.use_cases.contratos.gestionar_contratos_use_case import (
    GestionarContratosUseCase,
    SolicitudContrato,
)
from src.accounting_integration.application.use_cases.exportacion.consultar_aaef_use_case import (
    ConsultarAaefUseCase,
    SolicitudAaef,
)
from src.accounting_integration.domain.entities.contrato import VersionContrato, resolver_version
from src.accounting_integration.domain.services.aaef import (
    MAPPER_COMPRAS,
    MAPPER_COMPROBANTE_NIC41,
    CostoFactura,
    Periodo,
    SistemaOrigen,
    Titular,
)
from src.shared.errors import BusinessRuleError, NotFoundError

SISTEMA = SistemaOrigen(system_id="SGPMP", system_name="SIGAB", environment="TEST")


def _contrato(mapeadores: list[str], estado: str = "ACTIVO", version: str = "3.0") -> VersionContrato:
    return VersionContrato(1, version, "MINOR", datetime.date(2026, 1, 1), 1, mapeadores, estado=estado)


def _caso_de_uso(mapeadores: list[str]):
    fuente = MagicMock()
    fuente.titular.return_value = Titular("900123456", "Titular de prueba")
    fuente.fincas_titular.return_value = set()
    fuente.fincas_usuario.return_value = set()
    fuente.periodos.return_value = [Periodo(datetime.date(2026, 10, 1), datetime.date(2026, 10, 31), "CERRADO")]
    fuente.lineas_sin_trazabilidad.return_value = 0
    fuente.costos_factura.return_value = [CostoFactura(
        1, "900777571", "Proveedor S.A.S.", "CP", "1187", datetime.date(2026, 10, 8), None,
        "ALIMENTO", __import__("decimal").Decimal("380000"), "158405", "activo1",
    )]
    fuente.comprobantes.return_value = []
    contratos = MagicMock()
    contratos.listar_contratos.return_value = [_contrato(mapeadores)]
    uc = ConsultarAaefUseCase(fuente=fuente, contratos=contratos, sistema=SISTEMA, limite_bytes=20 * 1024 * 1024,
                              hoy=lambda: datetime.date(2026, 11, 18))
    return uc


class TestSubCasoV30SoloInvocaComprasConfirmadoCorrecto:
    def test_con_solo_compras_en_mapeadores_nunca_se_invoca_comprobantes(self):
        """CONFIRMADO CORRECTO: equivalente real en TEST es el contrato activo v2.1
        (mapeadores=['COMPRAS']). Aunque fuente.comprobantes() devolviera datos, el use
        case jamas los mapea porque MAPPER_COMPROBANTE_NIC41 no esta en mapeadores."""
        uc = _caso_de_uso([MAPPER_COMPRAS])
        uc.fuente.comprobantes.return_value = [MagicMock()]  # si se invocara, fallaria el Mapper real
        resultado = uc.execute(SolicitudAaef("900123456", datetime.date(2026, 10, 1), datetime.date(2026, 10, 31),
                                             1, "contador@pecuaria.co"))
        assert resultado.documentos == 1  # solo el 02, el comprobante synthetic nunca se tocó
        uc.fuente.comprobantes.assert_not_called() if hasattr(uc.fuente.comprobantes, 'assert_not_called') else None


class TestSubCasoV31InvocaAmbosMappers:
    def test_con_ambos_mapeadores_si_se_invoca_comprobantes(self):
        """Con mapeadores=['COMPRAS','COMPROBANTE_NIC41'] (equivalente de v3.1), el use
        case SI invoca mapear_comprobantes() -- confirmado llamando fuente.comprobantes()."""
        uc = _caso_de_uso([MAPPER_COMPRAS, MAPPER_COMPROBANTE_NIC41])
        uc.execute(SolicitudAaef("900123456", datetime.date(2026, 10, 1), datetime.date(2026, 10, 31),
                                 1, "contador@pecuaria.co"))
        uc.fuente.comprobantes.assert_called_once()


class TestSubCasoMapperNoDisponibleEsUnGuardianDeRegistroNoDeExportacion:
    def test_registrar_un_contrato_con_comprobante_nic41_sin_habilitar_lanza_mapper_no_disponible(self):
        """CONFIRMADO: MAPPER_NO_DISPONIBLE SI existe en el código real, pero se activa al
        REGISTRAR (RF-98) un contrato con ese mapeador mientras el feature flag
        M07_COMPROBANTE_NIC41_HABILITADO esta apagado (default en TEST) -- no al 'pedir' el
        Mapper 06 durante una exportación con v3.0, que es como lo enmarca la ficha. No
        existe ningún parámetro en la exportación para 'pedir' un Mapper especifico: los
        mapeadores vienen fijos por la versión de contrato ya resuelta."""
        uc = GestionarContratosUseCase(contratos=MagicMock(), auditoria=MagicMock(), db=MagicMock(),
                                       es_produccion=lambda: False, alertar=MagicMock(),
                                       comprobante_habilitado=False)
        solicitud = SolicitudContrato("3.1", "MAJOR", datetime.date(2026, 12, 1), 1,
                                      [MAPPER_COMPRAS, MAPPER_COMPROBANTE_NIC41], 90, "v3.1 de prueba")
        with pytest.raises(BusinessRuleError) as exc_info:
            uc.registrar(solicitud, id_usuario=1)
        assert exc_info.value.code == "MAPPER_NO_DISPONIBLE"

    def test_con_el_flag_habilitado_si_se_puede_registrar(self):
        """Control: con comprobante_habilitado=True el mismo registro no choca con
        MAPPER_NO_DISPONIBLE (puede fallar despues por otra razon -- anexo, etc. -- pero no
        por esta guarda)."""
        contratos = MagicMock()
        contratos.obtener_anexo.return_value = None  # fuerza el siguiente error, ya pasado el guardian
        uc = GestionarContratosUseCase(contratos=contratos, auditoria=MagicMock(), db=MagicMock(),
                                       es_produccion=lambda: False, alertar=MagicMock(),
                                       comprobante_habilitado=True)
        solicitud = SolicitudContrato("3.1", "MAJOR", datetime.date(2026, 12, 1), 1,
                                      [MAPPER_COMPRAS, MAPPER_COMPROBANTE_NIC41], 90, "v3.1 de prueba")
        with pytest.raises(BusinessRuleError) as exc_info:
            uc.registrar(solicitud, id_usuario=1)
        assert exc_info.value.code == "ANEXO_MAPEO_INVALIDO"  # no MAPPER_NO_DISPONIBLE


class TestSubCasoVersionNulaONoSoportadaSeRechaza:
    def test_sin_version_solicitada_toma_la_activa_de_mayor_numero(self):
        contratos = [_contrato([MAPPER_COMPRAS], estado="ACTIVO", version="2.1"),
                    _contrato([MAPPER_COMPRAS], estado="DEPRECADO", version="2.0")]
        resuelto = resolver_version(contratos, None)
        assert resuelto.contrato_version == "2.1"

    @pytest.mark.parametrize("version_pedida", ["2.0", "3.2"])
    def test_version_no_registrada_se_rechaza_sin_invocar_ningun_mapper(self, version_pedida):
        contratos = [_contrato([MAPPER_COMPRAS], estado="ACTIVO", version="2.1")]
        with pytest.raises(NotFoundError) as exc_info:
            resolver_version(contratos, version_pedida)
        assert exc_info.value.code == "VERSION_NO_REGISTRADA"


class TestSubCasoLosComprobantesDeUnPeriodoConV30NoSePierdenDocumentacion:
    def test_comprobantes_no_mapeados_no_se_marcan_ni_se_descartan_en_bd(self):
        """No es un defecto: fuente.comprobantes() es de solo lectura (RF-96 5.6); al no
        invocarse con v3.0, los comprobantes simplemente no entran al envelope de ESTA
        consulta -- no hay ningun UPDATE que los marque como 'perdidos' o 'exportados', por
        lo que una consulta futura con v3.1 SI los incluiria sin cambios previos."""
        archivo = __import__('pathlib').Path(__file__).resolve().parents[5] / (
            'src/accounting_integration/infrastructure/repositories/fuente_contable_repository.py')
        texto = archivo.read_text(encoding='utf-8')
        assert 'UPDATE' not in texto.upper()
