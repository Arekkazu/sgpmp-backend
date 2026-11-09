"""
TC-M06-G89 (RF-94 RNF-04, CA-5, Fase 4, FA-5, Fase 6, CU-05) - "Hash de
integridad y su fallo."

Construido 2026-11-07 contra el código real de RF-94. Primera ronda. Se
apoya en la evidencia ya reunida en TC-M06-G87 (orden de ejecución de
triggers BEFORE INSERT, marcador de 64 ceros).

Código bajo prueba:
    alembic/baseline/esquema_baseline.sql (CREATE FUNCTION modulo6.calcular_hash_auditoria,
        CREATE TRIGGER trg_hash_auditoria, CREATE FUNCTION fn_tgr_m06_13_inmutabilidad_auditoria)
    src/financial_valuation/infrastructure/repositories/auditoria_financiera_repository.py (_MARCADOR_HASH)

HALLAZGO PRINCIPAL (matiza la ficha: el hash SÍ es sobre "todo", calculado
por BD, con orden bien definido -- contradice la nota "BLOQUEANTE" de la
propia ficha): el hash real se calcula en un trigger de PostgreSQL,
`modulo6.calcular_hash_auditoria()` (disparado por `trg_hash_auditoria
BEFORE INSERT ON modulo6.auditorias_financieras`), no en Python:
```sql
NEW.hash_integridad := encode(digest(
  (SELECT string_agg(key || '=' || value, '&' ORDER BY key)
   FROM jsonb_each_text(to_jsonb(NEW) - 'hash_integridad')),
  'sha256'), 'hex');
```
Esto hashea TODAS las columnas de la fila (no solo el payload), serializadas
como `clave=valor` concatenadas con `&`, en un orden **determinista**:
alfabético por nombre de columna (`ORDER BY key`). La nota "BLOQUEANTE" de
la propia ficha ("sin un criterio fijo, dos recálculos del mismo registro
dan hashes distintos") es FALSA en este caso: el orden SÍ está fijo por
diseño de BD -- cualquier recálculo con los mismos valores de columna
produce exactamente el mismo hash, siempre. Esto cubre de más lo que pide
CA-5 (incluye `timestamp_evento`/`fecha_registro` e `id_evento` porque son
columnas de la fila igual que el payload), no de menos.

HALLAZGO (detectar alteración es teóricamente correcto pero prácticamente
imposible de observar, porque la alteración está bloqueada antes): el
trigger de hash es `BEFORE INSERT` únicamente -- no existe un trigger
equivalente `BEFORE UPDATE` que recalcule el hash tras una modificación.
Esto no es un hueco de seguridad: como ya se confirmó en TC-M06-G87/21, el
trigger `fn_tgr_m06_13_inmutabilidad_auditoria` BLOQUEA cualquier UPDATE o
DELETE sobre `modulo6.auditorias_financieras` con una excepción dura, para
TODOS los roles. Es decir, la alteración nunca llega a ocurrir -- "detectar
la alteración recalculando el hash" es un mecanismo que nunca necesita
dispararse en la práctica, porque hay una barrera más fuerte (inmutabilidad
total) un paso antes.

HALLAZGO GRAVE (HASH_CALCULO_FALLIDO no existe en absoluto): grep
exhaustivo de "HASH_CALCULO_FALLIDO" en todo `src/` y `alembic/` --
CERO resultados. El escenario completo de "fallback cuando el cálculo del
hash falla" que pide la ficha no tiene ninguna implementación: no hay
ningún valor especial, ningún except, ningún camino alterno. Si
`calcular_hash_auditoria()` fallara por cualquier motivo (p. ej. la función
`digest()` no disponible por falta de la extensión `pgcrypto`), el INSERT
completo fallaría con una excepción de Postgres sin controlar -- que
(según TC-M06-G85/16) también revierte la operación de negocio principal.

HALLAZGO (conexión con TC-M06-G87, no se repite aquí en detalle): el
truco del marcador de 64 ceros (`_MARCADOR_HASH`) existe precisamente
porque OTRO trigger (`fn_tgr_m06_27_tipo_actor_auditoria`, que corre antes
por orden alfabético "tgr" < "trg") exige que `hash_integridad` ya tenga 64
caracteres ANTES de que `trg_hash_auditoria` calcule el valor real.

Cómo se prueba: pytest de unidad por inspección del trigger real de hash y
del trigger de inmutabilidad -- no requiere BD viva (el cálculo de SHA-256
sobre datos reales se puede replicar en Python con `hashlib` para
confirmar coherencia del algoritmo, sin necesitar Postgres).

Como correrlo (Windows necesita el stub de fcntl):
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    $env:SECRET_KEY = "test"
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    python -m pytest <ruta>\\test_tc_m06_g89_hash_integridad_y_fallo.py -v \\
        --html=<ruta>\\resultados\\resultado_TC-M06-G89.html --self-contained-html
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[5]
BASELINE = REPO_ROOT / 'alembic/baseline/esquema_baseline.sql'
REPOSITORIO = REPO_ROOT / 'src/financial_valuation/infrastructure/repositories/auditoria_financiera_repository.py'


def _cuerpo_funcion(texto: str, nombre_funcion: str) -> str:
    return texto.split(f'{nombre_funcion}() RETURNS trigger')[1].split('$$;')[0]


class TestSubCasoElHashEsSobreTodasLasColumnasConOrdenDeterministaNoBloqueante:
    def test_el_trigger_real_hashea_to_jsonb_new_menos_hash_integridad(self):
        texto = BASELINE.read_text(encoding='utf-8', errors='ignore')
        cuerpo = _cuerpo_funcion(texto, 'modulo6.calcular_hash_auditoria')
        assert "to_jsonb(NEW) - 'hash_integridad'" in cuerpo
        assert "ORDER BY key" in cuerpo

    def test_el_orden_alfabetico_por_clave_es_determinista_contradice_la_nota_bloqueante_de_la_ficha(self):
        fila = {"tipo_evento": "COSTO_REGISTRADO", "id_usuario": "7", "severidad": "INFO"}
        agregado1 = "&".join(f"{k}={v}" for k, v in sorted(fila.items()))
        agregado2 = "&".join(f"{k}={v}" for k, v in sorted(dict(reversed(list(fila.items()))).items()))
        hash1 = hashlib.sha256(agregado1.encode()).hexdigest()
        hash2 = hashlib.sha256(agregado2.encode()).hexdigest()
        pytest.fail(
            f"HALLAZGO: ordenando las mismas columnas alfabeticamente (ORDER BY key, como hace "
            f"el trigger real) el hash es siempre identico sin importar el orden de entrada "
            f"({hash1 == hash2}) -- el orden de serializacion SI esta bien definido; la nota "
            f"'BLOQUEANTE' de la ficha sobre un 'criterio fijo' indefinido es incorrecta para "
            f"este trigger."
        ) if hash1 == hash2 else None

    def test_el_hash_cubre_mas_que_solo_el_payload_incluye_todas_las_columnas_de_la_fila(self):
        texto = BASELINE.read_text(encoding='utf-8', errors='ignore')
        cuerpo = _cuerpo_funcion(texto, 'modulo6.calcular_hash_auditoria')
        pytest.fail(
            "HALLAZGO: el trigger real hashea TODAS las columnas de la fila (to_jsonb(NEW) menos "
            "hash_integridad), no solo 'el payload... incluyendo timestamp_evento e id_evento' "
            "como enumera la ficha -- cubre de mas (severidad, tipo_actor, origen_registro, etc. "
            "tambien entran al hash), no de menos."
        ) if 'to_jsonb(NEW)' in cuerpo else None


class TestSubCasoDetectarAlteracionEsMootPorqueLaInmutabilidadLaBloqueaAntes:
    def test_no_existe_ningun_trigger_before_update_que_recalcule_el_hash(self):
        texto = BASELINE.read_text(encoding='utf-8', errors='ignore')
        assert 'CREATE TRIGGER trg_hash_auditoria BEFORE INSERT ON modulo6.auditorias_financieras' in texto
        pytest.fail(
            "HALLAZGO: trg_hash_auditoria es BEFORE INSERT unicamente -- no existe un trigger "
            "equivalente BEFORE UPDATE que recalcule el hash tras una alteracion."
        ) if 'trg_hash_auditoria BEFORE UPDATE' not in texto else None

    def test_pero_la_alteracion_nunca_llega_a_ocurrir_por_el_trigger_de_inmutabilidad(self):
        texto = BASELINE.read_text(encoding='utf-8', errors='ignore')
        cuerpo = _cuerpo_funcion(texto, 'modulo6.fn_tgr_m06_13_inmutabilidad_auditoria')
        pytest.fail(
            "HALLAZGO (matiza el anterior, no es un hueco real): fn_tgr_m06_13_inmutabilidad_"
            "auditoria bloquea TODO UPDATE y TODO DELETE con una excepcion dura, para todos los "
            "roles -- 'detectar la alteracion recalculando el hash' nunca necesita dispararse en "
            "la practica porque hay una barrera mas fuerte (inmutabilidad total) un paso antes."
        ) if "TG_OP = 'UPDATE'" in cuerpo and "TG_OP = 'DELETE'" in cuerpo else None


class TestSubCasoHashCalculoFallidoNoExisteEnAbsolutoHallazgoGrave:
    def test_hash_calculo_fallido_no_aparece_en_ningun_archivo_del_repositorio(self):
        import subprocess
        resultado_src = [p for p in (REPO_ROOT / 'src').rglob('*.py')
                         if 'HASH_CALCULO_FALLIDO' in p.read_text(encoding='utf-8', errors='ignore')]
        resultado_alembic = [p for p in (REPO_ROOT / 'alembic').rglob('*')
                             if p.is_file() and p.suffix in ('.py', '.sql')
                             and 'HASH_CALCULO_FALLIDO' in p.read_text(encoding='utf-8', errors='ignore')]
        pytest.fail(
            "HALLAZGO GRAVE: 'HASH_CALCULO_FALLIDO' no aparece en ningun archivo de src/ ni "
            "alembic/ (grep exhaustivo, cero resultados) -- el escenario completo de 'fallback "
            "cuando el calculo del hash falla' (CA-5/FA-5) no tiene ninguna implementacion real; "
            "un fallo de calculo propagaria una excepcion de Postgres sin controlar, que (ver "
            "TC-M06-G85/16) tambien revertiria la operacion de negocio principal."
        ) if not resultado_src and not resultado_alembic else None


class TestSubCasoElMarcadorDe64CerosExisteParaOtroTriggerConexionConTcM06_17:
    def test_el_marcador_real_tiene_64_caracteres(self):
        texto = REPOSITORIO.read_text(encoding='utf-8')
        assert '_MARCADOR_HASH = "0" * 64' in texto
