# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-11-09 | destroyerban | INC-M06-318-G20 RF-84: log de auditoría del ajuste manual de costos de venta |
"""INC-M06-318-G20 / RF-84 R5, salida 3: cada costo de venta sobrescrito a mano deja un evento
AJUSTE_MANUAL_COSTOS_VENTA con el ítem, el valor parametrizado original, el valor manual y la justificación.

Antes la auditoría del activo solo traía RECONOCIMIENTO_INICIAL: el tipo existía en el catálogo pero nada lo emitía."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from src.financial_valuation.application.services.propuesta_reconocimiento import ProponedorReconocimiento
from src.financial_valuation.application.services.valorador import Valorador
from src.financial_valuation.application.use_cases.reconocimiento.confirmar_reconocimiento_use_case import (
    ConfirmarReconocimientoUseCase,
)
from src.financial_valuation.domain.services.nic41 import costos_venta
from src.financial_valuation.domain.services.precios import Precio

D = Decimal
JUSTIFICACION = "Comisión pactada con el comprador de la subasta de noviembre por encima del parámetro."
BRUTO = D("10000000")  # 400 kg × 25.000


# --- Dominio ----------------------------------------------------------------------------------------

def test_el_costo_manual_guarda_el_valor_parametrizado_que_reemplaza() -> None:
    costos = costos_venta(BRUTO, D("0.01"), D("0.02"), D("0"), {"comisiones": D("250000"), "otros": D("5000")})

    assert costos.comisiones == D("250000") and costos.metodos["comisiones"] == "MANUAL"
    assert costos.originales == {"comisiones": D("200000"), "otros": None}  # «otros» nunca se parametriza
    assert costos.transporte == D("100000") and costos.metodos["transporte"] == "PARAMETRIZADO"


def test_sin_parametro_el_original_es_nulo() -> None:
    costos = costos_venta(BRUTO, None, None, None, {"transporte": D("80000")})

    assert costos.originales == {"transporte": None}


def test_sin_costos_manuales_no_hay_originales() -> None:
    assert costos_venta(BRUTO, D("0.01"), D("0.02"), D("0")).originales == {}


# --- Confirmación -----------------------------------------------------------------------------------

def _config():
    return SimpleNamespace(
        costos_venta_vigentes=lambda _e: SimpleNamespace(pct_transporte=D("0.01"), pct_comisiones=D("0.02"),
                                                         pct_impuestos=D("0"), id_parametro_costo_venta=1),
        parametro_especie=lambda _e: SimpleNamespace(clasificacion="PRODUCCION", vida_util_meses=None,
                                                     categoria_precio="PESO_KG"),
        obtener=lambda: SimpleNamespace(fecha_inicio_operacion=date(2020, 1, 1)),
        resolver_cuenta=lambda *a: None,
    )


def _confirmar(costos_manuales):
    precio = Precio(id_precio_mercado=12, id_especie=2, categoria="PESO_KG", precio_unitario=D("25000"),
                    unidad_medida="kg", fuente="MERCADO_ACTIVO", fecha_vigencia=date(2026, 9, 1))
    activo = SimpleNamespace(
        id_activo_biologico=7, identificador="BOV-007", especie="Bovino", id_especie=2, cabezas=1, id_evento_peso=None,
        numero_id_tributaria="900123456", id_finca=3, finca="La Esperanza", es_valorable=True, estado="ACTIVO",
        origen_financiero="nacimiento", costo_adquisicion=None, fecha_ingreso=date(2026, 10, 1),
        magnitud=lambda _c: (D("400"), "kg"))
    config = _config()
    valorador = Valorador(SimpleNamespace(de_especie=lambda *a: [precio]), config)
    eventos, calculos = [], []
    caso = ConfirmarReconocimientoUseCase(
        db=SimpleNamespace(commit=lambda: None, rollback=lambda: None),
        activos=SimpleNamespace(obtener=lambda _id: activo),
        valoraciones=SimpleNamespace(reconocimiento_confirmado=lambda _id: None,
                                     agregar_calculo=lambda c: calculos.append(c) or 55,
                                     agregar_reconocimiento=lambda _d: 81),
        proponedor=ProponedorReconocimiento(valorador, config),
        contabilizador=SimpleNamespace(periodo_para=lambda *a: SimpleNamespace(id_periodo_contable=4),
                                       asentar=lambda linea, _u: SimpleNamespace(
                                           id_linea_asiento_nic41=1, tipo_hecho=linea.tipo_hecho, sentido=linea.sentido,
                                           valor=linea.valor, cuenta_debito=None, cuenta_credito=None, estado="X"),
                                       auditar=eventos.append, config=config),
    )
    resultado = caso.execute(7, 9, costos_manuales=costos_manuales, justificacion=JUSTIFICACION)
    return resultado, eventos, calculos


def test_confirmar_con_comisiones_manuales_deja_el_log_del_ajuste() -> None:
    resultado, eventos, calculos = _confirmar({"comisiones": D("250000"), "transporte": None})

    assert resultado["valor_inicial"] == D("9650000")  # 10.000.000 − 100.000 transporte − 250.000 comisiones
    assert calculos[0].metodo_costo == "MIXTO"
    assert [e.tipo_evento for e in eventos] == ["AJUSTE_MANUAL_COSTOS_VENTA", "RECONOCIMIENTO_INICIAL"]
    ajuste = eventos[0]
    assert ajuste.payload["item"] == "comisiones"
    assert ajuste.payload["valor_original"] == "200000.0000" and ajuste.payload["metodo_original"] == "PARAMETRIZADO"
    assert ajuste.payload["valor_manual"] == "250000.0000"
    assert ajuste.payload["justificacion"] == JUSTIFICACION
    assert ajuste.id_usuario == 9 and ajuste.id_activo_biologico == 7 and ajuste.id_referencia == 55
    assert ajuste.id_periodo_contable == 4 and ajuste.monto_afectado == D("250000")
    assert ajuste.datos_anteriores == {"item": "comisiones", "valor": "200000.0000"}


def test_un_evento_por_cada_item_sobrescrito() -> None:
    _, eventos, _ = _confirmar({"comisiones": D("250000"), "otros": D("5000")})

    ajustes = [e.payload for e in eventos if e.tipo_evento == "AJUSTE_MANUAL_COSTOS_VENTA"]
    assert [(a["item"], a["valor_original"], a["valor_manual"]) for a in ajustes] == [
        ("comisiones", "200000.0000", "250000.0000"), ("otros", None, "5000.0000")]
    assert ajustes[1]["metodo_original"] == "SIN_PARAMETRO"


def test_sin_costos_manuales_no_hay_log_de_ajuste() -> None:
    _, eventos, _ = _confirmar(None)

    assert [e.tipo_evento for e in eventos] == ["RECONOCIMIENTO_INICIAL"]
