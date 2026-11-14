"""
TC-M06-G83 (RF-94 CA-1, CA-12, Fases 1-3 y 5, CU-01) - "Registro automático de
eventos del catálogo y enriquecimiento."

Construido 2026-11-07 contra el código real de RF-94. Primera ronda, código
nunca antes probado (implementado 2026-11-04/05).

Código bajo prueba:
    src/financial_valuation/domain/entities/contabilidad.py (EventoAuditoria)
    src/financial_valuation/infrastructure/repositories/auditoria_financiera_repository.py (registrar)
    src/financial_valuation/infrastructure/routers/m06_router.py (GET /finanzas/auditoria)
    alembic/baseline/esquema_baseline.sql (CREATE TABLE modulo6.auditorias_financieras + comentarios)

RECLASIFICADO 2026-11-13: todos los hallazgos de este archivo son diferencias con
la ficha (nombres, conteos, endpoints asumidos), no defectos de código -- se
reescriben como `assert` que confirman el comportamiento real.

HALLAZGO PRINCIPAL -- NO ES UN DEFECTO (la discrepancia que la propia ficha ya
señala, CONFIRMADA a favor de la Fase 3): la dataclass real `EventoAuditoria` NO tiene ningún
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
    python -m pytest <ruta>\\test_tc_m06_g83_registro_automatico_y_enriquecimiento.py -v \\
        --html=<ruta>\\resultados\\resultado_TC-M06-G83.html --self-contained-html
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


class TestSubCasoLosCuatroCamposSeGeneranSiemprePorElRepositorioNuncaPorElEmisorDocumentacion:
    def test_eventoauditoria_no_tiene_ningun_campo_id_evento_timestamp_modulo_u_origen(self):
        """No es un defecto: resuelve una discrepancia que la propia ficha anticipaba a favor
        de la Fase 3. Es estructuralmente imposible que el emisor provea estos 4 campos."""
        campos = {f.name for f in dataclasses.fields(EventoAuditoria)}
        prohibidos = {'id_evento', 'timestamp_evento', 'modulo', 'origen_registro'}
        assert not (campos & prohibidos)

    def test_el_insert_real_hardcodea_modulo_como_m06_literal(self):
        """No es un defecto en si mismo (ver el hallazgo relacionado y abierto en TC-M06-G94
        sobre la falta de repositorio centralizado): documenta que modulo_origen nunca lo
        controla el emisor."""
        texto = REPOSITORIO.read_text(encoding='utf-8')
        assert "'M06'" in texto

    def test_el_insert_real_hardcodea_origen_registro_como_repositorio_literal(self):
        """No es un defecto en si mismo (ver el hallazgo relacionado y abierto en TC-M06-G90
        sobre la ausencia de fallback): documenta que origen_registro nunca lo controla el
        emisor."""
        texto = REPOSITORIO.read_text(encoding='utf-8')
        assert "'REPOSITORIO'" in texto


class TestSubCasoM07NoEsUnGrupoEmisorDeEsteRepositorioDocumentacion:
    def test_ninguna_mencion_de_m07_en_financial_valuation_esta_en_contexto_de_auditoria(self):
        """No es un defecto: la ficha asume un repositorio comun para 'los grupos emisores de
        M06 y de M07' que no existe. Las menciones reales a M07 en src/financial_valuation
        (facturacion en registrar_costo_use_case.py, un comentario de formato en
        m06_router.py) nunca estan en contexto de auditoria. RF-94
        (modulo6.auditorias_financieras) y el audit trail real de M07
        (modulo7.auditoria_peticiones, en accounting_integration) son sistemas separados."""
        lineas_m07 = [
            l for p in FINANCIAL_VALUATION_DIR.rglob('*.py')
            for l in p.read_text(encoding='utf-8', errors='ignore').splitlines()
            if 'm07' in l.lower() or 'modulo7' in l.lower()
        ]
        assert lineas_m07  # si existe al menos una mencion real
        assert not any('audit' in l.lower() for l in lineas_m07)

    def test_m07_tiene_su_propia_tabla_y_triggers_de_auditoria_independientes(self):
        """No es un defecto: modulo7.auditoria_peticiones es una infraestructura de auditoria
        paralela e independiente de modulo6.auditorias_financieras, no un repositorio
        compartido como asume la ficha."""
        baseline = (REPO_ROOT / 'alembic/baseline/esquema_baseline.sql').read_text(encoding='utf-8', errors='ignore')
        assert 'modulo7.auditoria_peticiones' in baseline
        assert 'fn_tgr_m07_01_auditoria_peticiones_inmutable' in baseline


class TestSubCasoEsquemaBaseDeEventoauditoriaDocumentacion:
    def test_eventoauditoria_tiene_doce_campos_totales_no_trece(self):
        """No es un defecto: si id_activo_biologico e id_periodo_contable son los '2 campos
        adicionales' de M06 que pide la ficha, el 'esquema base' real tiene 10 campos, no 11
        (10+2=12, no 11+2=13). Diferencia aritmetica con la ficha, no una funcionalidad
        faltante."""
        campos = [f.name for f in dataclasses.fields(EventoAuditoria)]
        assert len(campos) == 12

    def test_id_activo_biologico_e_id_periodo_contable_si_son_los_dos_campos_adicionales_de_m06(self):
        campos = {f.name for f in dataclasses.fields(EventoAuditoria)}
        assert {'id_activo_biologico', 'id_periodo_contable'} <= campos


class TestSubCasoElEndpointRealDeConsultaEsAuditoriaNoAuditEventsDocumentacion:
    def test_no_existe_ningun_endpoint_post_de_registro_de_eventos(self):
        """No es un defecto: la ficha asume POST /api/v1/m06/audit/events -- el registro real
        nunca pasa por HTTP, se invoca internamente (registrar()) desde cada caso de uso de
        M06, en la misma transaccion de la operacion auditada (ver TC-M06-G85)."""
        texto = ROUTER.read_text(encoding='utf-8').lower()
        tiene_post_audit = '@router.post' in texto and 'audit' in texto.split('@router.post', 1)[1][:200]
        assert not tiene_post_audit

    def test_el_unico_endpoint_real_es_get_finanzas_auditoria(self):
        """No es un defecto: el unico endpoint real es GET /finanzas/auditoria (no
        /api/v1/m06/audit/events como asume la ficha), y es de solo consulta."""
        texto = ROUTER.read_text(encoding='utf-8')
        assert '@router.get("/auditoria"' in texto
