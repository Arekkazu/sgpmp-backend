"""
TC-M04-G107 (RF-71 v2.0 Entradas/E5/CA-10/RFC-009, CU-04) - "Validación de
parámetros de entrenamiento, enumerados de la RFC-009 y algoritmo por
defecto." Reintento sobre la ficha v2.0 (añade validación del enumerado
de 6 valores de tipo_modelo y del campo modo_generacion).

REEJECUTADO 2026-10-30 CONTRA CÓDIGO POST-MERGE. RELACIÓN CON TC-M04-G102
(hallazgo raíz, actualizado): no existe `POST /api/v1/m04/retrainings` ni
`PUT /api/v1/m04/config/retraining`; `modo_generacion` sigue sin existir
-- pero `tipo_modelo` YA NO tiene 4 valores: tiene 6
(`src/shared/tipo_modelo.py::TIPOS_MODELO`), organizados en 3 paradigmas,
y el campo `componente` SÍ existe como obligatorio para `POBLACIONAL`
(ver G102).

(a)/(e)-(i) -- HALLAZGO ÚNICO, sin cambios: `n_estimadores`,
    `tecnica_validacion`, `ventana_temporal_minutos`, `semilla_aleatoria`
    siguen sin existir en `src/prediction/` ni en `src/configuration/`.
(b) tipo_modelo, enumerado de 6 valores -- HALLAZGO INVERTIDO: el
    catálogo real (`TIPOS_MODELO`, importado de `src/shared/tipo_modelo.py`
    desde el 2026-10-29) SÍ tiene 6 valores
    (`MODELO_AVES`/`MODELO_PORCINOS`/`MODELO_ACUICULTURA`/
    `MODELO_ESPECIES_MEDIANAS`/`MODELO_ESPECIES_GRANDES`/
    `MODELO_RIESGO_CONTAGIO`). La vieja `_TIPOS_VALIDOS` de 4 valores ya
    no existe en el archivo. No son los mismos 2 valores "nuevos" que la
    ficha nombraba, pero el enumerado real sí creció a 6 y sí distingue
    paradigmas.
(c) modo_generacion ausente/vacío/fuera de {REENTRENAMIENTO,
    CALIBRACION_EN_SITIO} -> rechazo controlado -- SIGUE NO EVALUABLE EN
    LA FORMA PEDIDA: el campo sigue sin existir en el DTO, así que sigue
    sin haber "rechazo con el campo señalado" para él. MATIZ: el análogo
    real para POBLACIONAL (`componente`) SÍ tiene rechazo explícito y
    señalado -- `_validar_componente()` lanza `BusinessRuleError(code=
    "COMPONENTE_INVALIDO", field="componente")` si no está en
    `COMPONENTES_POBLACIONAL` -- es decir, el patrón de "rechazo
    controlado" que (c) pide SÍ existe en el sistema real, solo que
    aplicado a `componente`, no a `modo_generacion`.
(d) Combinaciones inválidas entre tipo_modelo y modo_generacion -- SIGUE
    NO EVALUABLE, mismo motivo que (c) (modo_generacion no existe). La
    combinación real que SÍ se valida es tipo_modelo/componente: un
    `componente` solo se exige si `es_poblacional(tipo_modelo)`.

Cómo se prueba: inspección directa de `TIPOS_MODELO`
(`src/shared/tipo_modelo.py`) y de la firma de `RegistrarVersionModeloDTO`.

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
from src.shared.tipo_modelo import COMPONENTES_POBLACIONAL, TIPOS_MODELO

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


class TestSubCasoBTipoModeloSiTieneSeisValoresAhora:
    def test_tipos_modelo_real_tiene_6_valores(self):
        pytest.fail(
            f"HALLAZGO (b) INVERTIDO: TIPOS_MODELO (src/shared/tipo_modelo.py) tiene "
            f"{len(TIPOS_MODELO)} valores -- {sorted(TIPOS_MODELO)!r} -- no 4. La vieja "
            f"_TIPOS_VALIDOS de 4 valores ya no existe en registrar_version_modelo_use_case.py."
        ) if len(TIPOS_MODELO) == 6 else None


class TestSubCasoCyDModoGeneracionSigueIgnoradoPeroComponenteSiSeRechaza:
    def test_modo_generacion_no_es_un_parametro_que_el_dto_pueda_rechazar(self):
        firma = inspect.signature(RegistrarVersionModeloDTO.__init__)
        parametros = set(firma.parameters)
        pytest.fail(
            "HALLAZGO (c)/(d) VIGENTE: modo_generacion no es un parametro declarado del DTO -- un "
            "cliente que lo envie no recibe ningun rechazo explicito 'con el campo senalado' "
            "(como pide (c)): FastAPI simplemente no lee ese campo del multipart/form-data."
        ) if 'modo_generacion' not in parametros else None

    def test_pero_componente_si_tiene_rechazo_explicito_y_senalado(self):
        """MATIZ: el patron de 'rechazo controlado con el campo senalado'
        que (c) pide SI existe en el sistema real -- solo que para
        'componente' (POBLACIONAL), no para 'modo_generacion'."""
        firma = inspect.signature(RegistrarVersionModeloDTO.__init__)
        parametros = set(firma.parameters)
        pytest.fail(
            f"MATIZ: 'componente' SI es un parametro declarado del DTO (obligatorio para "
            f"POBLACIONAL, valores validos {sorted(COMPONENTES_POBLACIONAL)!r}) y SI se rechaza "
            f"explicitamente con field='componente' si es invalido -- a diferencia de "
            f"modo_generacion, que ni siquiera llega a ser leido."
        ) if 'componente' in parametros else None
