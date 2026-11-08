"""
TC-M06-16 (RF-94 FA-1, Fase 2.1, 2.3 y 2.4, CU-03) - "Validación del evento
recibido."

Construido 2026-11-07 contra el código real de RF-94. Primera ronda. Se
apoya en la evidencia ya reunida en TC-M06-13 (no hay endpoint de
recepción) y TC-M06-15 (la auditoría es síncrona y bloqueante).

Código bajo prueba:
    src/financial_valuation/domain/entities/contabilidad.py (EventoAuditoria, sin validación)
    src/financial_valuation/infrastructure/repositories/auditoria_financiera_repository.py (registrar, sin validación)

HALLAZGO PRINCIPAL (la premisa entera de "evento recibido" no aplica): la
ficha asume que RF-94 "recibe" eventos de un emisor externo y debe
VALIDARLOS (rechazando `tipo_evento` fuera de catálogo, `payload_evento`
vacío o `id_referencia` nulo/malformado) antes de persistir. Esto no
corresponde a la arquitectura real: como ya se confirmó en TC-M06-13, no
existe ningún endpoint HTTP de recepción -- `EventoAuditoria` se construye
directamente en Python, dentro del mismo proceso, por el propio código de
M06 (nunca por un tercero "emisor" que pueda enviar datos arbitrarios o
mal formados). No hay una frontera de confianza que validar.

HALLAZGO (cero validación de aplicación): el método real `registrar()` NO
tiene ningún código de validación -- ni un `if` que compruebe
`evento.tipo_evento`, ni uno para `evento.payload`, ni uno para
`evento.id_referencia`. Simplemente serializa y ejecuta el INSERT. La
única comprobación que podría "rechazar" un `tipo_evento` inválido es el
`CAST(:tipo AS modulo6.enum_auditoria_financiera_tipo_evento)` de
PostgreSQL -- si el valor no está en el ENUM de BD, Postgres lanza una
excepción de tipo de dato (`invalid input value for enum`), que NO es un
rechazo silencioso ni un flujo de error controlado: es una excepción dura
que (según TC-M06-15) provoca el mismo `rollback()` que revierte también la
operación de negocio principal.

HALLAZGO (no existe "LOG TÉCNICO" como concepto separado del repositorio):
no existe en todo `financial_valuation` ningún logger ni registro
específico para "eventos rechazados de auditoría" -- los únicos `logger =
logging.getLogger(__name__)` del módulo están en casos de uso de
negocio (cierre, provisiones M05, eventos M02), para sus propios errores de
negocio, no para eventos de auditoría inválidos. La distinción
"log técnico vs. repositorio" que la ficha exige como esencial no tiene
ninguna implementación real: simplemente no hay una ruta de código que
decida "esto no es válido, lo mando al log en vez de al repositorio".

HALLAZGO (no existe alerta al Administrador): grep exhaustivo de
"alerta.*administrador" / "notificar.*administrador" en `financial_valuation`
no encuentra ningún resultado -- no hay ningún mecanismo que avise al
Administrador ante un evento inválido.

HALLAZGO (no existe la distinción "no interrumpe el proceso del emisor"):
de hecho es lo opuesto, ya confirmado en TC-M06-15 -- cualquier fallo en
`registrar()` (incluida una excepción de CAST por un tipo_evento inválido)
SÍ interrumpe/revierte el proceso que lo invoca, porque comparten la misma
transacción y el mismo bloque try/except/rollback.

Cómo se prueba: pytest de unidad sobre el código real de `registrar()` y
`EventoAuditoria` (ausencia de validación), más grep de los mecanismos que
la ficha exige (log técnico separado, alerta al Administrador) -- no
requiere BD viva.

Como correrlo (Windows necesita el stub de fcntl):
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    $env:SECRET_KEY = "test"
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    python -m pytest <ruta>\\test_tc_m06_16_validacion_evento_recibido.py -v \\
        --html=<ruta>\\resultados\\resultado_TC-M06-16.html --self-contained-html
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[5]
REPOSITORIO = REPO_ROOT / 'src/financial_valuation/infrastructure/repositories/auditoria_financiera_repository.py'
FINANCIAL_VALUATION_DIR = REPO_ROOT / 'src/financial_valuation'


class TestSubCasoLaPremisaDeEventoRecibidoDeUnEmisorExternoNoAplica:
    def test_registrar_no_valida_tipo_evento_payload_ni_id_referencia(self):
        texto = REPOSITORIO.read_text(encoding='utf-8')
        cuerpo_registrar = texto.split('def registrar(')[1].split('def consultar(')[0]
        tiene_validacion = 'raise' in cuerpo_registrar or 'if evento.' in cuerpo_registrar
        pytest.fail(
            "HALLAZGO: el metodo real registrar() no contiene ningun 'if evento....' ni 'raise' -- "
            "no valida tipo_evento, payload ni id_referencia antes de insertar. La unica barrera "
            "posible es el CAST a ENUM de Postgres, una excepcion dura, no un rechazo controlado."
        ) if not tiene_validacion else None

    def test_un_tipo_evento_invalido_solo_se_detectaria_por_cast_de_postgres_no_por_validacion_python(self):
        texto = REPOSITORIO.read_text(encoding='utf-8')
        assert 'CAST(:tipo AS modulo6.enum_auditoria_financiera_tipo_evento)' in texto


class TestSubCasoNoExisteNingunLogTecnicoSeparadoDelRepositorioHallazgo:
    def test_no_hay_ningun_logger_dedicado_a_eventos_de_auditoria_rechazados(self):
        archivos_con_logger = [p for p in FINANCIAL_VALUATION_DIR.rglob('*.py')
                               if 'logging.getLogger' in p.read_text(encoding='utf-8', errors='ignore')]
        nombres = [p.name for p in archivos_con_logger]
        pytest.fail(
            f"HALLAZGO: los unicos loggers de financial_valuation ({nombres!r}) son para errores "
            f"de negocio de casos de uso especificos (cierre, provisiones M05, eventos M02) -- "
            f"ninguno existe para 'eventos de auditoria invalidos'. No hay distincion real entre "
            f"'log tecnico' y 'repositorio' para RF-94: simplemente no hay ninguna ruta de codigo "
            f"que decida rechazar un evento hacia un log en vez de insertarlo en la BD."
        ) if archivos_con_logger else None


class TestSubCasoNoExisteNingunaAlertaAlAdministradorHallazgo:
    def test_no_existe_ningun_mecanismo_de_alerta_al_administrador_por_evento_invalido(self):
        coincidencias = [
            str(p.relative_to(REPO_ROOT)) for p in FINANCIAL_VALUATION_DIR.rglob('*.py')
            for patron in ('alerta_administrador', 'notificar_administrador', 'AlertaAdministrador')
            if patron.lower() in p.read_text(encoding='utf-8', errors='ignore').lower()
        ]
        pytest.fail(
            "HALLAZGO: no existe ningun mecanismo de alerta al Administrador ante un evento de "
            "auditoria invalido en todo financial_valuation (grep exhaustivo, cero resultados)."
        ) if not coincidencias else None


class TestSubCasoElProcesoDelEmisorSiSeInterrumpeLoOpuestoDeLaFicha:
    def test_una_falla_de_cast_comparte_la_misma_transaccion_que_la_operacion_principal(self):
        """Ver TC-M06-15: registrar() se invoca dentro del mismo try/commit/except-rollback que
        la operacion de negocio. Una excepcion de CAST (tipo_evento invalido) no es distinta de
        cualquier otra excepcion de auditoria: ambas revierten y propagan."""
        texto = (REPO_ROOT / 'src/financial_valuation/application/use_cases/reportes/'
                 'generar_estado_resultados_use_case.py').read_text(encoding='utf-8')
        pytest.fail(
            "HALLAZGO: self.auditoria.registrar(...) esta dentro del mismo bloque try que "
            "self.db.commit() con un 'except Exception: self.db.rollback(); raise' -- cualquier "
            "excepcion de validacion de evento (incluida un CAST invalido) SI interrumpe/revierte "
            "el proceso del emisor, al contrario de lo que pide la ficha (Restriccion 4)."
        ) if 'self.auditoria.registrar(' in texto and 'self.db.rollback()' in texto else None
