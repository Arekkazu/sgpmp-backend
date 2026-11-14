"""
TC-M06-G85 (RF-94 CA-6, RNF-09, Restricción 4, CU-01) - "Operación asíncrona y
no bloqueante."

Construido 2026-11-07 contra el código real de RF-94. Primera ronda. Este es
el hallazgo más grave de todo RF-94: la ficha pide confirmar exactamente lo
contrario de lo que el código real hace.

Código bajo prueba:
    src/financial_valuation/application/use_cases/reportes/generar_estado_resultados_use_case.py
    src/financial_valuation/application/use_cases/cierre/ejecutar_cierre_periodo_use_case.py
    src/financial_valuation/infrastructure/repositories/auditoria_financiera_repository.py (docstring propio)

HALLAZGO GRAVE, BLOQUEANTE (confirma exactamente el riesgo que la propia
ficha anticipa en su columna de observaciones): el registro de auditoría de
RF-94 es SIEMPRE SÍNCRONO Y BLOQUEANTE, nunca "fire-and-forget". La prueba
más directa es el propio docstring de
`SqlAlchemyAuditoriaFinancieraRepository` (línea 9): *"La escritura va en la
misma transacción de la operación auditada (RF-86 RNF Fiabilidad)"* -- un
reconocimiento explícito y deliberado de que la auditoría NO es asíncrona.

El código de `GenerarEstadoResultadosUseCase.generar()` lo demuestra de
forma concreta (líneas 37-54):
```python
try:
    resultado = self.constructor.guardar(...)        # 1. guarda el estado
    self.auditoria.registrar(EventoAuditoria(...))    # 2. registra el evento
    self.db.commit()                                  # 3. UN SOLO commit para ambos
except Exception:
    self.db.rollback()                                # si (2) falla, se deshace (1) tambien
    raise
```
Si `self.auditoria.registrar(...)` lanza CUALQUIER excepción (el repositorio
cae, el trigger `tgr_m06_27` rechaza el hash/actor, timeout de red a la BD,
etc.), el bloque `except Exception: self.db.rollback(); raise` se dispara, y
el `rollback()` deshace TAMBIÉN el guardado del estado de resultados que ya
se había calculado con éxito en el paso 1. Es decir: una falla puramente de
auditoría cancela la operación de negocio principal -- el escenario
EXACTAMENTE opuesto al "fire-and-forget... ni la caída total... interrumpen
el proceso principal" que pide la ficha.

El mismo patrón (try/commit/except-rollback envolviendo tanto la operación
de negocio como `auditoria.registrar`) se repite en
`ejecutar_cierre_periodo_use_case.py` (líneas 137-143, 160-198) -- el cierre
de período (la operación más crítica de todo M06) también se revierte
íntegramente si el registro de auditoría de cualquiera de sus pasos falla.
Esto confirma literalmente la nota "BLOQUEANTE" de la propia ficha: *"Si la
auditoría es síncrona de hecho, una caída del repositorio detiene el cierre
contable del período."* -- lo es, y lo hace.

No existe en todo `financial_valuation` ningún mecanismo de encolado,
`async def`, hilo, cola de mensajes, `BackgroundTasks` de FastAPI, ni
llamada HTTP saliente hacia un servicio de auditoría separado -- `registrar()`
es una llamada Python síncrona y directa dentro de la misma sesión de BD y
la misma transacción que la operación que audita.

Cómo se prueba: pytest de unidad con un repositorio de auditoría simulado
que lanza una excepción deliberada, confirmando que `generar()` también
falla (propaga la excepción) y que `db.rollback()` se invoca -- es decir,
que la operación principal SÍ se bloquea/revierte por un fallo exclusivo de
auditoría.

Como correrlo (Windows necesita el stub de fcntl):
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    $env:SECRET_KEY = "test"
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    python -m pytest <ruta>\\test_tc_m06_g85_operacion_asincrona_no_bloqueante.py -v \\
        --html=<ruta>\\resultados\\resultado_TC-M06-G85.html --self-contained-html
"""
from __future__ import annotations

import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.financial_valuation.application.services.reportes import ConstructorEstadoResultados
from src.financial_valuation.application.use_cases.reportes.generar_estado_resultados_use_case import (
    GenerarEstadoResultadosUseCase,
)
from src.financial_valuation.domain.entities.contabilidad import Periodo
from src.shared.errors import NotFoundError

REPO_ROOT = Path(__file__).resolve().parents[5]
USE_CASE_GENERAR = REPO_ROOT / 'src/financial_valuation/application/use_cases/reportes/generar_estado_resultados_use_case.py'
USE_CASE_CIERRE = REPO_ROOT / 'src/financial_valuation/application/use_cases/cierre/ejecutar_cierre_periodo_use_case.py'
REPOSITORIO_AUDITORIA = REPO_ROOT / 'src/financial_valuation/infrastructure/repositories/auditoria_financiera_repository.py'


def _construir_caso_de_uso(auditoria_falla: bool):
    periodos = MagicMock()
    periodos.obtener.return_value = Periodo(
        id_periodo_contable=94, numero_id_tributaria='900123456', tipo_cierre='MENSUAL',
        fecha_inicio=datetime.date(2026, 10, 1), fecha_fin=datetime.date(2026, 10, 31), estado='CERRADO',
    )
    periodos.ultima_ejecucion.return_value = {'activos_excluidos': []}
    reportes = MagicMock()
    reportes.movimientos.return_value = []
    reportes.siguiente_version_estado.return_value = 1
    reportes.agregar_estado.return_value = 1
    costos = MagicMock()
    costos.del_periodo.return_value = []
    constructor = ConstructorEstadoResultados(reportes=reportes, costos=costos)
    auditoria = MagicMock()
    if auditoria_falla:
        auditoria.registrar.side_effect = RuntimeError('repositorio de auditoria caido / timeout de red')
    db = MagicMock()
    uc = GenerarEstadoResultadosUseCase(db=db, periodos=periodos, reportes=reportes,
                                        constructor=constructor, auditoria=auditoria)
    return uc, db


class TestSubCasoLaDocumentacionRealYaReconoceQueEsSincronaNoAsincrona:
    def test_el_docstring_del_repositorio_real_dice_misma_transaccion(self):
        texto = REPOSITORIO_AUDITORIA.read_text(encoding='utf-8')
        pytest.fail(
            "HALLAZGO GRAVE: el propio docstring del repositorio real de RF-94 dice explicitamente "
            "'La escritura va en la misma transaccion de la operacion auditada' -- un "
            "reconocimiento directo de que NO es asincrona ni fire-and-forget, al contrario de lo "
            "que pide confirmar la ficha (CA-6, RNF-09)."
        ) if 'misma transacción de la operación auditada' in texto else None


class TestSubCasoUnFalloExclusivoDeAuditoriaRevierteYBloqueaLaOperacionPrincipalHallazgoGrave:
    def test_generar_propaga_la_excepcion_si_solo_falla_la_auditoria(self):
        """El calculo del estado (constructor.guardar) tiene EXITO -- solo auditoria.registrar()
        falla. Si la auditoria fuera realmente asincrona/no bloqueante, generar() deberia
        completarse igual. En la realidad, se propaga la excepcion: la operacion de negocio
        principal SI se bloquea por un fallo puramente de auditoria."""
        uc, db = _construir_caso_de_uso(auditoria_falla=True)
        with pytest.raises(RuntimeError, match='repositorio de auditoria caido'):
            uc.generar(id_periodo_contable=94, filtros={}, id_usuario=1)
        pytest.fail(
            "HALLAZGO GRAVE CONFIRMADO: generar() propaga la excepcion del repositorio de "
            "auditoria -- un fallo EXCLUSIVO de RF-94 bloquea/aborta la generacion del estado de "
            "resultados (RF-93), al contrario de 'ni un error de RF-94... interrumpen el proceso "
            "principal' que exige la ficha."
        )

    def test_generar_hace_rollback_del_db_cuando_solo_falla_la_auditoria(self):
        """El rollback deshace TAMBIEN el guardado del estado que ya se habia calculado con
        exito -- no solo se 'bloquea', se REVIERTE una operacion de negocio que ya habia
        tenido exito, por un fallo que no tiene nada que ver con ese negocio."""
        uc, db = _construir_caso_de_uso(auditoria_falla=True)
        with pytest.raises(RuntimeError):
            uc.generar(id_periodo_contable=94, filtros={}, id_usuario=1)
        pytest.fail(
            f"HALLAZGO GRAVE CONFIRMADO: db.rollback() fue invocado ({db.rollback.called}) y "
            f"db.commit() NUNCA se llego a invocar ({db.commit.called}) -- el estado de resultados "
            f"ya calculado con exito se revierte por una falla exclusiva del repositorio de "
            f"auditoria de RF-94."
        ) if db.rollback.called and not db.commit.called else None

    def test_sin_fallo_de_auditoria_la_generacion_si_se_completa_con_un_solo_commit(self):
        """Control: confirma que en el camino feliz ambos (guardado + auditoria) comparten
        exactamente UN commit -- la prueba directa de que estan en la MISMA transaccion."""
        uc, db = _construir_caso_de_uso(auditoria_falla=False)
        uc.generar(id_periodo_contable=94, filtros={}, id_usuario=1)
        assert db.commit.call_count == 1
        assert not db.rollback.called


class TestSubCasoElMismoPatronBloqueanteSeRepiteEnElCierreDePeriodoElMasCritico:
    def test_ejecutar_cierre_periodo_envuelve_commit_rollback_alrededor_de_auditoria_registrar(self):
        texto = USE_CASE_CIERRE.read_text(encoding='utf-8')
        tiene_try_commit_rollback = texto.count('self.db.commit()') >= 2 and texto.count('self.db.rollback()') >= 2
        pytest.fail(
            "HALLAZGO GRAVE: ejecutar_cierre_periodo_use_case.py repite el mismo patron "
            "try/commit/except-rollback alrededor de sus llamadas a auditoria.registrar() -- el "
            "CIERRE CONTABLE DEL PERIODO (la operacion mas critica de M06) tambien se revierte "
            "integramente si falla el registro de auditoria de cualquiera de sus pasos. Confirma "
            "literalmente la nota BLOQUEANTE de la propia ficha."
        ) if tiene_try_commit_rollback else None


class TestSubCasoNoExisteNingunMecanismoDeEncoladoAsincronoEnTodoElModulo:
    def test_no_existe_ningun_async_def_hilo_cola_ni_backgroundtasks(self):
        archivos = list((REPO_ROOT / 'src/financial_valuation').rglob('*.py'))
        patrones = ('async def ', 'BackgroundTasks', 'Thread(', 'Queue(', 'celery', '.delay(', 'asyncio')
        encontrados = [p.name for p in archivos for pat in patrones if pat in p.read_text(encoding='utf-8', errors='ignore')]
        pytest.fail(
            f"HALLAZGO: no existe ningun mecanismo de ejecucion asincrona real (async def, "
            f"BackgroundTasks, hilos, colas, celery) en todo src/financial_valuation (coincidencias "
            f"espurias si las hay: {encontrados!r}) -- 'operacion asincrona y no bloqueante' no "
            f"tiene ninguna implementacion que la sustente."
        ) if not encontrados else None
