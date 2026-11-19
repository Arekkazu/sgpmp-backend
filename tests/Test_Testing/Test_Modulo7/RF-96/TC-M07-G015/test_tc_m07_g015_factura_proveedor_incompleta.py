"""
TC-M07-G015 (RF-96 FA-1, 5.3, CU-03) - "Factura de proveedor incompleta."
Agrupa TC-96-021 a TC-96-025.

Construido 2026-11-18 contra el código real (mapear_compras(), aaef.py).

HALLAZGO (código de error no literal): el código real NO lanza
'FACTURA_PROVEEDOR_INCOMPLETA' -- lanza `AaefError('MAPPER_FALLIDO', ...,
campo='Header')` para cualquiera de las 4 validaciones que sí existen.
El código de error específico de la ficha no aparece en ningún archivo de
`src/accounting_integration/`. RF-102 sí recibe el campo afectado
('Header'), solo que bajo un código distinto. Mismo patrón ya visto en
M06 (ej. G93/G94): el mecanismo funcional existe, el nombre del código no
coincide con la ficha.

HALLAZGO (el prefijo NO es obligatorio, es deliberado): de los 5 campos
que la ficha exige, el código real solo valida 4 (NIT tercero, razón
social tercero, número de factura, fecha de factura) -- el prefijo NO
se valida. Esto es intencional y está documentado en el propio módulo:
"Prefix = '' si la factura no tiene prefijo: AgroFusión acepta el texto
vacío y SIGCON usa solo el número; exigirlo tumbaría el envelope completo
por un costo." No es un hallazgo nuevo de omisión, es una decisión de
diseño ya razonada en el código.

Código bajo prueba:
    src/accounting_integration/domain/services/aaef.py (mapear_compras)

Cómo se prueba: pytest de unidad invocando mapear_compras() con costos
donde falta cada campo, uno a la vez.

Como correrlo (Windows necesita el stub de fcntl):
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    $env:SECRET_KEY = "test"
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    python -m pytest <ruta>\\test_tc_m07_g015_factura_proveedor_incompleta.py -v \\
        --html=<ruta>\\resultados\\resultado_TC-M07-G015.html --self-contained-html
"""
from __future__ import annotations

import datetime
from decimal import Decimal

import pytest

from src.accounting_integration.domain.services.aaef import AaefError, CostoFactura, mapear_compras

D = Decimal


def _costo(**kw) -> CostoFactura:
    base = dict(id_registro_costo=1, tercero_nit="900777571", tercero_razon_social="Concentrados La Pradera S.A.S.",
                factura_prefijo="CP", factura_numero="1187", fecha_factura=datetime.date(2026, 10, 8),
                fecha_vencimiento_factura=datetime.date(2026, 11, 7), subtipo_costo="ALIMENTO",
                monto_costo=D("380000"), cuenta_debito="158405", activo="QA-M07-BUF-F2")
    base.update(kw)
    return CostoFactura(**base)


class TestSubCasoCuatroCamposObligatoriosSiProvocanMapperFallido:
    @pytest.mark.parametrize("campo_faltante,valor", [
        ("tercero_nit", None), ("tercero_nit", ""),
        ("tercero_razon_social", None), ("tercero_razon_social", ""),
        ("factura_numero", None), ("factura_numero", ""),
    ])
    def test_falta_nit_razon_social_o_numero_lanza_mapper_fallido(self, campo_faltante, valor):
        """No es FACTURA_PROVEEDOR_INCOMPLETA (ver docstring del módulo): el código real
        usa MAPPER_FALLIDO con campo='Header' -- el mecanismo de bloqueo SI existe."""
        costo = _costo(**{campo_faltante: valor})
        with pytest.raises(AaefError) as exc_info:
            mapear_compras([costo])
        assert exc_info.value.codigo == "MAPPER_FALLIDO"
        assert exc_info.value.campo == "Header"

    def test_falta_fecha_de_factura_lanza_mapper_fallido(self):
        costo = _costo(fecha_factura=None)
        with pytest.raises(AaefError) as exc_info:
            mapear_compras([costo])
        assert exc_info.value.codigo == "MAPPER_FALLIDO"


class TestSubCasoElPrefijoNoEsObligatorioPorDisenoDocumentacion:
    def test_falta_el_prefijo_no_lanza_ningun_error(self):
        """No es un defecto: Prefix vacío es aceptado deliberadamente (ver docstring de
        aaef.py) -- AgroFusión acepta el texto vacío y SIGCON usa solo el número."""
        costo = _costo(factura_prefijo=None)
        documentos = mapear_compras([costo])
        assert documentos[0]["Header"]["Prefix"] == ""

    def test_falta_el_prefijo_junto_con_otro_campo_si_bloquea_por_el_otro_campo(self):
        """Confirma que el prefijo nunca es la causa del bloqueo, incluso combinado con un
        campo que si es obligatorio."""
        costo = _costo(factura_prefijo=None, factura_numero=None)
        with pytest.raises(AaefError) as exc_info:
            mapear_compras([costo])
        assert exc_info.value.codigo == "MAPPER_FALLIDO"


class TestSubCasoSinSalidaParcialAnteElPrimerError:
    def test_un_costo_incompleto_entre_otros_validos_bloquea_todo_el_lote(self):
        """FA-1/Fase 5: ningún costo se entrega si uno falla -- mapear_compras() itera y
        lanza en el primer problema, sin devolver los documentos ya construidos."""
        valido = _costo(id_registro_costo=1)
        incompleto = _costo(id_registro_costo=2, factura_numero=None)
        with pytest.raises(AaefError):
            mapear_compras([valido, incompleto])
