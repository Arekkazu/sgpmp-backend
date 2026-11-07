# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-03 | Arekkazu | RF-57 E7: un reintento por minuto elegido y pausa de 1 min si el SMTP falla |
"""RF-57 E7: la tarea corre cada 10 s; el reintento de correo no debe repetirse en cada vuelta.

En dev, con el SMTP caído, cada notificación se reintentaba ~6 veces por minuto
elegido y salían ~40 conexiones SMTP por minuto.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from src.telemetry.infrastructure.adapters import notificacion_alerta_rf14_adapter as modulo
from src.telemetry.infrastructure.adapters.notificacion_alerta_rf14_adapter import NotificacionAlertaRf14Adapter

INICIO = datetime(2026, 11, 3, 6, 0, tzinfo=timezone.utc)


class _Db:
    def __init__(self, filas): self.filas, self.actualizadas = filas, []
    def execute(self, sql, params=None):
        if "UPDATE" in str(sql):
            self.actualizadas.append(params["id"])
        return SimpleNamespace(all=lambda: list(self.filas))
    def commit(self): pass


def _fila(id_notificacion: int):
    return SimpleNamespace(id_notificacion=id_notificacion, mensaje="Alerta #1. Detalle", fecha_envio=INICIO,
                           correo_electronico=f"u{id_notificacion}@example.com")


@pytest.fixture(autouse=True)
def estado_limpio(monkeypatch):
    monkeypatch.setattr(modulo, "_minuto_reintentado", {}, raising=False)
    monkeypatch.setattr(modulo, "_pausa_hasta", None, raising=False)


def _cada_10_s(adaptador, desde: datetime, vueltas: int):
    for i in range(vueltas):
        adaptador.reintentar_fallidas(desde + timedelta(seconds=10 * i))


def test_un_solo_reintento_por_minuto_elegido(monkeypatch):
    envios = []
    monkeypatch.setattr(modulo, "send_email", lambda **kw: envios.append(kw["to"]))
    db = _Db([_fila(1), _fila(2)])

    # Las 6 vueltas del minuto 1 reintentan cada notificación una sola vez.
    _cada_10_s(NotificacionAlertaRf14Adapter(db), INICIO + timedelta(minutes=1), 6)

    assert sorted(envios) == ["u1@example.com", "u2@example.com"]
    assert sorted(db.actualizadas) == [1, 2]


def test_smtp_caido_una_conexion_por_minuto(monkeypatch):
    intentos = []

    def smtp_caido(**kw):
        intentos.append(kw["to"])
        raise ConnectionError("Connection unexpectedly closed")

    monkeypatch.setattr(modulo, "send_email", smtp_caido)
    db = _Db([_fila(i) for i in range(1, 21)])

    # 20 notificaciones en su minuto 16, durante todo ese minuto (6 vueltas).
    _cada_10_s(NotificacionAlertaRf14Adapter(db), INICIO + timedelta(minutes=16), 6)

    assert len(intentos) == 1  # antes: 20 por vuelta, 120 en el minuto
    assert db.actualizadas == []
