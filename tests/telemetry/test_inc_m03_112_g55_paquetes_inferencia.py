# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-26 | destroyerban | INC-M03-112-G55 RF-56: envio de pendientes en lotes de maximo 500 |
# | 2026-10-27 | destroyerban | INC-M03-113-G56 RF-56: el repositorio en memoria respeta el backoff; lote no confirmado se reprograma |
# | 2026-10-28 | Arekkazu | INC-M03-116-G59 RF-56: el repositorio en memoria implementa obtener() del puerto |
"""INC-M03-112-G55 (RF-56): generación del paquete y envío batch fragmentado a máximo 500.

TC-M03-090: el paquete lleva los campos obligatorios de la Salida de RF-56.
TC-M03-092: 501 paquetes pendientes salen en dos lotes (500 + 1), en orden cronológico.
TC-M03-091 (envío real a M04) sigue bloqueado: no hay motor ni contrato IA-1; aquí el
motor es un doble del puerto.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import Mock

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Query, Session

from src.shared.errors import ValidationError
from src.telemetry.application.use_cases.inferencia.consolidar_paquete_inferencia_use_case import ConsolidarEnviarPaqueteUseCase
from src.telemetry.application.use_cases.inferencia.drenar_paquetes_pendientes_use_case import DrenarPaquetesPendientesUseCase
from src.telemetry.domain.entities.telemetria import (
    ESPERAS_REINTENTO_INFERENCIA_SEG,
    MAX_REGISTROS_POR_ENVIO_INFERENCIA,
    EventoEdgeComputing,
    PaqueteInferencia,
)
from src.telemetry.domain.repositories.motor_inferencia_port import MotorInferenciaNoIntegradoError, MotorInferenciaPort
from src.telemetry.domain.repositories.paquete_inferencia_repository import PaqueteInferenciaRepository
from src.telemetry.infrastructure.adapters.motor_inferencia_stub_adapter import MotorInferenciaStubAdapter
from src.telemetry.infrastructure.repositories.paquete_inferencia_repository import SqlAlchemyPaqueteInferenciaRepository

_BASE = datetime(2026, 10, 26, 12, 0, tzinfo=timezone.utc)


class _RepoMemoria(PaqueteInferenciaRepository):
    """Pendientes en memoria; listar_pendientes devuelve en orden de id (= captura).

    Respeta el backoff de RF-56 contra `self.ahora`, que la prueba puede adelantar.
    """

    def __init__(self, cantidad: int) -> None:
        self.ahora = None  # None = reloj real
        self.paquetes = {
            i: PaqueteInferencia(
                id_paquetes_inferencia=i, id_sensor=3, id_dispositivo_iot=2, id_evento_edge_computing=i,
                tipo_variable="TEMPERATURA_AMBIENTAL", valor_numerico=Decimal("38.5"),
                estado_calidad="LECTURA_VALIDA", fecha_envio=_BASE, estado_paquete="PENDIENTE",
                intento_envios=0, contexto_incompleto=False,
            )
            for i in range(1, cantidad + 1)
        }

    def obtener_por_evento(self, id_evento, *, bloquear_evento=False): ...

    def obtener(self, id_paquete, *, ids_fincas_permitidas=None): ...

    def guardar(self, paquete): ...

    def actualizar_estado(self, id_paquete, estado, intento, fecha_intento=None):
        cambios = dict(estado_paquete=estado, intento_envios=intento)
        if fecha_intento is not None:
            # Con reloj controlado, el intento ocurre "ahora" para poder probar el backoff.
            cambios["fecha_envio"] = self.ahora or fecha_intento
        self.paquetes[id_paquete] = replace(self.paquetes[id_paquete], **cambios)

    def _vencido(self, p):
        if p.intento_envios == 0:
            return True
        ahora = self.ahora or datetime.now(timezone.utc)
        espera = ESPERAS_REINTENTO_INFERENCIA_SEG[min(p.intento_envios, len(ESPERAS_REINTENTO_INFERENCIA_SEG) - 1)]
        return p.fecha_envio + timedelta(seconds=espera) <= ahora

    def listar_pendientes(self, limite):
        pendientes = [p for p in self.paquetes.values() if p.estado_paquete == "PENDIENTE" and self._vencido(p)]
        return pendientes[:limite]

    def estados(self):
        return {p.estado_paquete for p in self.paquetes.values()}


def _motor(**kw):
    motor = Mock(spec=MotorInferenciaPort)
    motor.enviar_lote.configure_mock(**kw)
    return motor


def test_501_pendientes_se_envian_en_lotes_de_500_y_1_en_orden():
    repo, db = _RepoMemoria(501), Mock()
    motor = _motor(return_value=True)
    resultado = DrenarPaquetesPendientesUseCase(db, repo, motor).execute()
    enviados = [call.args[0] for call in motor.enviar_lote.call_args_list]
    assert [len(lote) for lote in enviados] == [500, 1] == resultado.lotes
    assert all(len(lote) <= MAX_REGISTROS_POR_ENVIO_INFERENCIA for lote in enviados)
    ids = [p.id_paquetes_inferencia for lote in enviados for p in lote]
    assert ids == list(range(1, 502))  # orden cronológico, sin repetir ni saltar
    assert resultado.enviados == 501 and resultado.fallidos == 0
    assert repo.estados() == {"ENVIADO"}
    assert {p.intento_envios for p in repo.paquetes.values()} == {1}
    assert db.commit.call_count == 2


def test_exactamente_500_salen_en_un_solo_lote():
    repo = _RepoMemoria(500)
    motor = _motor(return_value=True)
    resultado = DrenarPaquetesPendientesUseCase(Mock(), repo, motor).execute()
    assert resultado.lotes == [500]


def test_tamano_de_lote_menor_fragmenta_en_mas_lotes():
    repo = _RepoMemoria(501)
    resultado = DrenarPaquetesPendientesUseCase(Mock(), repo, _motor(return_value=True), tamano_lote=200).execute()
    assert resultado.lotes == [200, 200, 101]


@pytest.mark.parametrize("tamano", [0, MAX_REGISTROS_POR_ENVIO_INFERENCIA + 1])
def test_tamano_de_lote_fuera_del_limite_se_rechaza(tamano):
    with pytest.raises(ValidationError) as error:
        DrenarPaquetesPendientesUseCase(Mock(), _RepoMemoria(1), _motor(), tamano_lote=tamano)
    assert error.value.code == "TAMANO_LOTE_INVALIDO"


def test_sin_integracion_los_paquetes_siguen_pendientes():
    repo, db = _RepoMemoria(501), Mock()
    motor = Mock(wraps=MotorInferenciaStubAdapter())
    resultado = DrenarPaquetesPendientesUseCase(db, repo, motor).execute()
    assert resultado.motor_integrado is False and resultado.lotes == []
    assert motor.enviar_lote.call_count == 1
    assert repo.estados() == {"PENDIENTE"}
    assert {p.intento_envios for p in repo.paquetes.values()} == {0}
    db.rollback.assert_called_once()
    db.commit.assert_not_called()


def test_stub_de_lote_senala_falta_de_integracion():
    with pytest.raises(MotorInferenciaNoIntegradoError):
        MotorInferenciaStubAdapter().enviar_lote([])


@pytest.mark.parametrize("respuesta", [{"return_value": False}, {"side_effect": ConnectionError("sin red")}])
def test_lote_no_confirmado_queda_pendiente_con_un_intento(respuesta):
    # INC-M03-113-G56: RF-56 restricción 14, se reprograma en vez de quedar FALLIDO.
    repo = _RepoMemoria(3)
    resultado = DrenarPaquetesPendientesUseCase(Mock(), repo, _motor(**respuesta)).execute()
    assert resultado.reprogramados == 3 and resultado.fallidos == 0 and resultado.enviados == 0
    assert repo.estados() == {"PENDIENTE"}
    assert {p.intento_envios for p in repo.paquetes.values()} == {1}


def test_sin_pendientes_no_llama_al_motor():
    motor = _motor(return_value=True)
    resultado = DrenarPaquetesPendientesUseCase(Mock(), _RepoMemoria(0), motor).execute()
    assert resultado.lotes == [] and resultado.motor_integrado is True
    motor.enviar_lote.assert_not_called()


def test_max_lotes_acota_una_ejecucion():
    repo = _RepoMemoria(1200)
    resultado = DrenarPaquetesPendientesUseCase(Mock(), repo, _motor(return_value=True)).execute(max_lotes=2)
    assert resultado.lotes == [500, 500]
    assert sum(p.estado_paquete == "PENDIENTE" for p in repo.paquetes.values()) == 200


def test_fallo_al_guardar_estado_revierte_el_lote():
    repo, db = _RepoMemoria(2), Mock()
    repo.actualizar_estado = Mock(side_effect=RuntimeError("bd caida"))
    with pytest.raises(RuntimeError):
        DrenarPaquetesPendientesUseCase(db, repo, _motor(return_value=True)).execute()
    db.rollback.assert_called_once()
    db.commit.assert_not_called()


def test_listar_pendientes_ordena_por_captura_limita_y_salta_bloqueados(monkeypatch):
    capturado = {}

    def all_(query):
        capturado["sql"] = str(query.statement.compile(
            dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
        return []

    monkeypatch.setattr(Query, "all", all_)
    assert SqlAlchemyPaqueteInferenciaRepository(Session()).listar_pendientes(500) == []
    sql = " ".join(capturado["sql"].split())
    assert "estado_paquete = 'PENDIENTE'" in sql
    assert "ORDER BY modulo3.eventos_edge_computing.fecha_captura, modulo3.paquetes_inferencia.id_paquetes_inferencia" in sql
    assert "LIMIT 500" in sql
    assert "FOR UPDATE OF modulo3.paquetes_inferencia SKIP LOCKED" in sql or "FOR UPDATE OF paquetes_inferencia SKIP LOCKED" in sql


def test_paquete_generado_lleva_los_campos_obligatorios_de_rf56():
    """TC-M03-090: Salida de RF-56, campos obligatorios presentes en el paquete."""
    ts = datetime.now(timezone.utc) - timedelta(minutes=1)
    evento = EventoEdgeComputing(
        id_evento_edge_computing=7, id_sensor=3, id_dispositivo_iot=2,
        clasificacion_rf55="DESVIACION_SIMPLE", tipo_evento="ALERTA_GENERADA", severidad="MODERADO",
        fecha_captura=ts, fecha_procesamiento=ts + timedelta(milliseconds=200),
        origen_dato="TIEMPO_REAL", estado_conectividad=True,
        variables_involucradas=[{"tipo_variable": "TEMPERATURA_AMBIENTAL", "valor": "38.5000", "unidad": "°C"}],
    )
    repo = Mock(spec=PaqueteInferenciaRepository)
    repo.obtener_por_evento.return_value = None
    repo.guardar.side_effect = lambda p: replace(p, id_paquetes_inferencia=11)
    paquete = ConsolidarEnviarPaqueteUseCase(Mock(), repo, MotorInferenciaStubAdapter()).execute(evento)

    assert paquete.id_paquetes_inferencia == 11                      # id_paquete
    assert (paquete.id_sensor, paquete.id_dispositivo_iot) == (3, 2)  # sensor_id, dispositivo_id
    assert paquete.metadatos["timestamp_captura"] == ts.isoformat()
    assert paquete.metadatos["timestamp_procesamiento_edge"] == evento.fecha_procesamiento.isoformat()
    assert (paquete.tipo_variable, paquete.valor_numerico, paquete.unidad) == (
        "TEMPERATURA_AMBIENTAL", Decimal("38.5000"), "°C")
    assert paquete.estado_calidad == "LECTURA_VALIDA"
    assert (paquete.estado_desviacion, paquete.severidad, paquete.origen) == (
        "DESVIACION_SIMPLE", "MODERADO", "TIEMPO_REAL")
    assert paquete.estado_paquete == "PENDIENTE" and paquete.intento_envios == 0
