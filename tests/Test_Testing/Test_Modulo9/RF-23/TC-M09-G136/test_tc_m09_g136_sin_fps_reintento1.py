"""
TC-M09-G136 (RF-23, G136-02) - Parametros por categoria / fps - reintento1.

Ficha: "BLOQUEADO. `ConfigurarRemotamenteDTO` no tiene `fps`, y RF-23 v1.1
no define que codigo devuelve enviar `frecuencia_captura` a una CAMARA
(§8.2). Bloqueo heredado de G134-02 (las precondiciones exigen asociacion
a area)."

Confirmacion estructural: se leen los campos reales de
`ConfigurarRemotamenteDTO` (solo `frecuencia_captura`/`intervalo_transmision`,
ya documentado tambien para TC-M09-G69) y se confirma que no existe `fps`
en ninguna parte del contrato de configuracion remota. El dispositivo
`GET /configuracion/dispositivos-iot/{id}` SI expone un campo `fps` en la
RESPUESTA (hallazgo de TC-M09-G57: siempre null, atributo "de vision" sin
uso real) -- pero eso es lectura, no el contrato de escritura que este TC
necesita para configurar remotamente una camara. Se verifican ambos.

Como correrlo:
    python -m pytest tests/Test_Testing/Test_Modulo9/RF-23/TC-M09-G136/test_tc_m09_g136_sin_fps_reintento1.py -v \
        --html=resultados/resultado_TC-M09-G136_reintento1.html --self-contained-html
"""
from __future__ import annotations

from src.configuration.infrastructure.dto.configurar_remotamente_dto import ConfigurarRemotamenteDTO

_CAMPOS_ESPERADOS = {"frecuencia_captura", "intervalo_transmision"}


class TestTCM09G136SinFps:
    """TC-M09-G136 / G136-02: confirma estructuralmente el bloqueo (sin `fps` en el contrato de escritura)."""

    def test_configurar_remotamente_dto_no_tiene_fps(self):
        campos_declarados = set(ConfigurarRemotamenteDTO.model_fields.keys())
        assert campos_declarados == _CAMPOS_ESPERADOS, (
            f"BLOQUEO LEVANTADO (o cambio inesperado): se esperaba exactamente "
            f"{_CAMPOS_ESPERADOS!r}; se encontraron {campos_declarados!r}. Si aparecio "
            f"'fps', revisar si TC-M09-G136/G137 se pueden desbloquear."
        )
        assert "fps" not in campos_declarados

    def test_fps_de_respuesta_de_dispositivo_no_es_configurable(self):
        """El 'fps' que SI existe (TC-M09-G57) es de solo lectura en la
        respuesta de GET /dispositivos-iot/{id}, no del contrato de escritura
        de /configurar -- confirmar que son contratos distintos, no el mismo
        campo con otro nombre."""
        campos_configurar = set(ConfigurarRemotamenteDTO.model_fields.keys())
        assert "fps" not in campos_configurar, (
            "El DTO de escritura (configurar) no debe compartir el campo de solo "
            "lectura 'fps' de la respuesta de dispositivo."
        )
