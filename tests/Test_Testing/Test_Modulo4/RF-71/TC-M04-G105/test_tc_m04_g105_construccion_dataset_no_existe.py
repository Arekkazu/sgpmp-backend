"""
TC-M04-G105 (RF-71 v2.0 Fase 2/Restricción 1/CA-1/CA-15 acotado a
INDIVIDUAL por RFC-009, CU-03) - "Construcción del dataset y prioridad de
etiquetas." Reintento sobre la ficha v2.0 (añade el subescenario negativo
(d) sobre POBLACIONAL).

RELACIÓN CON TC-M04-G102 (hallazgo raíz): no existe ningún código de
construcción de dataset en M04 (confirmado en G102); `tipo_modelo`
POBLACIONAL no existe como valor válido (solo 4 valores, ninguno
POBLACIONAL).

(a)-(c)/(e)-(g) -- HALLAZGO ÚNICO, sin cambios respecto a la ronda
    anterior: no existe ningún caso de uso que construya un dataset a
    partir de RF-62/RF-67/RF-72/RF-59, ni ninguna noción de "prioridad de
    etiquetado".
(d) CA-15 sobre POBLACIONAL debe rechazarse de forma controlada -- NO
    EVALUABLE, en un sentido más fuerte que "no implementado": como
    `tipo_modelo` ni siquiera acepta `POBLACIONAL` como valor
    (confirmado en G102 -- el enumerado real tiene 4 valores, no 6), no
    existe ningún punto del sistema donde "forzar CA-15 sobre
    POBLACIONAL" sea una entrada posible de probar. El rechazo ocurriría,
    pero por el motivo equivocado (tipo_modelo inválido en general), no
    porque el sistema distinga POBLACIONAL de los tipos supervisados.

Cómo se prueba: grep exhaustivo de términos del dominio de construcción
de dataset en src/prediction/.

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


class TestSubCasoDPoblacionalNiSiquieraEsUnaEntradaPosible:
    def test_poblacional_no_es_un_valor_valido_de_tipo_modelo(self):
        archivo = REPO_ROOT / 'src/prediction/application/use_cases/versiones_modelo/registrar_version_modelo_use_case.py'
        texto = archivo.read_text(encoding='utf-8')
        pytest.fail(
            "HALLAZGO (d): 'POBLACIONAL' no aparece entre los valores de _TIPOS_VALIDOS -- "
            "'forzar CA-15 sobre POBLACIONAL' no es una entrada que el sistema pueda distinguir "
            "de cualquier otro tipo_modelo invalido; el rechazo, de ocurrir, no demuestra que "
            "CA-15 este correctamente acotado a INDIVIDUAL."
        ) if 'POBLACIONAL' not in texto else None
