# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-23 | destroyerban | DEV-37 RF-73: reintentos, respaldo local y sincronización de la bitácora M04 |
# | 2026-10-27 | Leandro | INC-M04-158-G086 RF-73: mantener pruebas de contingencia con un evento de entrada valido. |
"""DEV-37 (RF-73 E2, E8 y CA-14): reintentos, respaldo local y sincronización de la bitácora de M04.

E2: N reintentos ante una falla de persistencia; si todos fallan, el evento va al
respaldo local junto con AUDITORIA_FALLA_PERSISTENCIA (CRITICAL). E8: al
recuperarse la BD, el respaldo se sincroniza en orden con origen FALLBACK, la
fecha original y la alerta AUDITORIA_FALLBACK_ACTIVADO al Administrador.
"""
from __future__ import annotations

import contextlib
import json
from datetime import datetime, timezone

import pytest

from src.prediction.application.use_cases.auditoria.sincronizar_respaldo_auditoria_m04_use_case import (
    SincronizarRespaldoAuditoriaM04UseCase,
)
from src.prediction.infrastructure.adapters.respaldo_auditoria_m04_archivo_adapter import (
    RespaldoAuditoriaM04ArchivoAdapter,
)
from src.prediction.infrastructure.repositories.evento_auditoria_m04_repository import (
    SqlAlchemyEventoAuditoriaM04Repository,
)
from src.shared.errors import InfrastructureError

HOY = datetime.now(timezone.utc).strftime("%Y%m%d")


class _Sesion:
    """Falla los primeros ``fallas`` flush; cada intento va en su savepoint."""

    def __init__(self, fallas: int):
        self.fallas, self.flushes, self.guardados, self._pendiente = fallas, 0, [], None

    def begin_nested(self): return contextlib.nullcontext()
    def add(self, orm): self._pendiente = orm

    def flush(self):
        self.flushes += 1
        if self.flushes <= self.fallas:
            raise RuntimeError("could not connect to server")
        self.guardados.append(self._pendiente)


class _RespaldoMemoria:
    def __init__(self): self.eventos = []
    def guardar(self, evento): self.eventos.append(json.loads(json.dumps(evento, default=str)))


def _registrar(sesion, respaldo, severidad="CRITICAL", reintentos=3):
    repo = SqlAlchemyEventoAuditoriaM04Repository(sesion, respaldo, reintentos=reintentos, pausa_reintento=0)
    repo.registrar(
        tipo_evento="INTENTO_CARGA_MODELO_EXTERNO", tipo_actor="SISTEMA", id_sistema="DESCONOCIDO",
        severidad_evento=severidad, id_referencia="p-1", entidad_referencia="proceso_rf71", payload_evento={"motivo": "clave ausente", "id_proceso_rf71": "p-1"},
    )


# ── E2: reintentos ─────────────────────────────────────────────────────────

def test_una_falla_transitoria_se_resuelve_con_un_reintento_sin_respaldo():
    sesion, respaldo = _Sesion(fallas=2), _RespaldoMemoria()
    _registrar(sesion, respaldo)
    assert sesion.flushes == 3 and len(sesion.guardados) == 1
    assert sesion.guardados[0].origen_registro == "DESARROLLO_M04"
    assert respaldo.eventos == []


def test_tras_n_intentos_fallidos_el_evento_va_al_respaldo_con_la_falla_critica():
    sesion, respaldo = _Sesion(fallas=99), _RespaldoMemoria()
    _registrar(sesion, respaldo, reintentos=4)  # no lanza: el evento quedó a salvo (RNF-07)

    assert sesion.flushes == 4
    original, falla = respaldo.eventos
    assert original["tipo_evento"] == "INTENTO_CARGA_MODELO_EXTERNO"
    assert original["severidad_evento"] == "CRITICAL" and original["id_evento"] and original["fecha_evento"]
    assert original["payload_evento"]["id_proceso_rf71"] == "p-1" and original["hash_evento"]
    assert original["respaldo"]["motivo"] == "FALLA_PERSISTENCIA"

    assert (falla["tipo_evento"], falla["severidad_evento"], falla["resultado_operacion"]) == (
        "AUDITORIA_FALLA_PERSISTENCIA", "CRITICAL", "FALLIDO")
    assert (falla["tipo_actor"], falla["id_sistema"], falla["id_usuario"]) == ("SISTEMA", "DESARROLLO_M04", None)
    assert falla["payload_evento"]["id_evento_original"] == original["id_evento"]
    assert falla["payload_evento"]["intentos"] == 4
    assert falla["correlacion_id"] == original["correlacion_id"]


def test_un_evento_info_tampoco_se_pierde():
    respaldo = _RespaldoMemoria()
    _registrar(_Sesion(fallas=99), respaldo, severidad="INFO")
    assert [e["tipo_evento"] for e in respaldo.eventos] == ["INTENTO_CARGA_MODELO_EXTERNO", "AUDITORIA_FALLA_PERSISTENCIA"]


def test_sin_respaldo_posible_se_lanza_500():
    class _RespaldoRoto:
        def guardar(self, _evento): raise OSError("disco lleno")
    with pytest.raises(InfrastructureError) as exc:
        _registrar(_Sesion(fallas=99), _RespaldoRoto())
    assert exc.value.code == "AUDITORIA_M04_NO_PERSISTIDA"


# ── Respaldo en archivo ────────────────────────────────────────────────────

def test_el_respaldo_va_a_audit_fallback_M04_YYYYMMDD_log(tmp_path):
    respaldo = RespaldoAuditoriaM04ArchivoAdapter(tmp_path)
    respaldo.guardar({"tipo_evento": "A", "fecha_evento": "2026-10-23T10:00:00+00:00", "id_evento": "1"})
    archivo = tmp_path / f"audit_fallback_M04_{HOY}.log"
    assert json.loads(archivo.read_text(encoding="utf-8"))["tipo_evento"] == "A"
    assert respaldo.hay_pendientes()


def test_los_pendientes_salen_en_orden_y_se_descartan_al_terminar(tmp_path):
    (tmp_path / "audit_fallback_M04_20261022.log").write_text(
        json.dumps({"id_evento": "1", "fecha_evento": "2026-10-22T23:59:00+00:00", "tipo_evento": "A"}) + "\n", encoding="utf-8")
    respaldo = RespaldoAuditoriaM04ArchivoAdapter(tmp_path)
    respaldo.guardar({"id_evento": "2", "fecha_evento": "2026-10-23T00:01:00+00:00", "tipo_evento": "B"})
    respaldo.guardar({"id_evento": "3", "fecha_evento": "2026-10-23T00:02:00+00:00", "tipo_evento": "C"})

    with respaldo.pendientes() as pendientes:
        assert [e["id_evento"] for e in pendientes] == ["1", "2", "3"]
    assert not respaldo.hay_pendientes()


def test_si_la_sincronizacion_falla_el_respaldo_se_conserva(tmp_path):
    respaldo = RespaldoAuditoriaM04ArchivoAdapter(tmp_path)
    respaldo.guardar({"id_evento": "1", "fecha_evento": "2026-10-23T00:01:00+00:00", "tipo_evento": "A"})
    with pytest.raises(RuntimeError):
        with respaldo.pendientes():
            raise RuntimeError("la BD sigue caída")
    assert respaldo.hay_pendientes()
    respaldo.guardar({"id_evento": "2", "fecha_evento": "2026-10-23T00:02:00+00:00", "tipo_evento": "B"})
    with respaldo.pendientes() as pendientes:
        assert [e["id_evento"] for e in pendientes] == ["1", "2"]


def test_una_linea_del_formato_anterior_se_completa_con_id_estable(tmp_path):
    linea = json.dumps({"tipo_evento": "INTENTO_CARGA_MODELO_EXTERNO", "correlacion_id": "c-1", "origen_registro": "FALLBACK"})
    (tmp_path / "audit_fallback_M04_20261020.log").write_text(linea + "\n" + "{roto\n", encoding="utf-8")
    respaldo = RespaldoAuditoriaM04ArchivoAdapter(tmp_path)
    with pytest.raises(RuntimeError):
        with respaldo.pendientes() as primera:
            raise RuntimeError
    with respaldo.pendientes() as segunda:
        assert len(segunda) == 1  # la línea truncada se descarta
        assert segunda[0]["id_evento"] == primera[0]["id_evento"]  # no se duplica al reintentar
        assert segunda[0]["fecha_evento"] == "2026-10-20T00:00:00+00:00"
        assert segunda[0]["respaldo"]["fecha_aproximada"] is True


# ── E8: sincronización ─────────────────────────────────────────────────────

class _Db:
    def __init__(self): self.commits = self.rollbacks = 0
    def commit(self): self.commits += 1
    def rollback(self): self.rollbacks += 1


class _RepoBitacora:
    def __init__(self, caida=False):
        self.caida, self.insertados, self.registrados = caida, [], []

    def insertar_desde_respaldo(self, evento):
        if self.caida:
            raise InfrastructureError(code="AUDITORIA_M04_NO_PERSISTIDA", message="caída")
        if evento["id_evento"] in self.insertados:
            return False
        self.insertados.append(evento["id_evento"])
        return True

    def registrar(self, **kw): self.registrados.append(kw)


class _Aviso:
    def __init__(self, db): self.db, self.avisos = db, []
    def avisar_fallback_activado(self, resumen): self.avisos.append((resumen, self.db.commits))


def _sincronizar(tmp_path, repo, db=None):
    db = db or _Db()
    aviso = _Aviso(db)
    respaldo = RespaldoAuditoriaM04ArchivoAdapter(tmp_path)
    resultado = SincronizarRespaldoAuditoriaM04UseCase(db=db, repo=repo, respaldo=respaldo, aviso=aviso).execute()
    return resultado, aviso, respaldo


def _respaldar_caida(tmp_path):
    """Dos eventos que no se pudieron persistir, como los deja el repositorio."""
    respaldo = _RespaldoMemoria()
    _registrar(_Sesion(fallas=99), respaldo)
    _registrar(_Sesion(fallas=99), respaldo, severidad="ERROR")
    archivo = RespaldoAuditoriaM04ArchivoAdapter(tmp_path)
    for evento in respaldo.eventos:
        archivo.guardar(evento)
    return respaldo.eventos


def test_al_recuperarse_sincroniza_en_orden_y_alerta_al_administrador(tmp_path):
    eventos = _respaldar_caida(tmp_path)
    repo, db = _RepoBitacora(), _Db()
    resultado, aviso, respaldo = _sincronizar(tmp_path, repo, db)

    assert repo.insertados == [e["id_evento"] for e in eventos]  # FIFO
    assert resultado.eventos_sincronizados == 4
    alerta = repo.registrados[0]
    assert (alerta["tipo_evento"], alerta["severidad_evento"]) == ("AUDITORIA_FALLBACK_ACTIVADO", "CRITICAL")
    assert alerta["payload_evento"]["inicio_contingencia"] == eventos[0]["fecha_evento"]
    assert alerta["payload_evento"]["fallas_persistencia"] == 2
    assert db.commits == 1 and not respaldo.hay_pendientes()
    # El aviso sale después del commit, con el inicio de la contingencia.
    (resumen, commits_al_avisar), = aviso.avisos
    assert commits_al_avisar == 1 and resumen["inicio_contingencia"] == eventos[0]["fecha_evento"]


def test_con_la_bd_aun_caida_no_se_pierde_nada_ni_se_avisa(tmp_path):
    _respaldar_caida(tmp_path)
    db = _Db()
    with pytest.raises(InfrastructureError):
        _sincronizar(tmp_path, _RepoBitacora(caida=True), db)
    assert db.rollbacks == 1
    _, aviso, respaldo = _sincronizar(tmp_path, _RepoBitacora())  # al volver la BD
    assert len(aviso.avisos) == 1 and not respaldo.hay_pendientes()


def test_sin_respaldo_no_toca_la_bd(tmp_path):
    repo, db = _RepoBitacora(), _Db()
    resultado, aviso, _ = _sincronizar(tmp_path, repo, db)
    assert resultado.eventos_sincronizados == 0 and db.commits == 0 and aviso.avisos == []


def test_un_evento_ya_sincronizado_no_se_duplica(tmp_path):
    eventos = _respaldar_caida(tmp_path)
    repo = _RepoBitacora()
    repo.insertados.append(eventos[0]["id_evento"])  # una sincronización previa alcanzó a guardarlo
    resultado, _, _ = _sincronizar(tmp_path, repo)
    assert (resultado.eventos_sincronizados, resultado.eventos_ya_presentes) == (3, 1)
