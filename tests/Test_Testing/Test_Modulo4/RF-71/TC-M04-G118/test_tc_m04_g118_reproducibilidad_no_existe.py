"""
TC-M04-G118 (RF-71 RNF-04/RNF-05/RNF-12/Salida 3, CU-14) -
"Reproducibilidad del entrenamiento." Grupo existente de RF-71.

RELACIÓN CON TC-M04-G102/G110 (hallazgos raíz): no existe ningún proceso
de entrenamiento ejecutable desde este backend (confirmado en G102); el
`dataset_entrenamiento_hash` que (c)/(e) asumen reconstruible nunca se
verifica contra datos reales (TC-M04-G110(a)) -- es un valor que el
llamador declara, no algo que este backend pueda usar para "recuperar" el
dataset correspondiente, porque no hay ningún almacenamiento de datasets
alcanzable.

(a)/(b) Misma semilla -> mismo resultado; semilla distinta -> resultado
    distinto -- NO EVALUABLE: no existe ningún concepto de semilla
    aleatoria en el contrato real (confirmado en TC-M04-G107); no hay
    ningún entrenamiento que este backend ejecute para comparar.
(c) El registro de ejecución permite reconstruir el experimento
    (dataset_hash, parámetros, versión de catálogo, modelo base,
    semilla) -- HALLAZGO: `VersionModelo` no tiene ningún campo de
    parámetros de entrenamiento ni de semilla (confirmado en
    TC-M04-G107); sí tiene `dataset_entrenamiento_hash`, pero ese hash no
    es recuperable hacia ningún dataset real porque el dataset nunca se
    almacena en este backend (confirmado en TC-M04-G110(a)).
(d) Reproducir un entrenamiento de hace 6 meses -- NO EVALUABLE, mismo
    motivo que (c).
(e) El dataset sigue siendo recuperable y auditable aunque no esté
    expuesto públicamente -- HALLAZGO: no hay ningún endpoint ni tabla
    alcanzable que almacene el CONTENIDO del dataset -- solo su hash
    declarado (ver TC-M04-G110(a)); no hay nada que "recuperar", solo un
    valor de 64 caracteres sin ningún dato detrás en este backend.

Cómo se prueba: confirmación de que `VersionModelo` no tiene campos de
parámetros de entrenamiento/semilla y de que no existe ningún
`GET /api/v1/m04/datasets/{dataset_hash}` (ya confirmado estructuralmente
en G102, aquí se re-verifica contra el modelo de dominio real).

Como correrlo:
    python -m pytest <ruta>\\test_tc_m04_g118_reproducibilidad_no_existe.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M04-G118.html --self-contained-html
"""
from __future__ import annotations

from dataclasses import fields
from pathlib import Path

import pytest

from src.prediction.domain.entities.version_modelo import VersionModelo

REPO_ROOT = Path(__file__).resolve().parents[5]


class TestNoHayCamposParaReproducibilidad:
    def test_version_modelo_no_tiene_semilla_ni_version_de_catalogo(self):
        nombres_campos = {f.name for f in fields(VersionModelo)}
        pytest.fail(
            f"HALLAZGO (c): VersionModelo declara {sorted(nombres_campos)!r} -- ningun campo "
            f"de semilla aleatoria ni de version de catalogo RF-64. dataset_entrenamiento_hash "
            f"si existe, pero no hay ningun dataset real detras de ese hash en este backend "
            f"(ver TC-M04-G110(a))."
        ) if 'semilla_aleatoria' not in nombres_campos and 'version_catalogo' not in nombres_campos else None

    def test_no_existe_ningun_endpoint_para_consultar_el_dataset_por_hash(self):
        archivos_routers = list((REPO_ROOT / 'src/prediction/infrastructure/routers').glob('*.py'))
        archivos_con_match = [
            p.name for p in archivos_routers if 'dataset' in p.read_text(encoding='utf-8', errors='ignore').lower()
        ]
        pytest.fail(
            f"HALLAZGO (e): ningun router de M04 menciona 'dataset' (revisados: "
            f"{[p.name for p in archivos_routers]!r}) -- no existe GET /api/v1/m04/datasets/"
            f"{{dataset_hash}} ni ningun equivalente real; el dataset_entrenamiento_hash "
            f"declarado al registrar un modelo no tiene ningun contenido recuperable detras."
        ) if not archivos_con_match else None
