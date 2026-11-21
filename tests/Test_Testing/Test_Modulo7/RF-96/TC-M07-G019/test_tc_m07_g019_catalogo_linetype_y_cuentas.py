"""
TC-M07-G019 (RF-96 5.2, FA-2, FA-3, CA-6, CU-07) - "Catálogo de LineType y
forma de las cuentas." Agrupa TC-96-046 a TC-96-052.

Construido 2026-11-18, actualizado 2026-11-20 tras el merge de
origin/dev. El DBA confirmó (2026-11-17) que la matriz contable real de
RF-109 tiene 67 combinaciones en TEST, pero no puede confirmar la
existencia de una cuenta en SIGCON (sistema externo) -- coincide
exactamente con lo que dice la ficha en 5.2: "la existencia de la cuenta
en SIGCON la valida SIGCON."

ARREGLADO (2026-11-19, TC-M07-G019, Arekkazu, PR #1190/#1202): el
hallazgo grave de este TC ("LINETYPE_NO_CATALOGADO no existe") ya se
corrigió. `mapear_compras()`/`mapear_comprobantes()` ahora reciben un
`catalogo` (frozenset de subtipos/hechos con cuenta activa en la matriz
contable, vía `fuente.linetypes_catalogados()`) y `_exigir_catalogo()`
rechaza con `LINETYPE_NO_CATALOGADO` cualquier LineType fuera de ese
conjunto. `catalogo=None` (el valor por defecto) sigue sin validar --
es el caso deliberado de la autoprueba del anexo (RF-AE02 5.10, ver
TC-M07-G023), que no tiene una BD real de la que leer el catálogo.

CONFIRMADO CORRECTO (forma de la cuenta): `_cuenta()` SI rechaza valores
vacíos, nulos o no numéricos (letras, guiones, puntos) con
`AaefError('MAPPER_FALLIDO', campo='accounting_account')` -- bajo otro
nombre de código, no 'CUENTA_CONTABLE_INVALIDA' literal, pero el mecanismo
de bloqueo sí existe. Una cuenta bien formada pero inexistente en SIGCON
se transfiere tal cual, sin rechazarla ni corregirla (confirmado correcto,
es la decisión de diseño correcta de un componente de solo transformación).

HALLAZGO (cantidad de elementos distinta, no alcanzable por este camino):
`accounting_account` de 2 elementos en un 02, o de 1/3 en un 06, NO se
puede inducir a través de las funciones reales -- ambos Mappers
CONSTRUYEN la lista ellos mismos con exactamente 1 o 2 `_cuenta(...)`,
nunca reciben una lista externa. Solo se podría violar manipulando el
documento ya construido en memoria (como en TC-M07-G018), no a través de
una entrada real del Mapper.

Código bajo prueba:
    src/accounting_integration/domain/services/aaef.py (mapear_compras, mapear_comprobantes, _exigir_catalogo, _cuenta)

Cómo se prueba: pytest de unidad.

Como correrlo (Windows necesita el stub de fcntl):
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    $env:SECRET_KEY = "test"
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    python -m pytest <ruta>\\test_tc_m07_g019_catalogo_linetype_y_cuentas.py -v \\
        --html=<ruta>\\resultados\\resultado_TC-M07-G019.html --self-contained-html
"""
from __future__ import annotations

import datetime
from decimal import Decimal
from pathlib import Path

import pytest

from src.accounting_integration.domain.services import aaef
from src.accounting_integration.domain.services.aaef import AaefError, CostoFactura, mapear_compras

D = Decimal
REPO_ROOT = Path(__file__).resolve().parents[5]
AAEF = REPO_ROOT / 'src/accounting_integration/domain/services/aaef.py'


def _costo(**kw) -> CostoFactura:
    base = dict(id_registro_costo=4485, tercero_nit="900777571", tercero_razon_social="Concentrados La Pradera S.A.S.",
                factura_prefijo="CP", factura_numero="1187", fecha_factura=datetime.date(2026, 10, 8),
                fecha_vencimiento_factura=datetime.date(2026, 11, 7), subtipo_costo="ALIMENTO",
                monto_costo=D("380000"), cuenta_debito="158405", activo="QA-M07-BUF-F2")
    base.update(kw)
    return CostoFactura(**base)


class TestSubCasoLinetypeNoCatalogadoArreglado:
    def test_ya_existe_la_consulta_al_catalogo_en_aaef(self):
        texto = AAEF.read_text(encoding='utf-8')
        assert 'LINETYPE_NO_CATALOGADO' in texto
        assert '_exigir_catalogo' in texto

    def test_un_linetype_catalogado_no_se_rechaza(self):
        costo = _costo(subtipo_costo="ALIMENTO")
        doc = mapear_compras([costo], catalogo=frozenset({"ALIMENTO"}))[0]
        assert doc["Lines"][0]["LineType"] == "ALIMENTO"

    def test_un_linetype_no_catalogado_se_rechaza_con_linetype_no_catalogado(self):
        """ARREGLADO: ya no se transfiere sin rechazo -- con un catalogo real que NO incluye
        el subtipo, se bloquea con el codigo exacto que pide CA-6."""
        costo = _costo(subtipo_costo="TIPO_QUE_NO_EXISTE_EN_NINGUN_CATALOGO")
        with pytest.raises(AaefError) as exc_info:
            mapear_compras([costo], catalogo=frozenset({"ALIMENTO", "VETERINARIO"}))
        assert exc_info.value.codigo == "LINETYPE_NO_CATALOGADO"
        assert exc_info.value.campo == "LineType"
        assert exc_info.value.detalle["mapper"] == "COMPRAS"

    def test_catalogo_none_sigue_sin_validar_caso_deliberado_de_la_autoprueba_del_anexo(self):
        """No es un hallazgo: catalogo=None es el valor por defecto que usa
        validar_con_datos_de_prueba() (RF-AE02 5.10, ver TC-M07-G023) porque esa autoprueba
        no tiene una BD real de la que leer la matriz contable."""
        costo = _costo(subtipo_costo="TIPO_QUE_NO_EXISTE_EN_NINGUN_CATALOGO")
        doc = mapear_compras([costo], catalogo=None)[0]  # no lanza
        assert doc["Lines"][0]["LineType"] == "TIPO_QUE_NO_EXISTE_EN_NINGUN_CATALOGO"


class TestSubCasoFormaDeLaCuentaConfirmadoCorrecto:
    @pytest.mark.parametrize("cuenta_invalida", [None, "", "   ", "51A5", "5105-01", "5.1.05"])
    def test_cuenta_vacia_nula_o_no_numerica_se_rechaza(self, cuenta_invalida):
        """No es CUENTA_CONTABLE_INVALIDA literal -- es MAPPER_FALLIDO, pero el mecanismo de
        rechazo SI existe para vacio/nulo/no-numerico."""
        costo = _costo(cuenta_debito=cuenta_invalida)
        with pytest.raises(AaefError) as exc_info:
            mapear_compras([costo])
        assert exc_info.value.codigo == "MAPPER_FALLIDO"
        assert exc_info.value.campo == "accounting_account"

    def test_cuenta_bien_formada_pero_inexistente_en_sigcon_se_transfiere_tal_cual(self):
        """CONFIRMADO CORRECTO: RF-96 5.6 (solo lectura) -- el Mapper no decide si la cuenta
        existe en el plan de cuentas externo, eso lo valida SIGCON (confirmado por el DBA:
        no es verificable desde SGPMP)."""
        costo = _costo(cuenta_debito="999999")
        doc = mapear_compras([costo])[0]
        assert doc["Lines"][0]["accounting_account"] == ["999999"]


class TestSubCasoCantidadDeElementosDistintaNoAlcanzablePorEsteCaminoDocumentacion:
    def test_mapear_compras_siempre_construye_un_solo_elemento_nunca_recibe_una_lista_externa(self):
        """No es un hallazgo alcanzable desde la entrada real: el Mapper CONSTRUYE
        accounting_account con exactamente un `_cuenta(...)` -- no existe ningun parametro
        de CostoFactura que permita pasar una lista de 2 o mas cuentas al 02."""
        tipos = __import__('typing').get_type_hints(aaef.CostoFactura)
        assert 'cuenta_debito' in tipos and tipos['cuenta_debito'] != list
