"""
TC-M06-20 (RF-94 CA-7, CA-2, FA-3, Fase 6, Restricción 7, CU-06) -
"Fallback local y sincronización."

Construido 2026-11-07 contra el código real de RF-94. Primera ronda.

Código bajo prueba:
    src/financial_valuation/infrastructure/repositories/auditoria_financiera_repository.py
    src/financial_valuation/infrastructure/routers/m06_router.py
    (contraste) src/prediction/infrastructure/adapters/respaldo_auditoria_m04_archivo_adapter.py

HALLAZGO GRAVE (ausencia total): la ficha completa de TC-M06-20 da por
hecho que existe un mecanismo de fallback a archivo local
(`audit_fallback_M06_YYYYMMDD.log`) para M06, activado por caída del
repositorio / timeout de 2s / error de escritura, con alerta CRITICAL y
sincronización FIFO posterior marcada `origen_registro=FALLBACK`. NINGUNA
parte de esto existe en `src/financial_valuation/`:

1. Grep exhaustivo de "fallback"/"FALLBACK" (case-insensitive) en TODO
   `src/financial_valuation/` -- CERO resultados.
2. El único `INSERT` real a `modulo6.auditorias_financieras`
   (`registrar()`) no tiene ningún `try/except` que capture una caída del
   repositorio y escriba a un archivo alterno -- si la escritura a BD
   falla, la excepción simplemente se propaga (y, según TC-M06-15, revierte
   también la operación de negocio que la originó).
3. `origen_registro` se hardcodea SIEMPRE al literal `'REPOSITORIO'` en el
   INSERT real -- el valor `'FALLBACK'` que la ficha espera ver tras una
   sincronización NUNCA se escribe desde ningún código de M06.
4. El router real (`m06_router.py`) no tiene ningún endpoint
   `GET /.../fallback-status` ni similar -- el único endpoint de auditoría
   es `GET /auditoria` (confirmado en TC-M06-13), de solo consulta técnica/
   legible, sin ningún indicador de estado de fallback.
5. No existe ningún timeout de 2 segundos configurado para la escritura de
   auditoría en ningún lugar del módulo (ni como parámetro, ni como
   constante, ni como `wait_timeout`/`statement_timeout` específico para
   esta tabla).

CONTRASTE INFORMATIVO (de dónde pudo salir el patrón de la ficha, no
aplica a M06): el módulo de predicción (M04, `src/prediction/`) SÍ tiene un
mecanismo análogo para SU PROPIA auditoría --
`respaldo_auditoria_m04_archivo_adapter.py` y
`sincronizar_respaldo_auditoria_m04_use_case.py` -- con su propia tabla y
su propio archivo de respaldo. Es un sistema completamente distinto, de
otro módulo, sobre otra tabla (`modulo4.auditorias_predicciones`, no
`modulo6.auditorias_financieras`). Ningún código de M04 escribe jamás en el
repositorio de auditoría de M06, y viceversa. Es plausible que la ficha
haya generalizado por error un patrón de M04 a M06; en la implementación
real de RF-94/M06 este mecanismo simplemente no existe.

Cómo se prueba: pytest de unidad por grep exhaustivo y por inspección del
router/repositorio reales -- no requiere BD viva ni simular una caída real
del repositorio, porque no hay código de fallback que ejercitar.

Como correrlo (Windows necesita el stub de fcntl):
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    $env:SECRET_KEY = "test"
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    python -m pytest <ruta>\\test_tc_m06_20_fallback_local_y_sincronizacion.py -v \\
        --html=<ruta>\\resultados\\resultado_TC-M06-20.html --self-contained-html
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[5]
FINANCIAL_VALUATION_DIR = REPO_ROOT / 'src/financial_valuation'
ROUTER = FINANCIAL_VALUATION_DIR / 'infrastructure/routers/m06_router.py'
REPOSITORIO = FINANCIAL_VALUATION_DIR / 'infrastructure/repositories/auditoria_financiera_repository.py'
PREDICTION_DIR = REPO_ROOT / 'src/prediction'


class TestSubCasoNoExisteNingunMecanismoDeFallbackEnFinancialValuationHallazgoGrave:
    def test_grep_exhaustivo_de_fallback_en_financial_valuation_no_encuentra_nada(self):
        coincidencias = [str(p.relative_to(REPO_ROOT)) for p in FINANCIAL_VALUATION_DIR.rglob('*.py')
                         if 'fallback' in p.read_text(encoding='utf-8', errors='ignore').lower()]
        pytest.fail(
            f"HALLAZGO GRAVE: grep exhaustivo de 'fallback' (case-insensitive) en todo "
            f"src/financial_valuation da CERO resultados (encontrados: {coincidencias!r}) -- "
            f"ningun archivo de M06 implementa el mecanismo de respaldo local que pide la ficha."
        ) if not coincidencias else None

    def test_registrar_no_tiene_ningun_try_except_que_capture_una_caida_del_repositorio(self):
        texto = REPOSITORIO.read_text(encoding='utf-8')
        cuerpo_registrar = texto.split('def registrar(')[1].split('def consultar(')[0]
        pytest.fail(
            "HALLAZGO: el metodo real registrar() no tiene ningun try/except alrededor del "
            "INSERT -- si la escritura a BD falla, la excepcion se propaga sin ningun fallback "
            "a archivo local."
        ) if 'try:' not in cuerpo_registrar else None

    def test_origen_registro_se_hardcodea_siempre_a_repositorio_nunca_a_fallback(self):
        texto = REPOSITORIO.read_text(encoding='utf-8')
        pytest.fail(
            "HALLAZGO: origen_registro se hardcodea siempre al literal 'REPOSITORIO' en el "
            "INSERT real -- el valor 'FALLBACK' que la ficha espera tras una sincronizacion "
            "nunca se escribe desde ningun codigo de M06."
        ) if "'REPOSITORIO'" in texto and 'FALLBACK' not in texto else None

    def test_no_existe_ningun_endpoint_de_estado_de_fallback(self):
        texto = ROUTER.read_text(encoding='utf-8').lower()
        pytest.fail(
            "HALLAZGO: no existe ningun endpoint '/fallback-status' ni similar en el router "
            "real de M06 -- el unico endpoint de auditoria es GET /auditoria, de solo consulta."
        ) if 'fallback' not in texto else None

    def test_no_existe_ningun_timeout_de_2_segundos_configurado_para_la_auditoria(self):
        coincidencias = [str(p.relative_to(REPO_ROOT)) for p in FINANCIAL_VALUATION_DIR.rglob('*.py')
                         if 'statement_timeout' in p.read_text(encoding='utf-8', errors='ignore')
                         or 'wait_timeout' in p.read_text(encoding='utf-8', errors='ignore')]
        pytest.fail(
            "HALLAZGO: no existe ningun timeout configurado (statement_timeout/wait_timeout) "
            "especificamente para la escritura de auditoria en todo financial_valuation -- el "
            "umbral de '2 segundos' que pide la ficha no tiene ninguna implementacion real."
        ) if not coincidencias else None


class TestSubCasoContrasteInformativoM04SiTieneSuPropioFallbackPeroEsOtraTabla:
    def test_m04_prediction_si_tiene_su_propio_adapter_de_respaldo_a_archivo(self):
        archivos = list(PREDICTION_DIR.rglob('respaldo_auditoria_m04_archivo_adapter.py'))
        assert len(archivos) == 1

    def test_ningun_codigo_de_m04_escribe_en_la_tabla_de_auditoria_de_m06(self):
        archivo = next(PREDICTION_DIR.rglob('respaldo_auditoria_m04_archivo_adapter.py'))
        texto = archivo.read_text(encoding='utf-8', errors='ignore')
        pytest.fail(
            "HALLAZGO: el adapter de respaldo de M04 no menciona 'auditorias_financieras' ni "
            "'modulo6' -- es un sistema de fallback completamente independiente, sobre la tabla "
            "modulo4.auditorias_predicciones, no sobre la de RF-94/M06."
        ) if 'auditorias_financieras' in texto or 'modulo6' in texto.lower() else None
