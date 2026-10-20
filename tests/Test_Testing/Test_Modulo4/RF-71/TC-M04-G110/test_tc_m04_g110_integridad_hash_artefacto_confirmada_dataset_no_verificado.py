"""
TC-M04-G110 (RF-71 Restricciones 2/8/13/14, CA-2/CA-14/CA-18, E9/RNF-08,
CU-07) - "Integridad del dataset y del artefacto del modelo." Grupo
existente de RF-71.

RELACIÓN CON TC-M04-G102 (hallazgo raíz): no existe ningún "RF-71" que
recalcule nada antes de enviar -- la verificación real ocurre en el
RECEPTOR (RF-69, `RegistrarVersionModeloUseCase`), que SÍ implementa
correctamente la verificación de hash del artefacto, con el matiz de que
es la capa receptora la que protege, no una capa emisora que no existe.

Código bajo prueba:
    src/prediction/application/use_cases/versiones_modelo/registrar_version_modelo_use_case.py

(a) CA-2, dataset_hash único con datos distintos/idénticos -- HALLAZGO DE
    ASIMETRÍA: `dataset_entrenamiento_hash` solo se valida en FORMATO (64
    hex) -- nunca se recalcula ni se verifica contra ningún dato real,
    porque el dataset en sí nunca se envía a este endpoint, solo su hash
    declarado. A diferencia del hash del artefacto (ver (d)), el sistema
    no tiene ninguna forma de detectar que un `dataset_entrenamiento_hash`
    declarado sea falso o no corresponda al dataset real usado.
(b) Restricción 8, dataset inmutable durante entrenamiento -- NO
    EVALUABLE: no hay almacenamiento de dataset alcanzable desde este
    backend.
(c) CA-14, hash del artefacto inmediatamente después del entrenamiento --
    NO EVALUABLE: el entrenamiento en sí no es observable desde este
    backend (ver G102).
(d) CA-18/Restricción 14, recálculo y comparación del hash antes de la
    entrega -- CONFIRMADO CORRECTO, CON MATIZ: `_verificar_hash_artefacto()`
    recalcula `hashlib.sha256(archivo_bytes).hexdigest()` y lo compara
    contra `hash_artefacto_sha256` declarado, rechazando con
    `HASH_ARTEFACTO_NO_COINCIDE` si no coinciden -- el control SÍ existe
    y funciona. El matiz: ocurre en el lado RECEPTOR (RF-69), no como un
    paso de RF-71 "antes de enviar" (ese paso de RF-71 no existe, ver
    G102) -- el efecto protector es equivalente o mejor (verificado por
    el lado de confianza), pero la ubicación no es la que describe la
    ficha.
(e) E9, fallo de hash -> REENTRENAMIENTO_FALLIDO con causa ERROR_HASH --
    HALLAZGO DE NOMENCLATURA Y REGISTRO: el código real de error es
    `HASH_ARTEFACTO_NO_COINCIDE`, no `ERROR_HASH`; y no se crea ningún
    registro "REENTRENAMIENTO_FALLIDO" -- se lanza una excepción HTTP
    (`BusinessRuleError`) y se registra un evento de auditoría
    `HASH_INVALIDO_DETECTADO` (distinto nombre también).
(f) El hash corresponde al archivo realmente entregado, no a una copia en
    memoria -- CONFIRMADO CORRECTO: `_verificar_hash_artefacto()` hashea
    los mismos `archivo_bytes` que luego `_guardar_artefacto()` escribe a
    disco -- es el mismo objeto en memoria, sin ninguna copia intermedia.

Cómo se prueba: inspección directa del código + pytest llamando a
`_verificar_hash_artefacto()` con una alteración de 1 byte para confirmar
el rechazo real.

Como correrlo (Windows necesita el stub de fcntl):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    $env:SECRET_KEY = "test"
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    python -m pytest <ruta>\\test_tc_m04_g110_integridad_hash_artefacto_confirmada_dataset_no_verificado.py -v \
        --html=<ruta>\\resultados\\resultado_TC-M04-G110.html --self-contained-html
"""
from __future__ import annotations

import hashlib
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
    )


class TestSubCasoAHashDeDatasetNuncaSeVerificaContraDatosReales:
    def test_dataset_entrenamiento_hash_solo_se_valida_en_formato(self):
        archivo = REPO_ROOT / 'src/prediction/application/use_cases/versiones_modelo/registrar_version_modelo_use_case.py'
        texto = archivo.read_text(encoding='utf-8')
        # El dataset_entrenamiento_hash pasa por el validador de FORMATO...
        se_valida_formato = '_validar_hash_sha256_campo(dto.dataset_entrenamiento_hash' in texto
        # ...pero nunca por una verificacion de CONTENIDO equivalente a _verificar_hash_artefacto
        # (esa funcion solo se invoca una vez, para el artefacto del modelo, nunca para el dataset)
        llamadas_verificacion_contenido = texto.count('self._verificar_hash_artefacto(')
        pytest.fail(
            f"HALLAZGO (a): dataset_entrenamiento_hash solo pasa por _validar_hash_sha256_campo() "
            f"(formato: 64 hex) -- self._verificar_hash_artefacto() (la unica funcion que SI "
            f"recalcula un hash contra contenido real) se invoca {llamadas_verificacion_contenido} "
            f"vez(ces) en todo el archivo, siempre para hash_artefacto_sha256, nunca para "
            f"dataset_entrenamiento_hash. El sistema no puede detectar un "
            f"dataset_entrenamiento_hash falso -- lo acepta con solo que tenga el formato correcto."
        ) if se_valida_formato and llamadas_verificacion_contenido == 1 else None


class TestSubCasoDRecalculoDeHashConfirmadoCorrecto:
    def test_alteracion_de_1_byte_es_detectada_y_rechazada(self):
        uc = _use_case()
        archivo_bytes = b'\x08' + b'contenido_del_modelo_de_prueba'
        hash_correcto = hashlib.sha256(archivo_bytes).hexdigest()
        archivo_alterado = archivo_bytes[:-1] + bytes([archivo_bytes[-1] ^ 0xFF])  # altera 1 byte

        with pytest.raises(BusinessRuleError) as exc_info:
            uc._verificar_hash_artefacto(archivo_alterado, hash_correcto, uuid.uuid4())
        assert exc_info.value.code == 'HASH_ARTEFACTO_NO_COINCIDE'

    def test_hash_identico_no_lanza_error(self):
        uc = _use_case()
        archivo_bytes = b'\x08' + b'contenido_del_modelo_de_prueba'
        hash_correcto = hashlib.sha256(archivo_bytes).hexdigest()
        uc._verificar_hash_artefacto(archivo_bytes, hash_correcto, uuid.uuid4())  # no debe lanzar


class TestSubCasoENomenclaturaYRegistroDeFalloDeHashNoCoinciden:
    def test_el_codigo_de_error_real_no_es_error_hash(self):
        uc = _use_case()
        with pytest.raises(BusinessRuleError) as exc_info:
            uc._verificar_hash_artefacto(b'contenido', 'a' * 64, uuid.uuid4())
        pytest.fail(
            f"HALLAZGO (e): el codigo de error real es '{exc_info.value.code}', no 'ERROR_HASH' "
            f"como pide la ficha. Tampoco se crea ningun registro 'REENTRENAMIENTO_FALLIDO' -- "
            f"se lanza una excepcion HTTP y se audita como 'HASH_INVALIDO_DETECTADO' (otro "
            f"nombre distinto tambien)."
        ) if exc_info.value.code == 'HASH_ARTEFACTO_NO_COINCIDE' else None


class TestSubCasoFElHashCorrespondeAlArchivoRealmenteEntregado:
    def test_se_hashea_el_mismo_objeto_bytes_que_se_guarda(self):
        archivo = REPO_ROOT / 'src/prediction/application/use_cases/versiones_modelo/registrar_version_modelo_use_case.py'
        texto = archivo.read_text(encoding='utf-8')
        assert 'archivo_bytes = dto.archivo_modelo.file.read()' in texto
        assert 'self._guardar_artefacto(archivo_bytes' in texto
