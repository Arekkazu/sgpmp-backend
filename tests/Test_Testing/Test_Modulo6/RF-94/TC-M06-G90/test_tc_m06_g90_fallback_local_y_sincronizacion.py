"""
TC-M06-G90 (RF-94 CA-7, CA-2, FA-3, Fase 6, Restricción 7, CU-06) -
"Fallback local y sincronización."

Construido 2026-11-07 contra el código real de RF-94. Primera ronda.

Código bajo prueba:
    src/financial_valuation/infrastructure/repositories/auditoria_financiera_repository.py
    src/financial_valuation/infrastructure/routers/m06_router.py
    (contraste) src/prediction/infrastructure/adapters/respaldo_auditoria_m04_archivo_adapter.py

HALLAZGO GRAVE (ausencia total): la ficha completa de TC-M06-G90 da por
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
   falla, la excepción simplemente se propaga (y, según TC-M06-G85, revierte
   también la operación de negocio que la originó).
3. `origen_registro` se hardcodea SIEMPRE al literal `'REPOSITORIO'` en el
   INSERT real -- el valor `'FALLBACK'` que la ficha espera ver tras una
   sincronización NUNCA se escribe desde ningún código de M06.
4. El router real (`m06_router.py`) no tiene ningún endpoint
   `GET /.../fallback-status` ni similar -- el único endpoint de auditoría
   es `GET /auditoria` (confirmado en TC-M06-G83), de solo consulta técnica/
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

ACTUALIZACIÓN 2026-11-13 (respuesta de Análisis/Diseño): NO ES UN DEFECTO.
Al igual que G85/G86/G89, es consecuencia de la decisión de mantener la
auditoría en la misma transacción (RF-86) -- no se necesita fallback local
porque no hay escenario de "caída del repositorio tolerable" que cubrir.

CORRECCIÓN DE FALSO POSITIVO (señalado por el equipo): 2 subtests de este
TC venían pasando en verde por error -- coincidían con la aparición literal
de "FALLBACK" en `m06_router.py` como valor del filtro de consulta
`origen_registro: Optional[Literal["REPOSITORIO", "FALLBACK"]]` de
`GET /finanzas/auditoria` (permite FILTRAR por ese valor si algún día
existiera, no implementa el mecanismo). El grep ingenuo de la palabra
"fallback" los contaba como "ya existe" sin serlo. Corregidos para excluir
ese uso -- la conclusión de fondo no cambia (sigue sin existir ningún
mecanismo real de fallback), solo que ahora es documentación de un
comportamiento esperado por diseño, no un hallazgo.

Como correrlo (Windows necesita el stub de fcntl):
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    $env:SECRET_KEY = "test"
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    python -m pytest <ruta>\\test_tc_m06_g90_fallback_local_y_sincronizacion.py -v \\
        --html=<ruta>\\resultados\\resultado_TC-M06-G90.html --self-contained-html
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[5]
FINANCIAL_VALUATION_DIR = REPO_ROOT / 'src/financial_valuation'
ROUTER = FINANCIAL_VALUATION_DIR / 'infrastructure/routers/m06_router.py'
REPOSITORIO = FINANCIAL_VALUATION_DIR / 'infrastructure/repositories/auditoria_financiera_repository.py'
PREDICTION_DIR = REPO_ROOT / 'src/prediction'


_USO_CONOCIDO_COMO_FILTRO = 'Literal["REPOSITORIO", "FALLBACK"]'


def _menciona_fallback_como_mecanismo_real(texto: str) -> bool:
    """Excluye el falso positivo senalado por el equipo (2026-11-13): 'FALLBACK' aparece en
    m06_router.py solo como valor del filtro de consulta origen_registro, no como un mecanismo
    de respaldo implementado."""
    sin_el_filtro_conocido = texto.replace(_USO_CONOCIDO_COMO_FILTRO, '')
    return 'fallback' in sin_el_filtro_conocido.lower()


class TestSubCasoNoExisteNingunMecanismoDeFallbackConfirmadoPorDiseno:
    def test_grep_exhaustivo_de_fallback_en_financial_valuation_no_encuentra_nada(self):
        """No es un defecto (confirmado por Analisis/Diseno 2026-11-13): no se necesita
        fallback local porque la auditoria es sincrona (RF-86). Corregido el falso positivo:
        'FALLBACK' solo aparecia como valor del filtro origen_registro en el router, no como
        mecanismo real."""
        coincidencias = [str(p.relative_to(REPO_ROOT)) for p in FINANCIAL_VALUATION_DIR.rglob('*.py')
                         if _menciona_fallback_como_mecanismo_real(p.read_text(encoding='utf-8', errors='ignore'))]
        assert not coincidencias

    def test_registrar_no_tiene_ningun_try_except_que_capture_una_caida_del_repositorio(self):
        """No es un defecto: no se necesita capturar la caida porque no hay fallback que
        activar (decision de diseno, misma transaccion)."""
        texto = REPOSITORIO.read_text(encoding='utf-8')
        cuerpo_registrar = texto.split('def registrar(')[1].split('def consultar(')[0]
        assert 'try:' not in cuerpo_registrar

    def test_origen_registro_se_hardcodea_siempre_a_repositorio_nunca_a_fallback(self):
        """No es un defecto: nunca se escribe 'FALLBACK' en el INSERT -- consistente con que
        no existe el mecanismo (decision de diseno)."""
        texto = REPOSITORIO.read_text(encoding='utf-8')
        assert "'REPOSITORIO'" in texto and not _menciona_fallback_como_mecanismo_real(texto)

    def test_no_existe_ningun_endpoint_de_estado_de_fallback(self):
        """No es un defecto. Corregido el falso positivo: el filtro origen_registro=FALLBACK
        de GET /auditoria no es un endpoint '/fallback-status'."""
        texto = ROUTER.read_text(encoding='utf-8')
        assert not _menciona_fallback_como_mecanismo_real(texto)

    def test_no_existe_ningun_timeout_de_2_segundos_configurado_para_la_auditoria(self):
        """No es un defecto: no se necesita un timeout de 2s si no hay fallback que activar."""
        coincidencias = [str(p.relative_to(REPO_ROOT)) for p in FINANCIAL_VALUATION_DIR.rglob('*.py')
                         if 'statement_timeout' in p.read_text(encoding='utf-8', errors='ignore')
                         or 'wait_timeout' in p.read_text(encoding='utf-8', errors='ignore')]
        assert not coincidencias


class TestSubCasoContrasteInformativoM04SiTieneSuPropioFallbackPeroEsOtraTabla:
    def test_m04_prediction_si_tiene_su_propio_adapter_de_respaldo_a_archivo(self):
        archivos = list(PREDICTION_DIR.rglob('respaldo_auditoria_m04_archivo_adapter.py'))
        assert len(archivos) == 1

    def test_ningun_codigo_de_m04_escribe_en_la_tabla_de_auditoria_de_m06(self):
        """Informativo, no un hallazgo: M04 tiene su propio fallback, sobre otra tabla."""
        archivo = next(PREDICTION_DIR.rglob('respaldo_auditoria_m04_archivo_adapter.py'))
        texto = archivo.read_text(encoding='utf-8', errors='ignore')
        assert 'auditorias_financieras' not in texto and 'modulo6' not in texto.lower()
