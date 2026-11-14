# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-20 | Arekkazu | DEV-22 RF-20: valida 1..N especies del mismo grupo de manejo (RFC-012) |
"""Reglas de RF-20 compartidas por registrar y editar un área.

RFC-009: cada especie debe existir y estar activa, y el `tipo_modelo_asignado`
(opcional) debe coincidir con el modelo que mapea su grupo de manejo. El
meta-modelo de contagio nunca se asigna a un área.

RFC-012 (R-MULTIESPECIE-01): el área tiene 1..N especies y todas comparten
`grupo_manejo`, así que el modelo se valida contra el grupo común.
"""
from __future__ import annotations

from typing import Iterable, Optional

from src.configuration.domain.entities.especie import Especie
from src.configuration.domain.repositories.especie_repository import EspecieRepository
from src.configuration.domain.services.capacidad_area import EspecieDelArea, validar_mismo_grupo
from src.shared.errors import BusinessRuleError
from src.shared.tipo_modelo import TIPOS_MODELO_ASIGNABLES


def a_especie_del_area(especie: Especie) -> EspecieDelArea:
    return EspecieDelArea(
        id_especie=especie.id_especie,
        nombre=especie.nombre.valor,
        grupo_manejo=especie.grupo_manejo,
        densidad=especie.densidad_maxima_por_especie,
    )


def validar_especies_y_modelo(
    especie_repo: EspecieRepository,
    id_especies: list[int],
    tipo_modelo_asignado: Optional[str],
    *,
    nombre_area: str,
    exigir_activas: Optional[Iterable[int]] = None,
) -> list[Especie]:
    """Devuelve las especies en el orden recibido.

    ``exigir_activas``: ids que deben estar activos; ``None`` = todos. En la edición
    solo se exige a las que se agregan: una especie desactivada después no bloquea
    editar el resto del área.
    """
    exigir = set(id_especies if exigir_activas is None else exigir_activas)
    especies: list[Especie] = []
    for id_especie in id_especies:
        especie = especie_repo.obtener_por_id(id_especie)
        if especie is None or (id_especie in exigir and not especie.es_activo):
            raise BusinessRuleError(
                code="ESPECIE_INVALIDA",
                message="Especie inválida: la especie seleccionada no existe o está inactiva.",
                field="especies",
            )
        especies.append(especie)

    validar_mismo_grupo(nombre_area, [a_especie_del_area(e) for e in especies])

    modelo_comun = especies[0].tipo_modelo
    if tipo_modelo_asignado is not None and (
        tipo_modelo_asignado not in TIPOS_MODELO_ASIGNABLES or tipo_modelo_asignado != modelo_comun
    ):
        raise BusinessRuleError(
            code="INCOHERENCIA_ESPECIE_MODELO",
            message=(
                f"Incoherencia de configuración: el modelo '{tipo_modelo_asignado}' no corresponde "
                f"a la especie '{especies[0].nombre.valor}' del área. Seleccione un modelo compatible."
            ),
            field="tipo_modelo_asignado",
        )
    return especies
