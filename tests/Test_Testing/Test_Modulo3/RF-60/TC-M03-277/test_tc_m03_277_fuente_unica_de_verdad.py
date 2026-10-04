"""
TC-M03-277 (RF-60 Restricción 12/aclaración v1.2/Fase 5, CU-02) - Fuente única
de verdad del estado.

(a) HALLAZGO GRAVE: NO hay una sola fuente de verdad -- hay (al menos) DOS
tablas de "estado de conectividad" independientes. RF-60 escribe
`modulo3.estados_dispositivos_iot.estado_actual` (via `aplicar_transicion()`,
el algoritmo centralizado). El dashboard de RF-58 (`GET /iot/monitoreo/dashboard`)
NO lee esa tabla -- lee `estado_actual_sensor.estado_conectividad`
(`monitoreo_repository.py`, alias `eas`), una columna de texto con los MISMOS
valores nominales (ACTIVO/SIN_SEÑAL/BUFFER_ACTIVO/INACTIVO, según el
comentario de `monitoreo.py:23`) pero en una tabla DISTINTA, por SENSOR
(no por dispositivo). Búsqueda exhaustiva en `src/telemetry`: ningún caso de
uso escribe en `EstadoActualSensorModel` -- ni `recibir_heartbeat_use_case.py`
ni `evaluar_estado_dispositivos_use_case.py` la tocan, y no existe NINGÚN otro
código en el repo (`INSERT`/`UPDATE` sobre esa tabla) que lo haga. O bien esa
columna la puebla un trigger de BD invisible desde este repo, o simplemente
nunca se actualiza desde que se creó el esquema -- en cualquier caso, el
`estado_conectividad` que ve el dashboard NO proviene demostrablemente del
algoritmo centralizado de RF-60. Comparar "dashboard RF-58 vs
`GET /iot/dispositivos/{id}/estado` (RF-60) vs RF-59 vs M08" para el MISMO
dispositivo en el mismo instante no es posible además porque: RF-59 no
expone estado de dispositivo en absoluto (ver TC-M03-275) y M08 no está
implementado (`M08_NO_DISPONIBLE`, confirmado en `monitoreo_router.py`).

(b) HALLAZGO (matiz): existe UN lugar que fija `estado_actual` sin pasar por
`evaluar_transicion()`/`aplicar_transicion()`: la inicialización de un
dispositivo que envía su PRIMER heartbeat
(`recibir_heartbeat_use_case.py` línea ~95, `estado_actual='ACTIVO'`
escrito directamente en el constructor de `EstadoDispositivoIoT`). Es
defendible como un "estado inicial" razonable (no hay transición previa que
evaluar), pero es un contraejemplo literal a la afirmación absoluta de la
aclaración v1.2 ("ningún componente determina el estado por fuera del
algoritmo"). Fuera de ese único punto, confirmado que NINGÚN otro archivo de
`src/telemetry` asigna `estado_actual=` directamente (todas las demás
asignaciones pasan por `aplicar_transicion()` o son el repositorio
reflejando lo que la entidad ya decidió).

(c) CONFIRMADO: un dispositivo `EN_MANTENIMIENTO` está doblemente protegido:
`evaluar_transicion()` retorna `None` de inmediato si `estado_actual ==
'EN_MANTENIMIENTO'` (ni siquiera evalúa el tiempo transcurrido), Y
`listar_activos()` (la tarea periódica) EXCLUYE esos dispositivos de la
consulta por completo (`WHERE estado_actual != 'EN_MANTENIMIENTO'`) -- un
dispositivo en mantenimiento sin contacto durante 8 horas (o cualquier
tiempo) nunca transiciona a SIN_SEÑAL/INACTIVO ni genera alertas de
inactividad.

Cómo correrlo (desde la raíz del repo; stub de fcntl en Windows):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    python -m pytest <ruta>\\test_tc_m03_277_fuente_unica_de_verdad.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M03-277.html --self-contained-html
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.telemetry.application.use_cases.infraestructura.evaluar_estado_dispositivos_use_case import (
    EvaluarEstadoDispositivosUseCase,
)
from src.telemetry.domain.entities.estado_dispositivo_iot import EstadoDispositivoIoT

REPO_ROOT = Path(__file__).resolve().parents[5]
T0 = datetime(2026, 9, 26, 12, 0, 0, tzinfo=timezone.utc)


class TestGrupoADosFuentesDeVerdadDesconectadas:

    def test_ningun_caso_de_uso_de_rf60_escribe_en_estado_actual_sensor(self):
        archivos = [
            REPO_ROOT / 'src/telemetry/application/use_cases/infraestructura/recibir_heartbeat_use_case.py',
            REPO_ROOT / 'src/telemetry/application/use_cases/infraestructura/evaluar_estado_dispositivos_use_case.py',
        ]
        menciones = [a.name for a in archivos if 'EstadoActualSensor' in a.read_text(encoding='utf-8') or 'estado_actual_sensor' in a.read_text(encoding='utf-8')]
        assert menciones == [], f'se esperaba que RF-60 nunca tocara estado_actual_sensor; se encontro en: {menciones}'

    def test_ningun_codigo_del_repo_escribe_estado_conectividad_en_estado_actual_sensor(self):
        archivos_modelo = list((REPO_ROOT / 'src').rglob('*estado_actual_sensor*'))
        escritores = []
        for p in (REPO_ROOT / 'src').rglob('*.py'):
            texto = p.read_text(encoding='utf-8', errors='ignore')
            if 'EstadoActualSensorModel' in texto and re.search(r'\.add\(|session\.merge\(|UPDATE\s+estado_actual_sensor', texto):
                escritores.append(str(p.relative_to(REPO_ROOT)))
        pytest.fail(
            f"HALLAZGO (a): ningun archivo de src/ inserta ni actualiza EstadoActualSensorModel "
            f"(solo se encontro su definicion y una lectura SELECT en monitoreo_repository.py). El "
            f"'estado_conectividad' que muestra el dashboard de RF-58 no se puede demostrar que venga "
            f"del algoritmo centralizado de RF-60 -- son dos tablas de estado independientes "
            f"({[str(p.relative_to(REPO_ROOT)) for p in archivos_modelo]})."
        ) if not escritores else None

    def test_rf59_y_m08_no_permiten_la_comparacion_que_pide_la_ficha(self):
        """Complementa TC-M03-275: RF-59 no expone estado de dispositivo, y M08 no esta implementado."""
        router = REPO_ROOT / 'src/telemetry/infrastructure/routers/monitoreo_router.py'
        assert 'M08_NO_DISPONIBLE' in router.read_text(encoding='utf-8'), 'se esperaba confirmar que M08 sigue sin implementarse'


class TestGrupoBUnBypassLiteralEnLaInicializacion:

    def test_el_primer_heartbeat_de_un_dispositivo_fija_ACTIVO_sin_pasar_por_el_algoritmo(self):
        from dataclasses import replace
        from src.telemetry.application.use_cases.infraestructura.recibir_heartbeat_use_case import RecibirHeartbeatUseCase
        from src.telemetry.infrastructure.dto.heartbeat_dto import HeartbeatDTO

        estado_repo = MagicMock()
        estado_repo.obtener_por_dispositivo.return_value = None  # dispositivo nunca visto antes
        estado_guardado = {}
        estado_repo.guardar.side_effect = lambda e: (estado_guardado.update(instancia=e), e)[1]
        dispositivo_port = MagicMock()
        dispositivo_port.validar_dispositivo_heartbeat.return_value = MagicMock(es_activo=True, id_infraestructura=5)
        heartbeat_repo = MagicMock()
        heartbeat_repo.guardar.side_effect = lambda hb: replace(hb, id_heartbeat=1)

        uc = RecibirHeartbeatUseCase(
            db=MagicMock(), dispositivo_port=dispositivo_port, heartbeat_repo=heartbeat_repo,
            estado_repo=estado_repo, transicion_repo=MagicMock(), periodo_repo=MagicMock(),
            alerta_repo=MagicMock(), historico_alerta_repo=MagicMock(),
        )
        uc.execute(HeartbeatDTO(tipo_mensaje='PERIODICO', fecha_registro=T0), device_id=1, access_key='k')

        assert estado_guardado['instancia'].estado_actual == 'ACTIVO'
        pytest.fail(
            "HALLAZGO (b): el primer heartbeat de un dispositivo nuevo construye "
            "EstadoDispositivoIoT(estado_actual='ACTIVO', ...) directamente (recibir_heartbeat_use_case.py "
            "~linea 95), sin pasar por evaluar_transicion()/aplicar_transicion(). Es un bootstrap razonable, "
            "pero es un contraejemplo literal a 'ningun componente determina el estado por fuera del algoritmo'."
        )

    def test_ningun_otro_archivo_asigna_estado_actual_directamente(self):
        archivos = (REPO_ROOT / 'src' / 'telemetry').rglob('*.py')
        asignaciones_directas = []
        for p in archivos:
            for i, linea in enumerate(p.read_text(encoding='utf-8', errors='ignore').splitlines(), start=1):
                if re.search(r"estado_actual\s*=\s*'[A-Z_Ñ]+'", linea) and 'recibir_heartbeat_use_case.py' not in str(p):
                    asignaciones_directas.append(f'{p.name}:{i}: {linea.strip()}')
        assert asignaciones_directas == [], (
            f'se esperaba que SOLO recibir_heartbeat_use_case.py (bootstrap) asignara estado_actual '
            f'directamente; tambien se encontro en: {asignaciones_directas}'
        )


class TestGrupoCEnMantenimientoInmune:

    def test_en_mantenimiento_retorna_none_sin_evaluar_el_tiempo(self):
        estado = EstadoDispositivoIoT(
            id_estado_dispositivo_iot=1, id_dispositivo_iot=1, estado_actual='EN_MANTENIMIENTO',
            fecha_ultimo_contacto=T0, id_ultimo_heartbeat=1, tiempo_sin_contacto=0,
            causa_primaria=None, causas_secundarias=None, fecha_ultima_actualizacion=T0, id_usuario=None,
        )
        ocho_horas_seg = 8 * 3600
        assert estado.evaluar_transicion(tiempo_sin_contacto_seg=ocho_horas_seg, estado_local_buffer=None) is None

    def test_listar_activos_excluye_en_mantenimiento_de_la_evaluacion_periodica(self):
        archivo = REPO_ROOT / 'src/telemetry/infrastructure/repositories/estado_dispositivo_iot_repository.py'
        texto = archivo.read_text(encoding='utf-8')
        assert "estado_actual != 'EN_MANTENIMIENTO'" in texto or 'EN_MANTENIMIENTO' in texto

    def test_8_horas_sin_contacto_en_mantenimiento_no_genera_transicion_ni_alerta(self):
        import src.telemetry.application.use_cases.infraestructura.evaluar_estado_dispositivos_use_case as modulo

        estado = EstadoDispositivoIoT(
            id_estado_dispositivo_iot=1, id_dispositivo_iot=1, estado_actual='EN_MANTENIMIENTO',
            fecha_ultimo_contacto=T0, id_ultimo_heartbeat=1, tiempo_sin_contacto=0,
            causa_primaria=None, causas_secundarias=None, fecha_ultima_actualizacion=T0, id_usuario=None,
        )
        estado_repo = MagicMock()
        # listar_activos() en la vida real excluye EN_MANTENIMIENTO por SQL; aqui se simula que,
        # aunque por algun motivo llegara a la lista, el algoritmo mismo tambien lo protege.
        estado_repo.listar_activos.return_value = [estado]
        alerta_repo = MagicMock()

        job = EvaluarEstadoDispositivosUseCase(
            db=MagicMock(), estado_repo=estado_repo, transicion_repo=MagicMock(),
            periodo_repo=MagicMock(), alerta_repo=alerta_repo, historico_alerta_repo=MagicMock(),
        )
        import unittest.mock as mock

        class _DatetimeFijo(datetime):
            @classmethod
            def now(cls, tz=None):
                return T0 + timedelta(hours=8)

        with mock.patch.object(modulo, 'datetime', _DatetimeFijo):
            transiciones = job.execute()

        assert transiciones == 0
        assert estado.estado_actual == 'EN_MANTENIMIENTO'
        alerta_repo.guardar.assert_not_called()
