"""
TC-M03-G132 (RF-60 Restricción 12/Fase 8, CA-1/CA-6/CA-20, CU-02) - "Algoritmo
único de evaluación (Restricción 12): recorrido completo de los PASOS 1->4 y
sus fronteras." Consolida CP-EST-01, 02, 04, 05, 06 (misma agrupación que
TC-M03-269) -- v1.3: corrige (c) y (e), añade (f).

RELACIÓN CON TC-M03-269 (mismo código, mismos CP-EST, NO duplicar): (a), (b),
(d) y (e) de esta ficha son exactamente CP-EST-01/02/05/06, que TC-M03-269 ya
construyó y ejecutó contra el mismo código
(`estado_dispositivo_iot.py::evaluar_transicion()` +
`evaluar_estado_dispositivos_use_case.py`), con el mismo hallazgo principal:
los umbrales NO son configurables por HB/FM/margen -- son constantes fijas
(`UMBRAL_ACTIVO_SEG=300s` 5min, `UMBRAL_SIN_SENAL_SEG=1800s` 30min,
`UMBRAL_INACTIVO_SEG=86400s` 24h), confirmado de nuevo hoy (2026-10-19): ningún
llamador de `evaluar_transicion()` sobreescribe esos valores. Ver
`TC-M03-269/test_tc_m03_269_algoritmo_evaluacion_estado.py` para la evidencia
completa de (a)/(b)/(d) y la primera mitad de (e) (el gap de alerta en CA-6).
Este archivo NO repite esas pruebas -- solo cubre lo que esta ficha v1.3
cambia de verdad frente a TC-M03-269:

(c) [CORREGIDO - BLOQUEADO en la ficha] -- la ficha afirma que la zona
"10 min < t <= 15 min sin buffer" queda SIN RESOLVER por ningún PASO del
algoritmo ("PASO 1 exige t<=10, PASO 2 exige buffer activo, PASO 3 exige
t>15"), y la marca bloqueante pendiente de escalar al Comité de Cambios.
**Esto no reproduce con el código actual, con ningún juego de umbrales:**
`evaluar_transicion()` es un if/elif/else puro y exhaustivo -- todo valor de
t cae en ACTIVO, SIN_SEÑAL, BUFFER_ACTIVO o INACTIVO, nunca en `None`/sin
resolver. La descripción de "PASO 2 exige buffer activo" no coincide con el
código real: el verdadero PASO 2 es `elif t < umbral_sin_señal: SIN_SEÑAL`
(sin exigir buffer); el chequeo de buffer es un PASO intermedio posterior
(solo relevante una vez *superado* umbral_sin_señal). No hay ninguna zona sin
resolver que escalar -- (c) se cierra por reencuadre, no por fix de código.

(f) [NUEVO] -- "Al pasar SIN_SEÑAL -> INACTIVO se mantiene UN solo periodo de
inactividad abierto (Fase 8); solo cambia estado_durante_periodo, no se abre
un segundo registro." Genuinamente nuevo, TC-M03-269 no lo probó de forma
explícita (solo infería lo mismo indirectamente via `alerta_repo.guardar.
assert_not_called()`). Confirmado aquí con assert directo sobre
`periodo_repo.abrir`:
  - "no se abre un segundo registro": CORRECTO, confirmado -- el guard
    `periodo_existente is None` evita un segundo `abrir()`.
  - "solo cambia estado_durante_periodo": INCORRECTO, nuevo hallazgo --
    `evaluar_estado_dispositivos_use_case.py` (rama `periodo_existente is not
    None`) no hace NADA con el periodo existente: no llama a
    `periodo_repo.actualizar(...)`, y `PeriodoInactividad`
    (`periodo_inactividad.py`) ni siquiera tiene un método para cambiar
    `estado_durante_periodo` (solo `cerrar()`). El campo queda congelado en
    'SIN_SEÑAL' para siempre, aunque el dispositivo ya esté INACTIVO.

CAVEAT heredado de TC-M03-278 (hallazgo arquitectónico 2026-10-04, sigue
aplicando igual aquí): este archivo prueba el algoritmo Python en
aislamiento (repos `MagicMock`). RF-60 tiene una SEGUNDA máquina de estados
independiente en triggers de Postgres
(`alembic/baseline/esquema_baseline.sql`, `trg_rf60_02_log_transicion_estado`)
que también abre una fila en `periodos_inactividad` ante CUALQUIER cambio de
`estado_actual` -- incluyendo, muy probablemente, la transición SIN_SEÑAL->
INACTIVO que aquí se prueba a nivel Python. Si el job periódico Python
también llama a `estado_repo.actualizar()` (lo hace, confirmado en el código)
y ESO dispara el trigger, la fila de `periodos_inactividad` del trigger
quedaría duplicada frente a la que Python decidió no abrir -- el mismo patrón
de doble registro ya confirmado para `historico_transiciones_dispositivos`
en TC-M03-278. **No verificado en vivo (requeriría acceso a BD real); se dejó
como advertencia explícita, no como hallazgo confirmado, para no repetir el
error de TC-277 (conclusión basada solo en grep de `src/`, corregida después
al encontrar los triggers).**

Cómo correrlo (mismo criterio que TC-M03-269; Windows necesita el stub de
fcntl):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    python -m pytest <ruta>\\test_tc_m03_g132_algoritmo_unico_y_periodo_unico.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M03-G132.html --self-contained-html
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from itertools import product
from unittest.mock import MagicMock

import pytest

from src.telemetry.application.use_cases.infraestructura.evaluar_estado_dispositivos_use_case import (
    EvaluarEstadoDispositivosUseCase,
)
from src.telemetry.domain.entities.estado_dispositivo_iot import (
    UMBRAL_ACTIVO_SEG,
    UMBRAL_INACTIVO_SEG,
    UMBRAL_SIN_SENAL_SEG,
    EstadoDispositivoIoT,
)

AHORA = datetime(2026, 10, 19, 12, 0, 0, tzinfo=timezone.utc)
_ESTADOS_VALIDOS = ('ACTIVO', 'SIN_SEÑAL', 'BUFFER_ACTIVO', 'INACTIVO')


def _estado(estado_actual: str = 'ACTIVO', fecha_ultimo_contacto: datetime = AHORA) -> EstadoDispositivoIoT:
    return EstadoDispositivoIoT(
        id_estado_dispositivo_iot=1,
        id_dispositivo_iot=132,
        estado_actual=estado_actual,
        fecha_ultimo_contacto=fecha_ultimo_contacto,
        id_ultimo_heartbeat=None,
        tiempo_sin_contacto=0,
        causa_primaria=None,
        causas_secundarias=None,
        fecha_ultima_actualizacion=fecha_ultimo_contacto,
        id_usuario=None,
    )


def _congelar_reloj(ahora: datetime):
    import unittest.mock as mock
    import src.telemetry.application.use_cases.infraestructura.evaluar_estado_dispositivos_use_case as modulo

    class _DatetimeFijo(datetime):
        @classmethod
        def now(cls, tz=None):
            return ahora

    return mock.patch.object(modulo, 'datetime', _DatetimeFijo)


def _use_case_con_dobles():
    estado_repo = MagicMock()
    transicion_repo = MagicMock()
    periodo_repo = MagicMock()
    alerta_repo = MagicMock()
    historico_alerta_repo = MagicMock()
    db = MagicMock()
    uc = EvaluarEstadoDispositivosUseCase(
        db=db, estado_repo=estado_repo, transicion_repo=transicion_repo,
        periodo_repo=periodo_repo, alerta_repo=alerta_repo,
        historico_alerta_repo=historico_alerta_repo,
    )
    return uc, estado_repo, periodo_repo, alerta_repo, historico_alerta_repo


class TestSubCasoCZonaSupuestamenteSinResolver:
    """(c) [CORREGIDO - BLOQUEADO en la ficha]: la ficha dice que la zona entre
    umbral_activo y umbral_sin_señal (sin buffer) no la resuelve ningún PASO.
    Confirma que el algoritmo real es exhaustivo (siempre resuelve a un
    estado valido) para CUALQUIER t, sin importar el modelo de umbrales --
    cierra (c) por reencuadre, no hay nada que escalar al Comité de Cambios."""

    @pytest.mark.parametrize('segundos', [
        0, 1,
        UMBRAL_ACTIVO_SEG - 1, UMBRAL_ACTIVO_SEG, UMBRAL_ACTIVO_SEG + 1,
        (UMBRAL_ACTIVO_SEG + UMBRAL_SIN_SENAL_SEG) // 2,  # a mitad de camino en la supuesta "zona sin resolver"
        UMBRAL_SIN_SENAL_SEG - 1, UMBRAL_SIN_SENAL_SEG, UMBRAL_SIN_SENAL_SEG + 1,
        UMBRAL_INACTIVO_SEG - 1, UMBRAL_INACTIVO_SEG, UMBRAL_INACTIVO_SEG + 1,
        UMBRAL_INACTIVO_SEG * 10,  # muy por encima de todo umbral
    ])
    @pytest.mark.parametrize('buffer', [None, 'I', 'A', 'L'])
    def test_el_algoritmo_siempre_resuelve_a_un_estado_valido(self, segundos, buffer):
        estado = _estado('ACTIVO')
        resultado = estado.evaluar_transicion(tiempo_sin_contacto_seg=segundos, estado_local_buffer=buffer)
        # None es "no hay transicion" (el estado ya era ese) -- lo normalizamos igual que el use case.
        resultado = resultado or estado.estado_actual
        assert resultado in _ESTADOS_VALIDOS, (
            f'a los {segundos}s con buffer={buffer!r} el algoritmo devolvio {resultado!r}, fuera de '
            f'{_ESTADOS_VALIDOS} -- si esto fallara, SI habria una zona sin resolver que reportar.'
        )

    def test_zona_10_a_15_min_asumida_por_la_ficha_resuelve_a_sin_senal_sin_excepcion(self):
        """Prueba puntual de la zona exacta que la ficha marca bloqueada (usando sus
        propios minutos 10-15, no los umbrales reales) -- demuestra que el PASO 2 real
        (`elif t < umbral_sin_señal`) la resuelve sin necesitar buffer activo."""
        for minuto in range(10, 16):
            estado = _estado('ACTIVO')
            resultado = estado.evaluar_transicion(
                tiempo_sin_contacto_seg=minuto * 60, estado_local_buffer=None,
            )
            assert resultado == 'SIN_SEÑAL', (
                f'minuto {minuto} (zona que la ficha marca "BLOQUEADO, ningun PASO resuelve"): '
                f'el algoritmo real SI resuelve, a {resultado!r}. (c) no tiene nada que escalar.'
            )


class TestSubCasoFUnSoloPeriodoDeInactividad:
    """(f) [NUEVO]: al pasar SIN_SEÑAL -> INACTIVO se espera UN solo periodo de
    inactividad abierto, con estado_durante_periodo actualizado."""

    def _dispositivo_ya_en_sin_senal_con_periodo_abierto(self):
        uc, estado_repo, periodo_repo, alerta_repo, historico_alerta_repo = _use_case_con_dobles()
        fecha_ultimo_contacto = AHORA - timedelta(seconds=UMBRAL_INACTIVO_SEG + 60)
        estado = _estado('SIN_SEÑAL', fecha_ultimo_contacto)  # ya SIN_SEÑAL de una corrida anterior
        estado_repo.listar_activos.return_value = [estado]
        periodo_abierto_previo = MagicMock(id_periodo_inactividad=321, estado_durante_periodo='SIN_SEÑAL')
        periodo_repo.obtener_abierto_por_dispositivo.return_value = periodo_abierto_previo
        return uc, estado, periodo_repo, periodo_abierto_previo

    def test_no_se_abre_un_segundo_periodo_al_escalar_a_inactivo(self):
        """Confirmado: coincide con lo que pide la ficha."""
        uc, estado, periodo_repo, _periodo_previo = self._dispositivo_ya_en_sin_senal_con_periodo_abierto()

        with _congelar_reloj(AHORA):
            uc.execute()

        assert estado.estado_actual == 'INACTIVO'
        periodo_repo.abrir.assert_not_called()

    def test_estado_durante_periodo_NO_se_actualiza_a_inactivo_hallazgo_nuevo(self):
        """HALLAZGO (f): la ficha asume que, si no se abre un segundo periodo, al menos
        se actualiza estado_durante_periodo del periodo existente. El codigo actual no
        hace ninguna de las dos cosas para el periodo ya abierto: no llama a
        periodo_repo.actualizar(...), y PeriodoInactividad ni siquiera expone un metodo
        para cambiar ese campo (solo cerrar())."""
        uc, estado, periodo_repo, periodo_previo = self._dispositivo_ya_en_sin_senal_con_periodo_abierto()

        with _congelar_reloj(AHORA):
            uc.execute()

        assert estado.estado_actual == 'INACTIVO', 'la transicion de ESTADO si ocurre correctamente'
        periodo_repo.actualizar.assert_not_called()
        assert periodo_previo.estado_durante_periodo == 'SIN_SEÑAL', (
            'HALLAZGO (f): estado_durante_periodo del periodo de inactividad abierto sigue en '
            "'SIN_SEÑAL' despues de escalar el dispositivo a INACTIVO -- la ficha pide que 'solo "
            "cambie estado_durante_periodo'; en el codigo actual NO cambia nada, ni el campo ni se "
            'persiste ninguna actualizacion del periodo (PeriodoInactividad.cerrar() es el unico '
            'metodo de mutacion disponible en la entidad, y no se invoca aqui).'
        )

    def test_el_periodo_SI_se_cierra_correctamente_al_volver_a_activo(self):
        """Control: confirma que el ciclo de vida del periodo si funciona correctamente
        en el otro extremo (ACTIVO), para que el hallazgo de arriba no se confunda con
        un periodo roto en general -- es especifico de la transicion SIN_SEÑAL->INACTIVO."""
        uc, estado_repo, periodo_repo, alerta_repo, historico_alerta_repo = _use_case_con_dobles()
        estado = _estado('SIN_SEÑAL', AHORA)  # heartbeat recien llegado -> tiempo_sin_contacto=0 en la proxima corrida
        estado.fecha_ultimo_contacto = AHORA  # 0s sin contacto -> ACTIVO
        estado_repo.listar_activos.return_value = [estado]
        periodo_abierto = MagicMock(id_periodo_inactividad=321)
        periodo_repo.obtener_abierto_por_dispositivo.return_value = periodo_abierto

        with _congelar_reloj(AHORA):
            uc.execute()

        assert estado.estado_actual == 'ACTIVO'
        periodo_repo.cerrar.assert_called_once_with(periodo_abierto)
