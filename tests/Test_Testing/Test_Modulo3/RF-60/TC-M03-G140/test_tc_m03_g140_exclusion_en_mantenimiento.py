"""
TC-M03-G140 (RF-60 Restricción 12 y aclaración v1.2/Fase 4/Fase 5, CU-02) -
"Fuente única de verdad del estado." Consolida CP-EST-13/14, misma
agrupación que TC-M03-277 (ya ejecutado, con autocorrección importante:
la sincronización dashboard RF-58 <-> estado RF-60 SÍ existe, pero a nivel
de triggers de Postgres, no de código Python).

RELACIÓN CON TC-M03-277 (NO duplicar): (a) y (b) ya están confirmados ahí
(incluyendo el descubrimiento de la arquitectura de triggers). Este archivo
cubre SOLO (c) [BLOQUEADO en la ficha]: dispositivo EN_MANTENIMIENTO sin
contacto 8h no debe transicionar ni generar alertas -- la ficha advierte que
"la Fase 4 excluye EN_MANTENIMIENTO del barrido, pero el algoritmo de la
Restricción 12, declarado única fuente de verdad, NO menciona esa
exclusión. Implementado al pie de la letra, el nodo pasaría a SIN_SEÑAL."

HALLAZGO (matiz importante, ni "bug" limpio ni "correcto" limpio): el
RESULTADO funciona -- un dispositivo EN_MANTENIMIENTO con 8h de silencio NO
transiciona ni genera alertas, confirmado con prueba directa abajo. Pero la
ficha tiene razón en el punto estructural que le preocupa: la exclusión
vive en DOS lugares distintos, no en uno solo dentro "del algoritmo":

  1. `EstadoDispositivoIoTRepository.listar_activos()`
     (`estado_dispositivo_iot_repository.py`): el propio SQL de la consulta
     excluye `WHERE estado_actual != 'EN_MANTENIMIENTO'` -- esta es la "Fase
     4" que la ficha menciona. Los dispositivos EN_MANTENIMIENTO ni siquiera
     LLEGAN al job periódico.
  2. `EstadoDispositivoIoT.evaluar_transicion()` (el algoritmo de la
     Restricción 12 en sí) TAMBIÉN tiene su propia guardia:
     `if self.estado_actual == 'EN_MANTENIMIENTO': return None`, como
     primera línea del método.

La guardia #2 es, en la práctica, código MUERTO para el camino del job
periódico (porque la consulta #1 ya filtró esos dispositivos antes de que
el job llame a `evaluar_transicion()`) -- pero SÍ es la única protección
real en el camino de heartbeat (`recibir_heartbeat_use_case.py` NO filtra
por estado al leer el dispositivo). Es decir: hay redundancia en un camino
y dependencia exclusiva de la guardia #2 en el otro. Esto confirma
literalmente lo que la ficha teme ("ningún componente determina el estado
por fuera del algoritmo centralizado" NO se cumple del todo: la consulta
SQL de `listar_activos()` SÍ determina, por fuera del algoritmo, qué
dispositivos ni siquiera se evalúan).

HALLAZGO SECUNDARIO (nuevo, relevante para G144 CA-7/CA-8): la guardia #2
protege `evaluar_transicion()`, pero el código que la LLAMA en
`recibir_heartbeat_use_case.py` IGNORA su resultado para el camino de buffer
-- las líneas 121-124 (`if dto.estado_local_buffer=='A': nuevo_estado=
'BUFFER_ACTIVO' else: nuevo_estado='ACTIVO'`) SOBREESCRIBEN el `None` que
`evaluar_transicion()` devolvió para EN_MANTENIMIENTO, sin condición. Un
heartbeat perdido que finalmente llega de un dispositivo EN_MANTENIMIENTO
lo saca de mantenimiento automáticamente, sin pasar por la confirmación
manual del ingeniero que pide CA-8. Se deja documentado aquí como hallazgo
colateral; la prueba completa de ese flujo le corresponde a TC-M03-G144
(CA-7/CA-8, ciclo de vida manual), que todavía no se ha construido.

Cómo se prueba: pytest a nivel de caso de uso, con repos de prueba.

Como correrlo (Windows necesita el stub de fcntl):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    python -m pytest <ruta>\\test_tc_m03_g140_exclusion_en_mantenimiento.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M03-G140.html --self-contained-html
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

REPO_ROOT = Path(__file__).resolve().parents[5]
AHORA = datetime(2026, 10, 19, 12, 0, 0, tzinfo=timezone.utc)


def _congelar_reloj(modulo, ahora: datetime):
    import unittest.mock as mock

    class _DatetimeFijo(datetime):
        @classmethod
        def now(cls, tz=None):
            return ahora

    return mock.patch.object(modulo, 'datetime', _DatetimeFijo)


class TestSubCasoCEnMantenimientoNoTransicionaTrasOchoHoras:
    """(c): confirma el resultado funcional (no transiciona, sin alertas) a
    traves de las DOS capas reales -- la guardia de la entidad (siempre) y
    el filtro de la consulta real del repositorio (via grep del SQL)."""

    def test_evaluar_transicion_devuelve_none_para_en_mantenimiento_tras_8h(self):
        estado = EstadoDispositivoIoT(
            id_estado_dispositivo_iot=1, id_dispositivo_iot=140, estado_actual='EN_MANTENIMIENTO',
            fecha_ultimo_contacto=AHORA - timedelta(hours=8), id_ultimo_heartbeat=1,
            tiempo_sin_contacto=0, causa_primaria=None, causas_secundarias=None,
            fecha_ultima_actualizacion=AHORA, id_usuario=None,
        )
        resultado = estado.evaluar_transicion(tiempo_sin_contacto_seg=8 * 3600, estado_local_buffer=None)
        assert resultado is None, (
            'La guardia de evaluar_transicion() (primera linea del metodo) SI excluye '
            'EN_MANTENIMIENTO correctamente, sin importar cuanto tiempo haya pasado.'
        )

    def test_el_job_periodico_completo_no_transiciona_ni_genera_alerta(self):
        """Confirmacion end-to-end a traves del use case completo, no solo la entidad."""
        estado = EstadoDispositivoIoT(
            id_estado_dispositivo_iot=1, id_dispositivo_iot=140, estado_actual='EN_MANTENIMIENTO',
            fecha_ultimo_contacto=AHORA - timedelta(hours=8), id_ultimo_heartbeat=1,
            tiempo_sin_contacto=0, causa_primaria=None, causas_secundarias=None,
            fecha_ultima_actualizacion=AHORA, id_usuario=None,
        )
        estado_repo = MagicMock()
        # listar_activos() en produccion YA excluye EN_MANTENIMIENTO por SQL -- aqui lo simulamos
        # incluyendolo de todas formas, para probar que AUNQUE llegara, la guardia #2 lo protege.
        estado_repo.listar_activos.return_value = [estado]
        transicion_repo = MagicMock()
        periodo_repo = MagicMock()
        alerta_repo = MagicMock()
        historico_alerta_repo = MagicMock()
        uc = EvaluarEstadoDispositivosUseCase(
            db=MagicMock(), estado_repo=estado_repo, transicion_repo=transicion_repo,
            periodo_repo=periodo_repo, alerta_repo=alerta_repo, historico_alerta_repo=historico_alerta_repo,
        )
        import src.telemetry.application.use_cases.infraestructura.evaluar_estado_dispositivos_use_case as modulo
        with _congelar_reloj(modulo, AHORA):
            transiciones = uc.execute()

        assert transiciones == 0
        assert estado.estado_actual == 'EN_MANTENIMIENTO'
        alerta_repo.guardar.assert_not_called()
        periodo_repo.abrir.assert_not_called()


class TestHallazgoEstructuralLaExclusionVivenEnDosCapas:
    """Confirma el punto estructural que preocupa a la ficha: la exclusion NO
    vive solo 'dentro del algoritmo' -- el repositorio tambien filtra por SQL."""

    def test_listar_activos_excluye_en_mantenimiento_por_sql_no_solo_la_entidad(self):
        archivo = REPO_ROOT / 'src/telemetry/infrastructure/repositories/estado_dispositivo_iot_repository.py'
        texto = archivo.read_text(encoding='utf-8')
        assert "EN_MANTENIMIENTO" in texto and "!=" in texto, (
            'Se esperaba encontrar un filtro SQL excluyendo EN_MANTENIMIENTO en listar_activos() -- '
            'si no aparece, la exclusion ya estaria centralizada solo en la entidad (c) se cerraria distinto).'
        )
        pytest.fail(
            "HALLAZGO estructural (c): la exclusion de EN_MANTENIMIENTO vive en DOS capas, no una -- "
            "el filtro SQL de listar_activos() (WHERE estado_actual != 'EN_MANTENIMIENTO') Y la "
            "guardia de evaluar_transicion(). El resultado FUNCIONAL es correcto (confirmado arriba), "
            "pero contradice la letra de la aclaracion v1.2 ('ningun componente determina el estado "
            "por fuera del algoritmo centralizado'): la consulta SQL SI determina, por fuera del "
            "algoritmo, que dispositivos se evaluan. Ademas (hallazgo colateral, no probado aqui, "
            "pendiente para TC-M03-G144): un heartbeat de reconexion SI saca a un dispositivo de "
            "EN_MANTENIMIENTO sin pasar por la confirmacion manual de CA-8, porque "
            "recibir_heartbeat_use_case.py sobreescribe el resultado de evaluar_transicion() sin "
            "condicion en su rama de buffer."
        )
