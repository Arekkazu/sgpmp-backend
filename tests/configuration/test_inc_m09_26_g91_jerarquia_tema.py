"""INC-M09-26-G91 — Jerarquía de resolución del tema visual (RF-27).

QA no contaba con un estado de datos controlado para ejecutar, sin afectar
otras pruebas, los dos niveles de la jerarquía distintos de "preferencia
personal presente": ni personal ni global es un caso especialmente delicado
porque el tema global es un singleton compartido por todo el ambiente de
dev (`uq_tema_global`), así que vaciarlo ahí afectaría a cualquier otra
cuenta sin preferencia personal en pruebas concurrentes.

Este test fija con fakes (sin BD) los tres niveles de
`ObtenerTemaResueltoUseCase.execute()` para dejar la jerarquía verificada de
forma reproducible. Para el nivel 2 (personal ausente, global presente) en
vivo contra dev, usar la cuenta `productor.ajeno.test@pecuaria.co`
(id_usuario=60): no tiene fila en `modulo9.temas_visuales`.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from src.configuration.application.use_cases.personalizacion.obtener_tema_resuelto_use_case import ObtenerTemaResueltoUseCase
from src.configuration.domain.entities.tema_visual import TemaVisual, ThemeMode
from src.identity_access.infrastructure.dependencies import UsuarioActual

ID_USUARIO = 60


class TemaRepoFake:
    def __init__(self, personal: Optional[TemaVisual], global_: Optional[TemaVisual]) -> None:
        self._personal = personal
        self._global = global_

    def obtener_por_usuario(self, id_usuario: int) -> Optional[TemaVisual]:
        return self._personal

    def obtener_global(self) -> Optional[TemaVisual]:
        return self._global


def _usuario() -> UsuarioActual:
    return UsuarioActual(id_usuario=ID_USUARIO, id_token=1, id_rol=2, id_estado_cuenta=2)


def test_con_preferencia_personal_gana_sobre_global() -> None:
    personal = TemaVisual(id_usuario=ID_USUARIO, theme_mode=ThemeMode.OSCURO, es_global=False,
                           fecha_actualizacion=datetime.now(timezone.utc), id_tema_visual=1)
    global_ = TemaVisual(id_usuario=1, theme_mode=ThemeMode.CLARO, es_global=True,
                          fecha_actualizacion=datetime.now(timezone.utc), id_tema_visual=2)
    uc = ObtenerTemaResueltoUseCase(tema_repo=TemaRepoFake(personal, global_))

    resultado = uc.execute(_usuario())

    assert resultado == {"theme_mode": ThemeMode.OSCURO.value, "fuente": "personal", "id_tema_visual": 1}


def test_sin_personal_cae_a_global() -> None:
    global_ = TemaVisual(id_usuario=1, theme_mode=ThemeMode.OSCURO, es_global=True,
                          fecha_actualizacion=datetime.now(timezone.utc), id_tema_visual=2)
    uc = ObtenerTemaResueltoUseCase(tema_repo=TemaRepoFake(None, global_))

    resultado = uc.execute(_usuario())

    assert resultado["fuente"] == "global"
    assert resultado["id_tema_visual"] == 2
    assert resultado["theme_mode"] == ThemeMode.OSCURO.value


def test_sin_personal_ni_global_cae_al_defecto_claro() -> None:
    uc = ObtenerTemaResueltoUseCase(tema_repo=TemaRepoFake(None, None))

    resultado = uc.execute(_usuario())

    assert resultado == {"theme_mode": ThemeMode.CLARO.value, "fuente": "defecto", "id_tema_visual": None}


if __name__ == "__main__":
    test_con_preferencia_personal_gana_sobre_global()
    test_sin_personal_cae_a_global()
    test_sin_personal_ni_global_cae_al_defecto_claro()
    print("OK")
