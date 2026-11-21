# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-11-14 | destroyerban | INC-M06-362-G94 RF-94: PRECIO_MARCADO_REEMPLAZADO guarda el precio anterior y el nuevo |
"""INC-M06-362-G94 / RF-94 CA-14 (sin BD): el evento de reemplazo trae los montos en su propio payload,
además de los ids que ya guardaba, para auditarlo sin consultar los precios de mercado."""
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal as D

from src.financial_valuation.application.use_cases.precios.registrar_precio_use_case import SolicitudPrecio
from tests.financial_valuation.test_tc_m06_g106_correccion_precio import HOY, _caso, _precio


class _Auditoria:
    def __init__(self):
        self.eventos = []

    def registrar(self, evento):
        self.eventos.append(evento)


def _con_auditoria(lista):
    uc, precios = _caso(lista)
    uc.auditoria = _Auditoria()
    return uc, precios


def _reemplazos(uc):
    return [e for e in uc.auditoria.eventos if e.tipo_evento == "PRECIO_MARCADO_REEMPLAZADO"]


def _nuevo(valor, vigencia, **extra):
    return SolicitudPrecio(id_especie=424, categoria="POR_CABEZA", precio_unitario=D(valor), fecha_vigencia=vigencia,
                           fuente="MERCADO_ACTIVO", evidencia_documental="Subasta", **extra)


def test_precio_nuevo_que_desplaza_al_vigente_guarda_ambos_montos():
    uc, _ = _con_auditoria([_precio(1, "100.00", HOY - timedelta(days=10))])
    resultado = uc.execute(_nuevo("110.50", HOY), id_usuario=7)
    (evento,) = _reemplazos(uc)
    assert evento.payload == {
        "id_precio_anterior": 1, "id_precio_nuevo": resultado["id_precio_mercado"],  # se conservan
        "precio_unitario_anterior": "100.00", "precio_unitario_nuevo": "110.50", "unidad_medida": "cabeza",
    }


def test_correccion_guarda_el_monto_corregido_y_el_nuevo():
    uc, _ = _con_auditoria([_precio(1, "100.00", HOY - timedelta(days=10))])
    uc.execute(_nuevo("105.00", None, id_precio_corregido=1), id_usuario=7)
    (evento,) = _reemplazos(uc)
    assert (evento.payload["precio_unitario_anterior"], evento.payload["precio_unitario_nuevo"]) == ("100.00", "105.00")


def test_sin_precio_anterior_de_la_misma_fuente_no_hay_evento_de_reemplazo():
    otra_fuente = replace(_precio(1, "90.00", HOY - timedelta(days=10)), fuente="TRANSACCION_RECIENTE")
    uc, _ = _con_auditoria([otra_fuente])
    uc.execute(_nuevo("100.00", HOY), id_usuario=7)
    assert _reemplazos(uc) == []

