# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-20 | Arekkazu | DEV-31 RF-57: vencer por SLA audita el incumplimiento y escala CRITICO/MODERADO |
"""DEV-31 (RF-57 E10): la tarea periódica pasa a VENCIDA las alertas sin atender."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.telemetry.application.use_cases.alertas.vencer_alertas_sla_use_case import VencerAlertasSlaUseCase
from src.telemetry.domain.entities.alerta import Alerta

AHORA = datetime(2026, 10, 21, 12, 0, tzinfo=timezone.utc)


class _Db:
    def __init__(self): self.eventos = []
    def commit(self): self.eventos.append("commit")
    def rollback(self): self.eventos.append("rollback")


class _Repo:
    def __init__(self, alertas): self.alertas = alertas
    def vencer_activas_con_sla_cumplido(self, ahora, limite=200):
        assert ahora == AHORA
        return self.alertas


class _Bitacora:
    def __init__(self): self.registros = []
    def registrar(self, evento):
        evento.id_evento = len(self.registros) + 1
        self.registros.append(evento)
        return evento


def _alerta(id_, severidad):
    return Alerta(id_alerta=id_, tipo_alerta="ESTRES_TERMICO", severidad=severidad, estado_alerta="VENCIDA",
                  origen_evento="EDGE", tipo_variable="TEMPERATURA", fecha_evento=AHORA,
                  fecha_generacion=AHORA - timedelta(minutes=6), fecha_vencimiento=AHORA - timedelta(minutes=1))


@pytest.mark.parametrize("severidad, tipos", [
    ("CRITICO", ["SLA_ALERTA_INCUMPLIDO", "ESCALAMIENTO_ALERTA_SLA"]),
    ("MODERADO", ["SLA_ALERTA_INCUMPLIDO", "ESCALAMIENTO_ALERTA_SLA"]),
    ("LEVE", ["SLA_ALERTA_INCUMPLIDO"]),
])
def test_incumplimiento_siempre_y_escalamiento_salvo_leve(severidad, tipos):
    db, bitacora = _Db(), _Bitacora()
    n = VencerAlertasSlaUseCase(db, _Repo([_alerta(7, severidad)]), bitacora).execute(AHORA)
    assert n == 1
    assert [e.tipo_evento for e in bitacora.registros] == tipos
    assert {e.entidad_afectada_id for e in bitacora.registros} == {"7"}
    assert db.eventos[0] == "commit"  # la alerta se vence antes de auditar
    if severidad == "CRITICO":
        assert all(e.severidad_log.value == "CRITICAL" for e in bitacora.registros)


def test_sin_alertas_vencidas_no_audita():
    bitacora = _Bitacora()
    assert VencerAlertasSlaUseCase(_Db(), _Repo([]), bitacora).execute(AHORA) == 0
    assert bitacora.registros == []
