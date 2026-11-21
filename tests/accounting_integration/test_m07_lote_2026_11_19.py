# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-19 | Arekkazu | TC-M07-G016/G019, INC-M07-G37/G38/G043: mapper, gracia de M09, aviso manual y nombre único |
"""Lote M07 del 2026-11-19, sin base de datos."""
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from src.accounting_integration.application.use_cases.clientes.registrar_cliente_externo_use_case import (
    RegistrarClienteExternoUseCase,
    SolicitudCliente,
)
from src.accounting_integration.application.use_cases.contratos.gestionar_contratos_use_case import (
    GestionarContratosUseCase,
    SolicitudContrato,
)
from src.accounting_integration.domain.entities.contrato import AnexoMapeo, VersionContrato
from src.accounting_integration.domain.services.aaef import (
    AaefError,
    ComprobanteNic41,
    CostoFactura,
    Titular,
    mapear_comprobantes,
    mapear_compras,
)
from src.shared.errors import AppError

TITULAR = Titular("900000001", "Titular SAS")


def _comprobante(valor, tipo="VARIACION_VR_TB"):
    return ComprobanteNic41(f"NIC-900000001-202610-{tipo}-1", tipo, "Bovino", date(2026, 10, 31),
                            [{"cuenta_debito": "15120501", "cuenta_credito": "42950501", "valor": valor}])


def _costo(subtipo="ALIMENTO"):
    return CostoFactura(1, "800000001", "Proveedor SAS", "FE", "1", date(2026, 10, 5), None, subtipo,
                        Decimal("100"), "51350501", "BOV-1")


def test_neto_negativo_invierte_las_cuentas_y_el_cero_se_rechaza():
    linea = mapear_comprobantes([_comprobante("-50000")], TITULAR)[0]["Lines"][0]
    assert linea["Value"] == Decimal("50000") and linea["accounting_account"] == ["42950501", "15120501"]
    with pytest.raises(AaefError) as cero:
        mapear_comprobantes([_comprobante("0")], TITULAR)
    assert cero.value.codigo == "MAPPER_FALLIDO"


def test_linetype_se_valida_contra_la_matriz_contable():
    assert mapear_compras([_costo()], frozenset({"ALIMENTO"}))
    assert mapear_compras([_costo()], frozenset({None}))  # fila de la matriz para todos los subtipos
    with pytest.raises(AaefError) as compra:
        mapear_compras([_costo()], frozenset({"MEDICAMENTO"}))
    assert compra.value.codigo == "LINETYPE_NO_CATALOGADO" and "ALIMENTO" not in compra.value.mensaje
    with pytest.raises(AaefError) as hecho:
        mapear_comprobantes([_comprobante("10")], TITULAR, frozenset({"BAJA_ACTIVO"}))
    assert hecho.value.codigo == "LINETYPE_NO_CATALOGADO"


def _contratos(*versiones, anexo_estado="APROBADO"):
    repo = MagicMock()
    repo.listar_contratos.return_value = list(versiones)
    repo.obtener_anexo.return_value = AnexoMapeo(1, "AAEF-3.0", "3.0", "doc", "a" * 64, estado=anexo_estado)
    repo.guardar_contrato.side_effect = lambda c: c
    return repo


def _caso(repo, alertar=None, gracia=(10, 20)):
    return GestionarContratosUseCase(repo, MagicMock(), MagicMock(), lambda: True, alertar or MagicMock(),
                                     gracia=lambda: gracia)


def test_gracia_minima_y_por_defecto_vienen_de_m09():
    caso = _caso(_contratos())
    solicitud = SolicitudContrato("4.0", "MAJOR", date(2026, 12, 1), 1, ["COMPRAS"])
    assert caso.registrar(solicitud, 1).periodo_gracia_dias == 20
    assert caso.registrar(SolicitudContrato("5.0", "MAJOR", date(2026, 12, 1), 1, ["COMPRAS"], 15), 1).periodo_gracia_dias == 15
    with pytest.raises(AppError) as corta:
        caso.registrar(SolicitudContrato("6.0", "MAJOR", date(2026, 12, 1), 1, ["COMPRAS"], 9), 1)
    assert corta.value.code == "PERIODO_GRACIA_INVALIDO" and "10 días" in corta.value.message
    activa = VersionContrato(7, "3.0", "MAJOR", date(2026, 1, 1), 1, ["COMPRAS"], estado="ACTIVO")
    assert _caso(_contratos(activa)).deprecar(7, None, 1).fecha_inactivacion.date() >= date.today()


def test_activacion_manual_bloqueada_avisa_al_administrador():
    alertar = MagicMock()
    pendiente = VersionContrato(9, "3.9", "MINOR", date(2026, 1, 1), 1, ["COMPRAS"])
    with pytest.raises(AppError) as e:
        _caso(_contratos(pendiente, anexo_estado="BORRADOR"), alertar).activar(9, id_usuario=5)
    assert e.value.code == "CONTRATO_NO_VALIDO" and pendiente.estado == "PENDIENTE"
    alertar.assert_called_once()
    assert "3.9" in alertar.call_args.args[0] and "anexo" in alertar.call_args.args[0]


def test_nombre_de_cliente_repetido_responde_409_en_nombre():
    clientes = MagicMock()
    clientes.obtener_por_identificador.return_value = None
    clientes.obtener_por_nombre.return_value = object()
    with pytest.raises(AppError) as e:
        RegistrarClienteExternoUseCase(clientes, MagicMock(), MagicMock()).execute(
            SolicitudCliente("NUEVO", " AgroFusion ", "nuevo-id", date(2099, 1, 1)), 1)
    assert e.value.status_code == 409 and e.value.field == "nombre"
    clientes.guardar.assert_not_called()
