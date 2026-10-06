"""Reglas de RF-20 v1.1 (RFC-009) compartidas por registrar y editar un área.

La especie del área debe existir y estar activa, y el `tipo_modelo_asignado`
(opcional) debe coincidir con la familia de modelo de esa especie
(`especies.tipo_modelo`). El meta-modelo de contagio nunca se asigna a un área.
"""
from __future__ import annotations

from typing import Optional

from src.configuration.domain.entities.especie import Especie
from src.configuration.domain.repositories.especie_repository import EspecieRepository
from src.shared.errors import BusinessRuleError
from src.shared.tipo_modelo import TIPOS_MODELO_ASIGNABLES


def validar_especie_y_modelo(
    especie_repo: EspecieRepository,
    id_especie: int,
    tipo_modelo_asignado: Optional[str],
    *,
    exigir_activa: bool = True,
) -> Especie:
    especie = especie_repo.obtener_por_id(id_especie)
    if especie is None or (exigir_activa and not especie.es_activo):
        raise BusinessRuleError(
            code="ESPECIE_INVALIDA",
            message="Especie inválida: la especie seleccionada no existe o está inactiva.",
            field="especie_id",
        )
    if tipo_modelo_asignado is not None and (
        tipo_modelo_asignado not in TIPOS_MODELO_ASIGNABLES
        or tipo_modelo_asignado != especie.tipo_modelo
    ):
        raise BusinessRuleError(
            code="INCOHERENCIA_ESPECIE_MODELO",
            message=(
                f"Incoherencia de configuración: el modelo '{tipo_modelo_asignado}' no corresponde "
                f"a la especie '{especie.nombre.valor}' del área. Seleccione un modelo compatible."
            ),
            field="tipo_modelo_asignado",
        )
    return especie
