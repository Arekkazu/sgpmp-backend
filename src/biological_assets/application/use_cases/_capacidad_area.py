# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-23 | destroyerban | DEV-23 RF-33/36/48: capacidad efectiva del área al entrar individuos (RFC-012) |
"""Regla de capacidad por densidad cuando entran individuos a un área (RFC-012 v1.1).

La aplican el registro (RF-33), el ingreso a un lote (RF-36) y la transferencia (RF-48):

1. Si la especie entrante aún no está asociada al área, debe compartir el
   ``grupo_manejo`` de las presentes (R-MULTIESPECIE-01) y se asocia como parte de la
   operación (422 si el grupo difiere).
2. Todas las especies del área, incluida la entrante, deben tener densidad (422).
3. ``Σ individuos del área + entrantes ≤ floor(MIN(densidad, entrante incluida) × superficie)``
   (422). Si el entrante baja el MIN, se rechaza al entrante; nunca se toca lo alojado (H-12.3).

La regla misma vive en ``capacidad_area`` de M09 (DEV-22): aquí solo se arma la
carga resultante y se apunta el error al campo del área en M02.
"""
from __future__ import annotations

from decimal import Decimal

from src.biological_assets.domain.repositories.infraestructura_consulta_port import (
    InfraestructuraConsulta,
    InfraestructuraConsultaPort,
)
from src.configuration.domain.services.capacidad_area import (
    EspecieDelArea,
    capacidad_efectiva,
    validar_capacidad,
    validar_mismo_grupo,
)
from src.shared.errors import BusinessRuleError, ValidationError


def _especies_tras_la_entrada(
    infra_port: InfraestructuraConsultaPort, infra: InfraestructuraConsulta, id_especie: int,
) -> tuple[list[EspecieDelArea], bool]:
    """Especies presentes tras la entrada y si la entrante hay que asociarla al área."""
    if id_especie in infra.id_especies:
        return list(infra.especies), False
    entrante = infra_port.obtener_especie(id_especie)
    if entrante is None:
        raise ValidationError(
            code='ESPECIE_INVALIDA',
            message=f'La especie con id {id_especie} no existe o no está activa.',
            field='id_especie',
        )
    return [*infra.especies, entrante], True


def validar_entrada_al_area(
    infra_port: InfraestructuraConsultaPort,
    infra: InfraestructuraConsulta,
    *,
    id_especie: int,
    entrantes: int,
    field: str,
) -> bool:
    """422 si los ``entrantes`` individuos de ``id_especie`` no caben en ``infra``.

    ``infra_port.calcular_ocupacion`` no debe contar todavía a los entrantes. Serializa
    en la transacción las entradas al mismo área, para que dos altas simultáneas no
    pasen ambas el chequeo. Devuelve True si la especie debe asociarse al área.
    """
    infra_port.bloquear_capacidad(infra.id_infraestructura)
    especies, asociar = _especies_tras_la_entrada(infra_port, infra, id_especie)
    try:
        if asociar:
            validar_mismo_grupo(infra.nombre, especies)
        if infra.superficie is None or infra.superficie <= 0:
            raise BusinessRuleError(
                code='SUPERFICIE_INFRAESTRUCTURA_INVALIDA',
                message='La infraestructura debe tener una superficie mayor a cero para calcular su capacidad.',
            )
        validar_capacidad(
            nombre_area=infra.nombre,
            superficie=infra.superficie,
            especies=especies,
            carga_resultante=infra_port.calcular_ocupacion(infra.id_infraestructura) + entrantes,
        )
    except BusinessRuleError as exc:
        exc.field = field  # el área es el campo de entrada en M02, no "especies" de M09
        raise
    return asociar


def admite_entrada(
    infra: InfraestructuraConsulta,
    entrante: EspecieDelArea,
    *,
    ocupacion: int,
    entrantes: int,
) -> bool:
    """La misma regla sin errores, para listar destinos (RF-48): grupo, densidades y cupo."""
    especies = list(infra.especies)
    if entrante.id_especie not in infra.id_especies:
        especies.append(entrante)
        if any(e.grupo_manejo != entrante.grupo_manejo for e in infra.especies):
            return False
    if infra.superficie is None or infra.superficie <= 0:
        return False
    capacidad = capacidad_efectiva(Decimal(infra.superficie), especies)
    return capacidad is not None and ocupacion + entrantes <= capacidad
