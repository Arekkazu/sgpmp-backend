"""
TC-M04-G120 (RF-71 CA-7/RNF-10/RNF-11/RNF-12, CU-16) - "Auditoría,
inmutabilidad y trazabilidad end-to-end." Grupo existente de RF-71.

RELACIÓN CON TC-M04-G102/G109/G110 (hallazgos ya establecidos): los 7
eventos de RF-71 (INICIADO/COMPLETADO/FALLIDO/ABORTADO/INTERRUMPIDO/
DEGRADACION_DETECTADA/PAUSADO_POR_PRIORIDAD) nunca se emiten desde código
alcanzable (G102); la trazabilidad hacia el dataset de origen está
incompleta porque el dataset_entrenamiento_hash no se verifica contra
ningún dato real (G110(a)).

Código bajo prueba:
    src/prediction/infrastructure/models/evento_auditoria_m04_model.py
    src/prediction/infrastructure/repositories/evento_auditoria_m04_repository.py
    alembic/baseline/esquema_baseline.sql (triggers de inmutabilidad)

HALLAZGO (c) NUEVO: el patrón de "tabla append-only con trigger BEFORE
DELETE OR UPDATE que lanza excepción" SÍ existe en el DDL baseline para
varias tablas de M04 -- `modulo4.ciclos_entrenamientos` (2 triggers:
`...no_delete` y `...inmutabilidad_completados`), `modulo4.datasets`
(`trg_fn_datasets_inmutabilidad`) y, sobre todo, `modulo4.auditorias_predicciones`
(`trg_fn_auditorias_predicciones_inmutabilidad`) -- pero la tabla
REALMENTE USADA por el repositorio Python
(`modulo4.eventos_auditoria_m04`, confirmada en `EventoAuditoriaM04Model.__tablename__`)
NO tiene ningún trigger de este tipo: un grep de todos los triggers sobre
esa tabla en el DDL solo encuentra índices, cero triggers BEFORE
DELETE/UPDATE. La tabla de auditoría que RF-71/RF-69 realmente usa en
producción es la única del módulo sin esa protección a nivel de BD -- la
inmutabilidad depende únicamente de que el repositorio Python no exponga
métodos `actualizar`/`eliminar` (cosa que sí es cierta), no de una
garantía de base de datos.

(a) 7 tipos de evento con timestamp/usuario/tipo_modelo/referencia --
    HALLAZGO: ninguno de los 7 nombres se emite jamás (ver G102); el
    catálogo real (`_PAYLOAD_REQUERIDO`) cubre VERSION_REGISTRADA/
    APROBADA/RECHAZADA/ACTIVADA/DEPRECADA y RETROALIMENTACION_*, no
    ninguno con prefijo REENTRENAMIENTO_ ni DEGRADACION_DETECTADA ni
    PAUSADO_POR_PRIORIDAD.
(b) RNF-10, latencia de registro <= 2s -- NO EVALUABLE: no hay eventos
    de RF-71 que medir.
(c) RNF-11, append-only con intento denegado y registrado -- HALLAZGO:
    ver arriba -- la tabla real no tiene protección de BD, a diferencia
    de otras tablas del mismo módulo que sí la tienen.
(d) RNF-12, trazabilidad versión -> dataset_hash -> registros de entrada
    -- HALLAZGO PARCIAL (ya anticipado por G110(a)): la cadena se rompe
    en `dataset_hash -> registros de entrada`, porque ese hash nunca se
    verifica ni se asocia a ningún dato real recuperable desde este
    backend.
(e) Log injection saneado -- MITIGADO ESTRUCTURALMENTE, SIN SANEAMIENTO
    EXPLÍCITO: `payload_evento` se almacena como JSONB estructurado
    (nunca se concatena a una línea de texto de log), lo que mitiga el
    ataque clásico de inyección de líneas de log falsas -- pero no hay
    ninguna función de saneamiento explícita de CRLF en
    `evento_auditoria_m04_repository.py`.

Cómo se prueba: grep exhaustivo del DDL para localizar todos los
triggers de inmutabilidad de M04 y confirmar sobre qué tablas actúan +
inspección del repositorio real.

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
    def test_tipo_de_evento_no_esta_en_el_catalogo_real_de_payload_requerido(self, tipo_evento):
        archivo = REPO_ROOT / 'src/prediction/infrastructure/repositories/evento_auditoria_m04_repository.py'
        texto = archivo.read_text(encoding='utf-8')
        pytest.fail(
            f"HALLAZGO (a): '{tipo_evento}' no aparece en _PAYLOAD_REQUERIDO ni en ningun otro "
            f"punto de evento_auditoria_m04_repository.py -- el catalogo real de M04 no incluye "
            f"ningun evento de RF-71 (confirma G102)."
        ) if tipo_evento not in texto else None


class TestSubCasoCTablaRealSinTriggerDeInmutabilidad:
    def test_eventos_auditoria_m04_no_tiene_ningun_trigger_before_delete_o_update(self):
        bloque_triggers_sobre_tabla = [
            l for l in DDL.splitlines()
            if 'ON modulo4.eventos_auditoria_m04' in l and 'CREATE TRIGGER' in l
        ]
        pytest.fail(
            f"HALLAZGO (c): CREATE TRIGGER ... ON modulo4.eventos_auditoria_m04 no aparece "
            f"ninguna vez en el DDL baseline (solo indices) -- la tabla real que usa el "
            f"repositorio Python no tiene ninguna proteccion de BD contra UPDATE/DELETE, a "
            f"diferencia de auditorias_predicciones, ciclos_entrenamientos y datasets, que SI "
            f"tienen triggers 'BEFORE DELETE OR UPDATE ... RAISE EXCEPTION'."
        ) if not bloque_triggers_sobre_tabla else None

    def test_otras_tablas_del_mismo_modulo_si_tienen_el_patron_de_proteccion(self):
        assert 'CREATE TRIGGER trg_auditorias_predicciones_inmutabilidad BEFORE DELETE OR UPDATE ON modulo4.auditorias_predicciones' in DDL

    def test_repositorio_python_no_expone_metodos_de_mutacion(self):
        archivo = REPO_ROOT / 'src/prediction/infrastructure/repositories/evento_auditoria_m04_repository.py'
        texto = archivo.read_text(encoding='utf-8')
        assert 'def actualizar' not in texto and 'def eliminar' not in texto


class TestSubCasoELogInjectionMitigadoPorEstructuraNoPorSaneamiento:
    def test_payload_se_almacena_como_jsonb_no_como_texto_concatenado(self):
        archivo_modelo = REPO_ROOT / 'src/prediction/infrastructure/models/evento_auditoria_m04_model.py'
        texto = archivo_modelo.read_text(encoding='utf-8')
        assert 'JSONB' in texto

    def test_no_hay_ninguna_funcion_explicita_de_saneamiento_de_crlf(self):
        archivo = REPO_ROOT / 'src/prediction/infrastructure/repositories/evento_auditoria_m04_repository.py'
        texto = archivo.read_text(encoding='utf-8')
        pytest.fail(
            "HALLAZGO (e), matiz: no hay ninguna funcion que sanee explicitamente CRLF ni "
            "secuencias de escape en payload_evento -- la proteccion real viene de que se "
            "almacena como JSONB estructurado (nunca se escribe a un archivo de log de texto "
            "plano), no de un saneamiento deliberado."
        ) if 'replace(' not in texto.lower() and 'sanitiz' not in texto.lower() else None
