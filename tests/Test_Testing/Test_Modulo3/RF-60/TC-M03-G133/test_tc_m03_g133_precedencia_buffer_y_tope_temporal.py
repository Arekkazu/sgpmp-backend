"""
TC-M03-G133 (RF-60 PASO 2/CA-2/CA-18/CA-21/E6, CU-04) - "Precedencia del PASO
2 (buffer) sobre el PASO 3 (sin señal)." Consolida CP-EST-03 y CP-EST-09
(misma agrupación que TC-M03-270) -- v1.3: (d) dividido en d1/d2, se añade
(e).

RELACIÓN CON TC-M03-270 (mismo código, mismo CU-04, NO duplicar): (a) CA-21,
(b) CA-18 y (c) BUFFER_PROLONGADO de esta ficha son exactamente lo que
TC-M03-270 ya construyó y ejecutó -- re-confirmado hoy (2026-10-19, ver
`TC-M03-270/test_tc_m03_270_precedencia_buffer_sobre_sin_senal.py`, 3
hallazgos siguen en rojo, 4 comportamientos correctos siguen en verde, sin
cambios en 2 semanas). Este archivo NO repite esas pruebas -- solo cubre lo
que esta ficha v1.3 cambia de verdad:

(d1) [CORREGIDO] "Al recibir heartbeat de reconexión con
datos_pendientes_buffer > 0 el estado es ACTIVO de inmediato (PASO 1:
tiempo_sin_contacto=0) y se registra el inicio de sincronización per E6."
Confirmado PARCIALMENTE con el código completo de
`recibir_heartbeat_use_case.py` (líneas 105-124): CUALQUIER heartbeat
recibido fuerza `tiempo_sin_contacto=0` SIEMPRE (línea 109, comentario
explícito "heartbeat recibido -> tiempo=0 -> ACTIVO") -- y de hecho el
resultado de `evaluar_transicion()` en la línea 108 ni siquiera se usa: las
líneas 121-124 lo SOBREESCRIBEN sin condición con un `if buffer=='A':
BUFFER_ACTIVO else: ACTIVO`. Así que SÍ, cualquier heartbeat de reconexión
(con o sin datos_pendientes_buffer > 0) deja el dispositivo en ACTIVO de
inmediato si buffer != 'A'. **PERO** "se registra el inicio de
sincronización per E6" NO existe en ningún lado: búsqueda exhaustiva de
'sincroniz' en `src/telemetry/` solo encuentra el campo `reloj_sincronizado`
(sincronización de RELOJ del dispositivo, booleano, nada que ver con
sincronizar datos de buffer) -- no hay ningún evento, estado ni registro de
"inicio de sincronización" en todo el módulo.

(d2) [CORREGIDO] "datos_pendientes_buffer decrece hasta 0 sin que el estado
vuelva a cambiar." Mismo hallazgo que TC-M03-270 (d): el campo nunca se lee
en ninguna condición de negocio -- se referencia aquí con un test propio y
puntual (no se repite todo TC-270(d), solo se confirma el ángulo que pide
d2: una SECUENCIA de heartbeats con datos_pendientes_buffer bajando hasta 0,
buffer siempre 'A', nunca cambia el estado por el conteo en sí).

(e) [NUEVO - BLOQUEADO en la ficha] "Nodo con buffer ACTIVO declarado y
silencio total de 8h: el PASO 2 no tiene techo temporal, de modo que nunca
alcanza el PASO 4 y queda enmascarado indefinidamente. Sin criterio en el
RF." **Este escenario NO reproduce -- y el motivo ya lo había encontrado
TC-M03-270 (a), por una razón distinta y más grave a la que la ficha teme.**
La ficha imagina que el PASO 2 (buffer) "gana" indefinidamente y nunca deja
pasar al PASO 4 (inactivo) -- es decir, teme que el dispositivo quede
ATASCADO en BUFFER_ACTIVO para siempre. La realidad es la opuesta: el PASO 2
NO TIENE MEMORIA EN ABSOLUTO fuera de la llegada de heartbeats --
`evaluar_estado_dispositivos_use_case.py` (la tarea periódica que corre
cuando NO llegan heartbeats nuevos, exactamente el escenario de "silencio
total" que describe (e)) SIEMPRE invoca `evaluar_transicion(...,
estado_local_buffer=None)`, sin excepción. Así que un dispositivo con buffer
ACTIVO declarado y silencio total NO queda enmascarado 8 horas: se degrada a
SIN_SEÑAL a los 5 minutos (`UMBRAL_ACTIVO_SEG`, el mismo umbral fijo de
TC-M03-269), muchísimo antes de llegar a las 8h. No hay ninguna zona ciega
que escalar al Comité de Cambios por "falta de techo temporal" -- el techo
temporal SI existe (son los mismos 5 minutos de siempre), lo que no existe
es la MEMORIA del buffer entre heartbeats. (e) se cierra citando el hallazgo
ya confirmado de TC-M03-270 (a), no como un bloqueante nuevo.

Cómo se prueba: igual que TC-M03-270 (pytest a nivel de caso de uso, repos
de prueba, sin golpear TEST/DEV -- el escenario de 8h de silencio tampoco es
practicable contra un backend real).

Como correrlo (Windows necesita el stub de fcntl):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    python -m pytest <ruta>\\test_tc_m03_g133_precedencia_buffer_y_tope_temporal.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M03-G133.html --self-contained-html
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
from src.telemetry.domain.entities.estado_dispositivo_iot import UMBRAL_ACTIVO_SEG, EstadoDispositivoIoT
from src.telemetry.infrastructure.dto.heartbeat_dto import HeartbeatDTO

REPO_ROOT = Path(__file__).resolve().parents[5]
AHORA = datetime(2026, 10, 19, 12, 0, 0, tzinfo=timezone.utc)


def _estado(estado_actual: str, fecha_ultimo_contacto: datetime, id_heartbeat=1) -> EstadoDispositivoIoT:
    return EstadoDispositivoIoT(
        id_estado_dispositivo_iot=1, id_dispositivo_iot=133, estado_actual=estado_actual,
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


class TestSubCasoD1ReconexionInmediataSinRegistroDeSincronizacion:
    """(d1) [CORREGIDO]: heartbeat de reconexion con datos_pendientes_buffer>0
    deja el dispositivo en ACTIVO de inmediato (confirmado) pero no registra
    ningun 'inicio de sincronizacion' E6 (hallazgo: no existe)."""

    def test_heartbeat_de_reconexion_con_datos_pendientes_deja_activo_de_inmediato(self):
        """Confirmado: coincide con la mitad de (d1) que SI pide la ficha."""
        estado = _estado('SIN_SEÑAL', AHORA - timedelta(hours=2))  # llevaba 2h sin contacto
        uc, estado_existente, transicion_repo, periodo_repo, alerta_repo = _heartbeat_use_case(estado)
        import src.telemetry.application.use_cases.infraestructura.recibir_heartbeat_use_case as modulo
        with _congelar_reloj(modulo, AHORA):
            uc.execute(_heartbeat_dto('I', datos_pendientes_buffer=250), device_id=133, access_key='k')

        assert estado_existente.estado_actual == 'ACTIVO', (
            'PASO 1 gana de inmediato en cualquier heartbeat (tiempo_sin_contacto se fuerza a 0), '
            'sin importar cuanto buffer pendiente traiga ni cuanto tiempo llevaba sin contacto -- '
            'coincide con lo que pide (d1).'
        )
        assert estado_existente.tiempo_sin_contacto == 0

    def test_no_existe_ningun_registro_de_inicio_de_sincronizacion_E6(self):
        """HALLAZGO (d1): la ficha pide 'se registra el inicio de sincronizacion per E6'.
        Busqueda inicial (mas amplia) encontro 2 mecanismos reales relacionados con
        'sincronizacion' que investigue antes de concluir nada (leccion de TC-277 - no
        descartar por un grep superficial):
          1. `SincronizarBufferUseCase` (ingerir_telemetria_use_case.py:412,
             POST /iot/telemetria/batch, RF-53 Flujo C) -- SI existe, pero es un
             endpoint de INGESTA EN LOTE de telemetria acumulada, no un evento de
             "inicio". Lei su execute() completo: recorre los registros, los procesa
             uno a uno y devuelve un resumen (aceptados/rechazados/duplicados) al
             terminar -- no escribe ningun registro/alerta/log al EMPEZAR el lote, solo
             al terminar (y eso ya es el resultado final, no un "inicio").
          2. `EstadoAlerta.PENDIENTE_SINCRONIZACION` (alerta.py) -- existe como valor de
             enum con una transicion declarada, pero grep confirma que NINGUN use case
             lo asigna jamas (0 usos fuera de su propia declaracion) -- estado muerto,
             nunca se activa.
        Ninguno de los dos es lo que pide (d1): un evento que se dispare en el momento
        exacto de RECONEXION (heartbeat) marcando 'inicio de sincronizacion'. Ese evento
        no existe -- recibir_heartbeat_use_case.py no llama a SincronizarBufferUseCase
        ni a ningun otro mecanismo al procesar un heartbeat de reconexion."""
        # Archivos ya investigados a fondo arriba (RF-53 Flujo C / alerta.py) -- excluidos por
        # nombre de archivo, no por frase, para no depender de coincidencias de texto/encoding.
        archivos_ya_investigados = {
            'ingerir_telemetria_use_case.py',  # SincronizarBufferUseCase (RF-53 Flujo C)
            'telemetria_router.py',            # su router (POST /iot/telemetria/batch)
            'alerta.py',                       # EstadoAlerta.PENDIENTE_SINCRONIZACION
        }
        archivos = [
            p for p in (REPO_ROOT / 'src' / 'telemetry').rglob('*.py')
            if '__pycache__' not in p.parts and p.name not in archivos_ya_investigados
        ]
        patron = re.compile(r'sincroniz', re.I)
        excluir = ('reloj_sincronizado', 'reloj_desincronizado')
        coincidencias = []
        for archivo in archivos:
            for i, linea in enumerate(archivo.read_text(encoding='utf-8', errors='ignore').splitlines(), start=1):
                if patron.search(linea) and not any(e in linea for e in excluir):
                    coincidencias.append(f'{archivo.relative_to(REPO_ROOT)}:{i}: {linea.strip()}')
        assert coincidencias == [], (
            f'Se esperaba no encontrar NINGUNA otra mencion de sincronizacion ademas de los 2 '
            f'mecanismos ya investigados (SincronizarBufferUseCase, PENDIENTE_SINCRONIZACION); '
            f'se encontraron nuevas: {coincidencias!r} -- revisar si (d1) esta mas implementado '
            f'de lo que este test asume.'
        )

        # Confirma ademas que el heartbeat NO dispara SincronizarBufferUseCase ni nada similar.
        import inspect
        from src.telemetry.application.use_cases.infraestructura import recibir_heartbeat_use_case as modulo_hb
        fuente_heartbeat = inspect.getsource(modulo_hb)
        assert 'Sincronizar' not in fuente_heartbeat, (
            'recibir_heartbeat_use_case.py menciona algo de Sincronizar -- revisar si ya se conecto '
            'con SincronizarBufferUseCase, lo que podria cambiar la conclusion de (d1).'
        )

        pytest.fail(
            "HALLAZGO (d1): no existe ningun evento de 'inicio de sincronizacion' (E6) disparado por "
            "la reconexion (heartbeat). Existe un mecanismo de sincronizacion de datos real "
            "(SincronizarBufferUseCase, RF-53 Flujo C, POST /iot/telemetria/batch) pero es un "
            "endpoint de ingesta en lote INDEPENDIENTE que el cliente debe llamar aparte -- no se "
            "dispara automaticamente al procesar el heartbeat de reconexion, y ni siquiera ese "
            "endpoint deja un registro de 'inicio', solo un resumen al terminar. La reconexion SI "
            "deja el dispositivo en ACTIVO de inmediato (confirmado arriba), pero no 'registra el "
            "inicio de sincronizacion' como pide (d1) -- a lo sumo, el equipo de desarrollo podria "
            "conectar el heartbeat de reconexion con una llamada a SincronizarBufferUseCase para "
            "cumplir esta parte, pero hoy esa conexion no existe."
        )


class TestSubCasoD2ConteoDecrecienteNoCambiaElEstado:
    """(d2) [CORREGIDO]: una secuencia de heartbeats con datos_pendientes_buffer
    bajando hasta 0 (buffer siempre 'A') no debe cambiar el estado por el
    conteo en si -- mismo hallazgo que TC-M03-270(d), confirmado aqui con una
    secuencia completa en vez de un solo heartbeat suelto."""

    def test_secuencia_decreciente_hasta_cero_nunca_cambia_el_estado_por_el_conteo(self):
        estado = _estado('BUFFER_ACTIVO', AHORA - timedelta(minutes=1))
        uc, estado_existente, transicion_repo, periodo_repo, alerta_repo = _heartbeat_use_case(estado)
        import src.telemetry.application.use_cases.infraestructura.recibir_heartbeat_use_case as modulo

        for i, pendientes in enumerate([500, 300, 100, 10, 0]):
            ahora_ciclo = AHORA + timedelta(minutes=i)
            with _congelar_reloj(modulo, ahora_ciclo):
                uc.execute(_heartbeat_dto('A', datos_pendientes_buffer=pendientes), device_id=133, access_key='k')

        assert estado_existente.estado_actual == 'BUFFER_ACTIVO', (
            'HALLAZGO (d2) confirmado: con datos_pendientes_buffer llegando exactamente a 0 pero '
            "estado_local_buffer siguiendo en 'A', el dispositivo nunca sale de BUFFER_ACTIVO -- "
            'ninguna transicion ocurrio por el conteo decreciente en si, solo la bandera importa.'
        )
        # Ninguna transicion de estado se registro en ningun ciclo (siempre fue BUFFER_ACTIVO->BUFFER_ACTIVO).
        transicion_repo.registrar.assert_not_called()


class TestSubCasoENoHayEnmascaramientoIndefinido:
    """(e) [NUEVO - BLOQUEADO en la ficha]: la ficha teme que el PASO 2 enmascare
    el dispositivo en BUFFER_ACTIVO indefinidamente tras 8h de silencio total.
    No reproduce -- el motivo real (sin memoria de buffer entre heartbeats) ya
    esta confirmado en TC-M03-270(a); aqui se repite el escenario puntual a
    8h, el que pide esta ficha, para que quede su propia evidencia."""

    def test_8_horas_de_silencio_con_buffer_activo_declarado_no_enmascara_se_degrada_normal(self):
        import src.telemetry.application.use_cases.infraestructura.evaluar_estado_dispositivos_use_case as modulo

        estado = _estado('BUFFER_ACTIVO', AHORA - timedelta(hours=8))  # ultimo heartbeat: buffer ACTIVO, hace 8h
        estado_repo = MagicMock()
        estado_repo.listar_activos.return_value = [estado]
        transicion_repo = MagicMock()
        periodo_repo = MagicMock()
        periodo_repo.obtener_abierto_por_dispositivo.return_value = None
        alerta_repo = MagicMock()
        alerta_repo.guardar.return_value = MagicMock(id_alerta=950)
        historico_alerta_repo = MagicMock()
        uc = EvaluarEstadoDispositivosUseCase(
            db=MagicMock(), estado_repo=estado_repo, transicion_repo=transicion_repo,
            periodo_repo=periodo_repo, alerta_repo=alerta_repo, historico_alerta_repo=historico_alerta_repo,
        )

        with _congelar_reloj(modulo, AHORA):
            uc.execute()

        assert estado.estado_actual != 'BUFFER_ACTIVO', (
            'Si esto fallara (el dispositivo SIGUIERA en BUFFER_ACTIVO a las 8h), (e) SI seria un '
            'hallazgo real de enmascaramiento indefinido -- pero el codigo actual no tiene memoria '
            'de buffer entre heartbeats, asi que esto no deberia pasar nunca.'
        )
        assert estado.estado_actual == 'SIN_SEÑAL', (
            f'(e) no reproduce como "enmascarado indefinidamente": a las 8h de silencio, el '
            f'dispositivo paso a {estado.estado_actual!r}, degradado por el mismo mecanismo ya '
            f'confirmado en TC-M03-270(a) -- la tarea periodica siempre evalua con '
            f'estado_local_buffer=None (pierde la memoria del ultimo buffer reportado) y el umbral '
            f'fijo de {UMBRAL_ACTIVO_SEG}s (5 min) ya paso hace rato. No hay ninguna "falta de techo '
            f'temporal" que escalar al Comite de Cambios -- el problema real (ya reportado por '
            f'TC-M03-270) es el opuesto: el buffer se pierde demasiado rapido, no que persista '
            f'demasiado tiempo.'
        )
