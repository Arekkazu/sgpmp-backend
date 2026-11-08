"""
TC-M06-24 (RF-94 CA-2, CA-10, CA-11, CA-12, CA-14, RNF-01, RNF-02, RNF-06,
RNF-08, CU-11/CU-12/CU-13) - "Correlación transversal, consistencia
temporal, eventos de precios y rendimiento."

Construido 2026-11-07 contra el código real de RF-94. Primera ronda. Se
apoya en la evidencia ya reunida en TC-M06-13 (M07 es un sistema de
auditoría separado) y TC-M06-21 (patrón de "comentario de documentación sin
implementación activa", ya visto con M08 en RF-93 y con la retención de 10
años aquí mismo).

Código bajo prueba:
    src/financial_valuation/infrastructure/repositories/auditoria_financiera_repository.py (modulo_origen hardcodeado)
    src/financial_valuation/infrastructure/routers/m06_router.py (único endpoint real)
    src/financial_valuation/application/use_cases/precios/registrar_precio_use_case.py (PRECIO_MARCADO_REEMPLAZADO)
    alembic/baseline/esquema_baseline.sql (comentario de columna modulo_origen y fecha_registro)

HALLAZGO GRAVE (no existe ningún repositorio centralizado de auditoría
cross-módulo): la ficha pide confirmar que los eventos "conviven en el
repositorio compartido diferenciados por `modulo`" y permiten reconstruir
la cadena "M03 → M04 → M02 → M06" con los mismos filtros base. Esto es
falso en el código real: `modulo_origen` en el INSERT real es el literal
Python hardcodeado `'M06'` -- nunca varía, nunca se lee de otro módulo.
No existe en todo el backend ningún endpoint `GET /api/v1/audit/events`
(repositorio centralizado); el único endpoint real de auditoría de M06,
`GET /finanzas/auditoria`, consulta EXCLUSIVAMENTE
`modulo6.auditorias_financieras` -- no hay ningún `UNION`, vista ni join
hacia las tablas de auditoría de M02/M03/M04 (que, confirmado en este
mismo backend, viven en esquemas completamente separados, p. ej.
`modulo4.auditorias_predicciones` para M04). La cadena "M03 → M04 → M02 →
M06" es irreconstruible a través de este endpoint: no tiene ninguna forma
de incluir eventos de otros módulos.

HALLAZGO (la premisa de "repositorio centralizado" es documentación
aspiracional, nunca implementada -- mismo patrón que M08/RF-93 y que la
retención de 10 años de TC-M06-21): el COMENTARIO de columna real sobre
`modulo_origen` (en `esquema_baseline.sql`) dice literalmente: *"Permite
correlacionar eventos de este módulo con eventos de RF-52 (M02), RF-63
(M03) y RF-73 (M04) en el repositorio centralizado de auditoría para
construir la cadena de trazabilidad de RF-91."* -- es una intención de
diseño documentada en un COMENTARIO SQL, no una tabla, vista ni consulta
real. El repositorio centralizado que describe no existe en el código
Python de este backend.

HALLAZGO (la sincronización NTP es también solo un comentario, sin
ninguna verificación activa): la única mención de "NTP" en TODO el
backend (`grep -rni "ntp" src/ alembic/`, cero resultados en `src/`) está
en el COMENTARIO de la columna `fecha_registro`: *"Sincronizado con el
reloj NTP del sistema..."* -- documentación, no código. No existe ningún
cálculo de desviación horaria, ninguna comparación con un servidor NTP,
ni ningún código que verifique "±1 segundo" en ningún lugar de
`financial_valuation`. La columna es simplemente `DEFAULT now()` del
servidor de BD.

HALLAZGO (matiza la ficha sobre PRECIO_MARCADO_REEMPLAZADO): SÍ se
registra un evento con el precio anterior y el nuevo, pero por REFERENCIA
(IDs), no por VALOR. El payload real es exactamente
`{"id_precio_anterior": anterior.id_precio_mercado, "id_precio_nuevo":
precio.id_precio_mercado}` (`registrar_precio_use_case.py`) -- dos
identificadores de fila, no los montos (`precio_unitario`) en sí. Para
obtener los valores anterior/nuevo hay que resolver esos dos IDs contra
`precios_mercado` (una consulta adicional, no incluida en el propio
evento). En reemplazos encadenados, esto SÍ permite reconstruir la cadena
completa caminando los eventos (cada reemplazo apunta a su predecesor
inmediato), pero NINGÚN evento individual contiene el valor del precio
"anterior" directamente -- solo su identificador.

HALLAZGO (rendimiento: no verificable por inspección estática, requiere
infraestructura real): los umbrales de carga de la ficha (900/1.000/1.200
eventos por minuto, 1M/10M de registros) exigen una prueba de carga real
contra una BD viva (JMeter/k6 + EXPLAIN) -- no hay ninguna forma de
"simular" esto con pruebas unitarias/mocks sin que el resultado sea una
ficción. Siguiendo la misma convención ya usada en TC-M06-G12 de RF-93
("rendimiento con 1.000 activos" quedó marcado como no verificado, no
simulado), este TC documenta que la verificación de rendimiento queda
explícitamente PENDIENTE de una ronda de pruebas de carga contra un
entorno real (TEST/DEV), y no se fabrica aquí un resultado sintético.

Cómo se prueba: pytest de unidad por inspección de código real (grep +
lectura directa de `registrar()`, el router y el caso de uso de precios) y
documentación explícita del límite de lo verificable sin infraestructura
real -- no requiere BD viva salvo para la parte de rendimiento, que queda
marcada como pendiente.

Como correrlo (Windows necesita el stub de fcntl):
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    $env:SECRET_KEY = "test"
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    python -m pytest <ruta>\\test_tc_m06_24_correlacion_temporal_precios_rendimiento.py -v \\
        --html=<ruta>\\resultados\\resultado_TC-M06-24.html --self-contained-html
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[5]
REPOSITORIO = REPO_ROOT / 'src/financial_valuation/infrastructure/repositories/auditoria_financiera_repository.py'
ROUTER = REPO_ROOT / 'src/financial_valuation/infrastructure/routers/m06_router.py'
PRECIO_USE_CASE = REPO_ROOT / 'src/financial_valuation/application/use_cases/precios/registrar_precio_use_case.py'
BASELINE = REPO_ROOT / 'alembic/baseline/esquema_baseline.sql'
FINANCIAL_VALUATION_DIR = REPO_ROOT / 'src/financial_valuation'
SRC_DIR = REPO_ROOT / 'src'


class TestSubCasoNoExisteNingunRepositorioCentralizadoCrossModuloHallazgoGrave:
    def test_modulo_origen_es_siempre_el_literal_m06_hardcodeado(self):
        texto = REPOSITORIO.read_text(encoding='utf-8')
        pytest.fail(
            "HALLAZGO GRAVE: el INSERT real pasa 'M06' como literal fijo para modulo_origen -- "
            "nunca varia, nunca se lee de otro modulo. No hay forma de que un evento de M02/M03/"
            "M04 llegue jamas a esta tabla con un modulo_origen distinto."
        ) if "'M06'" in texto else None

    def test_no_existe_ningun_endpoint_get_api_v1_audit_events_centralizado(self):
        texto = ROUTER.read_text(encoding='utf-8')
        pytest.fail(
            "HALLAZGO GRAVE: el unico endpoint real de auditoria es GET /finanzas/auditoria "
            "(prefix /finanzas) -- no existe ningun GET /api/v1/audit/events centralizado en "
            "todo el router de M06."
        ) if '/api/v1/audit/events' not in texto and router_prefix_es_finanzas(texto) else None

    def test_consultar_real_solo_toca_la_tabla_de_m06_sin_union_ni_join_cross_modulo(self):
        texto = REPOSITORIO.read_text(encoding='utf-8')
        pytest.fail(
            "HALLAZGO GRAVE: consultar() hace SELECT unicamente de modulo6.auditorias_financieras "
            "(con LEFT JOIN solo a modulo1.usuarios y modulo2.activos_biologicos, para resolver "
            "nombre/identificador, no para traer eventos de otros modulos) -- sin UNION ni vista "
            "hacia tablas de auditoria de M02/M03/M04. La cadena 'M03 -> M04 -> M02 -> M06' es "
            "irreconstruible desde este endpoint."
        ) if 'UNION' not in texto and 'modulo6.auditorias_financieras a' in texto else None


def router_prefix_es_finanzas(texto: str) -> bool:
    return 'prefix="/finanzas"' in texto


class TestSubCasoRepositorioCentralizadoEsDocumentacionAspiracionalNoImplementada:
    def test_el_comentario_de_modulo_origen_describe_un_repositorio_centralizado_que_no_existe(self):
        texto = BASELINE.read_text(encoding='utf-8', errors='ignore')
        pytest.fail(
            "HALLAZGO: el comentario SQL real de la columna modulo_origen promete "
            "'correlacionar... en el repositorio centralizado de auditoria' -- es documentacion "
            "de intencion de diseno, no una tabla ni consulta real (mismo patron que M08 en "
            "RF-93 y que la retencion de 10 anios en TC-M06-21)."
        ) if 'repositorio centralizado de auditoría' in texto else None


class TestSubCasoLaSincronizacionNtpTambienEsSoloUnComentarioHallazgo:
    def test_ntp_no_aparece_en_ningun_codigo_real_de_src(self):
        archivos_con_ntp = [p for p in SRC_DIR.rglob('*.py') if 'ntp' in p.read_text(encoding='utf-8', errors='ignore').lower()]
        pytest.fail(
            f"HALLAZGO: 'ntp' no aparece en ningun archivo .py de src/ (coincidencias: "
            f"{archivos_con_ntp!r}) -- la unica mencion de NTP en todo el backend es el "
            f"comentario de la columna fecha_registro, documentacion sin implementacion activa."
        ) if not archivos_con_ntp else None

    def test_el_comentario_de_fecha_registro_menciona_ntp_solo_como_documentacion(self):
        texto = BASELINE.read_text(encoding='utf-8', errors='ignore')
        assert 'Sincronizado con el reloj NTP del sistema' in texto


class TestSubCasoPrecioMarcadoReemplazadoRegistraReferenciasNoValoresHallazgo:
    def test_el_payload_real_solo_tiene_los_dos_ids_no_los_montos(self):
        texto = PRECIO_USE_CASE.read_text(encoding='utf-8')
        pytest.fail(
            'HALLAZGO: el payload real de PRECIO_MARCADO_REEMPLAZADO es exactamente '
            '{"id_precio_anterior": anterior.id_precio_mercado, "id_precio_nuevo": '
            "precio.id_precio_mercado} -- dos IDENTIFICADORES de fila, no los montos "
            "(precio_unitario) del precio anterior y el nuevo. Para obtener los valores hay que "
            "resolver esos IDs contra precios_mercado por fuera del propio evento."
        ) if 'id_precio_anterior": anterior.id_precio_mercado, "id_precio_nuevo": precio.id_precio_mercado' in texto else None

    def test_se_emite_solo_si_la_nueva_vigencia_es_posterior_o_igual_a_la_anterior(self):
        texto = PRECIO_USE_CASE.read_text(encoding='utf-8')
        assert 'if anterior is not None and s.fecha_vigencia >= anterior.fecha_vigencia' in texto


class TestSubCasoRendimientoNoVerificablePorInspeccionEstaticaPendiente:
    def test_las_metricas_de_carga_de_la_ficha_requieren_infraestructura_real_no_simulada(self):
        """Siguiendo la convencion de TC-M06-G12 (RF-93): el rendimiento con volumenes reales
        (900/1.000/1.200 eventos/min, 1M/10M de registros) no se puede verificar con pruebas
        unitarias ni mocks sin fabricar un resultado ficticio. Se marca explicitamente como
        PENDIENTE de una ronda de carga real (JMeter/k6 + EXPLAIN) contra TEST/DEV."""
        pytest.fail(
            "PENDIENTE (no es un hallazgo de codigo, es una limitacion de este metodo de prueba): "
            "la verificacion de 900/1.000/1.200 eventos por minuto y de 1M/10M de registros "
            "requiere una prueba de carga real contra una base de datos viva -- no se simula "
            "aqui con mocks porque el resultado no tendria ningun valor probatorio real."
        )
