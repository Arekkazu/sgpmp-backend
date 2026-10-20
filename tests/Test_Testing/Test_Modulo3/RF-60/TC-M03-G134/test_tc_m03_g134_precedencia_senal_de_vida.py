"""
TC-M03-G134 (RF-60 CA-17/E10/Restricciones 8 y 11, CU-03) - "Precedencia de
la señal de vida y tolerancia a interrupciones." Consolida CP-EST-07/08/10.
Sin TC previo exacto para este CU en RF-60 (TC-M03-271, pensado para este
tema, quedó vacío -- nunca se construyó).

Código bajo prueba:
    src/telemetry/application/use_cases/infraestructura/recibir_heartbeat_use_case.py
    src/telemetry/application/use_cases/ingesta/ingerir_telemetria_use_case.py
    src/telemetry/domain/entities/estado_dispositivo_iot.py

HALLAZGO PRINCIPAL (invalida (a), (c) y reencuadra (b)): la ficha asume que
`timestamp_ultimo_contacto = MAX(heartbeat, telemetría válida RF-53)` -- es
decir, que una telemetría válida TAMBIÉN cuenta como prueba de vida. Esto NO
existe en el código: búsqueda exhaustiva en
`src/telemetry/application/use_cases/ingesta/` confirma que NINGÚN caso de
uso de ingesta de telemetría (`ingerir_telemetria_use_case.py`) importa,
inyecta ni llama a `EstadoDispositivoIoTRepository` o a nada que toque
`fecha_ultimo_contacto` -- la ingesta de telemetría (RF-53) y la máquina de
estados de conectividad (RF-60) están completamente desacopladas en el
código actual. Solo `recibir_heartbeat_use_case.py` actualiza
`fecha_ultimo_contacto`.

Consecuencia:
(a) MAX(heartbeat, telemetría) -- FALSO. El máximo real es simplemente
    "el último heartbeat", siempre, sin importar cuánta telemetría llegue
    entre medio.
(b) "Telemetría inválida o rechazada NO cuenta como prueba de vida" --
    técnicamente CIERTO, pero no por ninguna validación explícita: NINGUNA
    telemetría (válida o inválida) cuenta, así que esta aserción pasa por
    una razón distinta a la que la ficha supone (no hay un filtro
    válida/inválida que aplicar porque el canal entero está desconectado).
(c) CA-17 (telemetría cada 10 min sin heartbeat -> permanece ACTIVO, alerta
    HEARTBEAT_AUSENTE LEVE en el primer ciclo tras 10 min) -- FALSO. Un
    dispositivo sin heartbeats (aunque envíe telemetría) sigue el algoritmo
    normal de `evaluar_transicion()`: degrada a SIN_SEÑAL a los 5 minutos
    (UMBRAL_ACTIVO_SEG fijo, igual que TC-M03-269), no permanece ACTIVO
    hasta los 10 min. Además, `HEARTBEAT_AUSENTE` no existe como tipo de
    alerta en ningún archivo de `src/` (grep exhaustivo) -- el job periódico
    solo genera alertas con `tipo_variable='FALLO_CONECTIVIDAD'`
    (`evaluar_estado_dispositivos_use_case.py`), nunca 'HEARTBEAT_AUSENTE'.

(d) [BLOQUEADO en la ficha] vinculado explícitamente a G132(c). Mismo
    resultado que ya se encontró ahí: NO reproduce como "zona indefinida".
    Con buffer inactivo, 11 minutos de silencio caen limpiamente en
    SIN_SEÑAL (dentro de [5 min, 24 h)), el mismo tramo que cualquier otro
    valor en ese rango -- no hay ninguna "supresión de un único heartbeat"
    que produzca un resultado distinto o indefinido. Se cierra citando
    TC-M03-G132(c), igual que pide la propia ficha ("mismo defecto, misma
    resolución").

Cómo se prueba: pytest a nivel de caso de uso (repos de prueba), mismo
criterio que TC-M03-269/270 -- "simulador LoRaWAN" se interpreta como DTOs
de heartbeat/telemetría simulados, sin requerir un gateway real.

Como correrlo (Windows necesita el stub de fcntl):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    python -m pytest <ruta>\\test_tc_m03_g134_precedencia_senal_de_vida.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M03-G134.html --self-contained-html
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.telemetry.application.use_cases.infraestructura.evaluar_estado_dispositivos_use_case import (
    EvaluarEstadoDispositivosUseCase,
)
from src.telemetry.domain.entities.estado_dispositivo_iot import UMBRAL_ACTIVO_SEG, EstadoDispositivoIoT
from datetime import datetime, timedelta, timezone

REPO_ROOT = Path(__file__).resolve().parents[5]
AHORA = datetime(2026, 10, 19, 12, 0, 0, tzinfo=timezone.utc)


def _estado(estado_actual: str, fecha_ultimo_contacto: datetime) -> EstadoDispositivoIoT:
    return EstadoDispositivoIoT(
        id_estado_dispositivo_iot=1, id_dispositivo_iot=134, estado_actual=estado_actual,
        fecha_ultimo_contacto=fecha_ultimo_contacto, id_ultimo_heartbeat=1,
        tiempo_sin_contacto=0, causa_primaria=None, causas_secundarias=None,
        fecha_ultima_actualizacion=fecha_ultimo_contacto, id_usuario=None,
    )


def _congelar_reloj(modulo, ahora: datetime):
    import unittest.mock as mock

    class _DatetimeFijo(datetime):
        @classmethod
        def now(cls, tz=None):
            return ahora

    return mock.patch.object(modulo, 'datetime', _DatetimeFijo)


class TestSubCasoAIngestaDeTelemetriaNuncaActualizaUltimoContacto:
    """(a) HALLAZGO: ningun caso de uso de ingesta de telemetria (RF-53) toca
    fecha_ultimo_contacto ni el repositorio de estado del dispositivo -- el
    MAX(heartbeat, telemetria) de la ficha no existe, es solo heartbeat."""

    def test_ingerir_telemetria_use_case_no_usa_repositorio_de_estado_de_dispositivo(self):
        archivo = REPO_ROOT / 'src' / 'telemetry' / 'application' / 'use_cases' / 'ingesta' / 'ingerir_telemetria_use_case.py'
        texto = archivo.read_text(encoding='utf-8')
        assert 'EstadoDispositivoIoTRepository' not in texto and 'fecha_ultimo_contacto' not in texto, (
            'Si esto aparece, RF-53 ya empezo a actualizar fecha_ultimo_contacto -- (a) podria estar '
            'implementado, revisar la logica real antes de descartar el hallazgo.'
        )
        pytest.fail(
            "HALLAZGO (a): ingerir_telemetria_use_case.py no referencia EstadoDispositivoIoTRepository "
            "ni fecha_ultimo_contacto en ningun lugar -- la ingesta de telemetria (RF-53) esta "
            "completamente desacoplada de la maquina de estados de conectividad (RF-60). El unico "
            "camino que actualiza fecha_ultimo_contacto es recibir_heartbeat_use_case.py. El "
            "MAX(heartbeat, telemetria) que pide la ficha no existe: el maximo real es siempre 'el "
            "ultimo heartbeat', sin importar cuanta telemetria llegue entre medio."
        )


class TestSubCasoCCA17NoImplementado:
    """(c) [CORREGIDO en la ficha] CA-17: sin heartbeat pero con telemetria cada
    10 min, deberia permanecer ACTIVO con alerta HEARTBEAT_AUSENTE (LEVE) en el
    primer ciclo tras 10 min, sin repetirse. HALLAZGO: ninguna parte de esto
    existe -- el dispositivo degrada normal (5 min) y la alerta no existe."""

    def test_sin_heartbeat_degrada_a_sin_senal_a_los_5_min_no_permanece_activo_hasta_10(self):
        uc_modulo = __import__(
            'src.telemetry.application.use_cases.infraestructura.evaluar_estado_dispositivos_use_case',
            fromlist=['EvaluarEstadoDispositivosUseCase'],
        )
        estado = _estado('ACTIVO', AHORA - timedelta(minutes=7))  # 7 min: entre el "5min real" y el "10min de la ficha"
        estado_repo = MagicMock()
        estado_repo.listar_activos.return_value = [estado]
        transicion_repo = MagicMock()
        periodo_repo = MagicMock()
        periodo_repo.obtener_abierto_por_dispositivo.return_value = None
        alerta_repo = MagicMock()
        alerta_repo.guardar.return_value = MagicMock(id_alerta=1000)
        historico_alerta_repo = MagicMock()
        uc = EvaluarEstadoDispositivosUseCase(
            db=MagicMock(), estado_repo=estado_repo, transicion_repo=transicion_repo,
            periodo_repo=periodo_repo, alerta_repo=alerta_repo, historico_alerta_repo=historico_alerta_repo,
        )
        with _congelar_reloj(uc_modulo, AHORA):
            uc.execute()

        assert estado.estado_actual != 'ACTIVO', (
            f'HALLAZGO (c): a los 7 minutos sin heartbeat (dentro de la ventana [5min real, 10min de '
            f'la ficha)) la ficha pide que el dispositivo permanezca ACTIVO -- pero ya degrado a '
            f'{estado.estado_actual!r} porque el umbral real y fijo es {UMBRAL_ACTIVO_SEG}s (5 min), '
            f'no 10 min. CA-17 no esta implementado: la telemetria no sostiene el estado ACTIVO.'
        )

    def test_no_existe_la_alerta_heartbeat_ausente_en_ningun_lado(self):
        archivos_con_alerta = [
            str(p.relative_to(REPO_ROOT)) for p in (REPO_ROOT / 'src').rglob('*.py')
            if 'HEARTBEAT_AUSENTE' in p.read_text(encoding='utf-8', errors='ignore')
        ]
        pytest.fail(
            f"HALLAZGO (c): 'HEARTBEAT_AUSENTE' no existe en ningun archivo de src/ (encontrados: "
            f"{archivos_con_alerta or 'ninguno'}). El job periodico solo genera alertas con "
            f"tipo_variable='FALLO_CONECTIVIDAD' -- no hay ninguna alerta distinta para 'hay "
            f"telemetria pero no heartbeat', porque la telemetria ni siquiera se considera."
        ) if not archivos_con_alerta else None


class TestSubCasoDSupresionUnHeartbeatNoEsZonaIndefinida:
    """(d) [BLOQUEADO en la ficha, vinculado a G132(c)]: 11 min de silencio (un
    heartbeat suprimido) NO cae en ninguna zona indefinida -- mismo resultado
    que TC-M03-G132(c), se cierra citandolo."""

    def test_11_minutos_de_silencio_resuelve_limpio_a_sin_senal(self):
        estado = _estado('ACTIVO', AHORA)
        resultado = estado.evaluar_transicion(tiempo_sin_contacto_seg=11 * 60, estado_local_buffer=None)
        assert resultado == 'SIN_SEÑAL', (
            f'(d) cita G132(c) como "misma zona indefinida" -- pero TC-M03-G132(c) ya confirmo que '
            f'esa zona no existe: a los 11 min (660s) el algoritmo resuelve limpio a {resultado!r}, '
            f'sin ambiguedad. Se cierra (d) con la misma conclusion que G132(c), no hay nada nuevo '
            f'que escalar.'
        )
