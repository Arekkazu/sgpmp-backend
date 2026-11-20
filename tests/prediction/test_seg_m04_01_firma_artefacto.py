# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-19 | Arekkazu | SEG-M04-01 RF-69: firma del artefacto al registrar y antes de correr en el motor |
"""SEG-M04-01: sin firma válida no se registra ni corre en el motor una versión de modelo."""
import hashlib
from unittest.mock import Mock

import pytest

from src.prediction.application.use_cases.versiones_modelo.registrar_version_modelo_use_case import (
    RegistrarVersionModeloUseCase,
)
from src.prediction.domain.services.firma_artefacto import firmar, sha256_archivo
from src.shared.errors import BusinessRuleError, ServiceUnavailableError
from tests.prediction.test_rfc010_version_por_animal_y_sombra import _version

pytestmark = pytest.mark.firma_real
CLAVE = "clave-de-firma"


def test_registro_exige_la_clave_y_una_firma_valida(monkeypatch):
    caso = RegistrarVersionModeloUseCase(db=Mock(), repo=Mock(), auditoria_repo=Mock(), variable_port=Mock(),
                                         aviso_port=Mock())
    sha = "a" * 64
    monkeypatch.delenv("M04_FIRMA_MODELOS_KEY", raising=False)
    with pytest.raises(ServiceUnavailableError):
        caso._verificar_firma(sha, firmar(sha, CLAVE), "proceso")
    monkeypatch.setenv("M04_FIRMA_MODELOS_KEY", CLAVE)
    assert caso._verificar_firma(sha, firmar(sha, CLAVE).upper(), "proceso") == firmar(sha, CLAVE)
    for firma in (None, firmar(sha, "otra-clave")):
        with pytest.raises(BusinessRuleError) as e:
            caso._verificar_firma(sha, firma, "proceso")
        assert e.value.code == "FIRMA_ARTEFACTO_INVALIDA"
    evento = caso._auditoria_repo.registrar.call_args.kwargs
    assert evento["tipo_evento"] == "HASH_INVALIDO_DETECTADO" and evento["payload_evento"]["motivo"] == "FIRMA_ARTEFACTO_INVALIDA"


def test_antes_del_motor_se_verifica_el_archivo_en_disco_y_su_firma(tmp_path):
    ruta = tmp_path / "modelo.onnx"
    ruta.write_bytes(b"\x08modelo")
    sha = hashlib.sha256(b"\x08modelo").hexdigest()
    version = _version()
    version.ruta_artefacto, version.hash_artefacto_sha256 = str(ruta), sha
    version.firma_artefacto = firmar(sha, CLAVE)
    version.exigir_artefacto_integro(sha256_archivo(str(ruta)), CLAVE)

    with pytest.raises(BusinessRuleError) as sin_firma:
        version.exigir_artefacto_integro(sha256_archivo(str(ruta)), "otra-clave")
    assert sin_firma.value.code == "FIRMA_ARTEFACTO_INVALIDA"
    ruta.write_bytes(b"\x08cambiado")
    with pytest.raises(BusinessRuleError) as alterado:
        version.exigir_artefacto_integro(sha256_archivo(str(ruta)), CLAVE)
    assert alterado.value.code == "ARTEFACTO_ALTERADO"
