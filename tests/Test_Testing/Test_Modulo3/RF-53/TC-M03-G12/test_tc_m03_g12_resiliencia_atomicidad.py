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

- _SesionFalsa modela la transaccion: lo escrito con flush queda "pendiente",
  commit lo pasa a "confirmado" y rollback lo descarta. Es lo que permite ver si
  queda un registro parcial.
- _RepoTelemetriaFalso puede simular la BD caida (OperationalError, que la app
  traduce a HTTP 503 BD_NO_DISPONIBLE) o fallar en un punto concreto.

El "resguardo temporal" de TC-M03-026 se modela como el buffer del dispositivo
Edge (RF-54): mientras la BD esta caida el backend debe rechazar sin perder nada,
y al restablecerse el Edge reenvia el lote por la sincronizacion BUFFER_LOCAL
(SincronizarBufferUseCase, el mismo de POST /iot/telemetria/batch).

Una ejecucion real contra TEST de TC-M03-026 (detener y restaurar el contenedor
de BD) queda para coordinar con Implementacion, como indica la ficha.

Como correrlo (desde la raiz del repo):

    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    python -m pytest tests/Test_Testing/Test_Modulo3/RF-53/TC-M03-G12 -v \
        --html=reporte-TC-M03-G12.html --self-contained-html
"""
from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "postgresql://qa:qa@localhost:5432/qa")

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import OperationalError

from src.telemetry.application.use_cases.ingesta.ingerir_telemetria_use_case import (
    IngerirTelemetriaUseCase,
    SincronizarBufferUseCase,
)
from src.telemetry.domain.entities.telemetria import (
    DispositivoInfo,
    ParametrosCalibacion,
    ReglaVariableI3P1,
)
from src.telemetry.infrastructure.dto.ingerir_telemetria_dto import (
    IngerirTelemetriaBatchDTO,
    IngerirTelemetriaDTO,
)

_DEVICE_ID = 10
_SENSOR_ID = 20
_ID_INFRAESTRUCTURA = 30


def _bd_caida() -> OperationalError:
    return OperationalError("INSERT INTO modulo3.telemetrias ...", None, Exception("connection refused"))


# --------------------------------------------------------------------------- dobles
class _SesionFalsa:
    """Transaccion minima: flush -> pendientes, commit -> confirmados, rollback -> descarta."""

    def __init__(self) -> None:
        self.pendientes: list = []
        self.confirmados: list = []
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1
        self.confirmados.extend(self.pendientes)
        self.pendientes.clear()

    def rollback(self) -> None:
        self.rollbacks += 1
        self.pendientes.clear()


class _RepoTelemetriaFalso:
    def __init__(self, sesion: _SesionFalsa) -> None:
        self.sesion = sesion
        self.caida = False
        self.fallar_en_guardar = False
        self._siguiente_id = 1000

    def existe_duplicado(self, id_sensor, id_variable, timestamp_captura, origen, ventana_agregacion_min=None) -> bool:
        if self.caida:
            raise _bd_caida()
        return any(
            t.id_sensor == id_sensor and t.id_variable == id_variable
            and t.timestamp_captura == timestamp_captura and t.origen == origen
            for t in self.sesion.confirmados
        )

    def guardar(self, entidad):
        if self.caida or self.fallar_en_guardar:
            raise _bd_caida()
        self._siguiente_id += 1
        entidad.id_telemetria = self._siguiente_id
        self.sesion.pendientes.append(entidad)
        return entidad


class _BitacoraFalsa:
    def __init__(self) -> None:
        self.exitos: list[dict] = []
        self.errores: list[dict] = []
        self.fallar_en_exito = False

    def registrar_exito(self, **kwargs) -> None:
        if self.fallar_en_exito:
            raise _bd_caida()
        self.exitos.append(kwargs)

    def registrar_error(self, **kwargs) -> None:
        self.errores.append(kwargs)


class _DispositivoFalso:
    def obtener_dispositivo_activo(self, device_id, sensor_id, access_key) -> Optional[DispositivoInfo]:
        return DispositivoInfo(
            id_dispositivo_iot=device_id,
            id_sensor=sensor_id,
            es_activo_dispositivo=True,
            es_activo_sensor=True,
            id_infraestructura=_ID_INFRAESTRUCTURA,
        )


class _VariableFalsa:
    def obtener_regla(self, tipo_variable, unidad) -> ReglaVariableI3P1:
        return ReglaVariableI3P1(
            id_variable=9,
            tipo_variable="TEMPERATURA_AMBIENTAL",
            categoria="AMBIENTAL",
            unidad_estandar="°C",
            unidades_aceptadas=["°C", "°F", "K"],
            valor_fisico_min=Decimal("-50"),
            valor_fisico_max=Decimal("100"),
        )


class _CalibracionEspia:
    """Devuelve ganancia 1.02 / offset -0.5 y registra que la fase 7 se ejecuto."""

    def __init__(self) -> None:
        self.llamadas = 0

    def obtener_parametros(self, sensor_id, id_dispositivo_iot) -> ParametrosCalibacion:
        self.llamadas += 1
        return ParametrosCalibacion(ganancia=Decimal("1.02"), offset=Decimal("-0.5"), version="2026-10-01")


class _Entorno:
    def __init__(self) -> None:
        self.sesion = _SesionFalsa()
        self.repo = _RepoTelemetriaFalso(self.sesion)
        self.bitacora = _BitacoraFalsa()
        self.calibracion = _CalibracionEspia()
        self.vincular = MagicMock()
        self.evaluar_calidad = MagicMock()
        self.reclasificar = MagicMock()

    def caso_de_uso(self) -> IngerirTelemetriaUseCase:
        return IngerirTelemetriaUseCase(
            db=self.sesion,
            repo=self.repo,
            bitacora_repo=self.bitacora,
            dispositivo_port=_DispositivoFalso(),
            variable_port=_VariableFalsa(),
            calibracion_port=self.calibracion,
            vincular_use_case=self.vincular,
            evaluar_calidad_use_case=self.evaluar_calidad,
            reclasificar_semaforo_use_case=self.reclasificar,
        )


def _lectura(ts: datetime, valor: str = "25.0", origen: str = "TIEMPO_REAL") -> IngerirTelemetriaDTO:
    return IngerirTelemetriaDTO(
        device_id=_DEVICE_ID,
        sensor_id=_SENSOR_ID,
        tipo_variable="TEMPERATURA_AMBIENTAL",
        valor=Decimal(valor),
        unidad="°C",
        timestamp_captura=ts,
        access_key="M03-G12-SERIAL",
        origen=origen,
    )


@pytest.fixture
def entorno() -> _Entorno:
    return _Entorno()


# --------------------------------------------------------------------------- TC-M03-060
def test_tc_m03_060a_fallo_al_escribir_tras_calcular_valor_ajustado_no_deja_registro(entorno):
    """Fallo entre la fase 7 (calibracion ya calculada) y la escritura del registro."""
    entorno.repo.fallar_en_guardar = True

    with pytest.raises(OperationalError):
        entorno.caso_de_uso().execute(_lectura(datetime.now(timezone.utc) - timedelta(seconds=2)))

    assert entorno.calibracion.llamadas == 1, "La falla debe ocurrir despues de calcular valor_ajustado (fase 7)"
    assert entorno.sesion.confirmados == [], "No debe quedar ningun registro en la base principal"
    assert entorno.sesion.pendientes == [], "No debe quedar ningun registro parcial pendiente de la transaccion"
    assert entorno.sesion.rollbacks >= 1, "La transaccion debe revertirse"
    assert entorno.sesion.commits == 0, "No debe confirmarse nada"
    entorno.vincular.execute.assert_not_called()
    entorno.evaluar_calidad.execute.assert_not_called()


def test_tc_m03_060b_fallo_despues_del_flush_y_antes_del_commit_revierte_todo(entorno):
    """El registro ya se escribio (flush) pero la bitacora de exito falla antes del commit."""
    entorno.bitacora.fallar_en_exito = True

    with pytest.raises(OperationalError):
        entorno.caso_de_uso().execute(_lectura(datetime.now(timezone.utc) - timedelta(seconds=2)))

    assert entorno.sesion.confirmados == [], "El registro escrito con flush no debe quedar confirmado"
    assert entorno.sesion.pendientes == [], "No debe quedar el registro en estado intermedio"
    assert entorno.sesion.commits == 0
    entorno.vincular.execute.assert_not_called()
    entorno.evaluar_calidad.execute.assert_not_called()
    entorno.reclasificar.execute.assert_not_called()


def test_tc_m03_060c_el_reintento_del_mismo_dato_se_procesa_completo(entorno):
    """Tras el fallo, el mismo dato se puede reintentar: no queda residuo que lo marque duplicado."""
    ts = datetime.now(timezone.utc) - timedelta(seconds=2)
    entorno.repo.fallar_en_guardar = True
    with pytest.raises(OperationalError):
        entorno.caso_de_uso().execute(_lectura(ts))

    entorno.repo.fallar_en_guardar = False
    resultado = entorno.caso_de_uso().execute(_lectura(ts))

    assert resultado.estado_calidad == "LECTURA_VALIDA"
    assert len(entorno.sesion.confirmados) == 1, "El reintento debe dejar exactamente un registro"
    registro = entorno.sesion.confirmados[0]
    assert registro.valor_crudo == Decimal("25.0")
    assert registro.valor_ajustado == Decimal("25.0") * Decimal("1.02") + Decimal("-0.5")
    assert registro.calibrado is True


# --------------------------------------------------------------------------- TC-M03-026
_N = 20


def _veinte_lecturas() -> list[IngerirTelemetriaDTO]:
    base = datetime.now(timezone.utc) - timedelta(hours=1)
    return [_lectura(base + timedelta(minutes=i), valor=f"{20 + i * 0.1:.1f}", origen="BUFFER_LOCAL") for i in range(_N)]


def test_tc_m03_026a_con_la_bd_caida_ninguna_lectura_queda_a_medias(entorno):
    """Durante la caida, cada lectura se rechaza con error de BD (HTTP 503) sin dejar nada escrito."""
    entorno.repo.caida = True
    for dto in _veinte_lecturas():
        with pytest.raises(OperationalError):
            entorno.caso_de_uso().execute(dto)

    assert entorno.sesion.confirmados == []
    assert entorno.sesion.pendientes == []
    assert entorno.sesion.rollbacks == _N


def test_tc_m03_026b_se_registra_falla_persistencia_por_cada_lectura(entorno):
    """La ficha exige registrar FALLA_PERSISTENCIA cuando la BD principal no esta disponible."""
    entorno.repo.caida = True
    for dto in _veinte_lecturas():
        with pytest.raises(OperationalError):
            entorno.caso_de_uso().execute(dto)

    estados = [e.get("estado_calidad") for e in entorno.bitacora.errores]
    assert estados.count("FALLA_PERSISTENCIA") == _N, (
        f"Se esperaban {_N} eventos FALLA_PERSISTENCIA; la bitacora registro: {estados or 'ninguno'}"
    )


def test_tc_m03_026c_al_restablecerse_los_20_datos_se_procesan_en_orden_sin_perdidas_ni_duplicados(entorno):
    """Tras restaurar la BD, el Edge reenvia su buffer (RF-54) en desorden y con un reenvio repetido."""
    lecturas = _veinte_lecturas()

    entorno.repo.caida = True
    for dto in lecturas:
        with pytest.raises(OperationalError):
            entorno.caso_de_uso().execute(dto)

    entorno.repo.caida = False
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
    capturas = [t.timestamp_captura for t in guardados]
    assert capturas == sorted(capturas), "Los datos deben persistirse en el orden original (cronologico)"
    assert capturas == [dto.timestamp_captura for dto in lecturas]
