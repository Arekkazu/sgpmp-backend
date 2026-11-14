"""
TC-M09-G134 (RF-22, G134-02) - Asociacion camara->area - reintento1.

Ficha: "BLOQUEADO. RF-22 v1.2 no tiene campo para identificar una camara
(`AsociarSensorAreaDTO` solo acepta `id_dispositivo_iot` y
`punto_instalacion`). Se desbloquea cuando RF-22 publique el campo y los
codigos de flujo alterno."

Confirmacion estructural (no de ejecucion en vivo): se leen los campos
reales declarados en `AsociarSensorAreaDTO` y se verifica que no existe
ningun campo que distinga "camara" de "sensor" (ni por nombre de campo ni
por un enum/categoria). Esto es consistente con TC-M09-G130 (RF-21, "CAMARA
no implementado") y con TC-M09-G136 (RF-23, sin `fps`) -- la nocion de
"camara" como categoria de dispositivo simplemente no existe en el backend
actual, en ningun endpoint de configuracion revisado esta sesion.

Como correrlo:
    python -m pytest tests/Test_Testing/Test_Modulo9/RF-22/TC-M09-G134/test_tc_m09_g134_sin_campo_camara_reintento1.py -v \
        --html=resultados/resultado_TC-M09-G134_reintento1.html --self-contained-html
"""
from __future__ import annotations

from src.configuration.infrastructure.dto.asociar_sensor_area_dto import AsociarSensorAreaDTO

_CAMPOS_ESPERADOS = {"id_dispositivo_iot", "id_infraestructura", "punto_instalacion", "confirmar"}
_PALABRAS_CAMARA = ("camara", "camera", "categoria")


class TestTCM09G134SinCampoCamara:
    """TC-M09-G134 / G134-02: confirma estructuralmente el bloqueo (sin campo de camara)."""

    def test_asociar_sensor_area_dto_no_tiene_campo_de_camara(self):
        campos_declarados = set(AsociarSensorAreaDTO.model_fields.keys())
        assert campos_declarados == _CAMPOS_ESPERADOS, (
            f"BLOQUEO LEVANTADO (o cambio inesperado): se esperaba exactamente "
            f"{_CAMPOS_ESPERADOS!r}; se encontraron {campos_declarados!r}. Si aparecio "
            f"un campo nuevo relacionado a camara, revisar si TC-M09-G134/G136/G137 "
            f"se pueden desbloquear."
        )
        for campo in campos_declarados:
            for palabra in _PALABRAS_CAMARA:
                assert palabra not in campo.lower(), (
                    f"Aparecio un campo relacionado a camara/categoria ('{campo}') -- "
                    f"reabrir TC-M09-G134, puede estar desbloqueado."
                )

    def test_dto_no_tiene_un_enum_o_catalogo_de_categoria(self):
        """Barrido del propio archivo fuente del DTO: ni una mencion de
        'camara'/'categoria' en el texto (ni siquiera en comentarios, para
        detectar tambien un bloqueo a medio implementar)."""
        import inspect

        codigo_fuente = inspect.getsource(AsociarSensorAreaDTO)
        for palabra in _PALABRAS_CAMARA:
            assert palabra not in codigo_fuente.lower(), (
                f"El DTO ya menciona '{palabra}' en su codigo fuente -- revisar si "
                f"el bloqueo de TC-M09-G134 sigue vigente."
            )
