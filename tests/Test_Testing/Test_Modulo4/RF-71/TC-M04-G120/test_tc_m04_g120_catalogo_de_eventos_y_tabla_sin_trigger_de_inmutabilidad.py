"""
TC-M04-G120 (RF-71 v2.0 CA-7/RNF-10/RNF-11/RNF-12/RFC-009, CU-16) -
"Auditoría, inmutabilidad y trazabilidad end-to-end." La v2.0 añade
modo_generacion a los campos de cada evento y pide verificar cobertura de
eventos propios de calibración/deriva poblacional.

REEJECUTADO 2026-10-30 CONTRA CÓDIGO POST-MERGE. RELACIÓN CON
TC-M04-G102/G109/G110 (hallazgos ya establecidos, matizados): los 7
nombres de evento ESPECÍFICOS DEL CICLO DE VIDA DE REENTRENAMIENTO que
pide la ficha siguen sin existir -- pero la premisa general "los eventos
de RF-71 nunca se emiten desde código alcanzable" queda MATIZADA/
INVERTIDA: `RegistrarVersionModeloUseCase` (el único tramo real de RF-71
alcanzable por HTTP, ver G102) SÍ auditada cada registro con eventos
reales (`VERSION_REGISTRADA`, `VERSION_APROBADA`/`VERSION_RECHAZADA`,
`INTENTO_CARGA_MODELO_EXTERNO`, `HASH_INVALIDO_DETECTADO`), y todo el
módulo `src/prediction/` tiene un sistema de auditoría M04 extenso (más
de 15 tipos de evento reales, incluyendo `CATALOGO_PATOLOGIA_*`,
`CONFIGURACION_MOTOR_CAMBIADA`, `DISTRIBUCION_POSPUESTA`,
`RETROALIMENTACION_REGISTRADA`, `NOTAS_REGISTRADAS`,
`TIMESTAMP_CORREGIDO`). Ninguno de esos nombres reales coincide con los 7
de la ficha (que son específicos del CICLO DE UN PROCESO DE
REENTRENAMIENTO que no existe), así que (a) sigue siendo un HALLAZGO
VIGENTE en su forma literal -- pero afirmar que "RF-71 nunca audita
nada" ya no sería preciso.

Código bajo prueba:
    src/prediction/application/use_cases/versiones_modelo/registrar_version_modelo_use_case.py
    src/prediction/infrastructure/models/evento_auditoria_m04_model.py
    src/prediction/infrastructure/repositories/evento_auditoria_m04_repository.py
    alembic/baseline/esquema_baseline.sql

(a) 7 tipos de evento con modo_generacion -- HALLAZGO VIGENTE EN SU FORMA
    LITERAL, MATIZADO: ninguno de los 7 nombres específicos de
    reentrenamiento (`REENTRENAMIENTO_INICIADO`, etc.) se emite jamás --
    pero SÍ se emiten eventos reales para el registro de una versión
    (`VERSION_REGISTRADA`/`VERSION_APROBADA`/`VERSION_RECHAZADA`). Y como
    `modo_generacion` no existe en ningún lado, tampoco podría incluirse
    en el payload de NINGÚN evento, ni los 7 de la ficha ni los reales.
(b) Cobertura de eventos de calibración/deriva poblacional -- HALLAZGO:
    ninguno de esos nombres (inicio/cierre de calibración, vencimiento,
    deriva sostenida) existe en absoluto, ni siquiera como valor de enum
    en el DDL -- a diferencia de los 7 de CA-7, que al menos existen como
    enum huérfano, aquí no hay ni eso.
(c) RNF-10, latencia <= 2s -- NO EVALUABLE: no hay eventos de RF-71 que
    medir.
(d) RNF-11, append-only -- HALLAZGO VIGENTE: la tabla real
    (`eventos_auditoria_m04`) no tiene ningún trigger `BEFORE DELETE OR
    UPDATE`, a diferencia de otras tablas del mismo módulo que sí lo
    tienen.
(e) RNF-12, trazabilidad -- HALLAZGO PARCIAL: la cadena se rompe en
    dataset_hash -> registros de entrada.
(f) Log injection -- MITIGADO ESTRUCTURALMENTE (JSONB), sin saneamiento
    explícito de CRLF.

Cómo se prueba: grep exhaustivo del DDL + inspección del repositorio
real.

Como correrlo:
    python -m pytest <ruta>\\test_tc_m04_g120_catalogo_de_eventos_y_tabla_sin_trigger_de_inmutabilidad.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M04-G120.html --self-contained-html
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[5]
DDL = (REPO_ROOT / 'alembic/baseline/esquema_baseline.sql').read_text(encoding='utf-8', errors='ignore')


class TestSubCasoACatalogoDeEventosRf71NoExiste:
    @pytest.mark.parametrize('tipo_evento', [
        'REENTRENAMIENTO_INICIADO', 'REENTRENAMIENTO_COMPLETADO', 'REENTRENAMIENTO_FALLIDO',
        'REENTRENAMIENTO_ABORTADO', 'REENTRENAMIENTO_INTERRUMPIDO', 'DEGRADACION_DETECTADA',
        'PAUSADO_POR_PRIORIDAD',
    ])
    def test_tipo_de_evento_no_esta_en_el_catalogo_real(self, tipo_evento):
        archivo = REPO_ROOT / 'src/prediction/infrastructure/repositories/evento_auditoria_m04_repository.py'
        texto = archivo.read_text(encoding='utf-8')
        pytest.fail(
            f"HALLAZGO (a) VIGENTE: '{tipo_evento}' (especifico del ciclo de reentrenamiento) "
            f"no aparece en el catalogo real de M04."
        ) if tipo_evento not in texto else None


class TestSubCasoAMatizRegistrarVersionSiAuditaConEventosReales:
    @pytest.mark.parametrize('tipo_evento', [
        'VERSION_REGISTRADA', 'VERSION_APROBADA', 'VERSION_RECHAZADA',
        'INTENTO_CARGA_MODELO_EXTERNO', 'HASH_INVALIDO_DETECTADO',
    ])
    def test_evento_real_de_registro_si_existe_y_se_emite(self, tipo_evento):
        archivo = REPO_ROOT / 'src/prediction/application/use_cases/versiones_modelo/registrar_version_modelo_use_case.py'
        texto = archivo.read_text(encoding='utf-8')
        pytest.fail(
            f"MATIZ: '{tipo_evento}' SI se emite desde registrar_version_modelo_use_case.py "
            f"(via self._auditoria_repo.registrar(tipo_evento=...)) -- RF-71/RF-69 SI auditan el "
            f"registro de versiones con eventos reales, aunque ninguno coincida con los 7 "
            f"nombres especificos de reentrenamiento que pide la ficha."
        ) if tipo_evento in texto else None


class TestSubCasoBEventosDeCalibracionNiSiquieraComoEnum:
    @pytest.mark.parametrize('termino', [
        'CALIBRACION_INICIADA', 'CALIBRACION_COMPLETADA', 'VENCIMIENTO_CALIBRACION', 'DERIVA_SOSTENIDA',
    ])
    def test_evento_de_calibracion_no_existe_ni_en_el_ddl(self, termino):
        pytest.fail(
            f"HALLAZGO (b): '{termino}' no existe ni en src/ ni en el DDL baseline -- a "
            f"diferencia del catalogo de CA-7, que al menos existe como enum huerfano."
        ) if termino not in DDL else None


class TestSubCasoDTablaRealSinTriggerDeInmutabilidad:
    def test_eventos_auditoria_m04_no_tiene_ningun_trigger_before_delete_o_update(self):
        bloque_triggers_sobre_tabla = [
            l for l in DDL.splitlines()
            if 'ON modulo4.eventos_auditoria_m04' in l and 'CREATE TRIGGER' in l
        ]
        pytest.fail(
            "HALLAZGO (d): CREATE TRIGGER ... ON modulo4.eventos_auditoria_m04 no aparece "
            "ninguna vez en el DDL baseline (solo indices)."
        ) if not bloque_triggers_sobre_tabla else None

    def test_repositorio_python_no_expone_metodos_de_mutacion(self):
        archivo = REPO_ROOT / 'src/prediction/infrastructure/repositories/evento_auditoria_m04_repository.py'
        texto = archivo.read_text(encoding='utf-8')
        assert 'def actualizar' not in texto and 'def eliminar' not in texto


class TestSubCasoFLogInjectionMitigadoPorEstructura:
    def test_payload_se_almacena_como_jsonb(self):
        archivo_modelo = REPO_ROOT / 'src/prediction/infrastructure/models/evento_auditoria_m04_model.py'
        texto = archivo_modelo.read_text(encoding='utf-8')
        assert 'JSONB' in texto

    def test_no_hay_funcion_explicita_de_saneamiento_de_crlf(self):
        archivo = REPO_ROOT / 'src/prediction/infrastructure/repositories/evento_auditoria_m04_repository.py'
        texto = archivo.read_text(encoding='utf-8')
        pytest.fail(
            "HALLAZGO (f), matiz: no hay ninguna funcion que sanee explicitamente CRLF -- la "
            "proteccion real viene de almacenar JSONB estructurado, no de un saneamiento "
            "deliberado."
        ) if 'replace(' not in texto.lower() and 'sanitiz' not in texto.lower() else None
