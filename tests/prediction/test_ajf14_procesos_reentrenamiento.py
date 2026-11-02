# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-02 | Arekkazu | AJF-14 RF-71: procesos de reentrenamiento (solicitud por animal, toma, latido, cierre, vigilante) |
"""AJF-14: la solicitud por animal abre un proceso que el motor de IA toma, reporta y cierra."""
from __future__ import annotations

import copy
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest

from src.prediction.application.use_cases.reentrenamiento.procesar_reentrenamiento_use_case import (
    ActualizacionProceso, ProcesarReentrenamientoUseCase,
)
from src.prediction.application.use_cases.reentrenamiento.solicitar_reentrenamiento_animal_use_case import (
    SolicitarReentrenamientoAnimalUseCase,
)
from src.prediction.domain.entities.proceso_reentrenamiento import (
    DatosAnimalReentrenamiento, ProcesoReentrenamiento,
)
from src.prediction.domain.services.validacion_auditoria_m04 import validar_evento
from src.prediction.infrastructure.schema.proceso_reentrenamiento_schema import ProcesoReentrenamientoResponse
from src.shared.errors import BusinessRuleError, ConflictError, FlowError, NotFoundError

T0 = datetime(2026, 11, 2, 12, tzinfo=timezone.utc)
GRANDES = "MODELO_ESPECIES_GRANDES"


class _Db:
    def __init__(self):
        self.commits = self.rollbacks = 0

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


class _Procesos:
    """Repositorio en memoria."""

    def __init__(self, datos=DatosAnimalReentrenamiento(GRANDES, 24 * 10, 7), version_registrada=None):
        self.filas: dict[uuid.UUID, ProcesoReentrenamiento] = {}
        self.datos = datos
        self.version_registrada = version_registrada

    def crear(self, p):
        p.id_proceso_reentrenamiento = uuid.uuid4()
        self.filas[p.id_proceso_reentrenamiento] = copy.deepcopy(p)
        return copy.deepcopy(p)

    def obtener(self, i):
        return copy.deepcopy(self.filas.get(i))

    def abierto_de(self, a):
        return next((p for p in self.filas.values() if p.id_activo_biologico == a and p.abierto), None)

    def tomar_siguiente(self):
        pend = sorted((p for p in self.filas.values() if p.estado == "PENDIENTE"), key=lambda p: p.fecha_solicitud)
        return copy.deepcopy(pend[0]) if pend else None

    def guardar(self, p):
        self.filas[p.id_proceso_reentrenamiento] = copy.deepcopy(p)
        return copy.deepcopy(p)

    def listar(self, **kw):
        return list(self.filas.values()), len(self.filas)

    def en_curso(self):
        return [copy.deepcopy(p) for p in self.filas.values() if p.estado == "EN_CURSO"]

    def datos_animal(self, a):
        return self.datos

    def version_de_proceso(self, i):
        return self.version_registrada

    def retroalimentaciones_verificadas(self, a):
        return []


class _Auditoria:
    def __init__(self):
        self.eventos = []

    def registrar(self, **kw):
        # Lo que exige la bitácora real (RF-73 E1) también aquí.
        errores = validar_evento(tipo_evento=kw["tipo_evento"], tipo_actor=kw["tipo_actor"], id_usuario=kw.get("id_usuario"),
                                 id_sistema=kw.get("id_sistema"), id_referencia=kw.get("id_referencia"),
                                 payload_evento=kw["payload_evento"])
        assert errores == (), errores
        self.eventos.append(kw)
        return SimpleNamespace(aceptado=True, id_evento=uuid.uuid4())


class _Estado:
    def execute(self):
        return [SimpleNamespace(tipo_modelo=GRANDES, registros_nuevos=3, minimo_solicitud=200, minimo_reentrenamiento=500)]


def _solicitar(procesos, dias_minimos=7):
    db, aud = _Db(), _Auditoria()
    uc = SolicitarReentrenamientoAnimalUseCase(db=db, procesos=procesos, estado_use_case=_Estado(),
                                               auditoria_repo=aud, dias_minimos=dias_minimos)
    return uc, db, aud


def test_solicitar_por_animal_abre_un_proceso_pendiente_sin_exigir_retroalimentaciones():
    procesos = _Procesos()
    uc, db, aud = _solicitar(procesos)
    _, _, proceso = uc.execute(id_activo_biologico=4, motivo=None, id_usuario=9, ahora=T0)
    assert proceso.estado == "PENDIENTE" and proceso.tipo_modelo == GRANDES and db.commits == 1
    assert aud.eventos[0]["tipo_evento"] == "REENTRENAMIENTO_SOLICITADO"
    assert aud.eventos[0]["payload_evento"]["id_proceso_reentrenamiento"] == str(proceso.id_proceso_reentrenamiento)


def test_segunda_solicitud_del_mismo_animal_es_409():
    procesos = _Procesos()
    uc, _, _ = _solicitar(procesos)
    uc.execute(id_activo_biologico=4, motivo=None, id_usuario=9, ahora=T0)
    with pytest.raises(ConflictError) as e:
        uc.execute(id_activo_biologico=4, motivo=None, id_usuario=9, ahora=T0)
    assert e.value.code == "REENTRENAMIENTO_EN_CURSO"


@pytest.mark.parametrize("datos, error, codigo", [
    (None, NotFoundError, "ACTIVO_NO_ENCONTRADO"),
    (DatosAnimalReentrenamiento("MODELO_AVES", 500, None), BusinessRuleError, "ACTIVO_SIN_MODELO_INDIVIDUAL"),
    (DatosAnimalReentrenamiento(GRANDES, 30, None), BusinessRuleError, "LECTURAS_INSUFICIENTES"),
])
def test_solicitud_rechazada(datos, error, codigo):
    uc, db, _ = _solicitar(_Procesos(datos=datos))
    with pytest.raises(error) as e:
        uc.execute(id_activo_biologico=4, motivo=None, id_usuario=9, ahora=T0)
    assert e.value.code == codigo and db.commits == 0


def _en_curso():
    procesos = _Procesos(version_registrada=31)
    uc, _, _ = _solicitar(procesos)
    _, _, p = uc.execute(id_activo_biologico=4, motivo=None, id_usuario=9, ahora=T0)
    aud = _Auditoria()
    motor = ProcesarReentrenamientoUseCase(db=_Db(), procesos=procesos, auditoria_repo=aud)
    tomado = motor.tomar(ahora=T0 + timedelta(minutes=1))
    return procesos, motor, aud, tomado


def test_el_motor_toma_el_pendiente_y_queda_en_la_fase_1():
    procesos, motor, aud, p = _en_curso()
    assert (p.estado, p.fase_actual, p.id_version_modelo_referencia) == ("EN_CURSO", 1, 7)
    assert aud.eventos[0]["tipo_evento"] == "REENTRENAMIENTO_INICIADO"
    assert motor.tomar(ahora=T0) is None  # no hay otro pendiente


def test_latido_avanza_fases_sin_retroceder_y_guarda_recursos():
    procesos, motor, _, p = _en_curso()
    p = motor.actualizar(p.id_proceso_reentrenamiento, ActualizacionProceso(fase=4, progreso=55, cpu=Decimal("68.5"), ram_mb=900), ahora=T0 + timedelta(minutes=9))
    assert (p.fase_actual, p.porcentaje_progreso, p.porcentaje_cpu, p.memoria_ram_mb) == (4, 55, Decimal("68.5"), 900)
    assert [f["resultado"] for f in p.fases] == ["OK", "OK", "OK", None]
    with pytest.raises(FlowError):
        motor.actualizar(p.id_proceso_reentrenamiento, ActualizacionProceso(fase=2), ahora=T0 + timedelta(minutes=10))


def test_completar_toma_la_version_registrada_con_su_id_de_proceso():
    procesos, motor, aud, p = _en_curso()
    p = motor.actualizar(p.id_proceso_reentrenamiento, ActualizacionProceso(estado="COMPLETADO", metricas={"f1_score_global": 0.9}), ahora=T0 + timedelta(hours=1))
    assert (p.estado, p.id_version_modelo_resultante, p.fase_actual, p.porcentaje_progreso) == ("COMPLETADO", 31, 7, 100)
    assert aud.eventos[-1]["tipo_evento"] == "REENTRENAMIENTO_COMPLETADO"
    assert all(f["resultado"] == "OK" for f in p.fases)


def test_fallar_guarda_el_codigo_y_la_fase_en_que_fallo():
    procesos, motor, aud, p = _en_curso()
    motor.actualizar(p.id_proceso_reentrenamiento, ActualizacionProceso(fase=3), ahora=T0 + timedelta(minutes=5))
    p = motor.actualizar(p.id_proceso_reentrenamiento, ActualizacionProceso(estado="FALLIDO", codigo_error="CALIBRACION_INCOMPLETA",
                                                                            motivos=["2 días de lecturas"]), ahora=T0 + timedelta(minutes=6))
    assert (p.estado, p.codigo_error, p.fases[-1]["resultado"]) == ("FALLIDO", "CALIBRACION_INCOMPLETA", "FALLIDA")
    assert aud.eventos[-1]["tipo_evento"] == "REENTRENAMIENTO_FALLIDO"


def test_vigilante_interrumpe_el_que_no_da_latido():
    procesos, motor, aud, p = _en_curso()
    assert motor.vigilar(ahora=T0 + timedelta(minutes=10)) == 0
    assert motor.vigilar(ahora=T0 + timedelta(minutes=30)) == 1
    assert procesos.obtener(p.id_proceso_reentrenamiento).estado == "INTERRUMPIDO"
    assert aud.eventos[-1]["tipo_evento"] == "REENTRENAMIENTO_INTERRUMPIDO"


def test_la_respuesta_trae_siempre_las_siete_fases():
    _, _, _, p = _en_curso()
    r = ProcesoReentrenamientoResponse.from_entity(p)
    assert [f.nombre for f in r.fases] == ["ACTIVACION", "DATASET", "PREPROCESAMIENTO", "ENTRENAMIENTO", "METRICAS", "ENTREGA", "CIERRE"]
    assert r.fases[0].fecha_inicio is not None and r.fases[1].fecha_inicio is None


@pytest.fixture
def cliente_motor(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from src.prediction.infrastructure.routers import motor_catalogo_router as router_mod
    from src.shared.broker_auth import require_token_servicio_motor_ia
    from src.shared.database import get_db_sistema
    from src.shared.error_handlers import register_error_handlers

    procesos = _Procesos(version_registrada=31)
    monkeypatch.setattr(router_mod, "SqlAlchemyProcesoReentrenamientoRepository", lambda db: procesos)
    monkeypatch.setattr(router_mod, "SqlAlchemyEventoAuditoriaM04Repository", lambda db: _Auditoria())
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(router_mod.router)
    app.dependency_overrides[get_db_sistema] = lambda: _Db()
    app.dependency_overrides[require_token_servicio_motor_ia] = lambda: None
    return TestClient(app), procesos


def test_rutas_del_motor(cliente_motor):
    client, procesos = cliente_motor
    assert client.post("/prediccion/motor/reentrenamientos/tomar").status_code == 204
    procesos.crear(ProcesoReentrenamiento.solicitar(tipo_modelo=GRANDES, id_activo_biologico=4, id_usuario=9, ahora=T0))
    tomado = client.post("/prediccion/motor/reentrenamientos/tomar").json()
    assert tomado["estado"] == "EN_CURSO" and len(tomado["fases"]) == 7
    r = client.patch(f"/prediccion/motor/reentrenamientos/{tomado['id_proceso_reentrenamiento']}", json={"fase": 2, "progreso": 20, "cpu": 40})
    assert r.status_code == 200 and r.json()["fase_actual"] == 2
    assert client.patch(f"/prediccion/motor/reentrenamientos/{tomado['id_proceso_reentrenamiento']}", json={"estado": "OTRO"}).status_code == 400
    assert client.get("/prediccion/motor/activos/4/retroalimentaciones").json() == {"retroalimentaciones": []}
