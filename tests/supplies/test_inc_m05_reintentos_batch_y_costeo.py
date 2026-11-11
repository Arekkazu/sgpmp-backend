# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-08 | Arekkazu | INC-M05-259-G07 / INC-M05-264-G31: reintentos del batch ICA y del costeo directo |
"""Reintentos de M05 sin base de datos.

- INC-M05-259-G07 (RF-74 E5): un error de BD traducido a 500 es fallo técnico (se reintenta y queda
  como fallo persistente con aviso), los activos que el límite dejó en cola cuentan como pendientes.
- INC-M05-264-G31 (RF-78 Restricción 9): intento inicial + 3 reintentos con esperas de 1, 3 y 5 s."""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from src.shared.errors import BusinessRuleError, InfrastructureError, es_fallo_tecnico
from src.supplies.application.use_cases.costeo_suministros import registrar_suministro_directo_use_case as directo
from src.supplies.application.use_cases.eficiencia import ejecutar_batch_ica_use_case as batch
from src.supplies.domain.entities.ejecucion_batch_ica import EjecucionBatchICA


class _Sesion:
    def rollback(self): pass
    def commit(self): pass
    def close(self): pass


def _batch(calculo, alertas: list, ejecucion: EjecucionBatchICA | None = None) -> batch.EjecutarBatchICAUseCase:
    uc = object.__new__(batch.EjecutarBatchICAUseCase)
    uc.db = _Sesion()
    uc.session_factory = _Sesion
    uc.construir_calculo = lambda db: calculo
    uc.construir_fallo_repo = lambda db: SimpleNamespace(registrar=lambda fallo: alertas.append(("fallo", fallo)))
    uc.notificador = SimpleNamespace(a_permiso=lambda *a: alertas.append(("aviso", a)))
    uc.ejecucion_repo = SimpleNamespace(obtener=lambda _id: ejecucion, guardar=lambda e: e)
    return uc


_CONFIG = SimpleNamespace(max_reintentos=3, backoff_minutos=[2, 4, 6])


def test_es_fallo_tecnico_separa_5xx_de_reglas_de_negocio():
    assert es_fallo_tecnico(RuntimeError("conexión perdida"))
    assert es_fallo_tecnico(InfrastructureError(code="ERROR_INTERNO", message="Error interno"))
    assert not es_fallo_tecnico(BusinessRuleError(code="ACTIVO_NO_ACTIVO", message="El activo no está activo."))


def test_error_de_bd_500_se_reintenta_y_queda_como_fallo_persistente(monkeypatch):
    esperas, registros = [], []
    monkeypatch.setattr(batch.time, "sleep", esperas.append)
    calculo = SimpleNamespace(execute=lambda **kw: (_ for _ in ()).throw(
        InfrastructureError(code="ERROR_INTERNO", message="Error interno de base de datos")))

    fallo = _batch(calculo, registros)._procesar_activo(7, _CONFIG, id_ejecucion=53)

    assert esperas == [120.0, 240.0, 360.0]  # 3 reintentos tras el intento inicial: 2, 4 y 6 minutos
    assert fallo["id_activo_biologico"] == 7 and fallo["causa_fallo"] == "Error interno de base de datos"
    [(_, persistente)] = registros
    assert (persistente.intentos, persistente.id_ejecucion_batch) == (3, 53)


def test_regla_de_negocio_no_se_reintenta(monkeypatch):
    esperas = []
    monkeypatch.setattr(batch.time, "sleep", esperas.append)
    calculo = SimpleNamespace(execute=lambda **kw: (_ for _ in ()).throw(
        BusinessRuleError(code="ACTIVO_NO_ACTIVO", message="El activo no está activo.")))
    assert _batch(calculo, [])._procesar_activo(7, _CONFIG, id_ejecucion=1) is None
    assert esperas == []


def test_finalizar_conserva_los_encolados_por_limite_y_avisa_los_fallos():
    ejecucion = EjecucionBatchICA(tipo_disparo="AUTOMATICO", hora_inicio=datetime.now(timezone.utc), num_workers=1,
                                  cantidad_activos_total=2, cantidad_activos_pendientes=1, id_ejecucion=9)
    avisos: list = []
    fallo = {"id_activo_biologico": 7, "causa_fallo": "x", "timestamp_ultimo_intento": "2026-11-08T00:00:00+00:00"}

    final = _batch(None, avisos, ejecucion)._finalizar(9, procesados=2, fallos=[fallo], interrumpido=False,
                                                       en_cola_por_limite=1)

    assert (final.estado.value, final.cantidad_fallidos, final.cantidad_activos_pendientes) == ("COMPLETADO", 1, 1)
    [(_, (_recurso, _accion, _tipo, mensaje, detalle))] = avisos
    assert "1 activo(s)" in mensaje and detalle["fallos"] == [fallo]


def test_costeo_directo_hace_tres_reintentos_con_esperas_de_1_3_y_5_segundos(monkeypatch):
    esperas, fallidos = [], []
    monkeypatch.setattr(directo.time, "sleep", esperas.append)
    uc = object.__new__(directo.RegistrarSuministroDirectoUseCase)
    uc.db = _Sesion()
    uc.registro_repo = SimpleNamespace(guardar=lambda e: (_ for _ in ()).throw(
        InfrastructureError(code="ERROR_INTERNO", message="Error interno de base de datos")))
    uc._registrar_fallo = lambda entidad, usuario, causa: fallidos.append(causa)

    with pytest.raises(InfrastructureError):
        uc._persistir_con_reintentos(SimpleNamespace(), SimpleNamespace(id_usuario=1))

    assert esperas == [1, 3, 5] and fallidos == ["Error interno de base de datos"]
