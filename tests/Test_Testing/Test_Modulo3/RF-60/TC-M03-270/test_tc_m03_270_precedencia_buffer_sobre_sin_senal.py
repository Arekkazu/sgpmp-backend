"""
TC-M03-270 (RF-60 PASO 2/CA-2/CA-18/CA-21, CU-04) - Precedencia del PASO 2
(buffer) sobre el PASO 3 (sin señal).

Código bajo prueba:
    src/telemetry/application/use_cases/infraestructura/recibir_heartbeat_use_case.py
        RecibirHeartbeatUseCase -- vía de "en vivo", cuando SI llega un heartbeat.
    src/telemetry/application/use_cases/infraestructura/evaluar_estado_dispositivos_use_case.py
        EvaluarEstadoDispositivosUseCase -- tarea periódica (60 s), cuando NO llega
        heartbeat nuevo.
    src/telemetry/domain/entities/estado_dispositivo_iot.py
        EstadoDispositivoIoT.evaluar_transicion() -- algoritmo de 4 pasos.

HALLAZGO PRINCIPAL (invalida literalmente (a) CA-21 tal como la plantea la
ficha): la precedencia del buffer sobre "sin señal" SOLO existe en el instante
en que llega un heartbeat real. `estado_local_buffer` NO es un campo
persistente de `EstadoDispositivoIoT` (la entidad de estado "actual" del
dispositivo) -- es un campo transitorio de cada fila `Heartbeat`. Cuando no
llega un heartbeat nuevo, la tarea periódica (la que detectaría "t=18 min sin
nada nuevo") llama a `evaluar_transicion()` con `estado_local_buffer=None`
SIEMPRE y sin excepción (`evaluar_estado_dispositivos_use_case.py` línea 53:
"sin heartbeat reciente -> no conocemos buffer"). El job NUNCA consulta el
último heartbeat conocido del dispositivo para recordar que estaba en
`estado_local_buffer='A'`.

Consecuencia observable: un dispositivo cuyo ÚLTIMO heartbeat reportó
`estado_local_buffer='A'` (y que por eso quedó en BUFFER_ACTIVO en ese
instante) es DEGRADADO a SIN_SEÑAL por la tarea periódica apenas pasan 5
minutos sin un heartbeat nuevo (el umbral real y fijo de
`UMBRAL_ACTIVO_SEG`, ver TC-M03-269) -- 13 minutos antes del t=18 min que la
ficha usa como escenario. Es decir, el PASO 2 solo "gana" al PASO 3 mientras
hay heartbeats llegando; en el vacío entre heartbeats, el PASO 3 (tiempo sin
contacto) SIEMPRE gana, sin importar cuál fue el último estado de buffer
reportado. Esto contradice directamente CA-21 tal como la redacta la ficha
("t=18 min con último heartbeat indicando estado_buffer_local=ACTIVO ->
BUFFER_ACTIVO").

(b) CA-18 SÍ se confirma: mientras SIGUEN llegando heartbeats regulares con
`estado_local_buffer='A'`, cada uno fija `nuevo_estado='BUFFER_ACTIVO'` de
forma incondicional (líneas 121-124 de `recibir_heartbeat_use_case.py`), sin
mirar el tiempo transcurrido ni la telemetría -- el PASO 2 sí precede al PASO
3 correctamente en esta vía.

(c) HALLAZGO: `umbral_buffer_prolongado` y la alerta `BUFFER_PROLONGADO` NO
EXISTEN en ninguna parte de `src/` (confirmado por búsqueda exhaustiva). No
hay ningún umbral de "demasiado tiempo en buffer" ni alerta asociada. Tampoco
existe ninguna distinción de comportamiento para `estado_local_buffer='L'`
(buffer LLENO, el tercer valor válido del DTO junto a 'I'/'A') -- un
dispositivo con el buffer lleno (peor escenario que "buffer activo normal")
recibe exactamente el mismo trato que uno con buffer inactivo: cae al `else`
de `recibir_heartbeat_use_case.py` y queda en ACTIVO, sin alerta.

(d) HALLAZGO: `datos_pendientes_buffer` se persiste en cada heartbeat
(`heartbeat_model.py`) pero NUNCA se lee en ninguna decisión de negocio -- ni
en `recibir_heartbeat_use_case.py` ni en `estado_dispositivo_iot.py`
(confirmado por búsqueda exhaustiva). La transición BUFFER_ACTIVO -> ACTIVO
depende ÚNICAMENTE de que `estado_local_buffer` cambie de `'A'` a otro valor
en el heartbeat siguiente -- NO de que `datos_pendientes_buffer` llegue a 0,
como asume la ficha ("al vaciarse"). Un heartbeat con `estado_local_buffer='A'`
y `datos_pendientes_buffer=0` (buffer ya vacío pero el dispositivo sigue
reportándose como "en buffer") queda en BUFFER_ACTIVO igual; uno con
`estado_local_buffer` distinto de 'A' y `datos_pendientes_buffer=9999`
(buffer lleno de datos sin enviar) pasaría a ACTIVO igual. El campo es
puramente informativo/de auditoría, no de control de estado.

Cómo se prueba (Backend + API / pytest, tal como pide la ficha -- "simulador
de nodos" se interpreta como invocar los casos de uso con DTOs de heartbeat
simulados, sin depender de un dispositivo IoT real): nivel caso de uso con
repos/puertos de prueba, igual que TC-M03-269.

Como correrlo (desde la raíz del repo; stub de fcntl en Windows, ver memoria
del proyecto):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    python -m pytest <ruta>\\test_tc_m03_270_precedencia_buffer_sobre_sin_senal.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M03-270.html --self-contained-html
"""
from __future__ import annotations

import re
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.telemetry.application.use_cases.infraestructura.evaluar_estado_dispositivos_use_case import (
    EvaluarEstadoDispositivosUseCase,
)
from src.telemetry.application.use_cases.infraestructura.recibir_heartbeat_use_case import (
    RecibirHeartbeatUseCase,
)
from src.telemetry.domain.entities.estado_dispositivo_iot import EstadoDispositivoIoT
from src.telemetry.infrastructure.dto.heartbeat_dto import HeartbeatDTO

REPO_ROOT = Path(__file__).resolve().parents[5]
AHORA = datetime(2026, 9, 26, 12, 0, 0, tzinfo=timezone.utc)


def _estado(estado_actual: str, fecha_ultimo_contacto: datetime, id_heartbeat=1) -> EstadoDispositivoIoT:
    return EstadoDispositivoIoT(
        id_estado_dispositivo_iot=1, id_dispositivo_iot=99, estado_actual=estado_actual,
        fecha_ultimo_contacto=fecha_ultimo_contacto, id_ultimo_heartbeat=id_heartbeat,
        tiempo_sin_contacto=0, causa_primaria=None, causas_secundarias=None,
        fecha_ultima_actualizacion=fecha_ultimo_contacto, id_usuario=None,
    )


def _heartbeat_dto(estado_local_buffer, datos_pendientes_buffer=0) -> HeartbeatDTO:
    return HeartbeatDTO(
        tipo_mensaje='PERIODICO',
        nivel_bateria_pct=Decimal('80'),
        estado_local_buffer=estado_local_buffer,
        datos_pendientes_buffer=datos_pendientes_buffer,
        fecha_registro=AHORA,
    )


def _heartbeat_use_case(estado_existente: EstadoDispositivoIoT):
    db = MagicMock()
    dispositivo_port = MagicMock()
    dispositivo_port.validar_dispositivo_heartbeat.return_value = MagicMock(es_activo=True, id_infraestructura=5)
    heartbeat_repo = MagicMock()
    heartbeat_repo.guardar.side_effect = lambda hb: replace(hb, id_heartbeat=1)
    estado_repo = MagicMock()
    estado_repo.obtener_por_dispositivo.return_value = estado_existente
    transicion_repo = MagicMock()
    periodo_repo = MagicMock()
    periodo_repo.obtener_abierto_por_dispositivo.return_value = None
    alerta_repo = MagicMock()
    historico_alerta_repo = MagicMock()
    uc = RecibirHeartbeatUseCase(
        db=db, dispositivo_port=dispositivo_port, heartbeat_repo=heartbeat_repo,
        estado_repo=estado_repo, transicion_repo=transicion_repo, periodo_repo=periodo_repo,
        alerta_repo=alerta_repo, historico_alerta_repo=historico_alerta_repo,
    )
    return uc, estado_existente, transicion_repo, periodo_repo, alerta_repo


def _congelar_reloj(modulo, ahora: datetime):
    import unittest.mock as mock

    class _DatetimeFijo(datetime):
        @classmethod
        def now(cls, tz=None):
            return ahora

    return mock.patch.object(modulo, 'datetime', _DatetimeFijo)


class TestGrupoACA21PrecedenciaNoSobreviveSinHeartbeatsNuevos:
    """(a) CA-21: la ficha pide que, 18 minutos después del último heartbeat (que
    reportó buffer ACTIVO), el dispositivo SIGA en BUFFER_ACTIVO. El algoritmo real
    de la tarea periódica no tiene memoria del buffer -- degrada a SIN_SEÑAL."""

    def test_18_min_despues_del_ultimo_heartbeat_con_buffer_activo_degrada_a_sin_senal(self):
        import src.telemetry.application.use_cases.infraestructura.evaluar_estado_dispositivos_use_case as modulo

        estado = _estado('BUFFER_ACTIVO', AHORA - timedelta(minutes=18))
        estado_repo = MagicMock()
        estado_repo.listar_activos.return_value = [estado]
        transicion_repo = MagicMock()
        periodo_repo = MagicMock()
        periodo_repo.obtener_abierto_por_dispositivo.return_value = None
        alerta_repo = MagicMock()
        alerta_repo.guardar.return_value = MagicMock(id_alerta=900)
        historico_alerta_repo = MagicMock()
        uc = EvaluarEstadoDispositivosUseCase(
            db=MagicMock(), estado_repo=estado_repo, transicion_repo=transicion_repo,
            periodo_repo=periodo_repo, alerta_repo=alerta_repo, historico_alerta_repo=historico_alerta_repo,
        )

        with _congelar_reloj(modulo, AHORA):
            uc.execute()

        if estado.estado_actual == 'BUFFER_ACTIVO':
            return  # si algun dia el job si recuerda el buffer, esta parte de la ficha quedaria confirmada

        alerta_generada = alerta_repo.guardar.called
        pytest.fail(
            f"HALLAZGO CA-21: a los 18 min sin heartbeats nuevos, un dispositivo cuyo ultimo heartbeat "
            f"reporto estado_local_buffer='A' (BUFFER_ACTIVO) fue degradado a {estado.estado_actual!r} "
            f"por la tarea periodica, en vez de permanecer en BUFFER_ACTIVO como pide la ficha. La tarea "
            f"periodica (evaluar_estado_dispositivos_use_case.py) siempre invoca evaluar_transicion con "
            f"estado_local_buffer=None -- no consulta el ultimo heartbeat conocido del dispositivo. "
            f"{'Ademas SI se genero una alerta de inactividad' if alerta_generada else 'No se genero alerta'}, "
            f"cuando la ficha pide explicitamente 'sin alerta de inactividad'."
        )


class TestGrupoBCA18BufferActivoConHeartbeatsRegulares:
    """(b) CA-18: mientras siguen llegando heartbeats con estado_local_buffer='A', el
    dispositivo permanece en BUFFER_ACTIVO sin importar cuanto tiempo lleve sin
    telemetria -- esta parte SI la cumple el codigo real."""

    def test_heartbeats_regulares_con_buffer_activo_mantienen_buffer_activo(self):
        estado = _estado('ACTIVO', AHORA - timedelta(minutes=5))
        uc, estado_existente, transicion_repo, periodo_repo, alerta_repo = _heartbeat_use_case(estado)

        import src.telemetry.application.use_cases.infraestructura.recibir_heartbeat_use_case as modulo
        # 3 "ciclos de muestreo" sin telemetria, cada uno con un heartbeat de buffer activo.
        for ciclo in range(3):
            ahora_ciclo = AHORA + timedelta(minutes=ciclo * 5)
            with _congelar_reloj(modulo, ahora_ciclo):
                uc.execute(_heartbeat_dto('A', datos_pendientes_buffer=10 * (ciclo + 1)), device_id=99, access_key='k')

        assert estado_existente.estado_actual == 'BUFFER_ACTIVO'
        # El cambio a BUFFER_ACTIVO ocurrio una sola vez (de ACTIVO a BUFFER_ACTIVO en el 1er ciclo);
        # los ciclos 2 y 3 no generan una transicion nueva porque el estado no cambia.
        assert transicion_repo.registrar.call_count == 1
        alerta_repo.guardar.assert_not_called()  # sin alerta de inactividad mientras hay buffer activo


class TestGrupoCBufferProlongadoNoImplementado:
    """(c) HALLAZGO: ni el umbral ni la alerta de 'buffer prolongado' existen en el
    backend. Tampoco hay tratamiento especial para estado_local_buffer='L' (lleno)."""

    def test_no_existe_umbral_buffer_prolongado_en_el_codigo(self):
        archivos_con_umbral = [
            str(p.relative_to(REPO_ROOT)) for p in (REPO_ROOT / 'src').rglob('*.py')
            if re.search(r'umbral_buffer_prolongado|BUFFER_PROLONGADO', p.read_text(encoding='utf-8', errors='ignore'))
        ]
        pytest.fail(
            f"HALLAZGO (c): no existe 'umbral_buffer_prolongado' ni la alerta 'BUFFER_PROLONGADO' en "
            f"ningun archivo de src/ (encontrados: {archivos_con_umbral or 'ninguno'}). RF-60 PASO 2 no "
            f"tiene implementado ningun limite de tiempo para permanecer en BUFFER_ACTIVO ni una alerta "
            f"que avise cuando se supera."
        ) if not archivos_con_umbral else None

    def test_buffer_lleno_L_no_recibe_tratamiento_distinto_de_buffer_inactivo(self):
        """El DTO admite 'L'=LLENO ademas de 'A'=ACTIVO/'I'=INACTIVO, pero el use case
        solo distingue 'A' de 'todo lo demas' -- 'L' cae al mismo else que 'I'."""
        estado = _estado('ACTIVO', AHORA - timedelta(minutes=1))
        uc, estado_existente, transicion_repo, periodo_repo, alerta_repo = _heartbeat_use_case(estado)
        import src.telemetry.application.use_cases.infraestructura.recibir_heartbeat_use_case as modulo
        with _congelar_reloj(modulo, AHORA):
            uc.execute(_heartbeat_dto('L', datos_pendientes_buffer=9999), device_id=99, access_key='k')

        assert estado_existente.estado_actual == 'ACTIVO', (
            "'L' (buffer lleno) no dispara BUFFER_ACTIVO ni ninguna alerta -- se trata exactamente igual "
            "que un buffer inactivo, aunque un buffer lleno con 9999 datos pendientes es, en principio, "
            "una condicion mas urgente que un buffer simplemente activo."
        )
        alerta_repo.guardar.assert_not_called()


class TestGrupoDTransicionControladaPorLaBanderaNoPorElConteo:
    """(d) HALLAZGO: la transicion BUFFER_ACTIVO -> ACTIVO depende solo de que
    estado_local_buffer cambie, no de que datos_pendientes_buffer llegue a 0."""

    def test_datos_pendientes_buffer_en_cero_no_saca_del_buffer_activo_si_la_bandera_sigue_en_A(self):
        estado = _estado('BUFFER_ACTIVO', AHORA - timedelta(minutes=1))
        uc, estado_existente, transicion_repo, periodo_repo, alerta_repo = _heartbeat_use_case(estado)
        import src.telemetry.application.use_cases.infraestructura.recibir_heartbeat_use_case as modulo
        with _congelar_reloj(modulo, AHORA):
            # Buffer ya vacio (0 datos pendientes) pero el dispositivo sigue marcando 'A'.
            uc.execute(_heartbeat_dto('A', datos_pendientes_buffer=0), device_id=99, access_key='k')

        assert estado_existente.estado_actual == 'BUFFER_ACTIVO', (
            "con datos_pendientes_buffer=0 la ficha esperaria la reconexion a ACTIVO 'al vaciarse', pero "
            "el codigo solo mira estado_local_buffer=='A' -- se queda en BUFFER_ACTIVO."
        )

    def test_datos_pendientes_buffer_alto_no_evita_pasar_a_activo_si_la_bandera_cambia(self):
        estado = _estado('BUFFER_ACTIVO', AHORA - timedelta(minutes=1))
        uc, estado_existente, transicion_repo, periodo_repo, alerta_repo = _heartbeat_use_case(estado)
        import src.telemetry.application.use_cases.infraestructura.recibir_heartbeat_use_case as modulo
        with _congelar_reloj(modulo, AHORA):
            # Bandera vuelve a 'I' pero todavia hay 500 datos pendientes de enviar.
            uc.execute(_heartbeat_dto('I', datos_pendientes_buffer=500), device_id=99, access_key='k')

        pytest.fail(
            f"HALLAZGO (d): con estado_local_buffer='I' pero datos_pendientes_buffer=500 (buffer con datos "
            f"aun sin enviar), el dispositivo pasa a {estado_existente.estado_actual!r} igual -- "
            f"'datos_pendientes_buffer' se persiste en el heartbeat pero nunca se consulta en ninguna "
            f"decision de negocio (confirmado por busqueda en recibir_heartbeat_use_case.py y "
            f"estado_dispositivo_iot.py). La condicion real de 'vaciado' que pide la ficha no existe."
        ) if estado_existente.estado_actual == 'ACTIVO' else None

    def test_datos_pendientes_buffer_no_se_lee_en_ninguna_decision_de_negocio(self):
        archivos = [
            REPO_ROOT / 'src/telemetry/application/use_cases/infraestructura/recibir_heartbeat_use_case.py',
            REPO_ROOT / 'src/telemetry/domain/entities/estado_dispositivo_iot.py',
            REPO_ROOT / 'src/telemetry/application/use_cases/infraestructura/evaluar_estado_dispositivos_use_case.py',
        ]
        usos_en_condicion = []
        for archivo in archivos:
            for i, linea in enumerate(archivo.read_text(encoding='utf-8').splitlines(), start=1):
                if 'datos_pendientes_buffer' in linea and re.search(r'(if|elif|while|assert)\b.*datos_pendientes_buffer', linea):
                    usos_en_condicion.append(f'{archivo.name}:{i}')
        assert usos_en_condicion == [], (
            f'se esperaba que datos_pendientes_buffer NUNCA apareciera en una condicion de negocio; '
            f'se encontro en: {usos_en_condicion} (si esto aparece, la ficha podria estar corregida)'
        )
