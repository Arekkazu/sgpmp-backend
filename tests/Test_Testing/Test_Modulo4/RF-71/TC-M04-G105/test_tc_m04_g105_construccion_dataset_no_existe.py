"""
TC-M04-G105 (RF-71 v2.0 Fase 2/Restricción 1/CA-1/CA-15 acotado a
INDIVIDUAL por RFC-009, CU-03) - "Construcción del dataset y prioridad de
etiquetas." Reintento sobre la ficha v2.0 (añade el subescenario negativo
(d) sobre POBLACIONAL).

REEJECUTADO 2026-10-30 CONTRA CÓDIGO POST-MERGE. RELACIÓN CON TC-M04-G102
(hallazgo raíz, actualizado): sigue sin existir ningún código de
construcción de dataset en M04 (confirmado en G102); PERO `POBLACIONAL`
SÍ existe ahora como paradigma válido de `tipo_modelo` -- esto invierte
la premisa de (d), aunque no necesariamente su conclusión práctica (ver
abajo).

(a)-(c)/(e)-(g) -- HALLAZGO ÚNICO, sin cambios respecto a la ronda
    anterior: no existe ningún caso de uso que construya un dataset a
    partir de RF-62/RF-67/RF-72/RF-59, ni ninguna noción de "prioridad de
    etiquetado".
(d) CA-15 sobre POBLACIONAL debe rechazarse de forma controlada --
    HALLAZGO ACTUALIZADO: a diferencia de la ronda anterior, `POBLACIONAL`
    SÍ es una entrada reconocida y distinguible del sistema real (vía
    `es_poblacional(tipo_modelo)`, ver G102) -- el sistema SÍ puede, en
    principio, distinguir un registro POBLACIONAL de uno supervisado. Sin
    embargo, esa distinción ocurre en `registrar_version_modelo_use_case.py`
    (validación de métricas/componente), NO en ningún código de
    "construcción de dataset" (que sigue sin existir). Es decir: CA-15
    sigue sin ser evaluable EN SU FORMA ORIGINAL (no hay construcción de
    dataset que "rechazar de forma controlada" para POBLACIONAL), pero ya
    no es cierto que el rechazo, de ocurrir, sería "por el motivo
    equivocado" -- el sistema sí tiene, en otra capa, un criterio real
    para diferenciar POBLACIONAL de los tipos supervisados.

Cómo se prueba: grep exhaustivo de términos del dominio de construcción
de dataset en src/prediction/ + inspección directa de `es_poblacional()`.

Como correrlo:
    python -m pytest <ruta>\\test_tc_m04_g105_construccion_dataset_no_existe.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M04-G105.html --self-contained-html
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[5]


class TestNoExisteConstruccionDeDataset:
    @pytest.mark.parametrize('termino', [
        'apto_para_ia', 'construir_dataset', 'ConstruirDataset', 'prioridad_etiquetado',
    ])
    def test_termino_de_construccion_de_dataset_no_existe_en_prediction(self, termino):
        archivos = [
            str(p.relative_to(REPO_ROOT)) for p in (REPO_ROOT / 'src/prediction').rglob('*.py')
            if termino in p.read_text(encoding='utf-8', errors='ignore')
        ]
        pytest.fail(
            f"HALLAZGO: '{termino}' no existe en ningun archivo de src/prediction/ (encontrados: "
            f"{archivos or 'ninguno'})."
        ) if not archivos else None


class TestSubCasoDPoblacionalSiEsUnaEntradaDistinguibleAhora:
    def test_poblacional_si_es_un_paradigma_real_y_distinguible(self):
        from src.shared.tipo_modelo import es_poblacional
        pytest.fail(
            "HALLAZGO (d) INVERTIDO EN SU PREMISA: es_poblacional('MODELO_AVES') == "
            f"{es_poblacional('MODELO_AVES')!r} -- el sistema SI distingue POBLACIONAL de los "
            "tipos supervisados mediante una funcion real, no solo mediante un rechazo generico "
            "de tipo_modelo invalido. La conclusion practica de (d) (CA-15 sigue sin ser "
            "evaluable porque no hay 'construccion de dataset' que probar) no cambia, pero ya "
            "no es por ausencia de distincion de POBLACIONAL."
        ) if es_poblacional('MODELO_AVES') else None

    def test_pero_la_distincion_vive_en_el_registro_no_en_construccion_de_dataset(self):
        archivo = REPO_ROOT / 'src/prediction/application/use_cases/versiones_modelo/registrar_version_modelo_use_case.py'
        texto = archivo.read_text(encoding='utf-8')
        pytest.fail(
            "HALLAZGO (d) VIGENTE EN SU CONCLUSION PRACTICA: es_poblacional() se usa dentro de "
            "registrar_version_modelo_use_case.py (validacion de metricas/componente), no en "
            "ningun caso de uso de 'construccion de dataset' -- ese concepto sigue sin existir "
            "del todo, asi que CA-15 sigue sin ser evaluable en la forma que pide la ficha."
        ) if 'es_poblacional' in texto else None
