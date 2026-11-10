# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-11-08 | destroyerban | INC-M06-313-G14 RF-83: excluye y registra los activos no elegibles |
"""INC-M06-313-G14 / RF-83: la medición por evento excluye los activos no elegibles y registra la exclusión.

INACTIVO se medía (0 → 1 medición, evento PROCESADO) y PENDIENTE_RECONOCIMIENTO no dejaba rastro. BAJA lo
rechaza M02, pero el propio evento de baja sí se valora (RF-83 FA-3) aunque el activo ya esté en BAJA."""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from src.financial_valuation.application.use_cases.auditoria.consultar_auditoria_financiera_use_case import DESCRIPCIONES
from src.financial_valuation.application.use_cases.valoracion.procesar_eventos_m02_use_case import (
    ProcesarEventosM02UseCase,
)
from src.financial_valuation.domain.repositories.evento_m02_port import EventoM02


def _activo(estado: str):
    return SimpleNamespace(id_activo_biologico=7, identificador="BOV-007", especie="Bovino", id_especie=2, id_finca=4,
                           numero_id_tributaria="900", id_dispositivo_iot=None, estado=estado,
                           es_valorable=estado in ("ACTIVO", "EN_TRATAMIENTO"))


class ContabilizadorFake:
    def __init__(self) -> None:
        self.eventos, self.periodo_para_llamado = [], False

    def periodo_para(self, *_a):
        self.periodo_para_llamado = True
        return SimpleNamespace(id_periodo_contable=78)

    def auditar(self, evento):
        self.eventos.append(evento)


class EventosFake:
    def __init__(self, evento: EventoM02) -> None:
        self.evento, self.registros = evento, []

    def pendientes(self, _limite):
        return [self.evento]

    def registrar_procesamiento(self, id_evento, resultado, detalle):
        self.registros.append((id_evento, resultado, detalle))


class DbFake:
    def commit(self): ...

    def rollback(self): ...


def _procesar(tipo: str, estado: str, sin_reconocimiento: bool = False):
    evento = EventoM02(55, 7, datetime(2026, 11, 8, 15, tzinfo=timezone.utc), tipo, {},
                       sin_reconocimiento=sin_reconocimiento)
    contabilizador, eventos, medidas = ContabilizadorFake(), EventosFake(evento), []
    medidor = SimpleNamespace(medir=lambda *a, **k: medidas.append(a) or SimpleNamespace(estado="MEDIDO", mensaje=None))
    valoraciones = SimpleNamespace(valoracion_costo_activa=lambda _id: None)
    caso = ProcesarEventosM02UseCase(DbFake(), eventos, SimpleNamespace(obtener=lambda _id: _activo(estado)),
                                     valoraciones, None, medidor, contabilizador, 1)
    caso._baja = lambda *a: ("PROCESADO", None)  # la valoración de la baja tiene sus propias pruebas
    caso.execute()
    return eventos.registros[0], contabilizador, medidas


@pytest.mark.parametrize("estado", ["INACTIVO", "AISLADO", "CERRADO"])
@pytest.mark.parametrize("tipo", ["CRECIMIENTO", "PRODUCTIVO", "INGRESO"])
def test_activo_en_estado_no_elegible_no_se_mide_y_queda_la_exclusion(tipo, estado) -> None:
    (id_evento, resultado, detalle), contabilizador, medidas = _procesar(tipo, estado)

    assert (id_evento, resultado) == (55, "SIN_EFECTO")
    assert medidas == [] and not contabilizador.periodo_para_llamado
    [auditoria] = contabilizador.eventos
    assert auditoria.tipo_evento == "MEDICION_EXCLUIDA" and auditoria.severidad == "INFO"
    assert auditoria.payload["motivo"] == f"ESTADO_{estado}" and auditoria.payload["estado_activo"] == estado
    assert auditoria.payload["id_evento"] == 55 and auditoria.payload["tipo_evento_m02"] == tipo
    assert auditoria.id_activo_biologico == 7 and auditoria.id_referencia == 55
    assert detalle == (f"El activo BOV-007 no se midió: está {estado.replace('_', ' ').lower()} y solo se miden los "
                       "activos activos o en tratamiento.")


def test_activo_pendiente_de_reconocimiento_queda_la_exclusion() -> None:
    (_, resultado, detalle), contabilizador, medidas = _procesar("CRECIMIENTO", "ACTIVO", sin_reconocimiento=True)

    assert resultado == "SIN_EFECTO" and medidas == []
    [auditoria] = contabilizador.eventos
    assert auditoria.tipo_evento == "MEDICION_EXCLUIDA" and auditoria.payload["motivo"] == "PENDIENTE_RECONOCIMIENTO"
    assert detalle == ("El activo BOV-007 no se midió: su reconocimiento inicial fue revertido y está pendiente de "
                       "un nuevo reconocimiento.")


@pytest.mark.parametrize("estado", ["ACTIVO", "EN_TRATAMIENTO"])
def test_activo_elegible_se_mide(estado) -> None:
    (_, resultado, _), contabilizador, medidas = _procesar("CRECIMIENTO", estado)

    assert resultado == "PROCESADO" and len(medidas) == 1 and contabilizador.eventos == []


def test_el_evento_de_baja_se_valora_aunque_el_activo_ya_este_en_baja() -> None:
    (_, resultado, _), contabilizador, _ = _procesar("BAJA", "BAJA")

    assert resultado == "PROCESADO" and contabilizador.eventos == []


def test_eventos_sin_efecto_no_registran_exclusion() -> None:
    (_, resultado, _), contabilizador, _ = _procesar("SANITARIO", "INACTIVO")

    assert resultado == "SIN_EFECTO" and contabilizador.eventos == []


def test_el_tipo_tiene_descripcion_legible() -> None:
    assert DESCRIPCIONES["MEDICION_EXCLUIDA"] == "Evento sin medición: activo no elegible"
