"""
TC-M03-269 (RF-60 Restricción 12, CA-1/CA-6/CA-20, CU-02) - Algoritmo único de
evaluación del estado de un dispositivo IoT: recorrido PASOS 1->4 y sus
fronteras.

Código bajo prueba:
    src/telemetry/domain/entities/estado_dispositivo_iot.py
        EstadoDispositivoIoT.evaluar_transicion() -- el algoritmo de 4 pasos.
    src/telemetry/application/use_cases/infraestructura/evaluar_estado_dispositivos_use_case.py
        EvaluarEstadoDispositivosUseCase -- tarea periódica (60 s) que lo invoca
        sobre todos los dispositivos y genera la alerta técnica + periodo de
        inactividad la PRIMERA vez que un dispositivo entra en SIN_SEÑAL/INACTIVO.

HALLAZGO PRINCIPAL (invalida literalmente los sub-casos (a), (b) y (c) de la
ficha, y desplaza (e) en ~18 horas): la ficha asume umbrales CONFIGURABLES por
dispositivo a partir de HB/FM/margen (umbral_activo=10 min, umbral_sin_señal=15
min, umbral_inactivo=6h15 para HB=5/FM=10/margen=5). Ese mecanismo NO EXISTE en
el código. `evaluar_transicion()` solo acepta umbrales fijos y ningún llamador
(ni el job periódico, ni `recibir_heartbeat_use_case.py`) los sobreescribe --
se usan siempre las constantes del módulo:

    UMBRAL_ACTIVO_SEG     = 300    (5 min)
    UMBRAL_SIN_SENAL_SEG  = 1800   (30 min) -- solo importa si estado_local_buffer == 'A'
    UMBRAL_INACTIVO_SEG   = 86400  (24 h)

Con buffer inactivo (el caso de esta ficha: "buffer INACTIVO"), el algoritmo
tiene en la práctica SOLO DOS fronteras observables, no tres:
    - ACTIVO -> SIN_SEÑAL en el segundo 300 (5 min).
    - SIN_SEÑAL -> INACTIVO en el segundo 86400 (24 h) -- el umbral de 30 min
      no produce ningún cambio visible cuando no hay buffer: tanto el tramo
      [5 min, 30 min) como el tramo [30 min, 24 h) devuelven 'SIN_SEÑAL' (ver
      líneas 45 y 52 del archivo: el `elif < umbral_sin_senal` y el `else`
      final caen en el mismo estado). El umbral de 30 min solo decide si, al
      llegar ahí, se permite la rama BUFFER_ACTIVO -- es un umbral de
      ARBITRAJE, no de estado para un dispositivo sin buffer.

Por eso, para HB=5/FM=10/margen=5 (sin que el código sepa nada de esos
valores):
    (a) t=8 min  (480 s, >= 300)      -> SIN_SEÑAL, no ACTIVO como pide la ficha.
    (b) 9:59/10:00/10:01               -> los tres SIN_SEÑAL (ya pasaron el
                                           umbral real de 5 min); no hay
                                           frontera en el minuto 10.
    (c) 14:59/15:00/15:01              -> los tres SIN_SEÑAL igual; no hay
                                           frontera en el minuto 15.
    (e) t=6h16 (22560 s, < 86400)      -> SIGUE SIN_SEÑAL, no INACTIVO. La
                                           frontera real a INACTIVO está a
                                           las 24 h, no a las 6h15.

(d) CA-20 SÍ se confirma como la ficha espera, porque t=18 min cae dentro del
tramo [5 min, 24 h) sin importar qué umbral intermedio se asuma.

HALLAZGO SECUNDARIO (CA-6, usando la frontera REAL de 24 h, no las 6h15 de la
ficha): al escalar de SIN_SEÑAL a INACTIVO el job periódico NO genera ninguna
alerta nueva. `evaluar_estado_dispositivos_use_case.py` (líneas 76-94) solo
genera la alerta si `periodo_repo.obtener_abierto_por_dispositivo(...) is
None` -- pero el periodo de inactividad ya quedó abierto cuando el dispositivo
entró en SIN_SEÑAL (5 min) y nunca se cierra hasta que vuelve a tener
contacto. Para cuando el mismo dispositivo llega a INACTIVO (24 h después),
ese `None` ya es `False` y el bloque de alerta se salta por completo. Además,
incluso si esa guarda no existiera, el mapeo de severidad de esa misma función
(línea 100: `'MODERADO' if nuevo_estado == 'INACTIVO' else 'LEVE'`) nunca
produce `'CRITICO'` para esta vía -- el enum real `SeveridadAlerta` sí tiene
`CRITICO` (SLA 5 min, ver `alerta.py`), pero esta función nunca lo usa. La
ficha pide "alerta CRITICO" al pasar a INACTIVO: con el código actual eso
nunca ocurre (ni como alerta nueva, ni con esa severidad).

HALLAZGO MENOR: el endpoint Swagger de la ficha (`GET /api/v1/devices/{device_id}/status`)
no existe. La ruta real es `GET /iot/dispositivos/{id_dispositivo_iot}/estado`
(`infraestructura_iot_router.py`, RBAC recurso 35 acción 2).

Cómo se prueba (Backend / pytest parametrizado + reloj simulado, tal como pide
la ficha): el "reloj simulado" es literal -- se pasa `tiempo_sin_contacto_seg`
directamente a `evaluar_transicion()` (nivel entidad, Grupo 1 y 2) y se
controla `fecha_ultimo_contacto` vs un `ahora` inyectado (nivel caso de uso,
Grupo 3 y 4, con repos de prueba). No se golpea el backend real: el recorrido
completo incluye un salto de 24 h que no es practicable contra TEST/DEV, y la
ficha pide expresamente esta herramienta.

Como correrlo (desde la raíz del repo; en Windows hace falta el stub de fcntl,
ver memoria del proyecto -- el buffer de auditoría RF-52 de M02 importa fcntl
sin guardia de plataforma y `tests/conftest.py` lo arrastra a toda la suite):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    python -m pytest <ruta>\\test_tc_m03_269_algoritmo_evaluacion_estado.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M03-269.html --self-contained-html
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
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

AHORA = datetime(2026, 9, 26, 12, 0, 0, tzinfo=timezone.utc)


def _estado(estado_actual: str = 'ACTIVO', fecha_ultimo_contacto: datetime = AHORA) -> EstadoDispositivoIoT:
    return EstadoDispositivoIoT(
        id_estado_dispositivo_iot=1,
        id_dispositivo_iot=99,
        estado_actual=estado_actual,
        fecha_ultimo_contacto=fecha_ultimo_contacto,
        id_ultimo_heartbeat=None,
        tiempo_sin_contacto=0,
        causa_primaria=None,
        causas_secundarias=None,
        fecha_ultima_actualizacion=fecha_ultimo_contacto,
        id_usuario=None,
    )


class TestGrupo1ValoresLiteralesDeLaFicha:
    """Corre los valores EXACTOS que pide la ficha (asumiendo HB=5/FM=10/margen=5
    -> umbral_activo=10 min, umbral_sin_señal=15 min) contra el algoritmo real,
    que no sabe nada de esos umbrales. Documenta, caso por caso, si el
    resultado coincide con lo que la ficha espera."""

    @pytest.mark.parametrize('minutos, segundos, esperado_ficha, motivo', [
        (8, 480, 'ACTIVO', '(a) t=8 min -> la ficha espera ACTIVO sin alerta'),
        (9 + 59 / 60, 599, 'ACTIVO', '(b) 9:59 -> la ficha espera ACTIVO (dentro del umbral activo asumido)'),
        (10, 600, 'ACTIVO', '(b) 10:00 -> la ficha espera ACTIVO (umbral activo asumido inclusive)'),
        (10 + 1 / 60, 601, 'SIN_SEÑAL', '(b) 10:01 -> la ficha espera la primera transición a SIN_SEÑAL'),
        (14 + 59 / 60, 899, 'SIN_SEÑAL', '(c) 14:59 -> la ficha espera SIN_SEÑAL, sin alerta todavía'),
        (15, 900, 'SIN_SEÑAL', '(c) 15:00 -> la ficha espera SIN_SEÑAL, frontera del umbral sin señal'),
        (15 + 1 / 60, 901, 'SIN_SEÑAL', '(c) 15:01 -> la ficha espera SIN_SEÑAL (ya pasado ese umbral)'),
    ], ids=['a_8min', 'b_9m59s', 'b_10m00s', 'b_10m01s', 'c_14m59s', 'c_15m00s', 'c_15m01s'])
    def test_valor_literal_de_la_ficha_vs_algoritmo_real(self, minutos, segundos, esperado_ficha, motivo):
        estado = _estado('ACTIVO')
        real = estado.evaluar_transicion(tiempo_sin_contacto_seg=segundos, estado_local_buffer=None) or 'ACTIVO'

        if real != esperado_ficha:
            pytest.fail(
                f'{motivo}. Con el algoritmo real (umbral_activo={UMBRAL_ACTIVO_SEG}s, fijo, no '
                f'configurable por HB/FM/margen) el resultado a los {segundos}s es {real!r}, no '
                f'{esperado_ficha!r}. Esto confirma que el modelo de umbrales configurables que asume '
                f'la ficha (HB=5, FM=10, margen=5 -> umbral_activo=10 min) no existe en el backend: '
                f'el umbral activo real son 5 min (300s) fijos para todo dispositivo.'
            )


class TestGrupo2FronterasRealesDelAlgoritmo:
    """Mismo algoritmo, pero en SUS propios umbrales (5 min y 24 h, buffer
    inactivo) -- confirma que el algoritmo en si funciona correctamente en sus
    propias fronteras; el Grupo 1 solo prueba que esas fronteras no son las que
    la ficha asumio."""

    @pytest.mark.parametrize('segundos, esperado', [
        (UMBRAL_ACTIVO_SEG - 1, 'ACTIVO'),      # 4:59
        (UMBRAL_ACTIVO_SEG, 'SIN_SEÑAL'),       # 5:00 (el <, no <=, hace que el umbral mismo ya transicione)
        (UMBRAL_ACTIVO_SEG + 1, 'SIN_SEÑAL'),   # 5:01
        (UMBRAL_SIN_SENAL_SEG - 1, 'SIN_SEÑAL'),   # 29:59 -- sin efecto observable sin buffer
        (UMBRAL_SIN_SENAL_SEG, 'SIN_SEÑAL'),       # 30:00
        (UMBRAL_SIN_SENAL_SEG + 1, 'SIN_SEÑAL'),   # 30:01
        (UMBRAL_INACTIVO_SEG - 1, 'SIN_SEÑAL'),  # 23:59:59
        (UMBRAL_INACTIVO_SEG, 'INACTIVO'),       # 24:00:00
        (UMBRAL_INACTIVO_SEG + 1, 'INACTIVO'),   # 24:00:01
    ], ids=['activo-1', 'activo', 'activo+1', 'sinsenal-1', 'sinsenal', 'sinsenal+1', 'inactivo-1', 'inactivo', 'inactivo+1'])
    def test_fronteras_reales_sin_buffer(self, segundos, esperado):
        estado = _estado('ACTIVO')
        real = estado.evaluar_transicion(tiempo_sin_contacto_seg=segundos, estado_local_buffer=None) or 'ACTIVO'
        assert real == esperado, (
            f'a los {segundos}s se esperaba {esperado!r} (fronteras reales del algoritmo: '
            f'{UMBRAL_ACTIVO_SEG}s / {UMBRAL_SIN_SENAL_SEG}s / {UMBRAL_INACTIVO_SEG}s), se obtuvo {real!r}'
        )

    def test_umbral_sin_senal_no_tiene_efecto_observable_sin_buffer(self):
        """Evidencia directa de que el umbral de 30 min no distingue ningun estado por si
        mismo cuando el dispositivo no reporta buffer activo: antes y despues de el, SIN_SEÑAL."""
        estado = _estado('ACTIVO')
        antes = estado.evaluar_transicion(tiempo_sin_contacto_seg=UMBRAL_SIN_SENAL_SEG - 1, estado_local_buffer=None)
        despues = estado.evaluar_transicion(tiempo_sin_contacto_seg=UMBRAL_SIN_SENAL_SEG + 1, estado_local_buffer=None)
        assert antes == despues == 'SIN_SEÑAL'


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


class TestGrupo3CA20SinSenalConAlerta:
    """(d) CA-20: t=18 min sin buffer -> SIN_SEÑAL + alerta con causa_primaria=FALLO_CONECTIVIDAD.
    Esta parte de la ficha SI se confirma con el algoritmo real, porque 18 min cae dentro del
    tramo [5 min, 24 h) sin importar el umbral intermedio asumido."""

    def test_18_min_sin_contacto_genera_sin_senal_y_alerta_fallo_conectividad(self):
        uc, estado_repo, periodo_repo, alerta_repo, historico_alerta_repo = _use_case_con_dobles()
        fecha_ultimo_contacto = AHORA - timedelta(minutes=18)
        estado = _estado('ACTIVO', fecha_ultimo_contacto)
        estado_repo.listar_activos.return_value = [estado]
        periodo_repo.obtener_abierto_por_dispositivo.return_value = None
        alerta_guardada = MagicMock(id_alerta=501)
        alerta_repo.guardar.return_value = alerta_guardada

        with _congelar_reloj(AHORA):
            transiciones = uc.execute()

        assert transiciones == 1
        assert estado.estado_actual == 'SIN_SEÑAL'
        assert estado.causa_primaria == 'FALLO_CONECTIVIDAD'

        periodo_abierto = periodo_repo.abrir.call_args.args[0]
        assert periodo_abierto.causa_primaria == 'FALLO_CONECTIVIDAD'
        assert periodo_abierto.estado_durante_periodo == 'SIN_SEÑAL'

        alerta_creada = alerta_repo.guardar.call_args.args[0]
        assert alerta_creada.tipo_variable == 'FALLO_CONECTIVIDAD', (
            'la ficha llama a esto "alerta DISPOSITIVO_SIN_SEÑAL" -- ese nombre literal no existe en '
            'el backend; el campo real que identifica la causa es tipo_variable=FALLO_CONECTIVIDAD, '
            'que si coincide con lo que pide la ficha para causa_primaria.'
        )
        assert alerta_creada.severidad == 'LEVE'
        historico_alerta_repo.registrar.assert_called_once()


def _congelar_reloj(ahora: datetime):
    """Parchea datetime.now() dentro del módulo bajo prueba para que 'ahora' sea fijo."""
    import unittest.mock as mock
    import src.telemetry.application.use_cases.infraestructura.evaluar_estado_dispositivos_use_case as modulo

    class _DatetimeFijo(datetime):
        @classmethod
        def now(cls, tz=None):
            return ahora

    return mock.patch.object(modulo, 'datetime', _DatetimeFijo)


class TestGrupo4CA6EscaladaAInactivoSinSegundaAlerta:
    """(e) CA-6, en la frontera REAL (24 h, no las 6h15 de la ficha): el dispositivo ya
    estaba SIN_SEÑAL (con un periodo de inactividad abierto desde la corrida anterior) y
    ahora supera el umbral de 24 h -> debe escalar a INACTIVO. La ficha espera una 'alerta
    CRITICO sin duplicar la anterior'. HALLAZGO: el codigo actual no genera NINGUNA alerta
    nueva en esta escalada (la guarda `periodo_existente is None` ya es False), y aunque la
    generara, esta via nunca asigna severidad CRITICO."""

    def test_de_sin_senal_a_inactivo_no_genera_ninguna_alerta_nueva(self):
        uc, estado_repo, periodo_repo, alerta_repo, historico_alerta_repo = _use_case_con_dobles()
        fecha_ultimo_contacto = AHORA - timedelta(seconds=UMBRAL_INACTIVO_SEG + 60)
        estado = _estado('SIN_SEÑAL', fecha_ultimo_contacto)  # ya estaba SIN_SEÑAL de una corrida anterior
        estado_repo.listar_activos.return_value = [estado]
        # El periodo de inactividad quedo abierto cuando entro en SIN_SEÑAL -- no es None.
        periodo_repo.obtener_abierto_por_dispositivo.return_value = MagicMock(id_periodo_inactividad=77)

        with _congelar_reloj(AHORA):
            transiciones = uc.execute()

        assert transiciones == 1
        assert estado.estado_actual == 'INACTIVO', 'la transicion de estado en si SI ocurre correctamente'

        alerta_repo.guardar.assert_not_called()
        historico_alerta_repo.registrar.assert_not_called()
        pytest.fail(
            'HALLAZGO CA-6: al escalar de SIN_SEÑAL a INACTIVO (24h) no se genero ninguna alerta '
            'nueva -- la guarda `periodo_existente is None` en evaluar_estado_dispositivos_use_case.py '
            '(linea ~81) ya es False porque el periodo se abrio al entrar en SIN_SEÑAL y nunca se '
            'cerro. La ficha pide una alerta CRITICO en este punto (CA-6); hoy no se genera ninguna.'
        )

    def test_la_severidad_moderado_es_el_techo_para_inactivo_nunca_critico(self):
        """Aunque se corrigiera la guarda anterior, esta prueba documenta el segundo defecto:
        el mapeo de severidad de este caso de uso jamas produce 'CRITICO'."""
        uc, estado_repo, periodo_repo, alerta_repo, historico_alerta_repo = _use_case_con_dobles()
        fecha_ultimo_contacto = AHORA - timedelta(seconds=UMBRAL_INACTIVO_SEG + 60)
        estado = _estado('SIN_SEÑAL', fecha_ultimo_contacto)
        estado_repo.listar_activos.return_value = [estado]
        periodo_repo.obtener_abierto_por_dispositivo.return_value = None  # forzar que SI se genere la alerta
        alerta_repo.guardar.return_value = MagicMock(id_alerta=502)

        with _congelar_reloj(AHORA):
            uc.execute()

        alerta_creada = alerta_repo.guardar.call_args.args[0]
        assert alerta_creada.severidad == 'MODERADO', (
            f'se obtuvo severidad={alerta_creada.severidad!r}; el codigo mapea INACTIVO a MODERADO como '
            f'techo (ver evaluar_estado_dispositivos_use_case.py linea ~100), nunca a CRITICO, aunque el '
            f'enum SeveridadAlerta real si tiene CRITICO (SLA 5 min) disponible.'
        )
        pytest.fail(
            "HALLAZGO CA-6 (severidad): incluso forzando a que se genere una alerta nueva en la "
            "escalada a INACTIVO, la severidad asignada es 'MODERADO' (SLA 30 min), nunca "
            "'CRITICO' (SLA 5 min) como pide la ficha -- el mapeo de severidad de esta función no "
            "distingue ninguna causa como critica."
        )
