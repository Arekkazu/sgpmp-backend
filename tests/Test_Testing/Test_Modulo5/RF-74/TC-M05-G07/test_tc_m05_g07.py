# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-11-06 | Juan Manuel      | TC-M05-G07 RF-74: fallos, reintentos, ventana y límite del batch |
# | 2026-11-06 | Juan Manuel      | TC-M05-G07: fallo técnico traducido (InfrastructureError) en el batch |
"""TC-M05-G07 / TC-M05-018 (RF-74, CU02 E5, FA-04…FA-07): fallo técnico del cálculo, reintentos del batch,
ventana de ejecución y límite de activos.

No se ejecuta en TEST: hay que inyectar fallos y controlar el tiempo. Se prueba sobre los casos de uso
reales (CalcularICAUseCase y EjecutarBatchICAUseCase), con los puertos reemplazados por dobles en
memoria. La ficha pide "Postgres local con los repositorios reales", pero en este entorno no hay base
local. Las reglas que se verifican (rollback, reintentos con backoff, fallo persistente, ventana,
límite y prioridad) viven en los casos de uso, no en los repositorios.

Uso:  pytest tests/Test_Testing/Test_Modulo5/RF-74/TC-M05-G07 -v
"""
from __future__ import annotations

import asyncio
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest

from src.shared.errors import InfrastructureError
from src.supplies.application.use_cases.eficiencia import ejecutar_batch_ica_use_case as modulo_batch
from src.supplies.application.use_cases.eficiencia.calcular_ica_use_case import CalcularICAUseCase
from src.supplies.application.use_cases.eficiencia.ejecutar_batch_ica_use_case import EjecutarBatchICAUseCase
from src.supplies.domain.repositories.activo_consulta_port import ActivoConsulta
from src.supplies.domain.repositories.activos_batch_port import ActivoBatchRef
from src.supplies.domain.repositories.configuracion_batch_ica_repository import ConfiguracionBatch
from src.supplies.domain.value_objects.eficiencia_enums import (
    CausaInterrupcionBatch,
    EstadoEjecucionBatch,
    MotivoEncolado,
    PeriodoEvaluacion,
    TipoCalculo,
)


# ─────────────────────────────── dobles ───────────────────────────────
class SesionFalsa:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0
        self.cerrada = False

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.cerrada = True


class ResultadoRepoQueFalla:
    """La persistencia del resultado lanza un error técnico (no AppError)."""

    def __init__(self):
        self.guardados = []

    def guardar(self, resultado):
        raise RuntimeError("fallo inyectado al persistir resultado_ica")

    def tiene_vigente_critica(self, id_activo):
        return False


class Registro:
    def __init__(self):
        self.eventos = []

    def registrar(self, evento):
        self.eventos.append(evento)


def _activo(id_activo=825):
    return ActivoConsulta(id_activo_biologico=id_activo, tipo="INDIVIDUAL", id_estado=1, nombre_estado="ACTIVO",
                          cantidad_actual=None, fecha_inicio_ciclo=date(2026, 10, 12))


def _calculo_manual(db, resultado_repo, auditoria):
    return CalcularICAUseCase(
        db=db,
        resultado_repo=resultado_repo,
        consumo_read_port=SimpleNamespace(sumar_alimento_validado=lambda *a: Decimal("30")),
        pesaje_port=SimpleNamespace(
            obtener_peso_en_o_antes=lambda id_, f, pob: Decimal("100") if f.day % 2 else Decimal("113"),
            obtener_peso_invalido_en_o_antes=lambda *a: None,
        ),
        activo_port=SimpleNamespace(obtener=lambda id_: _activo(id_)),
        ciclo_port=SimpleNamespace(obtener_abierto=lambda id_: None),
        alerta_port=SimpleNamespace(generar_alerta_critica=lambda **k: None),
        auditoria_port=auditoria,
    )


def _config(**cambios):
    base = dict(limite_activos=5000, num_workers_max=4, umbral_paralelizacion=500, ventana_horas=4,
                hora_ejecucion=time(2, 0), max_reintentos=3, backoff_minutos=[2, 4, 6], es_activo=True)
    base.update(cambios)
    return ConfiguracionBatch(**base)


class EjecucionRepoMemoria:
    def __init__(self, atrasar_inicio=False):
        self.ejecucion = None
        self.atrasar_inicio = atrasar_inicio

    def obtener_en_ejecucion(self):
        return None

    def crear(self, ejecucion):
        ejecucion.id_ejecucion = 900
        if self.atrasar_inicio:   # la corrida "empezó" hace 1 h: con ventana_horas=0 ya venció (sin depender del reloj)
            ejecucion.hora_inicio = ejecucion.hora_inicio - timedelta(hours=1)
        self.ejecucion = ejecucion
        return ejecucion

    def obtener(self, id_ejecucion):
        return self.ejecucion

    def guardar(self, ejecucion):
        self.ejecucion = ejecucion
        return ejecucion


class ColaMemoria:
    def __init__(self):
        self.encolados = []

    def encolar(self, item):
        self.encolados.append(item)

    def listar_pendientes(self):
        return []


class Notificador:
    def __init__(self):
        self.avisos = []

    def a_permiso(self, id_recurso, id_accion, tipo_evento, mensaje, detalle):
        self.avisos.append((id_recurso, tipo_evento, mensaje))

    def a_responsables_activo(self, *a):
        pass


def _batch(config, activos, *, calculo_falla=False, error=None, criticos=(), atrasar_inicio=False, monkeypatch):
    sesiones, fallos, encolados_ventana, notif = [], Registro(), [], Notificador()

    def fabrica_sesion():
        s = SesionFalsa()
        sesiones.append(s)
        return s

    intentos = []

    def construir_calculo(db):
        def execute(**k):
            intentos.append((k["id_activo_biologico"], k["periodo"], k["tipo_calculo"], k["intento"]))
            if error is not None:
                raise error
            if calculo_falla:
                raise RuntimeError("BD caída (fallo técnico inyectado)")
        return SimpleNamespace(execute=execute)

    uc = EjecutarBatchICAUseCase(
        db=SesionFalsa(),
        ejecucion_repo=EjecucionRepoMemoria(atrasar_inicio),
        cola_repo=ColaMemoria(),
        config_repo=SimpleNamespace(obtener=lambda: config),
        activos_batch_port=SimpleNamespace(listar_activos_para_batch=lambda: activos),
        resultado_repo=SimpleNamespace(tiene_vigente_critica=lambda id_: id_ in criticos),
        session_factory=fabrica_sesion,
        construir_calculo=construir_calculo,
        construir_fallo_repo=lambda db: fallos,
        notificador=notif,
    )
    esperas = []
    monkeypatch.setattr(modulo_batch.time, "sleep", lambda s: esperas.append(s))
    # Estos tres métodos abren repositorios SQLAlchemy concretos: se reemplazan para no necesitar BD.
    monkeypatch.setattr(uc, "_esta_interrumpido", lambda id_: False)
    monkeypatch.setattr(uc, "_encolar_pendiente", lambda t, motivo: encolados_ventana.append((t.id_activo, motivo)))
    monkeypatch.setattr(uc, "_marcar_cola", lambda id_: None)
    return SimpleNamespace(uc=uc, intentos=intentos, esperas=esperas, fallos=fallos, notif=notif,
                           encolados_ventana=encolados_ventana, sesiones=sesiones)


# ─────────────────────────────── TC-M05-018 ───────────────────────────────
def test_018a_fallo_manual_responde_500_hace_rollback_y_audita_el_paso():
    db, auditoria, repo = SesionFalsa(), Registro(), ResultadoRepoQueFalla()
    uc = _calculo_manual(db, repo, auditoria)
    with pytest.raises(InfrastructureError) as exc:
        uc.execute(id_activo_biologico=825, periodo=PeriodoEvaluacion.SEMANAL, tipo_calculo=TipoCalculo.MANUAL, id_usuario=137)
    assert exc.value.code == "ERROR_CALCULO_CA"
    assert "La operación fue revertida" in exc.value.message
    assert db.rollbacks >= 1, "el cálculo manual debe revertir la transacción"
    assert repo.guardados == [], "no debe quedar fila nueva en resultado_ica"
    assert len(auditoria.eventos) == 1, "E5: el fallo manual queda en la bitácora de M05"
    ev = auditoria.eventos[0]
    assert ev.tipo_operacion == "REGISTRO_FALLIDO" and ev.resultado == "FALLIDO" and ev.id_usuario == 137
    assert "paso_fallido=persistir_resultado" in ev.detalle_causa and "fallo inyectado" in ev.detalle_causa


def test_018b_batch_reintenta_3_veces_con_backoff_y_registra_fallo_persistente(monkeypatch):
    b = _batch(_config(), [ActivoBatchRef(id_activo_biologico=825, fecha_inicio_ciclo=date(2026, 10, 12))],
               calculo_falla=True, monkeypatch=monkeypatch)
    ejecucion = asyncio.run(b.uc.ejecutar(tipo_disparo="AUTOMATICO"))
    assert [i[3] for i in b.intentos] == [1, 2, 3], "3 intentos (max_reintentos=3)"
    assert [i[2] for i in b.intentos] == [TipoCalculo.AUTOMATICO, TipoCalculo.REINTENTO_AUTOMATICO, TipoCalculo.REINTENTO_AUTOMATICO]
    assert b.esperas == [120.0, 240.0], "backoff de 2 y 4 minutos entre intentos (el 6 no se usa con 3 intentos)"
    assert len(b.fallos.eventos) == 1, "tras agotar los reintentos queda fila en fallos_calculo_ica (CA_FALLO_PERSISTENTE)"
    f = b.fallos.eventos[0]
    assert f.id_activo_biologico == 825 and f.intentos == 3 and f.id_ejecucion_batch == 900 and "BD caída" in f.causa_fallo
    assert ejecucion.cantidad_fallidos == 1 and ejecucion.cantidad_activos_procesados == 1
    assert all(s.cerrada for s in b.sesiones), "cada intento cierra su sesión"


def test_018c_fallo_persistente_avisa_al_administrador(monkeypatch):
    """La ficha pide alerta al Administrador tras el fallo persistente (E5)."""
    b = _batch(_config(), [ActivoBatchRef(id_activo_biologico=825, fecha_inicio_ciclo=date(2026, 10, 12))],
               calculo_falla=True, monkeypatch=monkeypatch)
    asyncio.run(b.uc.ejecutar(tipo_disparo="AUTOMATICO"))
    assert b.notif.avisos, "no se envió ningún aviso al Administrador por el fallo persistente del activo 825"


def test_018d_ventana_excedida_interrumpe_y_deja_pendientes_en_cola(monkeypatch):
    activos = [ActivoBatchRef(id_activo_biologico=i, fecha_inicio_ciclo=date(2026, 10, 1)) for i in (1, 2, 3)]
    b = _batch(_config(ventana_horas=0), activos, atrasar_inicio=True, monkeypatch=monkeypatch)
    ejecucion = asyncio.run(b.uc.ejecutar(tipo_disparo="AUTOMATICO"))
    assert ejecucion.estado == EstadoEjecucionBatch.INTERRUMPIDO
    assert ejecucion.causa_interrupcion == CausaInterrupcionBatch.VENTANA_EXCEDIDA.value
    assert ejecucion.hora_corte is not None
    assert sorted(b.encolados_ventana) == [(1, MotivoEncolado.VENTANA_EXCEDIDA), (2, MotivoEncolado.VENTANA_EXCEDIDA),
                                           (3, MotivoEncolado.VENTANA_EXCEDIDA)], "FA-06: los pendientes quedan en cola"
    assert b.intentos == [], "no se procesa nada fuera de la ventana"
    assert any(t == "BATCH_ICA_INTERRUMPIDO" for _, t, _m in b.notif.avisos), "alerta interna al Administrador/Productor"


def test_018e_limite_superado_prioriza_criticos_y_encola_el_resto(monkeypatch):
    activos = [ActivoBatchRef(id_activo_biologico=i, fecha_inicio_ciclo=date(2026, 9, d))
               for i, d in ((10, 1), (20, 2), (30, 3))]
    b = _batch(_config(limite_activos=2), activos, criticos={30}, monkeypatch=monkeypatch)
    ejecucion = asyncio.run(b.uc.ejecutar(tipo_disparo="AUTOMATICO"))
    procesados = []
    for id_, *_ in b.intentos:
        if id_ not in procesados:
            procesados.append(id_)
    assert procesados == [30, 10], "primero el CRITICA (30), después el de ciclo más antiguo (10)"
    encolados = b.uc.cola_repo.encolados
    assert [(e.id_activo_biologico, e.motivo) for e in encolados] == [(20, MotivoEncolado.LIMITE_SUPERADO.value)], "FA-07"
    assert ejecucion.limite_configurado == 2
    assert any("superó el límite configurado de 2 activos" in m for _, _t, m in b.notif.avisos)


def test_018g_panel_cuenta_los_pendientes_por_limite(monkeypatch):
    """Observación: la corrida nace con cantidad_activos_pendientes = excedentes encolados, pero al completar
    se recalcula como total - procesados y el panel termina mostrando 0 pendientes con activos en cola."""
    activos = [ActivoBatchRef(id_activo_biologico=i, fecha_inicio_ciclo=date(2026, 9, d))
               for i, d in ((10, 1), (20, 2), (30, 3))]
    b = _batch(_config(limite_activos=2), activos, criticos={30}, monkeypatch=monkeypatch)
    ejecucion = asyncio.run(b.uc.ejecutar(tipo_disparo="AUTOMATICO"))
    assert len(b.uc.cola_repo.encolados) == 1
    assert ejecucion.cantidad_activos_pendientes == 1, (
        f"quedó 1 activo en cola por límite y la corrida informa {ejecucion.cantidad_activos_pendientes} pendientes")


def test_018h_fallo_tecnico_traducido_tambien_se_reintenta(monkeypatch):
    """En TEST el error de BD llega al batch ya traducido como InfrastructureError (subclase de AppError).
    El batch trata todo AppError como regla de negocio ("OK", sin reintento ni fallo): por eso las corridas 53 y 54
    del 2026-11-06 quedaron COMPLETADO con 498 procesados, 0 fallidos y ningún resultado guardado."""
    from src.shared.errors import InfrastructureError
    b = _batch(_config(), [ActivoBatchRef(id_activo_biologico=825, fecha_inicio_ciclo=date(2026, 10, 12))],
               error=InfrastructureError(code="ERROR_INTERNO", message="permission denied for schema public"),
               monkeypatch=monkeypatch)
    ejecucion = asyncio.run(b.uc.ejecutar(tipo_disparo="AUTOMATICO"))
    assert len(b.intentos) == 3, f"un fallo técnico debe reintentarse 3 veces; intentos: {len(b.intentos)}"
    assert len(b.fallos.eventos) == 1 and ejecucion.cantidad_fallidos == 1, (
        f"debe quedar como fallo persistente; fallos={len(b.fallos.eventos)}, cantidad_fallidos={ejecucion.cantidad_fallidos}")


def test_018f_valores_por_defecto_de_la_configuracion_del_batch():
    """Ventana 4 h, límite 5000, 3 reintentos y backoff [2, 4, 6] (server_default del modelo)."""
    from src.supplies.infrastructure.models.configuracion_batch_ica_model import ConfiguracionBatchIcaModel as M
    defaults = {c.name: str(c.server_default.arg) for c in M.__table__.columns if c.server_default is not None}
    assert defaults["ventana_horas"] == "4"
    assert defaults["limite_activos"] == "5000"
    assert defaults["max_reintentos"] == "3"
    assert defaults["backoff_minutos"].replace(" ", "") == "ARRAY[2,4,6]"
