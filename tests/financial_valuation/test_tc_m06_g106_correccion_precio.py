# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-11 | Arekkazu | TC-M06-G106 RF-89 FA-6: la corrección ocupa el lugar del precio corregido |
"""TC-M06-G106 / RF-89 FA-6 (sin BD): corregir un precio histórico no desplaza al aplicado hoy, la
corrección hereda la fecha del original y la desviación se mide contra el precio corregido."""
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal as D
from types import SimpleNamespace

import pytest

from src.financial_valuation.application.use_cases.precios.registrar_precio_use_case import (
    RegistrarPrecioUseCase,
    SolicitudPrecio,
)
from src.financial_valuation.domain.services.precios import Precio, estado_precio, precio_vigente
from src.shared.errors import ConflictError, ValidationError
from src.shared.fechas import hoy_usuario

HOY = hoy_usuario()


def _precio(i, valor, vigencia, corrige=None):
    return Precio(i, 424, "POR_CABEZA", D(valor), "cabeza", "MERCADO_ACTIVO", vigencia, id_precio_corregido=corrige)


class _Precios:
    def __init__(self, lista):
        self.lista = list(lista)

    def obtener(self, id_precio):
        return next((p for p in self.lista if p.id_precio_mercado == id_precio), None)

    def de_especie(self, *_):
        return list(self.lista)

    def agregar(self, precio, _region, _origen, _usuario, _estado):
        nuevo = replace(precio, id_precio_mercado=max(p.id_precio_mercado for p in self.lista) + 1)
        self.lista.append(nuevo)
        return nuevo


class _Nada:
    def __getattr__(self, _):
        return lambda *a, **k: None


def _caso(lista):
    precios = _Precios(lista)
    config = SimpleNamespace(obtener=lambda: SimpleNamespace(pct_umbral_desviacion_precio=D("20")))
    catalogo = SimpleNamespace(especie=lambda _: {"es_activo": True})
    return RegistrarPrecioUseCase(_Nada(), precios, config, _Nada(), catalogo, _Nada()), precios


def _correccion(valor, corrige, **extra):
    return SolicitudPrecio(id_especie=424, categoria="POR_CABEZA", precio_unitario=D(valor), fecha_vigencia=None,
                           fuente="MERCADO_ACTIVO", evidencia_documental="Subasta", id_precio_corregido=corrige, **extra)


def test_dominio_el_corregido_no_cuenta_y_la_correccion_ocupa_su_fecha():
    original = _precio(436, "4000000", HOY - timedelta(days=30))
    aplicado = _precio(645, "7650000", HOY)
    correccion = _precio(700, "4200000", original.fecha_vigencia, corrige=436)
    lista = [original, aplicado, correccion]
    assert precio_vigente(lista, HOY) == aplicado
    assert precio_vigente(lista, HOY - timedelta(days=1)) == correccion
    assert estado_precio(original, lista, HOY) == "CORREGIDO"
    assert estado_precio(correccion, lista, HOY) == "SUPERADO"
    assert estado_precio(aplicado, lista, HOY) == "ACTIVO"


def test_corregir_el_historico_hereda_fecha_y_no_toca_el_aplicado():
    original = _precio(436, "4000000", HOY - timedelta(days=30))
    caso, precios = _caso([original, _precio(645, "7650000", HOY)])
    resultado = caso.execute(_correccion("4200000", 436), 1)
    assert resultado["fecha_vigencia"] == original.fecha_vigencia
    assert resultado["desviacion_pct"] == D("5")  # contra el 436, no contra el 645
    assert precio_vigente(precios.lista, HOY).id_precio_mercado == 645


def test_corregir_el_aplicado_lo_reemplaza():
    caso, precios = _caso([_precio(645, "7650000", HOY)])
    nuevo = caso.execute(_correccion("7600000", 645), 1)["id_precio_mercado"]
    assert precio_vigente(precios.lista, HOY).id_precio_mercado == nuevo


def test_validaciones_de_la_correccion():
    caso, _ = _caso([_precio(436, "4000000", HOY - timedelta(days=30)), _precio(500, "4100000", HOY)])
    with pytest.raises(ValidationError) as otra_fecha:
        caso.execute(replace(_correccion("4200000", 436), fecha_vigencia=HOY), 1)
    assert otra_fecha.value.code == "FECHA_VIGENCIA_CORRECCION"
    with pytest.raises(ValidationError) as otra_fuente:
        caso.execute(replace(_correccion("4200000", 436), fuente="UPRA"), 1)
    assert otra_fuente.value.code == "CORRECCION_NO_COINCIDE"
    with pytest.raises(ConflictError) as desviada:
        caso.execute(_correccion("9000000", 436), 1)
    assert desviada.value.code == "DESVIACION_PRECIO_REQUIERE_CONFIRMACION"
    caso.execute(_correccion("4200000", 436), 1)
    with pytest.raises(ConflictError) as dos_veces:
        caso.execute(_correccion("4300000", 436), 1)
    assert dos_veces.value.code == "PRECIO_YA_CORREGIDO"
    with pytest.raises(ValidationError) as sin_fecha:
        caso.execute(replace(_correccion("4200000", 436), id_precio_corregido=None), 1)
    assert sin_fecha.value.code == "FECHA_VIGENCIA_OBLIGATORIA"
