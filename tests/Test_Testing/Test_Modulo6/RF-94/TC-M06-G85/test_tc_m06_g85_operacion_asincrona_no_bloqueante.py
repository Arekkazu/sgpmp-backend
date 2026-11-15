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

ACTUALIZACIÓN 2026-11-13 (respuesta de Análisis/Diseño): NO ES UN DEFECTO.
Se decidió deliberadamente mantener la auditoría de M06 en la misma
transacción que la operación auditada (RF-86, RNF de Fiabilidad). Análisis
va a ajustar la ficha de RF-94 para que ya no exija asincronía/
no-bloqueante. Todo lo confirmado en este TC (síncrono, misma transacción,
bloqueante ante fallo) describe el comportamiento DESEADO, no un hallazgo.

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


class TestSubCasoLaDocumentacionRealYaReconoceQueEsSincronaNoAsincronaConfirmadoPorDiseno:
    def test_el_docstring_del_repositorio_real_dice_misma_transaccion(self):
        """No es un defecto (confirmado por Analisis/Diseno 2026-11-13): la auditoria se
        mantiene deliberadamente en la misma transaccion que la operacion (RF-86)."""
        texto = REPOSITORIO_AUDITORIA.read_text(encoding='utf-8')
        assert 'misma transacción de la operación auditada' in texto


class TestSubCasoUnFalloExclusivoDeAuditoriaRevierteYBloqueaLaOperacionPrincipalConfirmadoPorDiseno:
    def test_generar_propaga_la_excepcion_si_solo_falla_la_auditoria(self):
        """No es un defecto (confirmado por Analisis/Diseno 2026-11-13): decision deliberada de
        mantener auditoria y operacion en la misma transaccion (RF-86). Si solo falla
        auditoria.registrar(), generar() SI debe propagar la excepcion -- es el comportamiento
        deseado, no 'ni un error de RF-94 interrumpe el proceso principal'."""
        uc, db = _construir_caso_de_uso(auditoria_falla=True)
        with pytest.raises(RuntimeError, match='repositorio de auditoria caido'):
            uc.generar(id_periodo_contable=94, filtros={}, id_usuario=1)

    def test_generar_hace_rollback_del_db_cuando_solo_falla_la_auditoria(self):
        """No es un defecto: el rollback deshaciendo tambien el guardado del estado ya calculado
        es el comportamiento esperado de 'misma transaccion', no una regresion."""
        uc, db = _construir_caso_de_uso(auditoria_falla=True)
        with pytest.raises(RuntimeError):
            uc.generar(id_periodo_contable=94, filtros={}, id_usuario=1)
        assert db.rollback.called and not db.commit.called

    def test_sin_fallo_de_auditoria_la_generacion_si_se_completa_con_un_solo_commit(self):
        """Control: confirma que en el camino feliz ambos (guardado + auditoria) comparten
        exactamente UN commit -- la prueba directa de que estan en la MISMA transaccion."""
        uc, db = _construir_caso_de_uso(auditoria_falla=False)
        uc.generar(id_periodo_contable=94, filtros={}, id_usuario=1)
        assert db.commit.call_count == 1
        assert not db.rollback.called


class TestSubCasoElMismoPatronSeRepiteEnElCierreDePeriodoConfirmadoPorDiseno:
    def test_ejecutar_cierre_periodo_envuelve_commit_rollback_alrededor_de_auditoria_registrar(self):
        """No es un defecto: mismo patron deliberado (misma transaccion) tambien en el cierre."""
        texto = USE_CASE_CIERRE.read_text(encoding='utf-8')
        tiene_try_commit_rollback = texto.count('self.db.commit()') >= 2 and texto.count('self.db.rollback()') >= 2
        assert tiene_try_commit_rollback


class TestSubCasoNoExisteNingunMecanismoDeEncoladoAsincronoConfirmadoPorDiseno:
    def test_no_existe_ningun_async_def_hilo_cola_ni_backgroundtasks(self):
        """No es un defecto: no se necesita encolado asincrono porque la auditoria es
        deliberadamente sincrona (misma transaccion, RF-86)."""
        archivos = list((REPO_ROOT / 'src/financial_valuation').rglob('*.py'))
        patrones = ('async def ', 'BackgroundTasks', 'Thread(', 'Queue(', 'celery', '.delay(', 'asyncio')
        encontrados = [p.name for p in archivos for pat in patrones if pat in p.read_text(encoding='utf-8', errors='ignore')]
        assert not encontrados
