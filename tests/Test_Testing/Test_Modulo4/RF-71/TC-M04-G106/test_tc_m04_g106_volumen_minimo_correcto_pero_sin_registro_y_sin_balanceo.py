"""
TC-M04-G106 (RF-71 Fases 2-3/E1/E2/CA-1, CU-03) - "Volumen mínimo y
balanceo de clases." Grupo existente de RF-71.

RELACIÓN CON TC-M04-G102 (hallazgo raíz): no existe ningún endpoint
alcanzable que inicie el proceso (confirmado en G102). Este TC, como
G104, encuentra que la frontera de volumen SÍ está bien implementada en
el SQL dormido -- pero con un matiz adicional: ni siquiera en ese SQL se
"registra" el aborto como pide (a); y el balanceo de clases (c)/(d)/(e)
no existe en ningún lugar, ni siquiera dormido.

Código bajo prueba: `modulo4.sp_iniciar_ciclo_reentrenamiento` en el DDL
baseline.

(a) 499 → aborta y SE REGISTRA REENTRENAMIENTO_ABORTADO con causa
    DATASET_INSUFICIENTE; 500/501 → continúa -- PARCIALMENTE CONFIRMADO,
    CON HALLAZGO: la condición `IF v_count < 500 THEN RAISE EXCEPTION
    'DATASET_INSUFICIENTE: ...'` es correcta para la frontera (499 aborta,
    500 y 501 continúan). Pero el `RAISE EXCEPTION` ocurre ANTES del
    `INSERT INTO modulo4.ciclos_entrenamientos` -- es decir, un intento
    con 499 registros NUNCA llega a crear una fila, por lo que no hay
    ningún "registro con estado ABORTADO" que consultar después: el
    intento simplemente lanza un error y no deja rastro en la tabla de
    ciclos. Lo que (a) pide verificar (un registro persistido y
    consultable con causa documentada) no existe -- solo existe un error
    transitorio de PostgreSQL.
(b) Alta proporción de apto_para_ia=false que baja el conteo válido bajo
    el mínimo -- NO EVALUABLE: depende de la función
    `fn_contar_registros_etiquetados_disponibles`, cuyo criterio exacto
    de conteo no se auditó en este TC; en cualquier caso, el hallazgo de
    alcance de (a) aplica igual.
(c)/(d)/(e) Balanceo de clases (oversampling/ponderación) y
    estratificación de conjuntos -- HALLAZGO: cero coincidencias de
    "balanceo"/"oversampling"/"estratificaci" en todo el repositorio
    (código Python Y DDL baseline). A diferencia de la frontera de
    volumen, que sí tiene una implementación dormida, el balanceo de
    clases no tiene NINGUNA implementación, ni siquiera inalcanzable.

Cómo se prueba: inspección directa del procedimiento en el DDL baseline +
grep exhaustivo de términos de balanceo/estratificación en todo el
repositorio.

Como correrlo:
    python -m pytest <ruta>\\test_tc_m04_g106_volumen_minimo_correcto_pero_sin_registro_y_sin_balanceo.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M04-G106.html --self-contained-html
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[5]
DDL = (REPO_ROOT / 'alembic/baseline/esquema_baseline.sql').read_text(encoding='utf-8', errors='ignore')


class TestSubCasoAFronteraCorrectaPeroSinRegistroPersistido:
    def test_la_condicion_de_minimo_500_es_correcta(self):
        bloque = DDL[DDL.index('CREATE PROCEDURE modulo4.sp_iniciar_ciclo_reentrenamiento'):]
        bloque = bloque[:bloque.index('ALTER PROCEDURE modulo4.sp_iniciar_ciclo_reentrenamiento')]
        assert 'IF v_count < 500 THEN' in bloque
        assert 'RAISE EXCEPTION' in bloque.split('IF v_count < 500 THEN')[1].split('END IF;')[0]

    def test_el_raise_exception_ocurre_antes_del_insert_no_deja_registro(self):
        bloque = DDL[DDL.index('CREATE PROCEDURE modulo4.sp_iniciar_ciclo_reentrenamiento'):]
        bloque = bloque[:bloque.index('ALTER PROCEDURE modulo4.sp_iniciar_ciclo_reentrenamiento')]
        posicion_raise = bloque.index('DATASET_INSUFICIENTE')
        posicion_insert = bloque.index('INSERT INTO modulo4.ciclos_entrenamientos')
        pytest.fail(
            "HALLAZGO (a): el RAISE EXCEPTION de DATASET_INSUFICIENTE ocurre ANTES del INSERT "
            "INTO ciclos_entrenamientos -- un intento con menos de 500 registros nunca crea una "
            "fila en la tabla. No hay ningun 'registro con estado ABORTADO y causa "
            "DATASET_INSUFICIENTE' que (a) pide poder consultar; solo hay un error transitorio "
            "que nadie persiste (y que, en todo caso, nunca se dispara porque nada invoca este "
            "procedimiento -- ver TC-M04-G102)."
        ) if posicion_raise < posicion_insert else None


class TestSubCasoCDEBalanceoDeClasesNoExiste:
    @pytest.mark.parametrize('termino', ['balanceo', 'oversampling', 'estratificaci', 'ponderacion'])
    def test_termino_de_balanceo_no_existe_en_ningun_lado(self, termino):
        archivos_py = [
            str(p.relative_to(REPO_ROOT)) for p in (REPO_ROOT / 'src').rglob('*.py')
            if termino in p.read_text(encoding='utf-8', errors='ignore').lower()
        ]
        en_ddl = termino in DDL.lower()
        pytest.fail(
            f"HALLAZGO (c)/(d)/(e): '{termino}' no aparece en ningun archivo Python de src/ "
            f"(encontrados: {archivos_py or 'ninguno'}) ni en el DDL baseline. A diferencia de la "
            f"frontera de volumen (a), que si tiene una implementacion dormida en SQL, el "
            f"balanceo de clases no tiene absolutamente ninguna implementacion."
        ) if not archivos_py and not en_ddl else None
