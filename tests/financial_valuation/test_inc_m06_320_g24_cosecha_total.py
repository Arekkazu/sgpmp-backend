# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-11-09 | destroyerban | INC-M06-320-G24 RF-85 FA-4: la cosecha del 100 % deja el activo en cero e inicia su baja |
"""INC-M06-320-G24 / RF-85 FA-4 y postcondición 6: la cosecha del 100 % de un producto de consumo deja el activo
en cero y, después del commit, inicia su baja en M02 (RF-45).

Antes: proporción 1 y valor_reduccion 18.800.000, pero el valor vigente seguía en 18.800.000, el activo quedaba
ACTIVO en M02 y solo salía la alerta «quedó cosechado completamente: registre su baja»."""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

from src.financial_valuation.application.use_cases.valoracion.procesar_eventos_m02_use_case import (
    ProcesarEventosM02UseCase,
)
from src.financial_valuation.domain.entities.valoracion import CalculoValor
from src.financial_valuation.domain.repositories.evento_m02_port import EventoM02

D = Decimal
DIA = date(2026, 11, 9)


def _base() -> CalculoValor:  # 1.000 kg a 20.000 menos 6 % de costos de venta = 18.800.000
    return CalculoValor(
        id_activo_biologico=7, id_precio_mercado=12, id_periodo_contable=4, magnitud=D("1000"), unidad_magnitud="kg",
        precio_unitario=D("20000"), valor_razonable_bruto=D("20000000"), costo_transporte=D("1200000"),
        costo_comisiones=D("0"), costo_impuestos_transaccion=D("0"), otros_costos_disposicion=D("0"),
        valor_neto=D("18800000"), metodo_costo="PARAMETRIZADO", json_metodo_costo={}, id_usuario=1,
        id_calculo_valor_razonable=90)


class _Bajas:
    def __init__(self, rechazo=None, registro=None) -> None:
        self.rechazo, self.llamadas, self.registro = rechazo, [], registro

    def dar_de_baja_por_cosecha(self, id_activo, fecha, motivo):
        self.llamadas.append((id_activo, fecha, motivo, list(self.registro)))
        return self.rechazo


def _procesador(cantidad: str, bajas=None):
    registro: list = []
    activo = SimpleNamespace(id_activo_biologico=7, identificador="TRU-007", id_especie=2, id_finca=3,
                             numero_id_tributaria="900123456", id_dispositivo_iot=None)
    evento = EventoM02(id_evento=500, id_activo_biologico=7, tipo="PRODUCTIVO",
                       fecha=datetime(2026, 11, 9, 15, tzinfo=timezone.utc),
                       datos={"cantidad_producida": cantidad, "id_metrica_produccion": 3})
    calculos, productos, eventos_auditoria, procesados = [], [], [], []
    db = SimpleNamespace(commit=lambda: registro.append("commit"), rollback=lambda: registro.append("rollback"))
    bajas = bajas if bajas is not None else _Bajas(registro=registro)
    bajas.registro = registro
    caso = ProcesarEventosM02UseCase(
        db=db,
        eventos=SimpleNamespace(pendientes=lambda _l: [evento],
                                registrar_procesamiento=lambda i, r, d: procesados.append((i, r, d))),
        activos=SimpleNamespace(obtener=lambda _id: activo,
                                metrica_produccion=lambda _id: {"id_metrica_produccion": 3, "nombre": "Trucha entera",
                                                                "unidad_medida": "kg"}),
        valoraciones=SimpleNamespace(valoracion_costo_activa=lambda _id: None, ultimo_calculo=lambda _id: _base(),
                                     reconocimiento_confirmado=lambda _id: SimpleNamespace(clasificacion="CONSUMO"),
                                     agregar_producto=lambda d: productos.append(d) or 70,
                                     agregar_calculo=lambda c: calculos.append(c) or 91),
        precios=None,
        medidor=SimpleNamespace(valorador=SimpleNamespace(categoria=lambda _e: "PESO_KG"),
                                medir=lambda *a, **k: SimpleNamespace(estado="MEDIDO", id_medicion=33, mensaje=None)),
        contabilizador=SimpleNamespace(periodo_para=lambda *a: SimpleNamespace(id_periodo_contable=4),
                                       asentar=lambda *a: None, auditar=eventos_auditoria.append),
        id_usuario_servicio=1, bajas=bajas,
    )
    return caso, bajas, calculos, productos, eventos_auditoria, procesados, registro


def test_cosecha_del_100_por_ciento_deja_el_activo_en_cero_e_inicia_la_baja_tras_el_commit() -> None:
    caso, bajas, calculos, productos, eventos, procesados, registro = _procesador("1000")

    caso.execute()

    assert procesados == [(500, "PROCESADO", None)]
    assert productos[0]["proporcion_cosechada"] == D("1.0000")
    assert productos[0]["valor_reduccion_activo"] == D("18800000.00")
    assert productos[0]["id_calculo_valor_razonable"] == 90  # el cálculo consumido: deja de ser valor vigente
    assert calculos == []  # no queda base remanente
    cosecha = next(e for e in eventos if e.payload.get("estado_activo") == "COSECHADO_COMPLETAMENTE")
    assert cosecha.payload["valor_actual"] == "0" and cosecha.payload["id_calculo_consumido"] == 90
    assert cosecha.monto_afectado == D("18800000.00")
    (id_activo, fecha, motivo, antes), = bajas.llamadas
    assert (id_activo, fecha) == (7, DIA) and "Cosechado completamente" in motivo
    assert antes == ["commit"]  # la baja en M02 va después del commit de M06
    assert not any("registre su baja" in str(e.payload) for e in eventos)


def test_cosecha_parcial_no_inicia_la_baja() -> None:
    caso, bajas, calculos, productos, eventos, _, _ = _procesador("400")

    caso.execute()

    assert productos[0]["proporcion_cosechada"] == D("0.4000")
    assert [c.valor_neto for c in calculos] == [D("11280000.0000")]  # queda el 60 % como nueva base
    assert bajas.llamadas == []
    assert not any(e.payload.get("estado_activo") for e in eventos)


def test_si_m02_rechaza_la_baja_se_alerta_al_contador() -> None:
    caso, bajas, _, _, eventos, procesados, registro = _procesador("1000", _Bajas(rechazo="El activo ya está dado de baja."))

    caso.execute()

    assert procesados[0][1] == "PROCESADO"  # el reconocimiento del producto ya quedó
    alerta = eventos[-1]
    assert alerta.tipo_evento == "MEDICION_PENDIENTE" and alerta.severidad == "WARNING"
    assert "no se pudo registrar su baja: El activo ya está dado de baja." in alerta.payload["mensaje"]
    assert registro == ["commit", "commit"]  # el reconocimiento y, después, la alerta


def test_baja_posterior_de_un_activo_consumido_no_vuelve_a_asentar_su_valor() -> None:
    caso, _, _, _, eventos, _, _ = _procesador("1000")
    caso.valoraciones.ultimo_calculo = lambda _id: None  # el repositorio ya no devuelve el cálculo consumido
    baja = EventoM02(id_evento=501, id_activo_biologico=7, tipo="BAJA", fecha=datetime(2026, 11, 9, 16, tzinfo=timezone.utc),
                     datos={"tipo_baja": "sacrificio", "cantidad_afectada": 1})
    caso.activos.obtener = lambda _id: SimpleNamespace(
        id_activo_biologico=7, identificador="TRU-007", id_especie=2, id_finca=3, numero_id_tributaria="900123456",
        cantidad_actual=0, es_poblacional=True)

    assert caso._procesar(baja) == ("SIN_EFECTO", "Sin valor en libros para dar de baja")
    assert not any(e.tipo_evento == "BAJA_ACTIVO_REGISTRADA" for e in eventos)
