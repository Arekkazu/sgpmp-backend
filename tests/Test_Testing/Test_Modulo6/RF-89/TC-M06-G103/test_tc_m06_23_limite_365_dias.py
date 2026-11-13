# | Fecha      | Nombre | Que se hizo |
# |------------|--------|-------------|
# | 2026-11-10 | —      | TC-M06-23: el caso de uso acepta 365 días y rechaza 366, sin base ni notificaciones |
"""Prueba aislada de TC-M06-23. No abre TEST, no usa TEST_DATABASE_URL y no aprueba el caso funcional."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.financial_valuation.application.use_cases.precios import registrar_precio_use_case as registro
from src.financial_valuation.application.use_cases.precios.registrar_precio_use_case import (
    RegistrarPrecioUseCase,
    SolicitudPrecio,
)
from src.financial_valuation.domain.entities.contabilidad import ConfiguracionContable
from src.financial_valuation.domain.services.precios import Precio
from src.shared.errors import ValidationError

HOY = date(2026, 11, 10)
VIGENCIA_365 = date(2025, 11, 10)
VIGENCIA_366 = date(2025, 11, 9)
ID_ESPECIE = 99023
ID_USUARIO = 901
ID_PRECIO = 88023


class _Sesion:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class _Precios:
    def __init__(self) -> None:
        self.altas: list[tuple] = []
        self.consultas = 0

    def de_especie(self, id_especie: int, categoria: str, id_metrica_produccion: int | None = None) -> list:
        self.consultas += 1
        return []

    def agregar(self, precio: Precio, region, origen: str, id_usuario: int, estado_inicial: str) -> Precio:
        self.altas.append((precio, region, origen, id_usuario, estado_inicial))
        return Precio(
            id_precio_mercado=ID_PRECIO, id_especie=precio.id_especie, categoria=precio.categoria,
            precio_unitario=precio.precio_unitario, unidad_medida=precio.unidad_medida, fuente=precio.fuente,
            fecha_vigencia=precio.fecha_vigencia, fecha_vencimiento=precio.fecha_vencimiento,
            id_metrica_produccion=precio.id_metrica_produccion, evidencia=precio.evidencia,
            justificacion=precio.justificacion, id_precio_corregido=precio.id_precio_corregido,
        )

    def obtener(self, id_precio_mercado: int):
        raise AssertionError("Estos escenarios no corrigen un precio existente.")


class _Configuracion:
    def obtener(self) -> ConfiguracionContable:
        return ConfiguracionContable("MENSUAL", Decimal("50"), 30, date(2026, 1, 1))


class _Auditoria:
    def __init__(self) -> None:
        self.eventos: list = []

    def registrar(self, evento) -> None:
        self.eventos.append(evento)


class _Catalogo:
    def especie(self, id_especie: int) -> dict:
        return {"id_especie": id_especie, "es_activo": True}


class _Notificador:
    def __init__(self) -> None:
        self.llamadas: list[tuple] = []

    def a_contadores(self, tipo_evento: str, mensaje: str, detalle: dict, id_finca: int | None = None) -> None:
        self.llamadas.append((tipo_evento, mensaje, detalle, id_finca))


def _solicitud(vigencia: date) -> SolicitudPrecio:
    return SolicitudPrecio(
        id_especie=ID_ESPECIE, categoria="POR_CABEZA", precio_unitario=Decimal("100.00"),
        fecha_vigencia=vigencia, fuente="MERCADO_ACTIVO",
        evidencia_documental="Soporte de la prueba aislada del límite de 365 días.",
    )


def _caso(monkeypatch):
    monkeypatch.setattr(registro, "hoy_usuario", lambda: HOY)
    sesion, precios, auditoria, notificador = _Sesion(), _Precios(), _Auditoria(), _Notificador()
    caso = RegistrarPrecioUseCase(sesion, precios, _Configuracion(), auditoria, _Catalogo(), notificador)
    return caso, sesion, precios, auditoria, notificador


def test_vigencia_de_365_dias_sigue_el_alta_en_memoria(monkeypatch):
    assert (HOY - VIGENCIA_365).days == 365
    caso, sesion, precios, auditoria, notificador = _caso(monkeypatch)

    resultado = caso.execute(_solicitud(VIGENCIA_365), ID_USUARIO)

    assert resultado["estado"] == "ACTIVO"
    assert resultado["fecha_vigencia"] == VIGENCIA_365
    assert resultado["id_precio_mercado"] == ID_PRECIO
    assert resultado["unidad_medida"] == "cabeza"
    assert resultado["desviacion_pct"] is None
    assert len(precios.altas) == 1
    precio, region, origen, id_usuario, estado = precios.altas[0]
    assert precio.fecha_vigencia == VIGENCIA_365
    assert precio.id_especie == ID_ESPECIE
    assert region is None and origen == "MANUAL" and id_usuario == ID_USUARIO and estado == "ACTIVO"
    assert [evento.tipo_evento for evento in auditoria.eventos] == ["PRECIO_REGISTRADO"]
    assert auditoria.eventos[0].payload["estado"] == "ACTIVO"
    assert auditoria.eventos[0].payload["fecha_vigencia"] == VIGENCIA_365
    assert auditoria.eventos[0].id_referencia == ID_PRECIO
    assert sesion.commits == 1 and sesion.rollbacks == 0
    assert len(notificador.llamadas) == 1
    tipo, mensaje, detalle, id_finca = notificador.llamadas[0]
    assert tipo == "ALERTA_FINANCIERA_NIC41"
    assert isinstance(mensaje, str) and mensaje
    assert detalle == {"id_precio_mercado": ID_PRECIO} and id_finca is None


def test_vigencia_de_366_dias_se_rechaza_antes_de_persistir(monkeypatch):
    assert (HOY - VIGENCIA_366).days == 366
    caso, sesion, precios, auditoria, notificador = _caso(monkeypatch)

    with pytest.raises(ValidationError) as error:
        caso.execute(_solicitud(VIGENCIA_366), ID_USUARIO)

    assert error.value.code == "FECHA_VIGENCIA_FUERA_DE_RANGO"
    assert error.value.field == "fecha_vigencia"
    assert error.value.status_code == 400
    assert precios.consultas == 0 and precios.altas == []
    assert auditoria.eventos == []
    assert sesion.commits == 0 and sesion.rollbacks == 0
    assert notificador.llamadas == []
