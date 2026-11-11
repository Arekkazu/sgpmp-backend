"""
TC-M04-G107 (RF-71 v2.0 Entradas/E5/CA-10/RFC-009, CU-04) - "Validación de
parámetros de entrenamiento, enumerados de la RFC-009 y algoritmo por
defecto." Reintento sobre la ficha v2.0 (añade validación del enumerado
de 6 valores de tipo_modelo y del campo modo_generacion).

RELACIÓN CON TC-M04-G102 (hallazgo raíz): no existe `POST /api/v1/m04/
retrainings` ni `PUT /api/v1/m04/config/retraining` (confirmado en G102);
`tipo_modelo` real tiene 4 valores, no 6; `modo_generacion` no existe.

(a)/(e)-(i) -- HALLAZGO ÚNICO, sin cambios: no existe ningún DTO,
    validador ni catálogo en M09 para parámetros de entrenamiento.
(b) tipo_modelo, enumerado de 6 valores -- HALLAZGO: el único catálogo
    real (`_TIPOS_VALIDOS` en `registrar_version_modelo_use_case.py`)
    sigue teniendo 4 valores (`ESPECIES_PEQUEÑAS`, `ESPECIES_MEDIANAS`,
    `ESPECIES_GRANDES`, `CONTAGIO`), no 6. Los 2 valores adicionales que
    la RFC-009 pide no se añadieron.
(c) modo_generacion ausente/vacío/fuera de {REENTRENAMIENTO,
    CALIBRACION_EN_SITIO} -> rechazo controlado -- NO EVALUABLE EN LA
    FORMA PEDIDA: como el campo no existe en ningún DTO, no hay ningún
    "rechazo con el campo señalado" que observar -- cualquier valor
    enviado para `modo_generacion` sería simplemente ignorado (no leído),
    no rechazado explícitamente.
(d) Combinaciones inválidas entre tipo_modelo y modo_generacion -- NO
    EVALUABLE, mismo motivo que (c).

Cómo se prueba: inspección directa de `_TIPOS_VALIDOS` y de la firma de
`RegistrarVersionModeloDTO`.

Como correrlo (Windows necesita el stub de fcntl):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    $env:SECRET_KEY = "test"
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    python -m pytest <ruta>\\test_tc_m04_g107_validacion_parametros_no_existe.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M04-G107.html --self-contained-html
"""
from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from src.prediction.infrastructure.dto.registrar_version_modelo_dto import RegistrarVersionModeloDTO

REPO_ROOT = Path(__file__).resolve().parents[5]


class TestNoExisteValidacionDeParametrosDeEntrenamiento:
    @pytest.mark.parametrize('termino', [
        'n_estimadores', 'tecnica_validacion', 'ventana_temporal_minutos', 'semilla_aleatoria',
    ])
    def test_parametro_no_existe_en_prediction_ni_configuration(self, termino):
        archivos = [
            str(p.relative_to(REPO_ROOT)) for carpeta in ('src/prediction', 'src/configuration')
            for p in (REPO_ROOT / carpeta).rglob('*.py')
            if termino in p.read_text(encoding='utf-8', errors='ignore')
        ]
        pytest.fail(
            f"HALLAZGO: '{termino}' no existe en src/prediction/ ni en src/configuration/ (M09) "
            f"(encontrados: {archivos or 'ninguno'})."
        ) if not archivos else None


class TestSubCasoBTipoModeloSigueConCuatroValores:
    def test_tipos_validos_no_tiene_6_valores(self):
        archivo = REPO_ROOT / 'src/prediction/application/use_cases/versiones_modelo/registrar_version_modelo_use_case.py'
        texto = archivo.read_text(encoding='utf-8')
        pytest.fail(
            "HALLAZGO (b): _TIPOS_VALIDOS = {'ESPECIES_PEQUEÑAS', 'ESPECIES_MEDIANAS', "
            "'ESPECIES_GRANDES', 'CONTAGIO'} -- 4 valores, no el enumerado de 6 que pide la "
            "RFC-009."
        ) if texto.count("_TIPOS_VALIDOS = {") == 1 and 'POBLACIONAL' not in texto else None


class TestSubCasoCyDModoGeneracionNoEsRechazadoEsIgnorado:
    def test_modo_generacion_no_es_un_parametro_que_el_dto_pueda_rechazar(self):
        firma = inspect.signature(RegistrarVersionModeloDTO.__init__)
        parametros = set(firma.parameters)
        pytest.fail(
            "HALLAZGO (c)/(d): modo_generacion no es un parametro declarado del DTO -- un "
            "cliente que lo envie no recibe ningun rechazo explicito 'con el campo senalado' "
            "(como pide (c)): FastAPI simplemente no lee ese campo del multipart/form-data. No "
            "hay manera de distinguir 'rechazado' de 'ignorado silenciosamente' porque el "
            "campo nunca llega al codigo."
        ) if 'modo_generacion' not in parametros else None
