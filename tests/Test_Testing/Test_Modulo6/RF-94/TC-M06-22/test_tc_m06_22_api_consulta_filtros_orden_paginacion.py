"""
TC-M06-22 (RF-94 Fase 7, CA-11, CU-08) - "API de consulta: filtros,
ordenamiento y paginación."

Construido 2026-11-07 contra el código real de RF-94. Primera ronda. Se
apoya en la evidencia ya reunida en TC-M06-13 (único endpoint real:
GET /finanzas/auditoria) y TC-M06-16/17 (ausencia de validación adicional
en el repositorio).

Código bajo prueba:
    src/financial_valuation/infrastructure/routers/m06_router.py (consultar_auditoria)
    src/financial_valuation/application/use_cases/auditoria/consultar_auditoria_financiera_use_case.py (execute)

CONFIRMADO CORRECTO (a favor de la ficha): al menos un filtro obligatorio
-- `execute()` lanza `ValidationError(code="FILTRO_OBLIGATORIO", ...)` salvo
que al menos uno de `tipo_evento`, `id_periodo_contable` o
`id_activo_biologico` venga informado. Estos SON los tres filtros reales
(no hay un cuarto ni un conjunto distinto). El orden por defecto SÍ es
ascendente por `fecha_registro`/`timestamp_evento`
(`orden: Literal["ASC","DESC"] = "ASC"` en el router). El tamaño de página
SÍ está limitado a 500 (`Query(100, ge=1, le=500)` en el router, reforzado
de nuevo con `tamano = min(max(tamano, 1), 500)` en el caso de uso -- doble
clamp, redundante pero consistente).

HALLAZGO (no existe ninguna restricción de DESC por volumen de resultados):
la ficha pide probar que "no se permite DESC para consultas de más de
10.000 registros". No existe en absoluto ese código: ni el router ni
`ConsultarAuditoriaFinancieraUseCase.execute()` ni
`SqlAlchemyAuditoriaFinancieraRepository.consultar()` cuentan nunca el
total de filas ANTES de decidir si `orden=DESC` es válido -- el parámetro
`orden`/`descendente` es libre siempre, independientemente de cuántas filas
vaya a devolver la consulta. Grep exhaustivo de "10000"/"10_000"/"10.000"
en todo `financial_valuation`: cero resultados.

HALLAZGO (la "paginación obligatoria arriba de 100" no es una regla real):
no existe ningún código que fuerce paginación distinta por superar 100
registros -- `tamano` simplemente tiene un valor por defecto de 100 y un
tope de 500; la paginación (`pagina`/`tamano`) está siempre disponible
desde el primer registro, nunca "se activa" ni se vuelve obligatoria a
partir de un umbral. Es una descripción imprecisa de un límite que siempre
existe, no una regla condicional que se dispare.

Cómo se prueba: pytest de unidad invocando directamente
`ConsultarAuditoriaFinancieraUseCase.execute()` con un
`AuditoriaFinancieraRepository` simulado (MagicMock), sin requerir BD viva.

Como correrlo (Windows necesita el stub de fcntl):
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    $env:SECRET_KEY = "test"
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    python -m pytest <ruta>\\test_tc_m06_22_api_consulta_filtros_orden_paginacion.py -v \\
        --html=<ruta>\\resultados\\resultado_TC-M06-22.html --self-contained-html
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.financial_valuation.application.use_cases.auditoria.consultar_auditoria_financiera_use_case import (
    ConsultarAuditoriaFinancieraUseCase,
)
from src.shared.errors import ValidationError

REPO_ROOT = Path(__file__).resolve().parents[5]
ROUTER = REPO_ROOT / 'src/financial_valuation/infrastructure/routers/m06_router.py'
USE_CASE = REPO_ROOT / 'src/financial_valuation/application/use_cases/auditoria/consultar_auditoria_financiera_use_case.py'
REPOSITORIO = REPO_ROOT / 'src/financial_valuation/infrastructure/repositories/auditoria_financiera_repository.py'


def _caso_de_uso(total_filas: int = 0):
    auditoria = MagicMock()
    auditoria.consultar.return_value = (total_filas, [])
    auditoria.conteo_por_severidad.return_value = {"INFO": 0, "WARNING": 0, "ERROR": 0, "CRITICAL": 0}
    return ConsultarAuditoriaFinancieraUseCase(auditoria=auditoria), auditoria


class TestSubCasoFiltroObligatorioYOrdenAscendenteConfirmadosCorrectos:
    def test_sin_ningun_filtro_se_rechaza_con_filtro_obligatorio(self):
        uc, _ = _caso_de_uso()
        with pytest.raises(ValidationError) as exc_info:
            uc.execute(filtros={}, pagina=1, tamano=100, legible=False)
        assert exc_info.value.code == "FILTRO_OBLIGATORIO"

    @pytest.mark.parametrize("filtros", [
        {"tipo_evento": ["COSTO_REGISTRADO"]}, {"id_periodo_contable": 1}, {"id_activo_biologico": 1},
    ])
    def test_con_cualquiera_de_los_tres_filtros_reales_no_se_rechaza(self, filtros):
        uc, _ = _caso_de_uso()
        uc.execute(filtros=filtros, pagina=1, tamano=100, legible=False)

    def test_el_router_real_tiene_orden_asc_por_defecto(self):
        texto = ROUTER.read_text(encoding='utf-8')
        assert 'orden: Literal["ASC", "DESC"] = "ASC"' in texto


class TestSubCasoNoExisteNingunaRestriccionDeDescPorVolumenHallazgo:
    def test_no_existe_ningun_conteo_de_filas_antes_de_aceptar_orden_desc(self):
        for archivo in (ROUTER, USE_CASE, REPOSITORIO):
            texto = archivo.read_text(encoding='utf-8')
            assert '10000' not in texto and '10_000' not in texto and '10.000' not in texto

    def test_execute_acepta_descendente_true_sin_importar_el_total_de_filas(self):
        """Simula 50.000 filas totales -- execute() no rechaza ni ajusta orden=DESC."""
        uc, auditoria = _caso_de_uso(total_filas=50_000)
        resultado = uc.execute(filtros={"id_periodo_contable": 1}, pagina=1, tamano=100,
                                legible=False, descendente=True)
        pytest.fail(
            f"HALLAZGO: con total_registros={resultado['total_registros']} (50.000, muy por "
            f"encima de 10.000), execute() aceptó descendente=True sin ningun rechazo ni ajuste "
            f"-- no existe la restriccion de DESC por volumen que pide la ficha."
        ) if resultado['total_registros'] > 10_000 else None

    def test_el_repositorio_real_tampoco_cuenta_filas_antes_de_construir_el_order_by(self):
        texto = REPOSITORIO.read_text(encoding='utf-8')
        pytest.fail(
            "HALLAZGO: consultar() construye 'ORDER BY ... {orden}' a partir del booleano "
            "'descendente' recibido, sin ninguna consulta previa de conteo que condicione si "
            "DESC esta permitido segun el volumen de resultados."
        ) if 'orden = "DESC" if descendente else "ASC"' in texto else None


class TestSubCasoPaginacionObligatoriaArribaDeCienNoEsUnaReglaRealHallazgo:
    def test_tamano_tiene_tope_500_confirmado_correcto(self):
        texto = ROUTER.read_text(encoding='utf-8')
        assert 'tamano: int = Query(100, ge=1, le=500)' in texto
        texto_uc = USE_CASE.read_text(encoding='utf-8')
        assert 'tamano = min(max(tamano, 1), 500)' in texto_uc

    @pytest.mark.parametrize("tamano_solicitado,tamano_esperado", [
        (99, 99), (100, 100), (101, 101), (500, 500), (501, 500),
    ])
    def test_fronteras_99_100_101_500_501_solo_dependen_del_tope_500_no_de_una_regla_de_100(
            self, tamano_solicitado, tamano_esperado):
        """El unico comportamiento especial ocurre en 501 (se recorta a 500) -- 99/100/101 se
        tratan todos igual, sin ninguna transicion de comportamiento al cruzar 100."""
        uc, auditoria = _caso_de_uso()
        uc.execute(filtros={"id_periodo_contable": 1}, pagina=1, tamano=tamano_solicitado, legible=False)
        tamano_real_usado = auditoria.consultar.call_args.args[2]
        assert tamano_real_usado == tamano_esperado

    def test_no_existe_ningun_codigo_que_fuerce_paginacion_distinta_al_superar_100(self):
        texto = USE_CASE.read_text(encoding='utf-8')
        pytest.fail(
            "HALLAZGO: 'paginacion obligatoria por encima de 100 registros' no es una regla "
            "condicional real -- tamano simplemente tiene un valor por defecto de 100 y un tope "
            "de 500; la paginacion (pagina/tamano) esta siempre disponible desde el primer "
            "registro, no se 'activa' al pasar de 100."
        ) if 'if tamano > 100' not in texto and 'if total' not in texto else None
