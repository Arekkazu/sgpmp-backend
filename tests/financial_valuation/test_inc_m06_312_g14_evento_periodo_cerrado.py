# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-11-08 | destroyerban | INC-M06-312-G14 RF-83: evento en período cerrado queda pendiente y alerta |
# | 2026-11-10 | Arekkazu | Lote M05/M06: fakes al día con el lote integrado (elegibilidad, alertas, período cerrado, referencia documental) |
"""INC-M06-312-G14 / RF-83 restricción 2, RF-86 paso 1 c y FA-2: un evento de M02 cuya fecha cae en un período
CERRADO no se valora en el período siguiente: queda MEDICION_PENDIENTE, se audita y se alerta al Contador.
Los eventos encolados mientras el período estaba EN_CIERRE siguen yendo al período siguiente (RF-87)."""
from __future__ import annotations

from datetime import date, datetime, timezone
from types import SimpleNamespace

import pytest

from src.financial_valuation.application.services.contabilizador import Contabilizador
from src.financial_valuation.application.services.medidor import Medidor
from src.financial_valuation.application.use_cases.valoracion.procesar_eventos_m02_use_case import (
    ProcesarEventosM02UseCase,
)
from src.financial_valuation.domain.entities.contabilidad import Periodo
from src.financial_valuation.domain.repositories.evento_m02_port import EventoM02

CERRADO = Periodo(id_periodo_contable=77, numero_id_tributaria="900", tipo_cierre="MENSUAL",
                  fecha_inicio=date(2026, 11, 1), fecha_fin=date(2026, 11, 30), estado="CERRADO",
                  fecha_cierre=datetime(2026, 11, 8, 12, tzinfo=timezone.utc))
SIGUIENTE = Periodo(id_periodo_contable=78, numero_id_tributaria="900", tipo_cierre="MENSUAL",
                    fecha_inicio=date(2026, 12, 1), fecha_fin=date(2026, 12, 31), estado="ABIERTO")
ACTIVO = SimpleNamespace(estado="ACTIVO", es_valorable=True, id_activo_biologico=7, identificador="BOV-007", especie="Bovino", id_especie=2, id_finca=4,
                         numero_id_tributaria="900", id_dispositivo_iot=None)


class PeriodosFake:
    def __init__(self, periodo: Periodo) -> None:
        self.periodo = periodo

    def que_contiene(self, _nit, _dia):
        return self.periodo


class ContabilizadorFake:
    def __init__(self, cerrado) -> None:
        self.cerrado, self.eventos, self.periodo_para_llamado = cerrado, [], False

    def periodo_cerrado_en(self, _nit, _dia):
        return self.cerrado

    def periodo_para(self, *_a):
        self.periodo_para_llamado = True
        return SIGUIENTE

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
    def __init__(self) -> None:
        self.orden = []

    def commit(self):
        self.orden.append("commit")

    def rollback(self):
        self.orden.append("rollback")


class NotificadorFake:
    def __init__(self, db) -> None:
        self.db, self.avisos = db, []

    def a_contadores(self, tipo, mensaje, detalle, id_finca=None):
        self.db.orden.append("aviso")
        self.avisos.append((tipo, mensaje, detalle, id_finca))


def _evento(tipo="CRECIMIENTO", encolado=False) -> EventoM02:
    return EventoM02(55, 7, datetime(2026, 11, 8, 15, tzinfo=timezone.utc), tipo, {}, encolado_en_cierre=encolado)


def _procesar(evento: EventoM02, cerrado):
    contabilizador = ContabilizadorFake(cerrado)
    medidor = Medidor(None, None, contabilizador)  # real salvo ``medir``, que solo registra la llamada
    medidor.medidas = []
    medidor.medir = lambda *a, **k: medidor.medidas.append(a) or SimpleNamespace(estado="MEDIDO", mensaje=None, motivo=None)
    db, eventos = DbFake(), EventosFake(evento)
    notificador = NotificadorFake(db)
    valoraciones = SimpleNamespace(valoracion_costo_activa=lambda _id: None)
    ProcesarEventosM02UseCase(db, eventos, SimpleNamespace(obtener=lambda _id: ACTIVO), valoraciones, None, medidor,
                              contabilizador, 1, notificador).execute()
    return eventos, contabilizador, medidor, notificador, db


@pytest.mark.parametrize("tipo", ["CRECIMIENTO", "PRODUCTIVO", "BAJA", "INGRESO"])
def test_evento_en_periodo_cerrado_queda_pendiente_auditado_y_alerta(tipo) -> None:
    eventos, contabilizador, medidor, notificador, db = _procesar(_evento(tipo), CERRADO)

    [(id_evento, resultado, detalle)] = eventos.registros
    assert (id_evento, resultado) == (55, "MEDICION_PENDIENTE")
    assert detalle == ("El evento del 2026-11-08 del activo BOV-007 no se valoró: su fecha cae en el período contable "
                       "del 2026-11-01 al 2026-11-30, que ya está cerrado. Si el hecho debe reconocerse, regístrelo "
                       "como ajuste en el período abierto.")
    assert not contabilizador.periodo_para_llamado and medidor.medidas == []  # nada va al período siguiente
    [auditoria] = contabilizador.eventos
    assert auditoria.tipo_evento == "MEDICION_PENDIENTE" and auditoria.severidad == "WARNING"
    assert auditoria.payload["motivo"] == "PERIODO_CERRADO" and auditoria.payload["id_evento"] == 55
    assert auditoria.id_periodo_contable == 77 and auditoria.id_activo_biologico == 7
    assert db.orden == ["commit", "aviso"]
    [(tipo_aviso, mensaje, detalle_aviso, finca)] = notificador.avisos
    assert tipo_aviso == "ALERTA_FINANCIERA_NIC41" and mensaje == detalle and finca == 4
    assert detalle_aviso["motivo"] == "PERIODO_CERRADO" and detalle_aviso["fecha"] == "2026-11-08"


def test_evento_encolado_durante_el_cierre_sigue_al_periodo_siguiente() -> None:
    eventos, contabilizador, medidor, notificador, _ = _procesar(_evento(encolado=True), CERRADO)

    assert eventos.registros[0][1] == "PROCESADO"
    assert contabilizador.periodo_para_llamado and len(medidor.medidas) == 1
    assert contabilizador.eventos == [] and notificador.avisos == []


def test_evento_en_periodo_abierto_se_mide_normal() -> None:
    eventos, contabilizador, medidor, notificador, _ = _procesar(_evento(), None)

    assert eventos.registros[0][1] == "PROCESADO" and len(medidor.medidas) == 1
    assert notificador.avisos == []


def test_eventos_sin_efecto_no_consultan_el_periodo() -> None:
    eventos, contabilizador, _, notificador, _ = _procesar(_evento("SANITARIO"), CERRADO)

    assert eventos.registros[0][1] == "SIN_EFECTO" and contabilizador.eventos == [] and notificador.avisos == []


@pytest.mark.parametrize("estado, esperado", [("CERRADO", 77), ("ABIERTO", None), ("EN_CIERRE", None)])
def test_contabilizador_periodo_cerrado_en(estado, esperado) -> None:
    periodo = Periodo(77, "900", "MENSUAL", date(2026, 11, 1), date(2026, 11, 30), estado)
    contabilizador = Contabilizador(None, PeriodosFake(periodo), None, None)

    encontrado = contabilizador.periodo_cerrado_en("900", date(2026, 11, 8))

    assert (encontrado.id_periodo_contable if encontrado else None) == esperado
    assert contabilizador.periodo_cerrado_en(None, date(2026, 11, 8)) is None
