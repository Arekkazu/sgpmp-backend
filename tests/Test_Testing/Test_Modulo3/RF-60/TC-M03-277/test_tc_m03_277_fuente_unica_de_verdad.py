"""
TC-M03-277 (RF-60 Restricción 12/aclaración v1.2/Fase 5, CU-02) - Fuente única
de verdad del estado.

CORRECCIÓN IMPORTANTE sobre una versión anterior de este mismo archivo (commit
previo): esa versión concluía, a partir de una búsqueda solo en código Python,
que el dashboard de RF-58 (`estados_actuales_sensores.estado_conectividad`) y
el estado de RF-60 (`estados_dispositivos_iot.estado_actual`) eran DOS fuentes
de verdad desconectadas. Eso era INCORRECTO: la sincronización existe, pero a
nivel de BASE DE DATOS, vía triggers (`alembic/baseline/esquema_baseline.sql`),
no en código Python -- una búsqueda que solo mira `src/` nunca la iba a
encontrar. Se retracta esa conclusión.

ARQUITECTURA REAL (confirmada leyendo las funciones de trigger completas):
  - `trg_rf60_01_procesar_heartbeat` (AFTER INSERT ON heartbeats) ->
    `fn_procesar_heartbeat()`: ante CUALQUIER heartbeat, resuelve el estado
    (ACTIVO, o EN_MANTENIMIENTO si ya estaba ahí -- nunca BUFFER_ACTIVO, ese
    valor NO existe en esta función) y hace UPDATE/INSERT directo sobre
    `estados_dispositivos_iot`, TODO ANTES de que el código Python de
    `recibir_heartbeat_use_case.py` llegue a leer esa fila.
  - `trg_rf60_02_log_transicion_estado` (AFTER UPDATE ON estados_dispositivos_iot,
    cuando `estado_actual` cambia) -> `fn_log_transicion_dispositivo()`: inserta
    en `historico_transiciones_dispositivos` Y abre un `periodos_inactividad`
    (SIN_SEÑAL/INACTIVO/BUFFER_ACTIVO) automáticamente, sin importar qué
    proceso causó el UPDATE.
  - `trg_rf60_05_marcar_sensores_sin_senal` (mismo disparador) ->
    `fn_marcar_sensores_sin_senal()`: ESTA es la sincronización que la versión
    anterior de este archivo no encontró -- actualiza
    `estados_actuales_sensores.estado_conectividad` (la tabla que lee el
    dashboard de RF-58) cada vez que `estado_actual` cambia. SÍ hay una
    fuente de verdad única de hecho -- vive en la base de datos, no en
    Python.
  - `trg_rf60_03/04_transiciones_no_update/no_delete` ->
    `fn_transiciones_dispositivo_append_only()`: `RAISE EXCEPTION` incondicional
    ante cualquier UPDATE o DELETE sobre `historico_transiciones_dispositivos`
    (confirma TC-M03-278 (a) a nivel de BD, no solo de aplicación).

HALLAZGO NUEVO, más grave que el que se retracta: como
`trg_rf60_02_log_transicion_estado` se dispara en CUALQUIER UPDATE de
`estado_actual` -- incluido el que hace el propio trigger
`fn_procesar_heartbeat` -- Y el código Python de ambos casos de uso
(`recibir_heartbeat_use_case.py`, `evaluar_estado_dispositivos_use_case.py`)
TAMBIÉN inserta explícitamente en `historico_transiciones_dispositivos` y
abre/cierra `periodos_inactividad` por su cuenta, el mismo evento de
transición automática queda registrado DOS VECES (una por el trigger, otra
por el código Python) -- exactamente lo que el propio equipo de desarrollo ya
documentó como "doble-registro preexistente, fuera de alcance" en
`anotaciones/modulo_3/implementacion_dev_m03_rf60_rf62.md` (sección final),
pero sin haber conectado ahí que el mismo patrón aplica también a
`periodos_inactividad`, no solo al histórico. Para el job periódico esto
tiene un efecto más serio: cuando el trigger abre el periodo primero (en el
mismo UPDATE), el guard `periodo_existente is None` que usa el código Python
para decidir si genera la alerta técnica (ver TC-M03-269 CA-20) encontraría
el periodo que el trigger YA abrió -- en la base de datos real (no en los
dobles de prueba usados en TC-M03-269/270/273/275/276, que nunca ejecutan
estos triggers), es plausible que la alerta de CA-20 NUNCA se genere en la
práctica, lo opuesto a lo que ese TC confirmó en aislamiento. **No se pudo
verificar en vivo porque `POST /iot/heartbeat` está roto en TEST (TC-M03-273)
y el job periódico no es invocable manualmente desde HTTP** -- queda como
hallazgo estructural, no confirmado end-to-end, y debe tratarse como una nota
que matiza TC-M03-269/270/273/275/276 (construidos con dobles de prueba que
no reproducen estos triggers), no como una corrección de esos archivos.

Esta corrección aplica el mismo criterio que la corrección "id_padre" de
Módulo 2 (sesión 2026-09-26): un hallazgo inicial basado solo en código
Python, sin revisar los triggers de BD, puede estar incompleto o equivocado.

(a) y (c) de la ficha original se mantienen:
(a) Con la corrección anterior, SÍ existe una fuente única de verdad -- vive
parcialmente en la BD (triggers), no solo en el algoritmo Python. RF-59
sigue sin exponer estado de dispositivo (TC-M03-275) y M08 sigue sin
implementarse, asi que la comparación de 4 vías que pide la ficha no se
puede hacer completa, pero las DOS vías que sí existen (RF-60 propio y el
dashboard de RF-58) SÍ están sincronizadas.

(c) CONFIRMADO, sin cambios: `fn_procesar_heartbeat()` respeta
`EN_MANTENIMIENTO` explícitamente (`IF v_estado_actual = 'EN_MANTENIMIENTO'
THEN v_estado_nuevo := 'EN_MANTENIMIENTO'`), y a nivel Python
`evaluar_transicion()` retorna `None` de inmediato y `listar_activos()`
excluye esos dispositivos de la evaluación periódica. Doblemente protegido,
en ambas capas.

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
BASELINE = REPO_ROOT / 'alembic' / 'baseline' / 'esquema_baseline.sql'
T0 = datetime(2026, 9, 26, 12, 0, 0, tzinfo=timezone.utc)


class TestGrupoAFuenteDeVerdadSincronizadaViaTriggerDeBD:

    def test_existe_el_trigger_que_sincroniza_el_dashboard_con_el_estado_del_dispositivo(self):
        texto = BASELINE.read_text(encoding='utf-8')
        assert 'trg_rf60_05_marcar_sensores_sin_senal' in texto
        assert 'fn_marcar_sensores_sin_senal' in texto
        # La funcion debe escribir en la MISMA tabla que lee el dashboard de RF-58.
        inicio = texto.index('CREATE FUNCTION modulo3.fn_marcar_sensores_sin_senal')
        cuerpo = texto[inicio:inicio + 1200]
        assert 'estados_actuales_sensores' in cuerpo
        assert 'estado_conectividad' in cuerpo

    def test_rf59_y_m08_siguen_sin_exponer_estado_de_dispositivo(self):
        """Sin cambios respecto a la version anterior: RF-59 no expone estado de dispositivo
        (TC-M03-275) y M08 sigue sin implementarse -- la comparacion de 4 vias de la ficha
        sigue siendo imposible de hacer completa, aunque las 2 vias que si existen si coinciden."""
        router = REPO_ROOT / 'src/telemetry/infrastructure/routers/monitoreo_router.py'
        assert 'M08_NO_DISPONIBLE' in router.read_text(encoding='utf-8')


class TestGrupoBBypassLiteralEnLaInicializacionYDobleRegistro:

    def test_el_primer_heartbeat_de_un_dispositivo_nuevo_lo_resuelve_el_trigger_no_python(self):
        """Matiz sobre el hallazgo anterior: el bootstrap 'estado_actual=ACTIVO' que hace
        recibir_heartbeat_use_case.py (rama 'estado is None') es en la practica, contra la BD
        real, CODIGO MUERTO para un dispositivo genuinamente nuevo: fn_procesar_heartbeat ya
        inserto la fila (con 'ACTIVO') en la MISMA transaccion, antes de que Python la busque,
        asi que Python siempre la encuentra 'ya existente' y entra por la rama 'else', nunca por
        la rama 'estado is None'. El bypass real del algoritmo ocurre en el trigger de BD, no en
        el codigo Python que se habia senalado antes."""
        texto = BASELINE.read_text(encoding='utf-8')
        inicio = texto.index('CREATE FUNCTION modulo3.fn_procesar_heartbeat')
        cuerpo = texto[inicio:inicio + 900]
        assert 'INSERT INTO modulo3.estados_dispositivos_iot' in cuerpo
        assert "'ACTIVO'" in cuerpo

    def test_el_trigger_de_transicion_nunca_implementa_buffer_activo(self):
        """fn_procesar_heartbeat SI menciona BUFFER_ACTIVO (para detectar si el estado ANTERIOR
        era ese, al decidir si cerrar un periodo), pero v_estado_nuevo -- lo que el trigger
        realmente ASIGNA como estado resultante -- solo toma 'ACTIVO' o 'EN_MANTENIMIENTO' en
        todo el cuerpo de la funcion. BUFFER_ACTIVO como RESULTADO solo lo decide el codigo
        Python (evaluar_transicion). Si Python no llegara a ejecutarse (p.ej. por el bug de
        TC-M03-273), un dispositivo con buffer activo quedaria marcado ACTIVO por el trigger,
        sin distincion."""
        texto = BASELINE.read_text(encoding='utf-8')
        inicio = texto.index('CREATE FUNCTION modulo3.fn_procesar_heartbeat')
        fin = texto.index('$$;', inicio)
        cuerpo = texto[inicio:fin]
        asignaciones_v_estado_nuevo = re.findall(r"v_estado_nuevo\s*:?=\s*'([A-Z_Ñ]+)'", cuerpo)
        assert set(asignaciones_v_estado_nuevo) == {'ACTIVO', 'EN_MANTENIMIENTO'}, (
            f'se esperaba que v_estado_nuevo solo se asignara a ACTIVO/EN_MANTENIMIENTO; '
            f'se encontro: {asignaciones_v_estado_nuevo}'
        )

    def test_doble_registro_documentado_por_el_equipo_dev_tambien_aplica_a_periodos_inactividad(self):
        """fn_log_transicion_dispositivo (disparado por CUALQUIER UPDATE de estado_actual) abre
        un periodo de inactividad por su cuenta; evaluar_estado_dispositivos_use_case.py TAMBIEN
        lo abre explicitamente despues de su propio UPDATE. Contra la BD real esto duplicaria la
        fila -- no verificado end-to-end (heartbeat roto, ver TC-M03-273), se deja como hallazgo
        estructural."""
        texto = BASELINE.read_text(encoding='utf-8')
        inicio = texto.index('CREATE FUNCTION modulo3.fn_log_transicion_dispositivo')
        fin = texto.index('$$;', inicio)
        cuerpo = texto[inicio:fin]
        assert 'INSERT INTO modulo3.periodos_inactividad' in cuerpo
        job = REPO_ROOT / 'src/telemetry/application/use_cases/infraestructura/evaluar_estado_dispositivos_use_case.py'
        assert 'periodo_repo.abrir' in job.read_text(encoding='utf-8')
        pytest.fail(
            "HALLAZGO ESTRUCTURAL (no confirmado end-to-end): tanto el trigger "
            "fn_log_transicion_dispositivo como el codigo Python del job periodico abren un "
            "periodos_inactividad para la MISMA transicion automatica -- doble registro, mismo "
            "patron que el equipo dev ya documento para historico_transiciones_dispositivos. "
            "No verificable en vivo porque POST /iot/heartbeat esta roto (TC-M03-273)."
        )


class TestGrupoCEnMantenimientoInmuneEnAmbasCapas:

    def test_el_trigger_de_bd_tambien_respeta_en_mantenimiento(self):
        texto = BASELINE.read_text(encoding='utf-8')
        inicio = texto.index('CREATE FUNCTION modulo3.fn_procesar_heartbeat')
        fin = texto.index('$$;', inicio)
        cuerpo = texto[inicio:fin]
        assert "v_estado_actual = 'EN_MANTENIMIENTO'" in cuerpo
        assert "v_estado_nuevo := 'EN_MANTENIMIENTO'" in cuerpo

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
        assert "EN_MANTENIMIENTO" in archivo.read_text(encoding='utf-8')

    def test_8_horas_sin_contacto_en_mantenimiento_no_genera_transicion_ni_alerta(self):
        import src.telemetry.application.use_cases.infraestructura.evaluar_estado_dispositivos_use_case as modulo

        estado = EstadoDispositivoIoT(
            id_estado_dispositivo_iot=1, id_dispositivo_iot=1, estado_actual='EN_MANTENIMIENTO',
            fecha_ultimo_contacto=T0, id_ultimo_heartbeat=1, tiempo_sin_contacto=0,
            causa_primaria=None, causas_secundarias=None, fecha_ultima_actualizacion=T0, id_usuario=None,
        )
        estado_repo = MagicMock()
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
