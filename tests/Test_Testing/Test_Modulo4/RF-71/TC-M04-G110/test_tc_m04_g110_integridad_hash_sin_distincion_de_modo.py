"""
TC-M04-G110 (RF-71 v2.0 Restricciones 2/8/13/14/CA-2/CA-14/CA-18/E9/RNF-08,
CU-07) - "Integridad del dataset y del artefacto del modelo." Reintento
sobre la ficha v2.0 (añade (g): repetir (a)/(d) con modo_generacion =
CALIBRACION_EN_SITIO).

RELACIÓN CON TC-M04-G102 (hallazgo raíz): `modo_generacion` no existe en
ningún lado del código (confirmado en G102).

(a)-(f) -- SIN CAMBIOS respecto a la ronda anterior: el hash del
    artefacto SÍ se recalcula y compara correctamente
    (`_verificar_hash_artefacto`); el hash del dataset solo se valida en
    formato, nunca en contenido real.
(g) Repetir (a)/(d) con CALIBRACION_EN_SITIO -- HALLAZGO DE ALCANCE,
    MATIZADO POSITIVAMENTE: como `_verificar_hash_artefacto()` no
    inspecciona `modo_generacion` (de hecho, el parámetro ni siquiera
    existe) para decidir si aplicar la verificación, la MISMA cadena de
    integridad se ejecutaría igual si, hipotéticamente, un artefacto de
    calibración pasara por este mismo endpoint -- la protección no está
    condicionada por tipo de origen. El hallazgo real no es que la
    calibración tenga una integridad más débil, sino que no existe
    ningún camino (endpoint, DTO, campo) por el cual un artefacto de
    calibración pudiera siquiera llegar a invocar esta verificación,
    porque `CALIBRACION_EN_SITIO` no es una entrada reconocida en
    ningún punto del sistema (confirmado en G102/G106).

Cómo se prueba: inspección directa del código + pytest llamando a
`_verificar_hash_artefacto()`, confirmando que no recibe ni usa ningún
parámetro de modo/origen.

Como correrlo (Windows necesita el stub de fcntl):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    $env:SECRET_KEY = "test"
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    python -m pytest <ruta>\\test_tc_m04_g110_integridad_hash_sin_distincion_de_modo.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M04-G110.html --self-contained-html
"""
from __future__ import annotations

import hashlib
import inspect
import uuid
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.prediction.application.use_cases.versiones_modelo.registrar_version_modelo_use_case import (
    RegistrarVersionModeloUseCase,
)
from src.shared.errors import BusinessRuleError

REPO_ROOT = Path(__file__).resolve().parents[5]


def _use_case():
    return RegistrarVersionModeloUseCase(
        db=MagicMock(), repo=MagicMock(), auditoria_repo=MagicMock(), variable_port=MagicMock(),
        aviso_port=MagicMock(),
    )


class TestSubCasoAHashDeDatasetSigueSinVerificarseVigente:
    def test_dataset_entrenamiento_hash_solo_se_valida_en_formato(self):
        archivo = REPO_ROOT / 'src/prediction/application/use_cases/versiones_modelo/registrar_version_modelo_use_case.py'
        texto = archivo.read_text(encoding='utf-8')
        llamadas_verificacion_contenido = texto.count('self._verificar_hash_artefacto(')
        pytest.fail(
            f"HALLAZGO (a), vigente: self._verificar_hash_artefacto() se invoca "
            f"{llamadas_verificacion_contenido} vez(ces), siempre para hash_artefacto_sha256, "
            f"nunca para dataset_entrenamiento_hash."
        ) if llamadas_verificacion_contenido == 1 else None


class TestSubCasoDRecalculoDeHashSigueConfirmadoCorrecto:
    def test_alteracion_de_1_byte_es_detectada_y_rechazada(self):
        uc = _use_case()
        archivo_bytes = b'\x08' + b'contenido_del_modelo_de_prueba'
        hash_correcto = hashlib.sha256(archivo_bytes).hexdigest()
        archivo_alterado = archivo_bytes[:-1] + bytes([archivo_bytes[-1] ^ 0xFF])
        with pytest.raises(BusinessRuleError) as exc_info:
            uc._verificar_hash_artefacto(archivo_alterado, hash_correcto, uuid.uuid4())
        assert exc_info.value.code == 'HASH_ARTEFACTO_NO_COINCIDE'


class TestSubCasoGCalibracionNoTieneCaminoParaLlegarAEstaVerificacion:
    def test_verificar_hash_artefacto_no_recibe_ningun_parametro_de_modo(self):
        firma = inspect.signature(RegistrarVersionModeloUseCase._verificar_hash_artefacto)
        parametros = set(firma.parameters)
        assert 'modo_generacion' not in parametros and 'modo' not in parametros

    def test_pero_calibracion_en_sitio_no_es_una_entrada_reconocida_en_ningun_punto(self):
        pytest.fail(
            "HALLAZGO (g): _verificar_hash_artefacto() no distingue modo_generacion -- "
            "aplicaria la misma proteccion a cualquier artefacto que llegara por este endpoint. "
            "Pero no existe ningun camino (DTO, parametro, endpoint) por el cual un artefacto de "
            "CALIBRACION_EN_SITIO pudiera llegar a invocar esta funcion, porque ese modo no es "
            "una entrada reconocida en ningun punto del sistema (ver G102/G106). No es un "
            "hallazgo de integridad debil; es un hallazgo de que la calibracion no tiene ruta "
            "de entrega."
        )
