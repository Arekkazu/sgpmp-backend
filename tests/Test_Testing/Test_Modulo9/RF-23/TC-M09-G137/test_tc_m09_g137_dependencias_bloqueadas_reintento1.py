"""
TC-M09-G137 (RF-23, G137-02) - Ataques a la superficie de camara - reintento1.

Ficha: "BLOQUEADO (dependencia de RF-22 camara y de RF-23 fps)."

Este TC no tiene nada propio que verificar en codigo mas alla de confirmar
que sus DOS precondiciones (TC-M09-G134 y TC-M09-G136) siguen bloqueadas --
si cualquiera de las dos se desbloquea, este TC pasa a ser evaluable y debe
re-escribirse con casos reales de ataque a la superficie de camara (fuzzing
de `fps`/resolucion, etc.), no antes.

Como correrlo:
    python -m pytest tests/Test_Testing/Test_Modulo9/RF-23/TC-M09-G137/test_tc_m09_g137_dependencias_bloqueadas_reintento1.py -v \
        --html=resultados/resultado_TC-M09-G137_reintento1.html --self-contained-html
"""
from __future__ import annotations

from src.configuration.infrastructure.dto.asociar_sensor_area_dto import AsociarSensorAreaDTO
from src.configuration.infrastructure.dto.configurar_remotamente_dto import ConfigurarRemotamenteDTO


class TestTCM09G137DependenciasBloqueadas:
    """TC-M09-G137 / G137-02: confirma que ambas precondiciones (G134, G136) siguen bloqueadas."""

    def test_precondicion_rf22_camara_sigue_bloqueada(self):
        """Espejo de TC-M09-G134: sin campo de camara en AsociarSensorAreaDTO."""
        campos = set(AsociarSensorAreaDTO.model_fields.keys())
        assert not any("camara" in c.lower() or "categoria" in c.lower() for c in campos), (
            "Precondicion RF-22 (camara) parece desbloqueada -- revisar TC-M09-G134 "
            "antes de seguir asumiendo que G137 esta bloqueado."
        )

    def test_precondicion_rf23_fps_sigue_bloqueada(self):
        """Espejo de TC-M09-G136: sin fps en el contrato de escritura de configurar."""
        campos = set(ConfigurarRemotamenteDTO.model_fields.keys())
        assert "fps" not in campos, (
            "Precondicion RF-23 (fps) parece desbloqueada -- revisar TC-M09-G136 "
            "antes de seguir asumiendo que G137 esta bloqueado."
        )

    def test_g137_sigue_bloqueado_mientras_ambas_precondiciones_lo_esten(self):
        campos_asociar = set(AsociarSensorAreaDTO.model_fields.keys())
        campos_configurar = set(ConfigurarRemotamenteDTO.model_fields.keys())
        camara_bloqueada = not any(
            "camara" in c.lower() or "categoria" in c.lower() for c in campos_asociar
        )
        fps_bloqueado = "fps" not in campos_configurar
        assert camara_bloqueada and fps_bloqueado, (
            "Al menos una precondicion se desbloqueo -- TC-M09-G137 ya se puede "
            "re-evaluar con casos reales de ataque a la superficie de camara."
        )
