# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-27 | destroyerban | INC-M03-121-G64 RF-56 E6: ráfagas concurrentes contra uvicorn y PostgreSQL reales |
"""INC-M03-121-G64 (RF-56 E6, TC-M03-127): control de ráfagas de eventos Edge bajo carga real.

Servidor uvicorn real (solo 127.0.0.1) con el router de eventos Edge, una sesión de BD por
solicitud contra la base de TEST_DATABASE_URL y clientes HTTP concurrentes. Nada sale de la máquina.

Se verifica:
- El límite exacto por dispositivo bajo concurrencia (ni uno más), con 429 y Retry-After.
- Lo rechazado no se persiste (ni evento ni paquete).
- Los CRITICO no se frenan aunque el dispositivo esté saturado.
- Un dispositivo saturado no afecta a otro.
- La ventana se libera al vencer y el límite se ajusta por entorno.
- Una ráfaga de muchos dispositivos bajo su límite no pierde eventos (el caudal se mide y se imprime).
"""
from __future__ import annotations

import importlib
import pkgutil
import socket
import statistics
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import httpx
import pytest
import uvicorn
from fastapi import FastAPI
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from src.shared import rate_limit
from src.shared.database import declarar_identidad_sistema, get_db_sistema
from src.shared.error_handlers import register_error_handlers
from src.telemetry.application.use_cases.inferencia import recibir_evento_edge_use_case as uc
from src.telemetry.infrastructure.routers import evento_edge_router

pytestmark = pytest.mark.integration

TOKEN = "token-servicio-pruebas-g64"
CONCURRENCIA = 50


@pytest.fixture(scope="module", autouse=True)
def modelos():
    for paquete in ("src.configuration.infrastructure.models", "src.biological_assets.infrastructure.models",
                    "src.telemetry.infrastructure.models", "src.identity_access.infrastructure.models"):
        mod = importlib.import_module(paquete)
        for item in pkgutil.iter_modules(mod.__path__, paquete + "."):
            importlib.import_module(item.name)


@pytest.fixture(scope="module")
def motor(integration_engine):
    # Pool propio: cada solicitud concurrente usa su conexión, como en producción.
    engine = create_engine(integration_engine.url, pool_size=CONCURRENCIA, max_overflow=10,
                           use_insertmanyvalues=False)
    yield engine
    engine.dispose()


@pytest.fixture(scope="module")
def servidor(motor):
    sesiones = sessionmaker(bind=motor, autocommit=False, autoflush=False)

    def db_sistema():
        db = sesiones()
        try:
            declarar_identidad_sistema(db)
            yield db
        finally:
            db.close()

    app = FastAPI()
    register_error_handlers(app)
    app.include_router(evento_edge_router.router)
    app.dependency_overrides[get_db_sistema] = db_sistema

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        puerto = s.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=puerto, log_level="warning",
                                           limit_concurrency=None, backlog=512, timeout_keep_alive=60))
    hilo = threading.Thread(target=server.run, daemon=True)
    hilo.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    assert server.started, "uvicorn no arrancó"
    yield f"http://127.0.0.1:{puerto}"
    server.should_exit = True
    hilo.join(timeout=10)


@pytest.fixture(autouse=True)
def token_broker(monkeypatch):
    monkeypatch.setenv("BROKER_SERVICE_TOKEN", TOKEN)
    monkeypatch.delenv("IOT_EVENTOS_EDGE_LIMITE_POR_MINUTO", raising=False)


def _dispositivo(motor) -> dict:
    tag = uuid.uuid4().hex[:10]
    nombre = "Rafaga " + "".join(chr(97 + int(c, 16)) for c in tag)
    with motor.begin() as db:
        area = db.execute(text("""
            WITH finca AS (
              INSERT INTO modulo9.fincas(nombre,ubicacion,tamano_h,es_activo,fecha_creacion,fecha_actualizacion)
              VALUES (:nombre,'{}',10,true,now(),now()) RETURNING id_finca)
            INSERT INTO modulo9.infraestructuras(nombre,id_finca,superficie,es_activo,tipo)
            SELECT :nombre,id_finca,100,true,'Estanque' FROM finca RETURNING id_infraestructura
        """), {"nombre": nombre}).scalar_one()
        device = db.execute(text("""
            INSERT INTO modulo9.dispositivos_iot(serial,descripcion,es_activo,fecha_creacion,id_infraestructura,id_tipo_dispositivo)
            VALUES (:serial,'G64 nodo',true,now(),:area,3) RETURNING id_dispositivo_iot
        """), {"serial": f"RF-{tag}", "area": area}).scalar_one()
        sensor = db.execute(text("""
            INSERT INTO modulo9.sensores(id_dispositivo_iot,es_activo,nombre)
            VALUES (:device,true,'Temperatura G64') RETURNING id_sensores
        """), {"device": device}).scalar_one()
    return {"device": device, "sensor": sensor, "serial": f"RF-{tag}"}


def _payload(d, i, severidad="MODERADO"):
    ts = datetime.now(timezone.utc) - timedelta(seconds=30) + timedelta(milliseconds=i)
    return dict(device_id=d["device"], sensor_id=d["sensor"], serial=d["serial"],
                clasificacion_rf55="DESVIACION_SIMPLE", severidad=severidad, origen="TIEMPO_REAL",
                estado_conectividad=True, timestamp_captura=ts.isoformat(),
                timestamp_procesamiento_edge=(ts + timedelta(milliseconds=200)).isoformat(),
                variables_involucradas=[{"tipo_variable": "TEMPERATURA_AMBIENTAL", "valor": "38.5", "unidad": "°C"}])


def _rafaga(url, payloads):
    """Envía todos los payloads a la vez; devuelve [(status, headers, segundos)]."""
    with httpx.Client(base_url=url, headers={"Authorization": f"Bearer {TOKEN}"}, timeout=60,
                      limits=httpx.Limits(max_connections=CONCURRENCIA), trust_env=False) as cliente:
        barrera = threading.Barrier(min(CONCURRENCIA, len(payloads)))

        def enviar(p):
            try:
                barrera.wait(timeout=5)
            except threading.BrokenBarrierError:
                pass
            inicio = time.perf_counter()
            r = cliente.post("/iot/eventos-edge", json=p)
            return r.status_code, r.headers, time.perf_counter() - inicio, r.text

        with ThreadPoolExecutor(max_workers=CONCURRENCIA) as pool:
            return list(pool.map(enviar, payloads))


def _persistidos(motor, d):
    with motor.connect() as db:
        eventos = db.execute(text("SELECT count(*) FROM modulo3.eventos_edge_computing WHERE id_dispositivo_iot = :d"),
                             {"d": d["device"]}).scalar_one()
        paquetes = db.execute(text("SELECT count(*) FROM modulo3.paquetes_inferencia WHERE id_dispositivo_iot = :d"),
                              {"d": d["device"]}).scalar_one()
    return eventos, paquetes


def _conteo(resultados):
    return {c: sum(1 for r in resultados if r[0] == c) for c in {r[0] for r in resultados}}


def test_rafaga_concurrente_acepta_exactamente_el_limite_y_no_persiste_lo_rechazado(servidor, motor):
    d = _dispositivo(motor)
    resultados = _rafaga(servidor, [_payload(d, i) for i in range(100)])
    assert _conteo(resultados) == {201: 60, 429: 40}, [r[3] for r in resultados if r[0] not in (201, 429)][:3]
    rechazo = next(r for r in resultados if r[0] == 429)
    assert '"LIMITE_TASA_EXCEDIDO"' in rechazo[3]
    assert int(rechazo[1]["Retry-After"]) >= 1
    assert rechazo[1]["RateLimit-Limit"] == "60" and rechazo[1]["RateLimit-Remaining"] == "0"
    assert _persistidos(motor, d) == (60, 60)


def test_criticos_no_se_frenan_con_el_dispositivo_saturado(servidor, motor):
    d = _dispositivo(motor)
    saturacion = _rafaga(servidor, [_payload(d, i) for i in range(70)])
    assert _conteo(saturacion) == {201: 60, 429: 10}
    criticos = _rafaga(servidor, [_payload(d, 100 + i, "CRITICO") for i in range(30)])
    assert _conteo(criticos) == {201: 30}
    assert _rafaga(servidor, [_payload(d, 200)])[0][0] == 429  # el resto sigue frenado
    assert _persistidos(motor, d) == (90, 90)


def test_un_dispositivo_saturado_no_afecta_a_otro(servidor, motor):
    a, b = _dispositivo(motor), _dispositivo(motor)
    mezcla = [_payload(a, i) for i in range(90)] + [_payload(b, i) for i in range(40)]
    resultados = _rafaga(servidor, mezcla)
    de_a, de_b = resultados[:90], resultados[90:]
    assert _conteo(de_a) == {201: 60, 429: 30}
    assert _conteo(de_b) == {201: 40}
    assert _persistidos(motor, a) == (60, 60) and _persistidos(motor, b) == (40, 40)


def test_la_ventana_se_libera_al_vencer(servidor, motor, monkeypatch):
    d = _dispositivo(motor)
    assert _conteo(_rafaga(servidor, [_payload(d, i) for i in range(61)])) == {201: 60, 429: 1}
    reloj = time.monotonic
    monkeypatch.setattr(rate_limit.time, "monotonic", lambda: reloj() + 61)
    assert _conteo(_rafaga(servidor, [_payload(d, 100 + i) for i in range(5)])) == {201: 5}


def test_limite_configurable_por_entorno(servidor, motor, monkeypatch):
    monkeypatch.setenv("IOT_EVENTOS_EDGE_LIMITE_POR_MINUTO", "10")
    d = _dispositivo(motor)
    resultados = _rafaga(servidor, [_payload(d, i) for i in range(25)])
    assert _conteo(resultados) == {201: 10, 429: 15}
    assert next(r for r in resultados if r[0] == 429)[1]["RateLimit-Limit"] == "10"


@pytest.mark.parametrize("valor", ["0", "-5", "abc"])
def test_limite_invalido_en_entorno_usa_el_valor_por_defecto(monkeypatch, valor):
    monkeypatch.setenv("IOT_EVENTOS_EDGE_LIMITE_POR_MINUTO", valor)
    assert uc._limite_eventos_por_minuto() == uc.LIMITE_EVENTOS_POR_MINUTO == 60


def test_rafaga_de_muchos_dispositivos_bajo_el_limite_no_pierde_eventos(servidor, motor, capsys):
    """10 dispositivos × 30 eventos a la vez, todos bajo su límite: se aceptan y persisten todos.

    RF-56 no fija un caudal (su RNF de rendimiento es la detección < 500 ms en el Edge). El
    caudal medido se imprime como evidencia; el RNF de 50 mediciones/s es de RF-53 (ingesta MQTT).
    """
    dispositivos = [_dispositivo(motor) for _ in range(10)]
    payloads = [_payload(d, i) for i in range(30) for d in dispositivos]
    inicio = time.perf_counter()
    resultados = _rafaga(servidor, payloads)
    total = time.perf_counter() - inicio
    assert _conteo(resultados) == {201: 300}
    assert all(_persistidos(motor, d) == (30, 30) for d in dispositivos)
    latencias = sorted(r[2] * 1000 for r in resultados)
    p95 = latencias[int(len(latencias) * 0.95) - 1]
    with capsys.disabled():
        print(f"\n[G64] {len(resultados)} eventos con {CONCURRENCIA} clientes en {total:.2f} s = "
              f"{len(resultados) / total:.1f} eventos/s; latencia ms: mediana {statistics.median(latencias):.0f}, "
              f"p95 {p95:.0f}, máx {latencias[-1]:.0f}")
