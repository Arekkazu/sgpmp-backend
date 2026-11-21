"""
TC-M07-G030 (RF-97 5.3, 5.4, CA-5, CA-6, CA-13, FA-6, CU-07) - "Fuentes
según la versión de contrato." Agrupa TC-97-041 a TC-97-047.

La mayor parte de este TCG ya se confirmó EN VIVO en TEST (ver
RF-97-Verificacion-Live/ficha.md y la carpeta "TC-M07-G030" de la
colección Postman): con el contrato real v2.1 (equivalente de v3.0,
solo Compras) nunca aparece un `06` aunque el período SÍ tiene un
comprobante NIC 41 real; nunca aparece Type.Code 01/03/04/05; invoices
quedan ordenados por DocumentId; y un NIT inexistente da 404 antes de
siquiera llegar a resolver el contrato.

Este archivo cubre lo que la verificación en vivo no pudo ejercitar:
FA-6 (`CONTRATO_NO_ACTIVO`), que solo se dispara si NO hay ningún
contrato en estado ACTIVO -- imposible de provocar en TEST sin desactivar
el contrato real (acción de escritura fuera de alcance de esta sesión).

Código bajo prueba:
    src/accounting_integration/domain/entities/contrato.py (resolver_version)

Como correrlo (Windows necesita el stub de fcntl):
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    $env:SECRET_KEY = "test"
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    python -m pytest <ruta>\\test_tc_m07_g030_fuentes_segun_version_contrato.py -v \\
        --html=<ruta>\\resultados\\resultado_TC-M07-G030.html --self-contained-html
"""
from __future__ import annotations

import pytest

from src.accounting_integration.domain.entities.contrato import resolver_version
from src.shared.errors import BusinessRuleError


class TestSubCasoSinContratoActivoLanzaContratoNoActivoConfirmadoCorrecto:
    def test_lista_de_contratos_vacia_lanza_contrato_no_activo(self):
        with pytest.raises(BusinessRuleError) as exc_info:
            resolver_version([], None)
        assert exc_info.value.code == "CONTRATO_NO_ACTIVO"

    def test_contratos_todos_deprecados_o_pendientes_tambien_lanza_contrato_no_activo(self):
        import datetime
        from src.accounting_integration.domain.entities.contrato import VersionContrato
        contratos = [
            VersionContrato(1, "2.0", "MINOR", datetime.date(2024, 1, 1), 1, ["COMPRAS"], estado="DEPRECADO"),
            VersionContrato(2, "3.0", "MAJOR", datetime.date(2027, 1, 1), 1, ["COMPRAS"], estado="PENDIENTE"),
        ]
        with pytest.raises(BusinessRuleError) as exc_info:
            resolver_version(contratos, None)
        assert exc_info.value.code == "CONTRATO_NO_ACTIVO"
