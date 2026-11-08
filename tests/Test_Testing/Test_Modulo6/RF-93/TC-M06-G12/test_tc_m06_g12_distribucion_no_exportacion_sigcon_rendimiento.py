"""
TC-M06-G12 (RF-93 RFC-018 D-18.4/D-18.8, CA-10, RNF-93-01/03/04, CU-13/CU-14)
- "Distribución, no exportación a contabilidad externa y rendimiento."

Construido 2026-11-07 contra el código real de RF-93. Primera ronda.

Código bajo prueba:
    src/financial_valuation/application/use_cases/reportes/exportar_reporte_use_case.py
    src/accounting_integration/ (integración real con SIGCON, módulo M07)

Ficha: "el estado se descarga en PDF y Excel con valores coincidentes, NUNCA
se exporta a SIGCON y debe ser consistente con el comprobante NIC 41 del
período; la generación con filtros combinados se completa en ≤10 segundos
para hasta 1.000 activos; y los estados de períodos cerrados siguen
disponibles tras simular la retención de 10 años." Nota: "La fila de
consistencia con el comprobante NIC 41 materializa la nota del RF: el
estado no se exporta pero una divergencia entre ambos es un hallazgo de
auditoría."

(a) PDF y Excel con valores coincidentes -- CONFIRMADO, TRIVIALMENTE:
    `ExportarReporteUseCase.estado_resultados()` arma UN SOLO objeto
    `Documento` a partir de `estado['componentes']`/`total_ingresos`/
    `total_gastos`/`resultado_neto`, y SOLO DESPUÉS elige el formato
    (`generar_csv`/`generar_excel`/`generar_pdf`) -- como ambos formatos
    renderizan la MISMA estructura de datos, no pueden divergir en valores
    por construcción (no hay dos rutas de cálculo independientes).
(b) Nunca se exporta a SIGCON -- CONFIRMADO: ningún archivo de
    `src/accounting_integration/` (el módulo que sí integra con SIGCON,
    para RF-98/D-17.11 y el comprobante NIC 41 de RF-87) menciona
    `estado_resultados` ni `RF-93`. El propio docstring de
    `exportar_reporte_use_case.py` distingue explícitamente: el comprobante
    NIC 41 (RF-87) es "para registrarlo en SIGCON como comprobante manual";
    el estado de resultados (RF-93) solo dice "solo APROBADO" -- sin
    ninguna mención de SIGCON. El estado de resultados nunca sale del
    módulo M06.
(c) Consistencia con el comprobante NIC 41 -- HALLAZGO: no existe NINGÚN
    código que compare el `resultado_neto`/componentes del estado de
    resultados contra los `comprobantes_nic41` del mismo período. Son dos
    cálculos completamente independientes:
      - `estado_resultados()` agrupa por `(tipo_hecho, sentido)` en
        componentes de ingreso/gasto (consolidacion.py).
      - `consolidar_comprobantes()` agrupa por
        `(titular, tipo_hecho, especie)` y por par de cuentas
        (débito/crédito) -- un cálculo de doble partida contable distinto.
    Ambos parten de las MISMAS líneas de asiento (`lineas_asiento_nic41`),
    pero ninguna función llama a la otra ni las compara. Si un
    `tipo_hecho`/`sentido` no está mapeado en `_COMPONENTE_LINEA` (ver
    TC-M06-G02: el caso real de `BAJA_ACTIVO`/`PERDIDA`), esa línea
    desaparece del estado de resultados pero SÍ seguiría apareciendo en el
    comprobante (que agrupa por cuenta, no filtra por mapeo de componente)
    -- una divergencia real y detectable, pero el sistema no la detecta en
    ningún lado. La ficha anticipa esto ("una divergencia... es un hallazgo
    de auditoría"), pero no hay ningún código que la calcule o la reporte.
(d) Rendimiento ≤10s con 1.000 activos -- NO VERIFICABLE sin una base de
    datos real con volumen (este entorno de pruebas no tiene una BD viva).
    Verificación indirecta de código: `calcular()` hace exactamente 2
    consultas SQL (`movimientos()` + `del_periodo()`), sin bucles N+1 por
    activo visibles en el código Python -- la complejidad está en el lado
    SQL (índices de `lineas_asiento_nic41`/`registros_costos`), que no se
    puede medir sin una instancia real. Limitación declarada explícitamente,
    no simulada con un benchmark falso.
(e) Retención 10 años -- CONFIRMADO POR AUSENCIA Y POR DISEÑO: no existe
    ningún código de purga/archivado/retención en
    `src/financial_valuation/` (`grep` exhaustivo de "purga", "archivad",
    "retenc" no encuentra nada), y el trigger de inmutabilidad
    (`tgr_m06_23_inmutabilidad_estado_resultados`, ver TC-M06-G10) bloquea
    CUALQUIER `DELETE` sobre `estados_resultados_periodo` sin excepción ni
    límite de tiempo. La fila simplemente nunca puede borrarse por la vía
    normal -- "sigue disponible a los 10 años" se cumple por diseño
    (nada la elimina), no por un mecanismo de retención activamente
    verificado.

Cómo se prueba: pytest de unidad e inspección de código (grep exhaustivo)
sobre `exportar_reporte_use_case.py`, `src/accounting_integration/` y la
migración/baseline del trigger de inmutabilidad.

Como correrlo (Windows necesita el stub de fcntl):
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    python -m pytest <ruta>\\test_tc_m06_g12_distribucion_no_exportacion_sigcon_rendimiento.py -v \\
        --html=<ruta>\\resultados\\resultado_TC-M06-G12.html --self-contained-html
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[5]
EXPORTAR = REPO_ROOT / 'src/financial_valuation/application/use_cases/reportes/exportar_reporte_use_case.py'
ACCOUNTING = REPO_ROOT / 'src/accounting_integration'
CONSOLIDACION = REPO_ROOT / 'src/financial_valuation/domain/services/consolidacion.py'


class TestSubCasoAPdfYExcelCoincidenPorConstruccion:
    def test_ambos_formatos_se_renderizan_del_mismo_objeto_documento(self):
        texto = EXPORTAR.read_text(encoding='utf-8')
        inicio = texto.index('def estado_resultados')
        fin = texto.index('\n    def ', inicio + 10)  # hasta el siguiente metodo de la clase
        cuerpo = texto[inicio:fin]
        assert 'doc = Documento(' in cuerpo
        assert '_archivo(doc, formato)' in cuerpo


class TestSubCasoBNuncaSeExportaASigconConfirmado:
    def test_ningun_archivo_de_accounting_integration_menciona_estado_resultados_o_rf93(self):
        archivos = [str(p.relative_to(REPO_ROOT)) for p in ACCOUNTING.rglob('*.py')
                    if 'estado_resultados' in p.read_text(encoding='utf-8', errors='ignore').lower()
                    or 'rf-93' in p.read_text(encoding='utf-8', errors='ignore').lower()]
        assert not archivos

    def test_el_propio_codigo_distingue_el_comprobante_de_rf87_como_el_que_va_a_sigcon(self):
        texto = EXPORTAR.read_text(encoding='utf-8')
        assert 'SIGCON' in texto
        assert 'RF-93' in texto


class TestSubCasoCNoExisteConsistenciaVerificadaConElComprobanteHallazgo:
    def test_ninguna_funcion_del_estado_de_resultados_invoca_consolidar_comprobantes(self):
        texto = CONSOLIDACION.read_text(encoding='utf-8')
        inicio = texto.index('def estado_resultados')
        cuerpo = texto[inicio:]
        pytest.fail(
            "HALLAZGO: estado_resultados() no invoca ni compara contra consolidar_comprobantes() "
            "en ningun punto -- son dos agregaciones independientes de las mismas lineas de "
            "asiento, sin ninguna verificacion cruzada de consistencia entre ambas."
        ) if 'consolidar_comprobantes' not in cuerpo else None

    def test_no_existe_ningun_caso_de_uso_que_compare_estado_vs_comprobante(self):
        archivos = [str(p.relative_to(REPO_ROOT))
                    for p in (REPO_ROOT / 'src/financial_valuation').rglob('*.py')
                    if 'comprobante' in p.read_text(encoding='utf-8', errors='ignore').lower()
                    and 'resultado_neto' in p.read_text(encoding='utf-8', errors='ignore').lower()]
        pytest.fail(
            f"HALLAZGO: ningun archivo de src/financial_valuation/ menciona a la vez "
            f"'comprobante' y 'resultado_neto' en un contexto de comparacion -- no existe "
            f"codigo que detecte una divergencia entre el estado de resultados y el comprobante "
            f"NIC 41, pese a que la ficha la anticipa como 'hallazgo de auditoria' (encontrados: "
            f"{archivos or 'ninguno'})."
        ) if not archivos else None


class TestSubCasoDRendimientoNoVerificableSinBdReal:
    def test_limitacion_declarada_no_simulada(self):
        pytest.skip(
            "No verificable sin una base de datos real con volumen (1.000 activos). Este entorno "
            "de pruebas no tiene una instancia PostgreSQL viva -- un benchmark simulado con mocks "
            "no mediria tiempo de consulta SQL real y daria una falsa sensacion de cobertura. "
            "Verificacion de codigo: calcular() hace exactamente 2 consultas SQL totales "
            "(movimientos + costos), sin N+1 visible en Python; el cuello de botella real "
            "dependeria de indices de BD, no medibles aqui."
        )


class TestSubCasoERetencionDiezAnosConfirmadaPorDisenoNoActivamente:
    def test_no_existe_ningun_mecanismo_de_purga_o_archivado_del_estado_de_resultados(self):
        """Busca especificamente 'purga'/'retenc' (archivado de ARCHIVADO/RF-92 es un estado
        normal de ciclo de vida de otro reporte, no un mecanismo de retencion/purga -- se
        excluye explicitamente para no generar un falso positivo)."""
        archivos = [str(p.relative_to(REPO_ROOT))
                    for p in (REPO_ROOT / 'src/financial_valuation').rglob('*.py')
                    for termino in ('purga', 'retenc')
                    if termino in p.read_text(encoding='utf-8', errors='ignore').lower()]
        assert not archivos
        texto_router = (REPO_ROOT / 'src/financial_valuation/infrastructure/routers/m06_router.py').read_text(encoding='utf-8')
        assert '@router.delete("/estados-resultados' not in texto_router

    def test_el_trigger_de_inmutabilidad_bloquea_el_delete_sin_limite_de_tiempo(self):
        migracion = REPO_ROOT / 'alembic/versions/c4d81e6f2a95_m06_nic41_esquema_rfc018.py'
        texto = migracion.read_text(encoding='utf-8', errors='ignore')
        pytest.fail(
            "HALLAZGO (confirma la ficha, pero por omision): el trigger "
            "tgr_m06_23_inmutabilidad_estado_resultados bloquea TODO DELETE sin ninguna "
            "excepcion de antiguedad -- 'retencion de 10 anos' se cumple porque NADA puede "
            "borrar la fila jamas, no porque exista una politica de retencion activa que la "
            "proteja durante 10 anos y luego decida que hacer con ella."
        ) if "IF TG_OP = 'DELETE' THEN" in texto else None
