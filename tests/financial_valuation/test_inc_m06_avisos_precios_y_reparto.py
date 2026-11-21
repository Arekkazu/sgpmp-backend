# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-08 | Arekkazu | INC-M06-299-G81 / INC-M06-329-G85 / INC-M06-324-G27: avisos, reparto y conversión a kg |
"""M06 sin base de datos.

- INC-M06-299-G81 (RF-89 FA-4, CA-7): los avisos a 30, 15, 7 y 0 días salen una sola vez aunque el
  proceso diario se reinicie el mismo día, y un día sin ejecutar no pierde el aviso.
- INC-M06-329-G85 (RF-90 FA-11): un reparto sin cabezas ni biomasa responde 422, no un ``ValueError``.
- INC-M06-324-G27 (RF-85 precondición 7): reglas de conversión de masa a kg; sin regla, ``None`` (bloqueo)."""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal as D
from types import SimpleNamespace

import pytest

from src.financial_valuation.application.use_cases.costos.registrar_costo_use_case import RegistrarCostoUseCase, SolicitudCosto
from src.financial_valuation.application.use_cases.precios import alertar_vencimiento_precios_use_case as alertas
from src.financial_valuation.domain.services.nic41 import a_kg
from src.financial_valuation.domain.services.precios import Precio
from src.shared.errors import BusinessRuleError

HOY = date(2026, 11, 8)


class _Notificador:
    """Bandeja persistente simulada: guarda el detalle de cada aviso enviado."""

    def __init__(self) -> None:
        self.enviados: list[dict] = []

    def ya_notificado(self, tipo_evento, detalle) -> bool:
        return any(detalle.items() <= enviado.items() for enviado in self.enviados)

    def a_contadores(self, tipo_evento, mensaje, detalle, id_finca=None) -> None:
        self.enviados.append(detalle)


def _caso(precios: list[Precio], ventana: int = 30):
    repo = SimpleNamespace(por_vencer=lambda desde, hasta: [p for p in precios if desde <= p.fecha_vencimiento <= hasta],
                           de_especie=lambda *a: precios)
    config = SimpleNamespace(obtener=lambda: SimpleNamespace(dias_alerta_vencimiento_precio=ventana),
                             listar_parametros_especie=lambda: [{"id_especie": 2, "especie": "Bovino"}])
    notificador = _Notificador()
    return alertas.AlertarVencimientoPreciosUseCase(repo, config, notificador), notificador


def _precio(id_precio: int, vence: date) -> Precio:
    return Precio(id_precio, 2, "PESO_KG", D("8000"), "kg", "MERCADO_ACTIVO", date(2026, 1, 1), vence)


def test_umbral_alcanzado_usa_los_de_la_ventana():
    assert [alertas.umbral_alcanzado(d, 30) for d in (31, 30, 20, 15, 8, 7, 1, 0)] == [None, 30, 30, 15, 15, 7, 7, 0]
    assert [alertas.umbral_alcanzado(d, 7) for d in (8, 7, 3, 0)] == [None, 7, 7, 0]


def test_aviso_no_se_repite_si_el_proceso_corre_dos_veces_el_mismo_dia(monkeypatch):
    monkeypatch.setattr(alertas, "hoy_usuario", lambda: HOY)
    caso, notificador = _caso([_precio(1, HOY + timedelta(days=15))])
    assert caso.execute() == 1
    assert caso.execute() == 0  # reinicio del proceso: la marca persiste
    assert notificador.enviados == [{"id_precio_mercado": 1, "aviso": "15_DIAS"}]


def test_dia_sin_ejecutar_no_pierde_el_aviso_y_cada_umbral_sale_una_vez(monkeypatch):
    precio = _precio(1, HOY + timedelta(days=12))
    caso, notificador = _caso([precio])
    for dia in (HOY, HOY + timedelta(days=1), HOY + timedelta(days=6), HOY + timedelta(days=12), HOY + timedelta(days=13)):
        monkeypatch.setattr(alertas, "hoy_usuario", lambda dia=dia: dia)
        caso.execute()
    # A 12 días del vencimiento ya pasó el de 15; luego el de 7, el del día del vencimiento y el de vencido sin reemplazo.
    assert [e["aviso"] for e in notificador.enviados] == ["15_DIAS", "7_DIAS", "0_DIAS", "VENCIDO"]


def test_reparto_sin_participacion_responde_422():
    poblacionales = [SimpleNamespace(id_activo_biologico=i, peso_kg=None, cabezas=0) for i in (1, 2)]
    solicitud = SolicitudCosto(subtipo_costo="ALIMENTO", origen_costo="MANO_OBRA_PROPIA", monto_costo=D("900000"),
                               fecha_costo=HOY, activos_reparto=[1, 2], metodo_reparto="POR_BIOMASA")
    with pytest.raises(BusinessRuleError) as error:
        RegistrarCostoUseCase._repartir(solicitud, poblacionales)
    assert error.value.code == "REPARTO_INVALIDO" and error.value.status_code == 422


def test_conversion_a_kg_de_unidades_de_masa():
    assert a_kg(D("1500"), "g") == D("1.5000")
    assert a_kg(D("2"), " Toneladas ") == D("2000.0000")
    assert a_kg(D("4"), "@") == D("50.0000")
    assert a_kg(D("10"), "lb") == D("4.5359")
    assert a_kg(D("1000"), "mL") is None and a_kg(D("3"), "unidades") is None
