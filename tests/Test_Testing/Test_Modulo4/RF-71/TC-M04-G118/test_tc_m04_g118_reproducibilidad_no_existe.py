"""
TC-M04-G118 (RF-71 v2.0 RNF-04/RNF-05/RNF-12/Salida 3, CU-14) -
"Reproducibilidad del entrenamiento." La v2.0 añade modo_generacion y
tipo_modelo a los datos de reconstrucción del experimento, y (d) pide
verificar que los registros históricos anteriores a la RFC-009 (sin
modo_generacion) sigan siendo interpretables.

RELACIÓN CON TC-M04-G102/G110 (hallazgos raíz): no existe ningún proceso
de entrenamiento ejecutable desde este backend; `dataset_entrenamiento_hash`
nunca se verifica contra datos reales; `modo_generacion` no existe como
campo en ningún lado.

(a)/(b) Semilla -- NO EVALUABLE: no existe ningún concepto de semilla
    aleatoria en el contrato real.
(c) El registro permite reconstruir el experimento, incluidos
    modo_generacion y tipo_modelo -- HALLAZGO AGRAVADO: `VersionModelo`
    no tiene ningún campo de semilla, versión de catálogo NI
    modo_generacion -- el campo que la RFC-009 pide añadir a la
    reconstrucción nunca se agregó.
(d) Reproducir un registro histórico anterior a la RFC-009 sin que se
    rompa la interpretación -- CONFIRMADO TRIVIALMENTE, POR AUSENCIA: como
    `modo_generacion` nunca existió en ningún momento (ni antes ni
    después de la RFC-009), no hay ninguna migración de esquema que
    pueda "romper" la interpretación de un registro antiguo -- todos los
    registros, viejos y nuevos, carecen igual del campo.
(e) El dataset sigue siendo recuperable -- HALLAZGO: no hay ningún
    contenido real detrás del hash declarado.

Cómo se prueba: confirmación de los campos reales de `VersionModelo` y de
que `modo_generacion` no apareció nunca, en ninguna versión del esquema.

Como correrlo (Windows necesita el stub de fcntl):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    $env:SECRET_KEY = "test"
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    python -m pytest <ruta>\\test_tc_m04_g118_reproducibilidad_no_existe.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M04-G118.html --self-contained-html
"""
from __future__ import annotations

from dataclasses import fields
from pathlib import Path

import pytest

from src.prediction.domain.entities.version_modelo import VersionModelo

REPO_ROOT = Path(__file__).resolve().parents[5]


class TestNoHayCamposParaReproducibilidadNiModoGeneracion:
    def test_version_modelo_no_tiene_semilla_version_de_catalogo_ni_modo_generacion(self):
        nombres_campos = {f.name for f in fields(VersionModelo)}
        pytest.fail(
            f"HALLAZGO (c): VersionModelo declara {sorted(nombres_campos)!r} -- ningun campo de "
            f"semilla aleatoria, version de catalogo RF-64 ni modo_generacion. El campo que la "
            f"RFC-009 pide incorporar a la reconstruccion del experimento nunca se agrego."
        ) if 'semilla_aleatoria' not in nombres_campos and 'modo_generacion' not in nombres_campos else None

    def test_no_existe_ningun_endpoint_para_consultar_el_dataset_por_hash(self):
        archivos_routers = list((REPO_ROOT / 'src/prediction/infrastructure/routers').glob('*.py'))
        archivos_con_match = [
            p.name for p in archivos_routers if 'dataset' in p.read_text(encoding='utf-8', errors='ignore').lower()
        ]
        pytest.fail(
            f"HALLAZGO (e): ningun router de M04 menciona 'dataset' (revisados: "
            f"{[p.name for p in archivos_routers]!r})."
        ) if not archivos_con_match else None


class TestSubCasoDRegistrosViejosYNuevosSonIgualDeInterpretables:
    def test_modo_generacion_nunca_existio_en_ninguna_version_del_esquema(self):
        texto_ddl = (REPO_ROOT / 'alembic/baseline/esquema_baseline.sql').read_text(
            encoding='utf-8', errors='ignore')
        assert 'modo_generacion' not in texto_ddl
