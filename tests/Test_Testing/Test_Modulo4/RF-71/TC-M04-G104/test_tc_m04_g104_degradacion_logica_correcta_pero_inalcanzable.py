"""
TC-M04-G104 (RF-71 Fase 1/Restricción 11/CA-9/RNF-06, CU-02) - "Activación
por trigger DEGRADACION y evaluación de drift." Grupo existente de RF-71.

RELACIÓN CON TC-M04-G102/G103 (hallazgo raíz): no existe
`GET /api/v1/m04/drift-evaluation` ni ningún scheduler que invoque la
evaluación de forma periódica. Este TC añade un matiz importante: a
diferencia de la mayoría de RF-71, aquí SÍ existe lógica real -- en SQL,
dentro de `modulo4.sp_evaluar_degradacion_modelo` -- y, leída
directamente, implementa CORRECTAMENTE las dos fronteras que (b) y (c)
piden. El hallazgo no es "la lógica está mal": es que esa lógica,
correcta, nunca se ejecuta en producción.

Código bajo prueba: `alembic/baseline/esquema_baseline.sql`,
procedimiento `modulo4.sp_evaluar_degradacion_modelo`.

(b) Frontera f1_score: 0,7999 → activa; 0,80 → NO activa; 0,8001 → NO
    activa -- CONFIRMADO CORRECTO EN EL SQL (sin hallazgo de lógica): la
    condición real es `IF v_f1_score < 0.80 THEN ...` -- 0.7999 < 0.80 es
    verdadero (activa), 0.80 < 0.80 es falso (no activa), 0.8001 < 0.80
    es falso (no activa). Coincide exactamente con lo que pide la ficha.
    HALLAZGO DE ALCANCE: esta condición nunca se evalúa en producción
    (ver G102/G103) -- nadie llama a `sp_evaluar_degradacion_modelo`.
(c) Frontera ground truth: 99 → pospone y notifica SIN activar; 100 →
    evalúa normalmente -- CONFIRMADO CORRECTO EN EL SQL: la condición es
    `IF v_count_verificados < 100 THEN` (pospone) con un `RAISE NOTICE
    'DEGRADACION_DETECTADA_POSPUESTA: ... Notifique al administrador.'`
    seguido de `RETURN` (sin llegar a iniciar el ciclo). Mismo hallazgo
    de alcance que (b): lógica correcta, inalcanzable.
(a)/(d)/(e)/(f) -- NO EJECUTABLES: dependen de que el procedimiento se
    invoque alguna vez, lo cual no ocurre (ver G102/G103). (f) en
    particular: el `RAISE NOTICE` escribe en el log de PostgreSQL, no en
    ninguna tabla de auditoría de RF-73/M04 -- aunque el procedimiento se
    invocara manualmente, no generaría una fila consultable como evento
    DEGRADACION_DETECTADA (el catálogo real de auditoría de M04, usado en
    TC-M04-G120, no incluye ningún evento con ese nombre).

Cómo se prueba: inspección directa y literal de las condiciones del
procedimiento en el DDL baseline (no se ejecuta el procedimiento real
porque no hay infraestructura de base de datos de prueba conectada en
esta sesión para procedimientos PL/pgSQL; la verificación es de las
condiciones booleanas tal como están escritas, no de una ejecución en
vivo).

Como correrlo:
    python -m pytest <ruta>\\test_tc_m04_g104_degradacion_logica_correcta_pero_inalcanzable.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M04-G104.html --self-contained-html
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[5]
DDL = (REPO_ROOT / 'alembic/baseline/esquema_baseline.sql').read_text(encoding='utf-8', errors='ignore')


def _bloque_procedimiento() -> str:
    inicio = DDL.index('CREATE PROCEDURE modulo4.sp_evaluar_degradacion_modelo')
    fin = DDL.index('ALTER PROCEDURE modulo4.sp_evaluar_degradacion_modelo', inicio)
    return DDL[inicio:fin]


class TestSubCasoBFronteraF1CorrectaPeroInalcanzable:
    def test_la_condicion_f1_es_estrictamente_menor_que_080(self):
        bloque = _bloque_procedimiento()
        assert 'IF v_f1_score < 0.80 THEN' in bloque

    def test_nadie_invoca_el_procedimiento_en_produccion(self):
        archivos = [
            str(p.relative_to(REPO_ROOT)) for p in (REPO_ROOT / 'src').rglob('*.py')
            if 'sp_evaluar_degradacion_modelo' in p.read_text(encoding='utf-8', errors='ignore')
        ]
        pytest.fail(
            f"HALLAZGO DE ALCANCE (b): la condicion 'IF v_f1_score < 0.80' en "
            f"sp_evaluar_degradacion_modelo es logicamente correcta para las 3 fronteras que (b) "
            f"pide (0.7999 activa, 0.80 y 0.8001 no activan) -- pero el procedimiento nunca se "
            f"invoca desde Python (encontrados: {archivos or 'ninguno'}) ni desde ningun "
            f"scheduler (G103). La frontera correcta nunca se evalua en produccion."
        ) if not archivos else None


class TestSubCasoCFronteraGroundTruthCorrectaPeroInalcanzable:
    def test_la_condicion_de_minimo_100_registros_pospone_sin_activar(self):
        bloque = _bloque_procedimiento()
        assert 'IF v_count_verificados < 100 THEN' in bloque
        bloque_pospone = bloque.split('IF v_count_verificados < 100 THEN')[1].split('END IF;')[0]
        assert 'RETURN' in bloque_pospone
        assert 'sp_iniciar_ciclo_reentrenamiento' not in bloque_pospone

    def test_la_notificacion_de_pospuesto_es_solo_un_raise_notice_de_postgres(self):
        bloque = _bloque_procedimiento()
        bloque_pospone = bloque.split('IF v_count_verificados < 100 THEN')[1].split('END IF;')[0]
        pytest.fail(
            "HALLAZGO (f), de alcance: la 'notificacion al administrador' que (c) describe es, "
            "en el codigo real, un RAISE NOTICE de PostgreSQL (visible solo en el log del "
            "servidor de BD) -- no una fila en ninguna tabla de notificaciones ni en el catalogo "
            "de auditoria de M04 (TC-M04-G120). Ademas, como el procedimiento nunca se invoca "
            "(ver arriba), ni siquiera ese RAISE NOTICE llega a emitirse en produccion."
        ) if 'RAISE NOTICE' in bloque_pospone else None
