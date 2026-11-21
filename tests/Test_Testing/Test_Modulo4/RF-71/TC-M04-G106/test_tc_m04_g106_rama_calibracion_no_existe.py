"""
TC-M04-G106 (RF-71 v2.0 Fases 2-3/E1/E2/CA-1/RFC-009, CU-03) -
"Precondición de volumen: las DOS ramas de modo_generacion." Reescrito
por RFC-009 -- reemplaza la versión anterior (solo tenía la Rama A).

RELACIÓN CON TC-M04-G102/G104 (hallazgos raíz): `modo_generacion` y
`CALIBRACION_EN_SITIO` no existen en ningún lado (G102); el único
procedimiento de precondición dormido (`sp_iniciar_ciclo_reentrenamiento`)
no distingue tipo de proceso (G104).

RAMA A (REENTRENAMIENTO, mínimo 500 registros):
(a)/(b) -- CONFIRMADO CORRECTO EN EL SQL DORMIDO, HALLAZGO DE ALCANCE: la
    condición `IF v_count < 500 THEN RAISE EXCEPTION` sigue siendo
    correcta para 499/500/501 (ya confirmado en la ronda anterior), pero
    sigue sin invocarse desde ningún lugar alcanzable.
RAMA B (CALIBRACION_EN_SITIO, 72h + 3 auditorías de RF-24):
(c)/(d)/(e)/(f)/(g) -- HALLAZGO: no existe ninguna rama de precondición
    para `CALIBRACION_EN_SITIO` en el procedimiento real
    (`sp_iniciar_ciclo_reentrenamiento` solo conoce
    PROGRAMADO/MANUAL/DEGRADACION como valores de
    `p_trigger_reentrenamiento`; `CALIBRACION_EN_SITIO` ni siquiera es un
    trigger válido para él -- causaría `TRIGGER_INVALIDO`, no una
    evaluación de horas limpias ni de auditorías). No hay ninguna
    función que cuente horas de datos limpios ni que consulte auditorías
    de RF-24 (y, como ya confirmó G102, el RF-24 real no tiene ningún
    concepto de "auditoría" de todos modos).
BALANCEO (ambas ramas):
(h)/(i) -- HALLAZGO VIGENTE: `balanceo`/`oversampling`/`estratificaci`/
    `ponderacion` no existen en ningún lado (confirmado en la ronda
    anterior, sin cambios).

Cómo se prueba: inspección directa de los valores aceptados por
`p_trigger_reentrenamiento` en `sp_iniciar_ciclo_reentrenamiento` + grep
de términos de calibración/balanceo.

Como correrlo:
    python -m pytest <ruta>\\test_tc_m04_g106_rama_calibracion_no_existe.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M04-G106.html --self-contained-html
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[5]
DDL = (REPO_ROOT / 'alembic/baseline/esquema_baseline.sql').read_text(encoding='utf-8', errors='ignore')


def _bloque_sp_iniciar() -> str:
    inicio = DDL.index('CREATE PROCEDURE modulo4.sp_iniciar_ciclo_reentrenamiento')
    fin = DDL.index('ALTER PROCEDURE modulo4.sp_iniciar_ciclo_reentrenamiento', inicio)
    return DDL[inicio:fin]


class TestRamaACorrectaPeroInalcanzable:
    def test_la_condicion_de_500_sigue_siendo_correcta(self):
        bloque = _bloque_sp_iniciar()
        assert 'IF v_count < 500 THEN' in bloque


class TestRamaBCalibracionEnSitioNoExiste:
    def test_calibracion_en_sitio_no_es_un_trigger_valido_para_el_procedimiento(self):
        bloque = _bloque_sp_iniciar()
        pytest.fail(
            "HALLAZGO (c)-(g): sp_iniciar_ciclo_reentrenamiento solo reconoce "
            "PROGRAMADO/MANUAL/DEGRADACION como p_trigger_reentrenamiento -- cualquier otro "
            "valor, incluido 'CALIBRACION_EN_SITIO', cae en el ELSE y lanza TRIGGER_INVALIDO. "
            "No existe ninguna rama que evalue 72 horas de datos limpios ni auditorias de RF-24."
        ) if "WHEN 'PROGRAMADO'" in bloque and "WHEN 'CALIBRACION_EN_SITIO'" not in bloque else None

    def test_no_existe_ninguna_funcion_que_cuente_horas_de_datos_limpios(self):
        archivos = [
            str(p.relative_to(REPO_ROOT)) for p in (REPO_ROOT / 'src').rglob('*.py')
            if 'datos_limpios' in p.read_text(encoding='utf-8', errors='ignore')
        ]
        pytest.fail(
            f"HALLAZGO (c): 'datos_limpios' no existe en ningun archivo de src/ (encontrados: "
            f"{archivos or 'ninguno'}) ni ninguna funcion equivalente en el DDL -- la "
            f"precondicion de 72h de la Rama B no tiene ninguna implementacion."
        ) if not archivos and 'datos_limpios' not in DDL else None


class TestBalanceoDeClasesSigueSinExistir:
    @pytest.mark.parametrize('termino', ['balanceo', 'oversampling', 'estratificaci', 'ponderacion'])
    def test_termino_de_balanceo_no_existe(self, termino):
        archivos_py = [
            str(p.relative_to(REPO_ROOT)) for p in (REPO_ROOT / 'src').rglob('*.py')
            if termino in p.read_text(encoding='utf-8', errors='ignore').lower()
        ]
        pytest.fail(
            f"HALLAZGO (h)/(i): '{termino}' no aparece en ningun archivo Python de src/ relevante "
            f"a M04 (encontrados en todo src/: {archivos_py or 'ninguno'}, revisar si son de "
            f"otros modulos) ni en el DDL."
        ) if not archivos_py and termino not in DDL.lower() else None
