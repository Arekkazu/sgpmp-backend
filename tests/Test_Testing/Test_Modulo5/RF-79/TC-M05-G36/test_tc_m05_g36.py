# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-11-06 | Juan Manuel      | TC-M05-G36 RF-79: idempotencia de M06 y fallos de entrega |
"""TC-M05-G36 / TC-M05-059 y 061 (RF-79, CA-5, CA-9, CA-10, CA-13, E1, E7): idempotencia de la recepción en M06 y
fallos de entrega con reintentos, PROVISION_PENDIENTE y alertas.

No se ejecuta en TEST (requiere reenviar eventos y tumbar M06). Se prueban los casos de uso reales
(RecibirProvisionCostosUseCase de M06 y DespacharProvisionesM06UseCase de M05) con dobles en memoria.

Uso:  pytest tests/Test_Testing/Test_Modulo5/RF-79/TC-M05-G36 -v --noconftest
"""
from __future__ import annotations

import inspect
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.financial_valuation.application.use_cases.provision_costos.recibir_provision_costos_use_case import (
    RecibirProvisionCostosUseCase,
)
from src.financial_valuation.domain.entities.recepcion_provision import RecepcionProvision
from src.supplies.application.use_cases.provision_nic41 import despachar_provisiones_m06_use_case as mod_desp
from src.supplies.application.use_cases.provision_nic41.despachar_provisiones_m06_use_case import (
    DespacharProvisionesM06UseCase,
)
from src.supplies.domain.entities.evento_provision_m06 import EventoProvisionM06


class Sesion:
    def __init__(self):
        self.commits = self.rollbacks = 0

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


# ─────────────────────────────── TC-M05-059: idempotencia de la recepción ───────────────────────────────
class RecepcionesMemoria:
    """Emula la tabla recepciones_provisiones_m05 con su índice único por id_evento_provision."""

    def __init__(self):
        self.filas = {}

    def registrar_si_nueva(self, recepcion):
        if recepcion.id_evento_provision in self.filas:
            return False
        self.filas[recepcion.id_evento_provision] = recepcion
        return True


def _recepcion(id_evento):
    return RecepcionProvision(id_evento_provision=id_evento, modalidad="INCREMENTAL", schema_version="1.1",
                              id_activo_biologico=825, contenido={"costo_registro": "150000"}, id_gestion_fases=300)


def test_059a_mismo_evento_dos_veces_una_sola_recepcion_y_ack_en_ambas():
    repo, db, id_evento = RecepcionesMemoria(), Sesion(), uuid4()
    uc = RecibirProvisionCostosUseCase(db=db, repo=repo)
    a1 = uc.execute(_recepcion(id_evento))
    a2 = uc.execute(_recepcion(id_evento))
    assert (a1.recibido, a1.duplicado) == (True, False)
    assert (a2.recibido, a2.duplicado) == (True, True), "el reenvío se confirma (ACK) y se marca como duplicado"
    assert len(repo.filas) == 1, "solo existe 1 recepción"


def test_059b_el_repositorio_real_es_idempotente_por_id_evento_provision():
    """La idempotencia la da la BD: INSERT ... ON CONFLICT (id_evento_provision) DO NOTHING."""
    from src.financial_valuation.infrastructure.repositories import recepcion_provision_repository as mod
    fuente = inspect.getsource(mod)
    assert 'on_conflict_do_nothing(index_elements=["id_evento_provision"])' in fuente


# ─────────────────────────────── TC-M05-061: fallos de entrega ───────────────────────────────
class OutboxMemoria:
    def __init__(self, eventos, pendientes=0):
        self.eventos, self.pendientes = list(eventos), pendientes

    def listar_listos(self, ahora, limite):
        return [e for e in self.eventos if e.estado != "ENTREGADO" and (e.fecha_proximo_intento or ahora) <= ahora][:limite]

    def actualizar(self, evento):
        pass

    def contar_pendientes(self):
        return self.pendientes


class Registro:
    def __init__(self):
        self.eventos = []

    def registrar(self, e):
        self.eventos.append(e)


class Notificador:
    def __init__(self):
        self.avisos = []

    def a_permiso(self, id_recurso, id_accion, tipo_evento, mensaje, detalle):
        self.avisos.append((tipo_evento, mensaje))


class M06Caido:
    def __init__(self):
        self.intentos = []

    def entregar(self, evento):
        self.intentos.append(evento.id_evento_provision)
        raise ConnectionError("M06 no responde")


def _evento(gf=300, ahora=None):
    return EventoProvisionM06.incremental(
        id_activo_biologico=825, id_ciclo_productivo=4, id_gestion_fases=gf, id_registro_suministro=uuid4(),
        tipo_suministro="SERVICIO_VETERINARIO", tipo_operacion="REGISTRO", costo_registro=Decimal("150000"),
        acumulado_total_ciclo=Decimal("150000"), acumulado_por_categoria={"SERVICIO_VETERINARIO": Decimal("150000")},
        ahora=ahora or datetime.now(timezone.utc), fecha_aplicacion=datetime.now(timezone.utc).date())


class Reloj:
    """Reemplaza datetime en el módulo para avanzar el tiempo entre corridas del despachador."""

    def __init__(self, inicio):
        self.t = inicio

    def now(self, tz=None):
        return self.t


def _despachador(eventos, monkeypatch, pendientes=0):
    reloj = Reloj(datetime(2026, 11, 6, 12, 0, tzinfo=timezone.utc))
    monkeypatch.setattr(mod_desp, "datetime", SimpleNamespace(now=reloj.now))
    monkeypatch.setattr(mod_desp, "_ultima_alerta_critica", None)
    m06, aud, notif = M06Caido(), Registro(), Notificador()
    uc = DespacharProvisionesM06UseCase(db=Sesion(), outbox_repo=OutboxMemoria(eventos, pendientes), provision_repo=SimpleNamespace(),
                                        auditoria_port=aud, m06_port=m06, notificador=notif, id_usuario_sistema=1)
    return SimpleNamespace(uc=uc, reloj=reloj, m06=m06, aud=aud, notif=notif)


def test_061a_reintentos_a_5_15_30_60_s_y_provision_pendiente_al_quinto_fallo(monkeypatch):
    ev = _evento()
    d = _despachador([ev], monkeypatch)
    esperas = []
    for _ in range(5):
        ev.fecha_proximo_intento = d.reloj.t        # listo para reintentar ahora
        antes = d.reloj.t
        d.uc.ejecutar()
        if ev.estado != "PROVISION_PENDIENTE":
            esperas.append((ev.fecha_proximo_intento - antes).total_seconds())
        d.reloj.t = d.reloj.t + timedelta(seconds=61)
    assert esperas == [5, 15, 30, 60], f"esperas entre reintentos: {esperas}"
    assert ev.estado == "PROVISION_PENDIENTE" and ev.numero_intentos == 5
    assert len(ev.intentos_recientes) == 5, "se guardan los 5 timestamps de intento"


def test_061b_al_quinto_fallo_audita_y_notifica_al_administrador(monkeypatch):
    ev = _evento()
    d = _despachador([ev], monkeypatch)
    for _ in range(5):
        ev.fecha_proximo_intento = d.reloj.t
        d.uc.ejecutar()
        d.reloj.t += timedelta(seconds=61)
    tipos = [e.tipo_operacion for e in d.aud.eventos]
    assert tipos == ["PROVISION_INCREMENTAL_FALLIDA", "PROVISION_PENDIENTE"], f"eventos de auditoría: {tipos}"
    assert len(d.aud.eventos[0].fecha_intentos) == 5 and d.aud.eventos[0].numero_reintentos == 5
    assert [t for t, _ in d.notif.avisos] == ["PROVISION_M06_PENDIENTE"], "una sola notificación al administrador"


def test_061c_los_eventos_siguientes_del_mismo_ciclo_esperan(monkeypatch):
    ev1, ev2, otro = _evento(gf=300), _evento(gf=300), _evento(gf=301)
    d = _despachador([ev1, ev2, otro], monkeypatch)
    for e in (ev1, ev2, otro):
        e.fecha_proximo_intento = d.reloj.t
    d.uc.ejecutar()
    assert d.m06.intentos == [ev1.id_evento_provision, otro.id_evento_provision], (
        "tras fallar el primero del ciclo 300, el segundo del mismo ciclo no se intenta (orden cronológico)")


def test_061d_mas_de_10000_pendientes_alerta_critica(monkeypatch):
    d = _despachador([], monkeypatch, pendientes=10_001)
    d.uc.ejecutar()
    assert any("CRÍTICO" in m and "10001" in m for _, m in d.notif.avisos), f"avisos: {d.notif.avisos}"
