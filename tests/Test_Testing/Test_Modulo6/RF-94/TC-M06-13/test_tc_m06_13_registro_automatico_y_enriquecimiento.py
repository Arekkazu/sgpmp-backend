"""
TC-M06-13 (RF-94 CA-1, CA-12, Fases 1-3 y 5, CU-01) - "Registro automático de
eventos del catálogo y enriquecimiento."

Construido 2026-11-07 contra el código real de RF-94. Primera ronda, código
nunca antes probado (implementado 2026-11-04/05).

Código bajo prueba:
    src/financial_valuation/domain/entities/contabilidad.py (EventoAuditoria)
    src/financial_valuation/infrastructure/repositories/auditoria_financiera_repository.py (registrar)
    src/financial_valuation/infrastructure/routers/m06_router.py (GET /finanzas/auditoria)
    alembic/baseline/esquema_baseline.sql (CREATE TABLE modulo6.auditorias_financieras + comentarios)

HALLAZGO PRINCIPAL (la discrepancia que la propia ficha ya señala, CONFIRMADA
a favor de la Fase 3): la dataclass real `EventoAuditoria` NO tiene ningún
campo `id_evento`, `timestamp_evento`, `modulo` ni `origen_registro` -- es
estructuralmente imposible que el "emisor" (cualquier caso de uso de M06 que
construye un `EventoAuditoria`) los provea, porque no existen como
parámetros del constructor. Los cuatro se generan SIEMPRE del lado del
repositorio/BD, nunca del emisor:
  - `id_evento` -> `id_auditoria_financiera serial` (PK autogenerada).
  - `timestamp_evento` -> columna `fecha_registro timestamptz DEFAULT now()`.
  - `modulo` -> el INSERT real hardcodea el literal `'M06'` (ver
    `auditoria_financiera_repository.py` línea `'M06'` en la lista de
    VALUES) -- no es un valor que el emisor pueda fijar.
  - `origen_registro` -> el INSERT real hardcodea el literal `'REPOSITORIO'`.
Es decir: la "discrepancia" que la ficha pide confirmar entre la tabla de
Entradas ("obligatorios del emisor") y la Fase 3 ("RF-94 los genera") se
resuelve a favor de la Fase 3 -- la tabla de Entradas está simplemente
equivocada, el emisor JAMÁS puede ni necesita proveer esos 4 campos.

HALLAZGO SECUNDARIO GRAVE (M07 no es un "grupo emisor" de este repositorio):
la ficha (CA-12, Descripción-homologación) da por hecho que RF-94 captura
eventos "de los grupos emisores de M06 y de M07" en un repositorio común.
Esto es falso: "M07" en este backend es el módulo `accounting_integration`
(integración contable externa / AAEF-SIGCON), y tiene su PROPIA tabla de
auditoría completamente separada, `modulo7.auditoria_peticiones`, con sus
propios triggers (`fn_tgr_m07_01_auditoria_peticiones_inmutable`,
`fn_tgr_m07_02_auditoria_hash_obligatorio`) y su propio caso de uso
(`accounting_integration/.../consultar_auditoria_integracion_use_case.py`).
Ningún evento de M07 se escribe jamás en `modulo6.auditorias_financieras`.
La única mención real de M07 en todo `src/financial_valuation/` (grep
exhaustivo) es en `registrar_costo_use_case.py`, y es sobre FACTURACIÓN
("las facturas... viajan... por M07"), nada relacionado con auditoría.
"M06 y M07" comparten únicamente un patrón de diseño de BD (tabla
append-only + hash calculado por trigger), no un repositorio de auditoría.

HALLAZGO (11 campos del "esquema base de RF-10" + 2 adicionales): la
dataclass real `EventoAuditoria` tiene exactamente 12 campos totales
(`tipo_evento, severidad, payload, id_usuario, id_sistema,
id_activo_biologico, id_periodo_contable, id_referencia, monto_afectado,
datos_anteriores, metodo_anterior, metodo_nuevo`), no "11 + 2" = 13. De
estos, `id_activo_biologico` y `id_periodo_contable` son precisamente los
"2 campos adicionales" que la ficha menciona -- pero entonces el "esquema
base" real tiene 10 campos, no 11. La aritmética exacta de la ficha
(11+2=13) no coincide con la implementación real (10+2=12).

Cómo se prueba: pytest de unidad por inspección de la firma real de
`EventoAuditoria`, del cuerpo del INSERT real, y de la ausencia de M07 en
`src/financial_valuation/` (no requiere BD viva: son hechos de código y
esquema).

Como correrlo (Windows necesita el stub de fcntl):
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    $env:SECRET_KEY = "test"
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    python -m pytest <ruta>\\test_tc_m06_13_registro_automatico_y_enriquecimiento.py -v \\
        --html=<ruta>\\resultados\\resultado_TC-M06-13.html --self-contained-html
"""
from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from src.financial_valuation.domain.entities.contabilidad import EventoAuditoria

REPO_ROOT = Path(__file__).resolve().parents[5]
REPOSITORIO = REPO_ROOT / 'src/financial_valuation/infrastructure/repositories/auditoria_financiera_repository.py'
FINANCIAL_VALUATION_DIR = REPO_ROOT / 'src/financial_valuation'
ROUTER = REPO_ROOT / 'src/financial_valuation/infrastructure/routers/m06_router.py'


class TestSubCasoLosCuatroCamposSeGeneranSiemprePorElRepositorioNuncaPorElEmisor:
    def test_eventoauditoria_no_tiene_ningun_campo_id_evento_timestamp_modulo_u_origen(self):
        campos = {f.name for f in dataclasses.fields(EventoAuditoria)}
        prohibidos = {'id_evento', 'timestamp_evento', 'modulo', 'origen_registro'}
        pytest.fail(
            f"HALLAZGO (resuelve la discrepancia de la ficha a favor de la Fase 3): la dataclass "
            f"real EventoAuditoria no tiene ningun campo de {prohibidos} -- es estructuralmente "
            f"imposible que el emisor los provea. Campos reales: {sorted(campos)}."
        ) if not (campos & prohibidos) else None

    def test_el_insert_real_hardcodea_modulo_como_m06_literal(self):
        texto = REPOSITORIO.read_text(encoding='utf-8')
        pytest.fail(
            "HALLAZGO: el INSERT real pasa el literal \"'M06'\" como modulo_origen -- no es un "
            "parametro que el emisor controle ni que pueda variar por evento."
        ) if "'M06'" in texto else None

    def test_el_insert_real_hardcodea_origen_registro_como_repositorio_literal(self):
        texto = REPOSITORIO.read_text(encoding='utf-8')
        pytest.fail(
            "HALLAZGO: el INSERT real pasa el literal 'REPOSITORIO' como origen_registro -- "
            "tampoco es un valor que el emisor controle; solo el proceso de sincronizacion de "
            "respaldo (si existiera, ver TC-M06-20) podria producir otro valor."
        ) if "'REPOSITORIO'" in texto else None


class TestSubCasoM07NoEsUnGrupoEmisorDeEsteRepositorioHallazgoGrave:
    def test_la_unica_mencion_de_m07_en_financial_valuation_es_de_facturas_no_de_auditoria(self):
        """La unica referencia real a M07 en todo src/financial_valuation (grep exhaustivo) esta en
        registrar_costo_use_case.py: describe que las facturas de compra/servicio de terceros
        'viajan... por M07' -- una integracion de FACTURACION (RF-90 / comprobantes), nada que
        tenga que ver con el repositorio de auditoria de RF-94. Ningun EventoAuditoria se envia
        jamas a M07, y ningun evento de M07 llega jamas a modulo6.auditorias_financieras."""
        archivos_con_m07 = [
            p for p in FINANCIAL_VALUATION_DIR.rglob('*.py')
            if 'm07' in p.read_text(encoding='utf-8', errors='ignore').lower()
            or 'modulo7' in p.read_text(encoding='utf-8', errors='ignore').lower()
        ]
        texto_coincidencias = ' | '.join(
            l for p in archivos_con_m07 for l in p.read_text(encoding='utf-8', errors='ignore').splitlines()
            if 'm07' in l.lower() or 'modulo7' in l.lower()
        )
        pytest.fail(
            f"HALLAZGO GRAVE: la unica mencion real de M07 en src/financial_valuation es sobre "
            f"FACTURACION, no auditoria: {texto_coincidencias!r}. RF-94 (modulo6.auditorias_financieras) "
            f"y el audit trail real de M07 (modulo7.auditoria_peticiones, en 'accounting_integration') "
            f"son sistemas TOTALMENTE SEPARADOS -- la ficha asume un repositorio comun para 'los "
            f"grupos emisores de M06 y de M07' que no existe."
        ) if len(archivos_con_m07) == 1 and 'factura' in texto_coincidencias.lower() else None

    def test_m07_tiene_su_propia_tabla_y_triggers_de_auditoria_independientes(self):
        baseline = (REPO_ROOT / 'alembic/baseline/esquema_baseline.sql').read_text(encoding='utf-8', errors='ignore')
        pytest.fail(
            "HALLAZGO: modulo7.auditoria_peticiones existe con sus propios triggers "
            "(fn_tgr_m07_01_auditoria_peticiones_inmutable, fn_tgr_m07_02_auditoria_hash_obligatorio) "
            "-- una infraestructura de auditoria paralela e independiente de "
            "modulo6.auditorias_financieras (RF-94), no un repositorio compartido."
        ) if 'modulo7.auditoria_peticiones' in baseline and 'fn_tgr_m07_01_auditoria_peticiones_inmutable' in baseline else None


class TestSubCasoEsquemaBaseDeEventoauditoriaTieneDoceCamposNoTrece:
    def test_eventoauditoria_tiene_doce_campos_totales(self):
        campos = [f.name for f in dataclasses.fields(EventoAuditoria)]
        pytest.fail(
            f"HALLAZGO: EventoAuditoria tiene {len(campos)} campos reales {campos!r} -- si "
            f"id_activo_biologico e id_periodo_contable son los '2 campos adicionales' de M06 que "
            f"pide la ficha, el 'esquema base de RF-10' real tiene 10 campos, no 11 (10+2=12, no "
            f"11+2=13)."
        ) if len(campos) != 11 else None

    def test_id_activo_biologico_e_id_periodo_contable_si_son_los_dos_campos_adicionales_de_m06(self):
        campos = {f.name for f in dataclasses.fields(EventoAuditoria)}
        assert {'id_activo_biologico', 'id_periodo_contable'} <= campos


class TestSubCasoElEndpointRealDeConsultaEsAuditoriaNoAuditEvents:
    def test_no_existe_ningun_endpoint_post_de_registro_de_eventos(self):
        """La ficha asume POST /api/v1/m06/audit/events -- el registro real nunca pasa por HTTP:
        se invoca internamente (registrar()) desde cada caso de uso de M06, en la misma
        transaccion de la operacion auditada (ver TC-M06-15)."""
        texto = ROUTER.read_text(encoding='utf-8').lower()
        tiene_post_audit = '@router.post' in texto and 'audit' in texto.split('@router.post', 1)[1][:200]
        pytest.fail(
            "HALLAZGO: no existe ningun @router.post relacionado con 'audit' o 'auditoria' -- el "
            "registro de eventos de RF-94 no es un endpoint HTTP, es una llamada interna de "
            "Python (AuditoriaFinancieraRepository.registrar()) desde dentro de cada caso de uso."
        ) if not tiene_post_audit else None

    def test_el_unico_endpoint_real_es_get_finanzas_auditoria(self):
        texto = ROUTER.read_text(encoding='utf-8')
        assert '@router.get("/auditoria"' in texto
        pytest.fail(
            "HALLAZGO: el unico endpoint real es GET /finanzas/auditoria (no /api/v1/m06/audit/events "
            "como asume la ficha) -- y es de SOLO CONSULTA; no existe ningun endpoint de escritura."
        )
