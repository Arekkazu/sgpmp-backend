# | Fecha      | Nombre      | Que se hizo                                                              |
# |------------|-------------|--------------------------------------------------------------------------|
# | 2026-10-29 | Juan Manuel | TC-M03-G12 RF-53: 026b por la ruta real (INC-M03-125), 026d y catalogo M09 |
"""
TC-M03-G12 - Resiliencia y atomicidad del pipeline de ingesta ante fallos.

RF relacionado: RF-53 (CU01). Casos: TC-M03-026 (flujo alterno E12) y TC-M03-060
(RNF "Consistencia Atomica del Dato").

Criterios de la ficha:
    TC-M03-026: con la BD principal caida se envian 20 mediciones validas y se
    restaura el servicio. Se activa el resguardo temporal, se registra
    FALLA_PERSISTENCIA y al restablecerse los 20 datos se procesan en el orden
    original, sin perdidas ni duplicados.
    TC-M03-060: un fallo inducido despues de calcular valor_ajustado (fase 7) y
    antes de escribir el registro definitivo (fase 9) no deja ningun registro
    parcial; el dato se reintenta o se descarta por completo.

Por que en proceso y no contra el backend TEST desplegado (mismo criterio que
TC-M01-024): detener el Postgres de TEST requiere acceso de infraestructura que QA
no tiene y tumbaria la BD compartida para todo el equipo, y la inyeccion de fallos
a mitad del pipeline no es posible desde la API. Estas pruebas ejecutan el
IngerirTelemetriaUseCase real (el mismo codigo del endpoint POST /iot/telemetria)
con dobles de los puertos y de la sesion SQLAlchemy:

- _SesionFalsa modela la transaccion: lo que escribe la funcion de ingesta queda
  "pendiente", commit lo pasa a "confirmado" y rollback lo descarta. Es lo que
  permite ver si queda un registro parcial.
- _IngestaFalsa reemplaza a SqlAlchemyIngestaTelemetriaRepository. Desde la
  ingesta B+ las fases 3 a 9 (tiempo, unidad, rango, duplicado, calibracion y
  persistencia) corren dentro de modulo3.fn_ingesta_telemetria en una sola
  sentencia SQL, asi que el punto de fallo "despues de calcular valor_ajustado y
  antes de confirmar" es: la funcion ya escribio la fila y falla la lectura
  posterior de tiempos o el commit. Los errores de BD pasan por el mismo
  raise_from_db_error del repositorio real (OperationalError -> 503).

El calculo de valor_ajustado ya no ocurre en Python (lo hace la funcion SQL con
fn_obtener_calibracion), por eso aqui no se verifica; lo cubre TC-M03-G09 contra TEST.

El "resguardo temporal" de TC-M03-026 se modela como el buffer del dispositivo
Edge (RF-54): mientras la BD esta caida el backend debe rechazar sin perder nada,
y al restablecerse el Edge reenvia el lote por la sincronizacion BUFFER_LOCAL
(SincronizarBufferUseCase, el mismo de POST /iot/telemetria/batch).

Una ejecucion real contra TEST de TC-M03-026 (detener y restaurar el contenedor
de BD) queda para coordinar con Implementacion, como indica la ficha.

Como correrlo (desde la raiz del repo; --noconftest porque tests/conftest.py
levanta la app completa y este caso no la necesita):

    python -m pytest tests/Test_Testing/Test_Modulo3/RF-53/TC-M03-G12 -v --noconftest \
        --html=tests/Test_Testing/Test_Modulo3/RF-53/TC-M03-G12/Resultados/reporte-TC-M03-G12.html \
        --self-contained-html
"""
from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "postgresql://qa:qa@localhost:5432/qa")

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy.exc import OperationalError

from src.shared.db_error_translator import raise_from_db_error
from src.shared.errors import ServiceUnavailableError
from src.telemetry.application.use_cases.ingesta.ingerir_telemetria_use_case import (
    IngerirTelemetriaUseCase,
    SincronizarBufferUseCase,
)
from src.telemetry.domain.repositories.dispositivo_port import DispositivoHeartbeatInfo
from src.telemetry.domain.entities.telemetria import ReglaVariableI3P1
from src.telemetry.domain.repositories.ingesta_telemetria_port import ResultadoPersistenciaIngesta
from src.telemetry.infrastructure.dto.ingerir_telemetria_dto import (
    IngerirTelemetriaBatchDTO,
    IngerirTelemetriaDTO,
)

_DEVICE_ID = 10
_SENSOR_ID = 20
_ID_INFRAESTRUCTURA = 30
_SERIAL = "M03-G12-SERIAL"


def _bd_caida() -> OperationalError:
    return OperationalError("SELECT * FROM modulo3.fn_ingesta_telemetria(...)", None, Exception("connection refused"))


# --------------------------------------------------------------------------- dobles
class _SesionFalsa:
    """Transaccion minima: la ingesta deja pendientes, commit confirma, rollback descarta."""

    def __init__(self) -> None:
        self.pendientes: list[dict] = []
        self.confirmados: list[dict] = []
        self.commits = 0
        self.rollbacks = 0
        self.fallar_en_commit = False

    def commit(self) -> None:
        if self.fallar_en_commit:
            raise _bd_caida()
        self.commits += 1
        self.confirmados.extend(self.pendientes)
        self.pendientes.clear()

    def rollback(self) -> None:
        self.rollbacks += 1
        self.pendientes.clear()


class _IngestaFalsa:
    """Hace lo que fn_ingesta_telemetria: detecta duplicados y escribe la fila en la transaccion."""

    def __init__(self, sesion: _SesionFalsa) -> None:
        self.sesion = sesion
        self.caida = False
        self.fallar_tras_escribir = False
        self._siguiente_id = 1000

    def ingerir(self, parametros: dict) -> ResultadoPersistenciaIngesta:
        try:
            if self.caida:
                raise _bd_caida()
            clave = (parametros["sensor_id"], parametros["id_variable"],
                     parametros["timestamp_captura"], parametros["origen"])
            if any(f["clave"] == clave for f in self.sesion.confirmados):
                return ResultadoPersistenciaIngesta(None, None, "ERROR_DUPLICADO: Registro ya existe.")
            self._siguiente_id += 1
            self.sesion.pendientes.append({"id": self._siguiente_id, "clave": clave, "valor": parametros["valor"]})
            if self.fallar_tras_escribir:
                # La funcion ya escribio la fila; falla la consulta de tiempos posterior.
                raise _bd_caida()
            return ResultadoPersistenciaIngesta(
                self._siguiente_id, "LECTURA_VALIDA", "OK",
                timestamp_procesamiento=datetime.now(timezone.utc), latencia_procesamiento_ms=5,
            )
        except Exception as exc:
            raise_from_db_error(exc)


class _BitacoraFalsa:
    def __init__(self) -> None:
        self.errores: list[dict] = []

    def registrar_error(self, **kwargs) -> None:
        self.errores.append(kwargs)


class _DispositivoFalso:
    def validar_dispositivo_heartbeat(self, device_id, serial) -> DispositivoHeartbeatInfo:
        return DispositivoHeartbeatInfo(
            id_dispositivo_iot=device_id, id_infraestructura=_ID_INFRAESTRUCTURA, es_activo=True,
        )


class _CatalogoFalso:
    """Catalogo M09 (f8b62bc9): la variable existe y esta activa."""

    def obtener_regla(self, tipo_variable: str) -> ReglaVariableI3P1:
        return ReglaVariableI3P1(
            id_variable=1, tipo_variable=tipo_variable, categoria="AMBIENTAL", unidad_estandar="°C",
            unidades_aceptadas=["°C"], valor_fisico_min=Decimal("-40"), valor_fisico_max=Decimal("85"),
        )


class _Entorno:
    def __init__(self) -> None:
        self.sesion = _SesionFalsa()
        self.ingesta = _IngestaFalsa(self.sesion)
        self.bitacora = _BitacoraFalsa()

    def caso_de_uso(self) -> IngerirTelemetriaUseCase:
        return IngerirTelemetriaUseCase(
            db=self.sesion,
            ingesta_port=self.ingesta,
            dispositivo_port=_DispositivoFalso(),
            bitacora_repo=self.bitacora,
            catalogo_port=_CatalogoFalso(),
        )


def _lectura(ts: datetime, valor: str = "25.0", origen: str = "TIEMPO_REAL") -> IngerirTelemetriaDTO:
    return IngerirTelemetriaDTO(
        device_id=_DEVICE_ID,
        sensor_id=_SENSOR_ID,
        tipo_variable="TEMPERATURA_AMBIENTAL",
        valor=Decimal(valor),
        unidad="°C",
        timestamp_captura=ts,
        serial=_SERIAL,
        origen=origen,
    )


@pytest.fixture
def entorno() -> _Entorno:
    return _Entorno()


# --------------------------------------------------------------------------- TC-M03-060
def test_tc_m03_060a_fallo_tras_escribir_la_fila_no_deja_registro(entorno):
    """La funcion de ingesta ya escribio (calibracion incluida) y falla antes de confirmar."""
    entorno.ingesta.fallar_tras_escribir = True

    with pytest.raises(ServiceUnavailableError):
        entorno.caso_de_uso().execute(_lectura(datetime.now(timezone.utc) - timedelta(seconds=2)))

    assert entorno.sesion.confirmados == [], "No debe quedar ningun registro en la base principal"
    assert entorno.sesion.pendientes == [], "No debe quedar ningun registro parcial pendiente de la transaccion"
    assert entorno.sesion.rollbacks >= 1, "La transaccion debe revertirse"
    assert entorno.sesion.commits == 0, "No debe confirmarse nada"


def test_tc_m03_060b_fallo_en_el_commit_revierte_todo(entorno):
    """La fila quedo escrita en la transaccion pero el commit falla."""
    entorno.sesion.fallar_en_commit = True

    with pytest.raises(OperationalError):
        entorno.caso_de_uso().execute(_lectura(datetime.now(timezone.utc) - timedelta(seconds=2)))

    assert entorno.sesion.confirmados == [], "El registro escrito no debe quedar confirmado"
    assert entorno.sesion.pendientes == [], "No debe quedar el registro en estado intermedio"
    assert entorno.sesion.rollbacks >= 1
    assert entorno.sesion.commits == 0


def test_tc_m03_060c_el_reintento_del_mismo_dato_se_procesa_completo(entorno):
    """Tras el fallo, el mismo dato se puede reintentar: no queda residuo que lo marque duplicado."""
    ts = datetime.now(timezone.utc) - timedelta(seconds=2)
    entorno.ingesta.fallar_tras_escribir = True
    with pytest.raises(ServiceUnavailableError):
        entorno.caso_de_uso().execute(_lectura(ts))

    entorno.ingesta.fallar_tras_escribir = False
    resultado = entorno.caso_de_uso().execute(_lectura(ts))

    assert resultado.estado_calidad == "LECTURA_VALIDA"
    assert len(entorno.sesion.confirmados) == 1, "El reintento debe dejar exactamente un registro"
    assert entorno.sesion.confirmados[0]["valor"] == Decimal("25.0")


# --------------------------------------------------------------------------- TC-M03-026
_N = 20


def _veinte_lecturas() -> list[IngerirTelemetriaDTO]:
    base = datetime.now(timezone.utc) - timedelta(hours=1)
    return [_lectura(base + timedelta(minutes=i), valor=f"{20 + i * 0.1:.1f}", origen="BUFFER_LOCAL") for i in range(_N)]


def test_tc_m03_026a_con_la_bd_caida_ninguna_lectura_queda_a_medias(entorno):
    """Durante la caida, cada lectura se rechaza con 503 sin dejar nada escrito."""
    entorno.ingesta.caida = True
    for dto in _veinte_lecturas():
        with pytest.raises(ServiceUnavailableError) as exc:
            entorno.caso_de_uso().execute(dto)
        assert exc.value.status_code == 503

    assert entorno.sesion.confirmados == []
    assert entorno.sesion.pendientes == []
    assert entorno.sesion.rollbacks == _N


# INC-M03-125-G12 (f88d4402): FALLA_PERSISTENCIA es un evento de auditoria RF-63 que registra la ruta
# (RutaIngestaAuditada) en un respaldo SQLite local, porque la BD principal esta caida; un worker lo
# publica en modulo3.bitacora_auditoria_iot al recuperarse. Las lecturas no se guardan: las retiene el
# emisor (Edge/broker, RF-54). Se prueba por la ruta HTTP real, con get_db real apuntando a un puerto
# cerrado (la BD "caida"), sin tocar la BD compartida de TEST.
_TOKEN = "g12-solo-pruebas"


@pytest.fixture
def api_bd_caida(monkeypatch, tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from src.shared import database as modulo_db
    from src.shared.error_handlers import register_error_handlers
    from src.telemetry.infrastructure.adapters.respaldo_auditoria_iot_sqlite_adapter import (
        RespaldoAuditoriaIotSqliteAdapter,
    )
    from src.telemetry.infrastructure.routers.telemetria_router import router

    motor = create_engine("postgresql+psycopg2://qa:qa@127.0.0.1:1/qa", connect_args={"connect_timeout": 1})
    monkeypatch.setattr(modulo_db, "SessionLocal", sessionmaker(bind=motor, autoflush=False))
    monkeypatch.setattr(modulo_db, "_PAUSA_REINTENTO", 0)
    monkeypatch.setenv("ENABLE_TEST_SANDBOX", "false")
    monkeypatch.setenv("BROKER_SERVICE_TOKEN", _TOKEN)
    monkeypatch.setenv("IOT_AUDITORIA_RESPALDO_PATH", str(tmp_path / "fallas.sqlite3"))
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(router)
    with TestClient(app, raise_server_exceptions=False, headers={"Authorization": f"Bearer {_TOKEN}"}) as cliente:
        yield cliente, RespaldoAuditoriaIotSqliteAdapter()
    motor.dispose()


def _cuerpo(dto: IngerirTelemetriaDTO) -> dict:
    return {**dto.model_dump(mode="json", exclude_none=True), "valor": float(dto.valor)}


def test_tc_m03_026b_se_registra_falla_persistencia_por_cada_lectura(api_bd_caida):
    """Con la BD caida, cada POST /iot/telemetria responde 503 y deja un evento FALLA_PERSISTENCIA respaldado."""
    cliente, respaldo = api_bd_caida
    lecturas = _veinte_lecturas()
    for dto in lecturas:
        r = cliente.post("/iot/telemetria", json=_cuerpo(dto))
        assert r.status_code == 503, r.text
        assert r.json().get("error_code") == "BD_NO_DISPONIBLE"
        assert "id_telemetria" not in r.json(), "Un 503 no debe confirmar ninguna lectura"

    eventos = respaldo.listar(100)
    assert [e.tipo_evento for e in eventos] == ["FALLA_PERSISTENCIA"] * _N, (
        f"Se esperaban {_N} eventos FALLA_PERSISTENCIA en el respaldo; hay {len(eventos)}"
    )
    assert [e.accion_detallada.get("timestamp_captura") for e in eventos] == [
        dto.timestamp_captura.astimezone(timezone.utc).isoformat() for dto in lecturas
    ], "El respaldo debe conservar el orden original de los intentos"
    assert {e.entidad_afectada_id for e in eventos} == {str(_DEVICE_ID)}
    assert len({e.accion_detallada["id_correlacion"] for e in eventos}) == _N, "Cada intento debe tener su correlacion"
    for e in eventos:
        assert e.accion_detallada.get("resguardo_lectura") == "EDGE_RF54"
        assert "serial" not in e.accion_detallada and "valor" not in e.accion_detallada, (
            "El respaldo no debe guardar la identidad ni el valor de la lectura"
        )


def test_tc_m03_026d_al_recuperarse_la_bd_se_publican_los_eventos_en_orden(api_bd_caida):
    """El worker publica el respaldo en la bitacora en FIFO; si la publicacion falla, no se pierde nada."""
    from src.telemetry.application.use_cases.auditoria.sincronizar_respaldo_auditoria_iot_use_case import (
        SincronizarRespaldoAuditoriaIotUseCase,
    )

    cliente, respaldo = api_bd_caida
    for dto in _veinte_lecturas():
        assert cliente.post("/iot/telemetria", json=_cuerpo(dto)).status_code == 503
    pendientes = [e.id_evento for e in respaldo.listar(100)]

    class _Destino:
        def __init__(self, fallar_en: int | None = None) -> None:
            self.publicados, self.fallar_en = [], fallar_en

        def bloquear_respaldo(self) -> bool:
            return True

        def registrar_respaldo(self, evento) -> None:
            if self.fallar_en is not None and len(self.publicados) == self.fallar_en:
                raise _bd_caida()
            self.publicados.append(evento.id_evento)

    sesion = _SesionFalsa()
    with pytest.raises(OperationalError):
        SincronizarRespaldoAuditoriaIotUseCase(sesion, _Destino(fallar_en=7), respaldo).execute()
    assert [e.id_evento for e in respaldo.listar(100)] == pendientes, "Un lote fallido conserva todo el respaldo"

    destino = _Destino()
    assert SincronizarRespaldoAuditoriaIotUseCase(sesion, destino, respaldo).execute() == _N
    assert destino.publicados == pendientes, "Se publican los mismos eventos, en el orden original"
    assert not respaldo.hay_pendientes(), "Tras el commit el respaldo queda vacio"


def test_tc_m03_026c_al_restablecerse_los_20_datos_se_procesan_en_orden_sin_perdidas_ni_duplicados(entorno):
    """Tras restaurar la BD, el Edge reenvia su buffer (RF-54) en desorden y con un reenvio repetido."""
    lecturas = _veinte_lecturas()

    entorno.ingesta.caida = True
    for dto in lecturas:
        with pytest.raises(ServiceUnavailableError):
            entorno.caso_de_uso().execute(dto)

    entorno.ingesta.caida = False
    # El buffer llega desordenado y con la primera lectura repetida (reintento del Edge).
    reenvio = list(reversed(lecturas)) + [lecturas[0]]
    resultado = SincronizarBufferUseCase(
        ingerir_use_case_factory=entorno.caso_de_uso, db=entorno.sesion
    ).execute(IngerirTelemetriaBatchDTO(registros=reenvio))

    assert resultado["aceptados"] == _N, f"Se esperaban {_N} aceptados, hubo {resultado['aceptados']}"
    assert resultado["duplicados"] == 1, "El reenvio repetido debe detectarse como duplicado"
    assert resultado["rechazados"] == 0

    guardados = entorno.sesion.confirmados
    assert len(guardados) == _N, "Sin perdidas ni duplicados en la base principal"
    capturas = [f["clave"][2] for f in guardados]
    assert capturas == sorted(capturas), "Los datos deben persistirse en el orden original (cronologico)"
    assert capturas == [dto.timestamp_captura for dto in lecturas]
