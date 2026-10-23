# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-23 | Arekkazu | DEV-37 RF-73 E2/E8: reintentos, respaldo local y sincronización FIFO |
"""DEV-37 (RF-73): E2 reintenta ante una falla transitoria y, agotados los intentos,
deja el evento y AUDITORIA_FALLA_PERSISTENCIA en el respaldo local; E8 sincroniza el
respaldo en orden, sin duplicar, y avisa al Administrador."""
from __future__ import annotations

import contextlib
import json
import uuid

import pytest
from sqlalchemy.exc import IntegrityError, OperationalError

from src.prediction.application.use_cases.auditoria.sincronizar_fallback_auditoria_m04_use_case import (
    SincronizarFallbackAuditoriaM04UseCase,
)
from src.prediction.domain.repositories.fallback_auditoria_m04_port import LoteFallback
from src.prediction.infrastructure.adapters.fallback_auditoria_m04_archivo import FallbackAuditoriaM04Archivo
from src.prediction.infrastructure.repositories import evento_auditoria_m04_repository as repo_mod
from src.shared.errors import InfrastructureError


class _Session:
    """flush falla con los errores de la lista, en orden; luego acepta."""

    def __init__(self, errores):
        self.errores = list(errores)
        self.agregados = []
        self.intentos = 0

    @contextlib.contextmanager
    def begin_nested(self):
        yield

    def add(self, orm): self.agregados.append(orm)

    def flush(self):
        self.intentos += 1
        if self.errores:
            self.agregados.pop()
            raise self.errores.pop(0)


class _Fallback:
    def __init__(self): self.escritos = []
    def escribir(self, evento): self.escritos.append(evento)


def _caida():
    return OperationalError("INSERT", {}, Exception("server closed the connection unexpectedly"))


def _registrar(db, fallback):
    repo_mod.SqlAlchemyEventoAuditoriaM04Repository(db, fallback).registrar(
        tipo_evento="HISTORIAL_CONSULTADO", tipo_actor="SISTEMA", id_sistema="DESARROLLO_M04",
        payload_evento={"x": 1},
    )


@pytest.fixture(autouse=True)
def _sin_espera(monkeypatch):
    monkeypatch.setattr(repo_mod.time, "sleep", lambda _s: None)


def test_falla_transitoria_se_reintenta_y_se_guarda_sin_respaldo():
    db, fallback = _Session([_caida(), _caida()]), _Fallback()
    _registrar(db, fallback)
    assert db.intentos == 3 and len(db.agregados) == 1
    assert fallback.escritos == []


def test_agotados_los_intentos_va_al_respaldo_con_falla_persistencia_critica():
    db, fallback = _Session([_caida()] * 3), _Fallback()
    with pytest.raises(InfrastructureError):
        _registrar(db, fallback)
    assert db.intentos == 3
    original, falla = fallback.escritos
    assert original["tipo_evento"] == "HISTORIAL_CONSULTADO" and original["id_evento"] and original["fecha_evento"]
    assert falla["tipo_evento"] == "AUDITORIA_FALLA_PERSISTENCIA" and falla["severidad_evento"] == "CRITICAL"
    assert falla["payload_evento"]["id_evento_respaldado"] == str(original["id_evento"])


def test_error_no_transitorio_no_se_reintenta_ni_va_al_respaldo():
    # Fallaría igual al sincronizar y trabaría la cola FIFO del respaldo.
    db, fallback = _Session([IntegrityError("INSERT", {}, Exception("check"))]), _Fallback()
    with pytest.raises(InfrastructureError):
        _registrar(db, fallback)
    assert db.intentos == 1 and fallback.escritos == []


def test_archivo_de_respaldo_fifo_y_marca_sincronizado(tmp_path):
    archivo = FallbackAuditoriaM04Archivo(tmp_path)
    archivo.escribir({"id_evento": uuid.uuid4(), "fecha_evento": "2026-10-23T01:00:00+00:00", "tipo_evento": "A"})
    archivo.escribir({"id_evento": uuid.uuid4(), "fecha_evento": "2026-10-23T01:00:01+00:00", "tipo_evento": "B"})
    lote, = archivo.pendientes()
    assert [e["tipo_evento"] for e in lote.eventos] == ["A", "B"]
    assert all(e["origen_registro"] == "FALLBACK" for e in lote.eventos)
    archivo.marcar_sincronizado(lote.identificador)
    assert archivo.pendientes() == []


class _Repo:
    def __init__(self, fallar_en=None):
        self.insertados, self.registrados, self.fallar_en = [], [], fallar_en

    def registrar_desde_fallback(self, evento):
        if evento["tipo_evento"] == self.fallar_en:
            raise RuntimeError("la BD sigue caída")
        if evento["id_evento"] in [e["id_evento"] for e in self.insertados]:
            return False
        self.insertados.append(evento)
        return True

    def registrar(self, **kw): self.registrados.append(kw)


class _Lotes:
    def __init__(self, lotes): self.lotes, self.marcados = lotes, []
    def pendientes(self): return [l for l in self.lotes if l.identificador not in self.marcados]
    def marcar_sincronizado(self, ident): self.marcados.append(ident)


class _Aviso:
    def __init__(self): self.avisos = []
    def avisar_fallback_activado(self, **kw): self.avisos.append(kw)


class _Db:
    def __init__(self): self.commits = self.rollbacks = 0
    def commit(self): self.commits += 1
    def rollback(self): self.rollbacks += 1


def _evento(tipo, fecha):
    return {"id_evento": str(uuid.uuid4()), "fecha_evento": fecha, "tipo_evento": tipo}


def test_sincroniza_fifo_registra_fallback_activado_y_avisa():
    lotes = _Lotes([LoteFallback("a", [_evento("A", "2026-10-22T10:00:00+00:00")]),
                    LoteFallback("b", [_evento("B", "2026-10-23T10:00:00+00:00")])])
    repo, aviso = _Repo(), _Aviso()
    r = SincronizarFallbackAuditoriaM04UseCase(db=_Db(), repo=repo, fallback=lotes, aviso=aviso).execute()
    assert [e["tipo_evento"] for e in repo.insertados] == ["A", "B"] and lotes.marcados == ["a", "b"]
    assert (r.eventos, r.lotes, r.inicio_contingencia) == (2, 2, "2026-10-22T10:00:00+00:00")
    activado, = repo.registrados
    assert activado["tipo_evento"] == "AUDITORIA_FALLBACK_ACTIVADO" and activado["severidad_evento"] == "CRITICAL"
    assert aviso.avisos == [{"inicio_contingencia": "2026-10-22T10:00:00+00:00", "eventos": 2}]


def test_si_la_bd_vuelve_a_fallar_el_lote_queda_y_no_se_adelanta_el_siguiente():
    lotes = _Lotes([LoteFallback("a", [_evento("A", "2026-10-22T10:00:00+00:00")]),
                    LoteFallback("b", [_evento("B", "2026-10-23T10:00:00+00:00")])])
    repo, db, aviso = _Repo(fallar_en="A"), _Db(), _Aviso()
    r = SincronizarFallbackAuditoriaM04UseCase(db=db, repo=repo, fallback=lotes, aviso=aviso).execute()
    assert r.eventos == 0 and lotes.marcados == [] and repo.insertados == [] and aviso.avisos == []
    assert db.rollbacks == 1


def test_sin_respaldo_no_hace_nada():
    repo, aviso = _Repo(), _Aviso()
    r = SincronizarFallbackAuditoriaM04UseCase(db=_Db(), repo=repo, fallback=_Lotes([]), aviso=aviso).execute()
    assert r.lotes == 0 and repo.registrados == [] and aviso.avisos == []
