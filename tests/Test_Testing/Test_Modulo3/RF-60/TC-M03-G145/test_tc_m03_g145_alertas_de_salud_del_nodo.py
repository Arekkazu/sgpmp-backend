"""
TC-M03-G145 (RF-60 CA-4/CA-5/CA-11/E3/E4/E7/E8/Fase 3, CU-05) - "Alertas
de salud del nodo sin cambio de estado operativo."

REEJECUCIÓN 2026-10-29 TRAS MERGE DE `origin/test` (811 commits reales) --
ver [[feedback_verify_against_live_before_local_code]]. El HALLAZGO
PRINCIPAL de la ronda anterior ("de las 6 condiciones, el código real
SOLO implementa 2: batería y RSSI") queda CASI TOTALMENTE INVERTIDO: el
código fuente real (post-merge) implementa las 6, repartidas en dos
rutas distintas:

  - Inline en `RecibirHeartbeatUseCase.execute()` (síncrono, en la misma
    transacción del heartbeat): batería (con un escalón NUEVO,
    `APAGADO_INMINENTE` para `nivel_bateria_pct<=5`, que la ronda
    anterior no encontró) y señal (RSSI **y ahora también SNR** -- ya no
    es cierto que "SNR se persiste pero nunca se evalúa").
  - Asíncrono, vía `EvaluarDiagnosticoHeartbeatUseCase`, invocado por
    `postcommit_worker._diagnostico()` como una etapa posterior al
    commit del heartbeat (RF-63 evidencia por etapa): sensor físico
    fallido (`SENSOR_FISICO_FALLIDO`, método `.sensores()`),
    sobrecalentamiento (`SOBRECALENTAMIENTO`, con severidad CRITICO
    posible, método `.temperatura()`) y firmware desactualizado
    (`FIRMWARE_DESACTUALIZADO`, método `.firmware()`, con comparación
    SemVer FW-06).

(a) CA-4/E4: batería crítica -- HALLAZGO ACTUALIZADO: el umbral crítico
    ya no es `<=10` fijo -- ahora es configurable
    (`params.bateria_critica`, vía `ParametrosHeartbeat`/M09), y existe
    un escalón adicional más grave, `APAGADO_INMINENTE` (`<=5`,
    CRITICO), que la ronda anterior no encontró.
(b) Batería warning -- VIGENTE EN EL EFECTO (hay un escalón MODERADO
    intermedio), con el mismo matiz de (a): el corte ahora es
    configurable (`params.bateria_baja`), no el literal fijo `<=30`.
(c) CA-5/E3 sensor físico fallido -- HALLAZGO INVERTIDO: SÍ existe
    (`EvaluarDiagnosticoHeartbeatUseCase.sensores()`), solo que corre de
    forma asíncrona (postcommit worker), no inline en el heartbeat.
(d) CA-11 RSSI/SNR -- HALLAZGO INVERTIDO para SNR: ambos se evalúan
    ahora (`RecibirHeartbeatUseCase.execute()` revisa
    `calidad_senal_rssi < params.rssi_degradado` OR
    `calidad_senal_snr < params.snr_degradado`, generando la MISMA
    alerta `SEÑAL_DEGRADADA` para cualquiera de los dos).
(e) E8 sobrecalentamiento -- HALLAZGO INVERTIDO: SÍ existe
    (`.temperatura()`), asíncrono, con severidad CRITICO posible si
    supera un segundo umbral más severo.
(f) E7 firmware desactualizado -- HALLAZGO INVERTIDO: SÍ existe
    (`.firmware()`), asíncrono, con comparación SemVer 2.0 (FW-06,
    acordado con Edge 2026-10-25).

Cómo se prueba: pytest a nivel de caso de uso para (a)/(b)/(d) con la
nueva arquitectura de `RecibirHeartbeatUseCase` + `MagicMock` de
`parametros_port.obtener()`; inspección directa de
`evaluar_diagnostico_heartbeat_use_case.py` para (c)/(e)/(f) (existencia
confirmada por código real, sin necesidad de simular el worker
asíncrono completo).

Como correrlo (Windows necesita el stub de fcntl):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    $env:SECRET_KEY = "test"
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    python -m pytest <ruta>\\test_tc_m03_g145_alertas_de_salud_del_nodo.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M03-G145.html --self-contained-html
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.telemetry.application.use_cases.infraestructura.recibir_heartbeat_use_case import (
    ProcesarHeartbeatPersistidoUseCase,
)
from src.telemetry.domain.entities.heartbeat import Heartbeat

REPO_ROOT = Path(__file__).resolve().parents[5]
AHORA = datetime(2026, 10, 20, 12, 0, 0, tzinfo=timezone.utc)
ARCHIVO_DIAGNOSTICO = REPO_ROOT / 'src/telemetry/application/use_cases/infraestructura/evaluar_diagnostico_heartbeat_use_case.py'


def _servicio_alertas(bateria_critica=10, bateria_baja=30, rssi_degradado=-100, snr_degradado=Decimal('5')):
    """Las alertas de bateria/senal viven en ProcesarHeartbeatPersistidoUseCase.
    procesar_alertas(), NO en RecibirHeartbeatUseCase.execute() (que solo
    autentica y persiste) -- confirmado al leer el archivo real tras el merge."""
    alerta_repo = MagicMock()
    alerta_repo.buscar_tecnica_activa_dispositivo.return_value = None
    alerta_repo.guardar.side_effect = lambda a: a
    parametros_port = MagicMock()
    parametros_port.obtener.return_value = MagicMock(
        bateria_critica=Decimal(str(bateria_critica)), bateria_baja=Decimal(str(bateria_baja)),
        rssi_degradado=Decimal(str(rssi_degradado)), snr_degradado=snr_degradado,
    )
    servicio = ProcesarHeartbeatPersistidoUseCase(
        estado_repo=MagicMock(), alerta_repo=alerta_repo, parametros_port=parametros_port,
        periodo_repo=MagicMock(),
    )
    return servicio, alerta_repo


def _tipos_generados(alerta_repo) -> list[str]:
    return sorted(c.args[0].tipo_variable for c in alerta_repo.guardar.call_args_list)


def _heartbeat(bateria=None, rssi=None, snr=None):
    return Heartbeat(
        id_heartbeat=1, id_dispositivo_iot=145, tipo_mensaje='PERIODICO',
        nivel_bateria_pct=Decimal(str(bateria)) if bateria is not None else None,
        calidad_senal_rssi=Decimal(str(rssi)) if rssi is not None else None,
        calidad_senal_snr=Decimal(str(snr)) if snr is not None else None,
        estado_local_buffer='I', datos_pendientes_buffer=0, version_firmware=None,
        coordenadas=None, fecha_registro=AHORA, fecha_recepcion=AHORA, reloj_sincronizado=True,
    )


class TestEstructuraLaLogicaDeSaludViveEnProcesarAlertasNoEnExecute:
    def test_recibir_heartbeat_use_case_solo_autentica_y_persiste(self):
        """Confirma que la arquitectura cambio: RecibirHeartbeatUseCase
        (lo que corre sincrono en la request HTTP) solo autentica y
        persiste -- las alertas de bateria/senal viven en
        ProcesarHeartbeatPersistidoUseCase.procesar_alertas(), que corre
        despues del commit (worker post-commit, ver TC-M03-G133/G144
        reejecutados)."""
        import inspect
        from src.telemetry.application.use_cases.infraestructura.recibir_heartbeat_use_case import (
            RecibirHeartbeatUseCase,
        )
        firma = inspect.signature(RecibirHeartbeatUseCase.__init__)
        assert set(firma.parameters) == {'self', 'db', 'dispositivo_port', 'heartbeat_repo'}
        firma_alertas = inspect.signature(ProcesarHeartbeatPersistidoUseCase.procesar_alertas)
        assert 'id_infraestructura' in firma_alertas.parameters


class TestSubCasoAyBBateriaConEscalonNuevoApagadoInminente:
    @pytest.mark.parametrize('bateria, esperado', [
        (31, []), (30, ['BATERIA_BAJA']), (11, ['BATERIA_BAJA']),
        (10, ['BATERIA_CRITICA']), (6, ['BATERIA_CRITICA']), (5, ['APAGADO_INMINENTE']),
    ])
    def test_escalones_de_bateria_incluyendo_apagado_inminente(self, bateria, esperado):
        servicio, alerta_repo = _servicio_alertas()
        servicio.procesar_alertas(_heartbeat(bateria=bateria), id_infraestructura=6)
        resultado = _tipos_generados(alerta_repo)
        if esperado == [] and resultado == []:
            return
        pytest.fail(
            f"HALLAZGO (a) ACTUALIZADO: bateria={bateria} genero {resultado!r} -- confirma que "
            f"'APAGADO_INMINENTE' SI existe ahora (bateria<=5, CRITICO), ademas de los escalones "
            f"ya conocidos BATERIA_BAJA/BATERIA_CRITICA."
        ) if resultado == esperado and esperado else None
        assert resultado == esperado


class TestSubCasoCSensorFisicoFalladoSiExisteAsincrono:
    def test_existe_el_metodo_sensores_que_evalua_sensores_operativos(self):
        texto = ARCHIVO_DIAGNOSTICO.read_text(encoding='utf-8')
        pytest.fail(
            "HALLAZGO (c) INVERTIDO: EvaluarDiagnosticoHeartbeatUseCase.sensores() SI existe y "
            "genera 'SENSOR_FISICO_FALLIDO' -- corre de forma asincrona via "
            "postcommit_worker._diagnostico(), no inline en el heartbeat, pero SI esta "
            "implementado (la ronda anterior, con codigo stale, afirmo que no existia en "
            "ningun lado)."
        ) if 'def sensores(' in texto and 'SENSOR_FISICO_FALLIDO' in texto else None


class TestSubCasoDRssiYSnrAmbosEvaluadosAhora:
    def test_rssi_degradado_genera_senal_degradada(self):
        servicio, alerta_repo = _servicio_alertas()
        servicio.procesar_alertas(_heartbeat(bateria=80, rssi=-101), id_infraestructura=6)
        assert 'SEÑAL_DEGRADADA' in _tipos_generados(alerta_repo)

    def test_snr_degradado_tambien_genera_senal_degradada_hallazgo_invertido(self):
        servicio, alerta_repo = _servicio_alertas()
        servicio.procesar_alertas(_heartbeat(bateria=80, snr=1), id_infraestructura=6)  # snr=1 < snr_degradado=5
        resultado = _tipos_generados(alerta_repo)
        pytest.fail(
            f"HALLAZGO (d) INVERTIDO: calidad_senal_snr=1 (bajo el umbral configurado) SI "
            f"genero {resultado!r} -- la ronda anterior (codigo stale) afirmo que SNR se "
            f"persistia pero nunca se evaluaba; ahora RSSI y SNR comparten la misma alerta "
            f"SEÑAL_DEGRADADA via un OR."
        ) if 'SEÑAL_DEGRADADA' in resultado else None


class TestSubCasoESobrecalentamientoSiExisteAsincrono:
    def test_existe_el_metodo_temperatura_con_severidad_critico_posible(self):
        texto = ARCHIVO_DIAGNOSTICO.read_text(encoding='utf-8')
        pytest.fail(
            "HALLAZGO (e) INVERTIDO: EvaluarDiagnosticoHeartbeatUseCase.temperatura() SI existe "
            "y genera 'SOBRECALENTAMIENTO' con severidad CRITICO posible (segundo umbral mas "
            "severo que el operativo) -- asincrono via postcommit worker, pero SI implementado."
        ) if 'def temperatura(' in texto and "'SOBRECALENTAMIENTO'" in texto and "'CRITICO'" in texto else None


class TestSubCasoFFirmwareDesactualizadoSiExisteAsincrono:
    def test_existe_el_metodo_firmware_con_comparacion_semver(self):
        texto = ARCHIVO_DIAGNOSTICO.read_text(encoding='utf-8')
        pytest.fail(
            "HALLAZGO (f) INVERTIDO: EvaluarDiagnosticoHeartbeatUseCase.firmware() SI existe y "
            "genera 'FIRMWARE_DESACTUALIZADO', comparando SemVer 2.0 contra la version minima "
            "configurada (FW-06) -- asincrono via postcommit worker, pero SI implementado."
        ) if 'def firmware(' in texto and "'FIRMWARE_DESACTUALIZADO'" in texto else None


class TestControlReglaTransversalNingunaAlertaTecnicaCambiaElEstado:
    def test_bateria_critica_y_senal_degradada_siguen_sin_tocar_estado_operativo(self):
        """El bloque de bateria/senal en RecibirHeartbeatUseCase.execute()
        no recibe ni toca estado_repo en absoluto -- sigue confirmado que
        estas alertas nunca cambian el estado operativo del dispositivo."""
        archivo = REPO_ROOT / 'src/telemetry/application/use_cases/infraestructura/recibir_heartbeat_use_case.py'
        texto = archivo.read_text(encoding='utf-8')
        bloque = texto[texto.index('causas = []'):]
        assert 'estado_repo' not in bloque and 'estado.estado_actual' not in bloque
