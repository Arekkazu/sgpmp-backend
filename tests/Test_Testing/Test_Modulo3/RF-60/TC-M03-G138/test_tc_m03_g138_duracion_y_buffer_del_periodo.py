"""
TC-M03-G138 (RF-60 CA-10/Restricción 3/Postcondición 8/Fase 8, CU-14) -
"Trazabilidad hacia el historial de lecturas." Consolida CP-INT-02/03, misma
agrupación que TC-M03-275 (ya ejecutado: confirmó que NO existe ningún
endpoint de lectura de periodos de inactividad -- invalida (a) tal como lo
plantea la ficha, más una discrepancia de nombres de campo:
`duracion_min`/`buffer_activo_durante` reales vs `duracion_minutos`/
`buffer_activo_durante_periodo` de la ficha).

RELACIÓN CON TC-M03-275 (NO duplicar): (a) y la discrepancia de nombres ya
están confirmadas ahí. Este archivo cubre SOLO (a2) [NUEVO]: "validar que
duracion_minutos = timestamp_fin - timestamp_inicio, y que
buffer_activo_durante_periodo sea false en un ciclo sin buffer y true si
hubo buffer en algún momento del periodo." Como no hay endpoint para leer
esto por API (TC-275), se prueba a nivel de entidad/caso de uso -- es lo
único que SE PUEDE probar sin ese endpoint.

(a2), parte 1 (cálculo de duración) -- CONFIRMADO correcto:
`PeriodoInactividad.cerrar()` (`periodo_inactividad.py`) calcula
`duracion_min = int((fecha_fin - fecha_inicio).total_seconds() / 60)` --
aritmética correcta, confirmada aquí con varios casos incluyendo redondeo
hacia abajo (trunca, no redondea).

(a2), parte 2 (buffer_activo_durante) -- HALLAZGO NUEVO: el campo NUNCA se
pone en `True` en ningún punto del código. `evaluar_estado_dispositivos_use_case.py`
crea todo periodo nuevo con `buffer_activo_durante=False` HARDCODEADO (línea
confirmada en la lectura completa del archivo para TC-M03-G132/133), y
además solo abre periodos para `nuevo_estado in ('SIN_SEÑAL', 'INACTIVO')`
-- `BUFFER_ACTIVO` ni siquiera entra en esa condición, así que un periodo
nunca se abre estando en buffer. `recibir_heartbeat_use_case.py` solo
CIERRA periodos (nunca los abre). Conclusión: `buffer_activo_durante` es un
campo que la entidad declara pero que todo el código deja permanentemente
en `False` -- "true si hubo buffer en algún momento del periodo" (lo que
pide (a2)) no tiene ninguna ruta de código que lo haga realidad.

(b) no se prueba aquí (requiere un dataset de telemetría congelado + hashing
antes/después de un ciclo real de fallo/recuperación, infraestructura de
datos que esta sesión no tiene) -- pero se confirma estructuralmente, igual
que TC-M03-G134(a), que RF-60 nunca toca el repositorio de telemetría de
RF-53 (mismo hallazgo, ángulo complementario: allá se confirmó que RF-53 no
lee RF-60; aquí se confirma que RF-60 no escribe RF-53).

Como correrlo (Windows necesita el stub de fcntl):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    python -m pytest <ruta>\\test_tc_m03_g138_duracion_y_buffer_del_periodo.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M03-G138.html --self-contained-html
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.telemetry.application.use_cases.infraestructura.evaluar_estado_dispositivos_use_case import (
    EvaluarEstadoDispositivosUseCase,
)
from src.telemetry.domain.entities.estado_dispositivo_iot import EstadoDispositivoIoT
from src.telemetry.domain.entities.periodo_inactividad import PeriodoInactividad

REPO_ROOT = Path(__file__).resolve().parents[5]
AHORA = datetime(2026, 10, 19, 12, 0, 0, tzinfo=timezone.utc)


class TestSubCasoA2DuracionCalculadaCorrectamente:
    """(a2) parte 1: duracion_min = (fecha_fin - fecha_inicio) en minutos -- confirmado correcto."""

    @pytest.mark.parametrize('minutos, segundos_extra, esperado', [
        (1, 0, 1), (40, 0, 40), (480, 0, 480),  # 8h
        (5, 59, 5),   # 5:59 -> trunca a 5, no redondea a 6
        (5, 1, 5),    # 5:01 -> trunca a 5
    ])
    def test_duracion_min_se_calcula_correctamente_al_cerrar(self, minutos, segundos_extra, esperado):
        inicio = AHORA
        fin = inicio + timedelta(minutes=minutos, seconds=segundos_extra)
        periodo = PeriodoInactividad(
            id_periodo_inactividad=1, id_dispositivo_iot=138, sensores_afectados=[],
            fecha_inicio=inicio, fecha_fin=None, duracion_min=None,
            estado_durante_periodo='SIN_SEÑAL', causa_primaria='FALLO_CONECTIVIDAD',
            caso_diagnosticado={}, buffer_activo_durante=False, id_alerta=None,
        )
        periodo.cerrar(fin)
        assert periodo.duracion_min == esperado
        assert periodo.fecha_fin == fin


class TestSubCasoA2BufferActivoDuranteNuncaSePoneEnTrue:
    """(a2) parte 2 [HALLAZGO NUEVO]: buffer_activo_durante siempre queda False,
    sin importar si el dispositivo paso por BUFFER_ACTIVO durante el periodo."""

    def test_periodo_abierto_por_el_job_periodico_siempre_tiene_buffer_false(self):
        estado = EstadoDispositivoIoT(
            id_estado_dispositivo_iot=1, id_dispositivo_iot=138, estado_actual='ACTIVO',
            fecha_ultimo_contacto=AHORA - timedelta(minutes=10), id_ultimo_heartbeat=1,
            tiempo_sin_contacto=0, causa_primaria=None, causas_secundarias=None,
            fecha_ultima_actualizacion=AHORA, id_usuario=None,
        )
        estado_repo = MagicMock()
        estado_repo.listar_activos.return_value = [estado]
        transicion_repo = MagicMock()
        periodo_repo = MagicMock()
        periodo_repo.obtener_abierto_por_dispositivo.return_value = None
        alerta_repo = MagicMock()
        alerta_repo.guardar.return_value = MagicMock(id_alerta=1)
        historico_alerta_repo = MagicMock()
        uc = EvaluarEstadoDispositivosUseCase(
            db=MagicMock(), estado_repo=estado_repo, transicion_repo=transicion_repo,
            periodo_repo=periodo_repo, alerta_repo=alerta_repo, historico_alerta_repo=historico_alerta_repo,
        )
        import unittest.mock as mock
        import src.telemetry.application.use_cases.infraestructura.evaluar_estado_dispositivos_use_case as modulo

        class _DatetimeFijo(datetime):
            @classmethod
            def now(cls, tz=None):
                return AHORA

        with mock.patch.object(modulo, 'datetime', _DatetimeFijo):
            uc.execute()

        periodo_abierto = periodo_repo.abrir.call_args.args[0]
        assert periodo_abierto.buffer_activo_durante is False, (
            'HALLAZGO (a2): buffer_activo_durante quedo False incluso siendo el unico camino que '
            'abre periodos -- coincide con lo que se esperaba (nunca se pone en True).'
        )
        pytest.fail(
            "HALLAZGO (a2): buffer_activo_durante esta hardcodeado a False en "
            "evaluar_estado_dispositivos_use_case.py (el unico lugar que abre periodos), y "
            "BUFFER_ACTIVO ni siquiera esta en la lista de estados que abren periodo "
            "('SIN_SEÑAL', 'INACTIVO'). No existe ninguna ruta de codigo que ponga este campo en "
            "True -- 'true si hubo buffer en algun momento del periodo', que pide (a2), es "
            "irrealizable con el codigo actual."
        )


class TestSubCasoBRf60NuncaEscribeEnRf53:
    """(b) complementario a TC-M03-G134(a): confirma que ningun caso de uso de
    RF-60 (infraestructura/) importa o escribe en el repositorio de
    telemetria de RF-53 -- RF-60 nunca inserta/modifica/elimina lecturas."""

    def test_ningun_use_case_de_rf60_toca_el_repositorio_de_telemetria(self):
        carpeta = REPO_ROOT / 'src' / 'telemetry' / 'application' / 'use_cases' / 'infraestructura'
        archivos_sospechosos = []
        for archivo in carpeta.glob('*.py'):
            texto = archivo.read_text(encoding='utf-8')
            if 'TelemetriaRepository' in texto or 'telemetria_repo' in texto:
                archivos_sospechosos.append(archivo.name)
        assert archivos_sospechosos == [], (
            f'Se esperaba que ningun caso de uso de RF-60 (infraestructura/) tocara el repositorio '
            f'de telemetria de RF-53; se encontraron referencias en: {archivos_sospechosos!r} -- '
            f'revisar si RF-60 ahora modifica telemetria (cambiaria la conclusion de (b)).'
        )
