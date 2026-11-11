# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-08 | Arekkazu | INC-M06-299-G81 RF-89: avisos de vencimiento sin duplicados tras reinicios |
# | 2026-11-10 | —        | TC-M06-G109: la vía general de estos avisos exige SGPMP_ENTORNO=PROD |
"""Avisos de vencimiento de precios, sin base de datos.

INC-M06-299-G81 (RF-89 FA-4, CA-7), caso TC-M06-G109: los avisos a 30, 15, 7 y 0 días salen una
sola vez aunque el proceso diario se reinicie el mismo día, y un día sin ejecutar no pierde el aviso."""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal as D
from types import SimpleNamespace

from src.financial_valuation.application.use_cases.precios import alertar_vencimiento_precios_use_case as alertas
from src.financial_valuation.domain.services.precios import Precio

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
    monkeypatch.setenv("SGPMP_ENTORNO", "PROD")
    monkeypatch.delenv("M06_ALERTAS_QA_HABILITADAS", raising=False)
    monkeypatch.setattr(alertas, "hoy_usuario", lambda: HOY)
    caso, notificador = _caso([_precio(1, HOY + timedelta(days=15))])
    assert caso.execute() == 1
    assert caso.execute() == 0  # reinicio del proceso: la marca persiste
    assert notificador.enviados == [{"id_precio_mercado": 1, "aviso": "15_DIAS"}]


def test_dia_sin_ejecutar_no_pierde_el_aviso_y_cada_umbral_sale_una_vez(monkeypatch):
    monkeypatch.setenv("SGPMP_ENTORNO", "PROD")
    monkeypatch.delenv("M06_ALERTAS_QA_HABILITADAS", raising=False)
    precio = _precio(1, HOY + timedelta(days=12))
    caso, notificador = _caso([precio])
    for dia in (HOY, HOY + timedelta(days=1), HOY + timedelta(days=6), HOY + timedelta(days=12), HOY + timedelta(days=13)):
        monkeypatch.setattr(alertas, "hoy_usuario", lambda dia=dia: dia)
        caso.execute()
    # A 12 días del vencimiento ya pasó el de 15; luego el de 7, el del día del vencimiento y el de vencido sin reemplazo.
    assert [e["aviso"] for e in notificador.enviados] == ["15_DIAS", "7_DIAS", "0_DIAS", "VENCIDO"]
