"""Caso de uso: Registrar umbral ambiental con niveles de alerta (Flujo A — RF-17)."""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from src.configuration.domain.entities.nivel_alerta_ambiental import NivelAlertaAmbiental
from src.configuration.domain.entities.umbral_ambiental import UmbralAmbiental
from src.configuration.domain.entities.variable_ambiental import VariableAmbiental
from src.configuration.domain.repositories.auditoria_umbral_repository import AuditoriaUmbralRepository
from src.configuration.domain.repositories.especie_repository import EspecieRepository
from src.configuration.domain.repositories.umbral_ambiental_repository import UmbralAmbientalRepository
from src.configuration.domain.repositories.variable_ambiental_repository import VariableAmbientalRepository
from src.configuration.domain.value_objects.nivel_alerta import NivelAlerta
from src.configuration.infrastructure.dto.registrar_umbral_dto import RegistrarUmbralDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import BusinessRuleError, ConflictError, NotFoundError, ValidationError


def _validar_rangos(
    valor_min: Decimal,
    valor_max: Decimal,
    niveles: list[NivelAlertaAmbiental],
    variable: VariableAmbiental,
) -> None:
    # FA-04: límites físicos de la variable
    if valor_min < variable.valor_fisico_min or valor_max > variable.valor_fisico_max:
        raise ValidationError(
            code='RANGO_FISICO_INVALIDO',
            message=(
                f"Los valores deben estar dentro del rango físico permitido para "
                f"'{variable.nombre}': [{variable.valor_fisico_min}, {variable.valor_fisico_max}] "
                f"{variable.unidad}."
            ),
        )

    # FA-08: cada nivel debe estar dentro del rango general
    for n in niveles:
        if n.limite_inferior < valor_min or n.limite_superior > valor_max:
            raise ValidationError(
                code='NIVEL_FUERA_DE_RANGO',
                message=(
                    f"El nivel '{n.nivel.value}' ({n.limite_inferior}–{n.limite_superior}) "
                    f"cae fuera del rango general [{valor_min}, {valor_max}]."
                ),
            )

    # FA-05: sin solapamiento y cobertura completa [valor_min, valor_max]
    ordenados = sorted(niveles, key=lambda n: n.limite_inferior)
    if ordenados[0].limite_inferior != valor_min:
        raise BusinessRuleError(
            code='SOLAPAMIENTO_NIVELES',
            message=(
                f"El primer nivel debe comenzar en {valor_min} (el mínimo del umbral). "
                f"Actualmente comienza en {ordenados[0].limite_inferior}."
            ),
        )
    if ordenados[-1].limite_superior != valor_max:
        raise BusinessRuleError(
            code='SOLAPAMIENTO_NIVELES',
            message=(
                f"El último nivel debe terminar en {valor_max} (el máximo del umbral). "
                f"Actualmente termina en {ordenados[-1].limite_superior}."
            ),
        )
    for i in range(len(ordenados) - 1):
        if ordenados[i].limite_superior != ordenados[i + 1].limite_inferior:
            raise BusinessRuleError(
                code='SOLAPAMIENTO_NIVELES',
                message=(
                    f"Los niveles de alerta deben ser contiguos sin huecos ni solapamientos. "
                    f"El nivel '{ordenados[i].nivel.value}' termina en {ordenados[i].limite_superior} "
                    f"pero el siguiente comienza en {ordenados[i + 1].limite_inferior}."
                ),
            )


class RegistrarUmbralUseCase:

    def __init__(
        self,
        db: Session,
        umbral_repo: UmbralAmbientalRepository,
        especie_repo: EspecieRepository,
        variable_repo: VariableAmbientalRepository,
        auditoria_repo: AuditoriaUmbralRepository,
    ) -> None:
        self.db = db
        self.umbral_repo = umbral_repo
        self.especie_repo = especie_repo
        self.variable_repo = variable_repo
        self.auditoria_repo = auditoria_repo

    def execute(self, dto: RegistrarUmbralDTO, usuario_actual: UsuarioActual) -> UmbralAmbiental:
        # FA-01: especie activa
        especie = self.especie_repo.obtener_por_id(dto.id_especie)
        if especie is None or not especie.es_activo:
            raise BusinessRuleError(
                code='ESPECIE_INACTIVA',
                message="No se pueden configurar umbrales para una especie inactiva o inexistente.",
                field='id_especie',
            )

        # Variable ambiental existe
        variable = self.variable_repo.obtener_por_id(dto.id_variable_ambiental)
        if variable is None or not variable.es_activo:
            raise NotFoundError(
                code='VARIABLE_AMBIENTAL_NO_ENCONTRADA',
                message=f"No existe una variable ambiental activa con ID {dto.id_variable_ambiental}.",
                field='id_variable_ambiental',
            )

        # Construir entidades de niveles
        niveles = [
            NivelAlertaAmbiental(
                nivel=NivelAlerta.desde_string(n.nivel),
                limite_inferior=n.limite_inferior,
                limite_superior=n.limite_superior,
            )
            for n in dto.niveles
        ]

        _validar_rangos(dto.valor_min, dto.valor_max, niveles, variable)

        # FA-02: unicidad (especie, variable)
        existente = self.umbral_repo.obtener_por_especie_y_variable(
            dto.id_especie, dto.id_variable_ambiental
        )
        if existente is not None:
            raise ConflictError(
                code='UMBRAL_DUPLICADO',
                message=(
                    f"Ya existe un umbral para la variable '{variable.nombre}' "
                    f"en esta especie. Edite la configuración existente."
                ),
            )

        umbral = UmbralAmbiental.crear(
            id_especie=dto.id_especie,
            id_variable_ambiental=dto.id_variable_ambiental,
            unidad_medida=variable.unidad,
            valor_min=dto.valor_min,
            valor_max=dto.valor_max,
            niveles=niveles,
            id_usuario=usuario_actual.id_usuario,
        )

        try:
            umbral_guardado = self.umbral_repo.guardar(umbral)
            self.auditoria_repo.registrar(
                id_umbral_ambiental=umbral_guardado.id_umbral_ambiental,
                id_usuario=usuario_actual.id_usuario,
                tipo_operacion='CREATE',
                valores_nuevos=umbral_guardado._snapshot(),
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return umbral_guardado
