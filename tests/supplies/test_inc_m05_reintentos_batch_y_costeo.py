# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-08 | Arekkazu | INC-M05-259-G07 / INC-M05-264-G31: reintentos del batch ICA y del costeo directo |
# | 2026-11-12 | Leandro | INC-M05-350/351-G05 RF-74: verificar que finalizar conserva el corte manual y no repite su aviso. |
"""Reintentos de M05 sin base de datos.

- INC-M05-259-G07 (RF-74 E5): un error de BD traducido a 500 es fallo técnico (se reintenta y queda
  como fallo persistente con aviso), los activos que el límite dejó en cola cuentan como pendientes.
- INC-M05-264-G31 (RF-78 Restricción 9): intento inicial + 3 reintentos con esperas de 1, 3 y 5 s."""
from __future__ import annotations

import asyncio
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
    uc.ejecucion_repo = SimpleNamespace(obtener=lambda _id, **_: ejecucion, guardar=lambda e: e)
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


@pytest.mark.parametrize("corte_manual", [False, True])
def test_finalizar_solo_avisa_por_ventana_si_realiza_la_transicion(corte_manual):
    ahora = datetime.now(timezone.utc)
    corrida = EjecucionBatchICA(
        tipo_disparo="MANUAL", hora_inicio=ahora, num_workers=1,
        cantidad_activos_total=3, id_ejecucion=9,
    )
    if corte_manual:
        corrida.interrumpir(causa="MANUAL", hora_corte=ahora, id_usuario=137, motivo="Revisión")
    avisos = []

    final = _batch(None, avisos, corrida)._finalizar(
        9, procesados=1, fallos=[], interrumpido=True, en_cola_por_limite=2,
    )

    assert final.estado.value == "INTERRUMPIDO"
    assert final.cantidad_activos_procesados == 1
    assert final.cantidad_activos_pendientes == 4
    if corte_manual:
        assert (final.causa_interrupcion, final.motivo_interrupcion, final.hora_corte) == (
            "MANUAL", "Revisión", ahora,
        )
        assert avisos == []
    else:
        assert final.causa_interrupcion == "VENTANA_EXCEDIDA"
        assert len(avisos) == 1


def test_worker_encola_los_activos_restantes_despues_del_corte_manual():
    corrida = EjecucionBatchICA(
        tipo_disparo="MANUAL", hora_inicio=datetime.now(timezone.utc), num_workers=1,
        cantidad_activos_total=3, id_ejecucion=9,
    )
    uc = _batch(None, [], corrida)
    procesados, encolados = [], []
    uc._esta_interrumpido = lambda _: bool(procesados)

    def procesar(activo, *_):
        procesados.append(activo)

    uc._procesar_activo = procesar
    uc._encolar_pendiente = lambda trabajo, motivo: encolados.append((trabajo.id_activo, motivo.value))
    trabajos = [batch._Trabajo(id_activo, 100, None) for id_activo in (1, 2, 3)]

    resultado = asyncio.run(uc._procesar(trabajos, SimpleNamespace(ventana_horas=1), corrida, 1))

    assert resultado == (1, [], False)
    assert procesados == [1]
    assert encolados == [(2, "INTERRUMPIDO"), (3, "INTERRUMPIDO")]


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
