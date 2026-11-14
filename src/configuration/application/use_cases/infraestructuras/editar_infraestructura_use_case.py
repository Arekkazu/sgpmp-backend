# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-20 | Arekkazu | DEV-22 RF-20: edita 1..N especies, retiro con activos y capacidad efectiva (422) |
"""Caso de uso: Editar área productiva (PATCH RF-20). Concurrencia optimista (FA-14)."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.configuration.application.use_cases.infraestructuras._coherencia_especie_modelo import (
    a_especie_del_area,
    validar_especies_y_modelo,
)
from src.configuration.application.use_cases.infraestructuras.propagar_tipo_modelo_edge import PropagadorTipoModeloEdge
from src.configuration.domain.entities.infraestructura import Infraestructura
from src.configuration.domain.repositories.auditoria_infraestructura_repository import AuditoriaInfraestructuraRepository
from src.configuration.domain.repositories.especie_repository import EspecieRepository
from src.configuration.domain.repositories.infraestructura_dependency_port import InfraestructuraDependencyPort
from src.configuration.domain.repositories.finca_repository import FincaRepository
from src.configuration.domain.repositories.infraestructura_repository import InfraestructuraRepository
from src.configuration.domain.repositories.tipo_area_repository import TipoAreaRepository
from src.configuration.domain.services.capacidad_area import validar_capacidad
from src.configuration.domain.value_objects.nombre_infraestructura import NombreInfraestructura
from src.configuration.domain.value_objects.superficie import Superficie
from src.configuration.infrastructure.dto.editar_infraestructura_dto import EditarInfraestructuraDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import BusinessRuleError, NotFoundError, PreconditionFailedError, ValidationError


class EditarInfraestructuraUseCase:
    """Edita un área con concurrencia optimista (412).

    El tipo debe existir en el catálogo de tipos de área. RFC-012: no se puede
    retirar una especie con activos alojados, y si el área aloja individuos, agregar
    especies o cambiar la superficie se valida contra la capacidad efectiva (422).
    """

    def __init__(
        self,
        db: Session,
        infra_repo: InfraestructuraRepository,
        finca_repo: FincaRepository,
        tipo_area_repo: TipoAreaRepository,
        auditoria_repo: AuditoriaInfraestructuraRepository,
        especie_repo: EspecieRepository,
        dependency_port: InfraestructuraDependencyPort,
        propagador_tipo_modelo: PropagadorTipoModeloEdge,
    ) -> None:
        self.db = db
        self.infra_repo = infra_repo
        self.finca_repo = finca_repo
        self.tipo_area_repo = tipo_area_repo
        self.auditoria_repo = auditoria_repo
        self.especie_repo = especie_repo
        self.dependency_port = dependency_port
        self.propagador_tipo_modelo = propagador_tipo_modelo

    def execute(
        self, id_infraestructura: int, dto: EditarInfraestructuraDTO, usuario_actual: UsuarioActual
    ) -> Infraestructura:
        infra = self.infra_repo.obtener_por_id(id_infraestructura, bloquear=True)
        if infra is None:
            raise NotFoundError(
                code="INFRAESTRUCTURA_NO_ENCONTRADA",
                message=f"No existe un área productiva con ID {id_infraestructura}.",
            )

        finca = self.finca_repo.obtener_por_id(infra.id_finca)
        if finca is None or not finca.es_activo:
            raise BusinessRuleError(
                code="FINCA_INACTIVA_O_INEXISTENTE",
                message=(
                    "No es posible editar el área productiva porque la finca asociada "
                    "no existe o se encuentra inactiva."
                ),
            )

        ts_actual = infra.fecha_actualizacion
        ts_dto = dto.fecha_actualizacion
        if ts_actual is not None and ts_dto is not None:
            if ts_actual.astimezone(timezone.utc) != ts_dto.astimezone(timezone.utc):
                raise PreconditionFailedError(
                    code="CONFLICTO_CONCURRENCIA",
                    message=(
                        "La información del área ha sido actualizada por otro usuario. "
                        "Por favor, refresque la vista antes de aplicar sus cambios."
                    ),
                )
        elif ts_actual != ts_dto:
            raise PreconditionFailedError(
                code="CONFLICTO_CONCURRENCIA",
                message="El registro fue modificado por otro usuario. Recarga y reintenta.",
            )

        tipo_area = self.tipo_area_repo.obtener_por_nombre(dto.tipo_area)
        if tipo_area is None or not tipo_area.es_activo:
            # RF-20, flujo alterno "Tipo de area no reconocido": el RF lo
            # clasifica como "Dato invalido ... HTTP 400: Bad Request", no como
            # violacion de regla de negocio (422). Vive en el use case y no en el
            # DTO porque el catalogo de tipos es dinamico (tabla, no enum).
            raise ValidationError(
                code="TIPO_AREA_NO_RECONOCIDO",
                message=(
                    f"El tipo de área '{dto.tipo_area}' no corresponde a ningún tipo activo "
                    "en el catálogo de infraestructura productiva."
                ),
                field="tipo_area",
            )

        # Una especie que se desactivó después no bloquea editar el resto del área;
        # solo se exige activa a la que se agrega.
        agregadas = [i for i in dto.especies if i not in infra.id_especies]
        retiradas = [i for i in infra.id_especies if i not in dto.especies]
        especies = validar_especies_y_modelo(
            self.especie_repo, dto.especies, dto.tipo_modelo_asignado,
            nombre_area=infra.nombre.valor, exigir_activas=agregadas,
        )

        if retiradas:
            activos_por_especie = self.dependency_port.contar_activos_por_especie(id_infraestructura)
            for id_especie in retiradas:
                if activos_por_especie.get(id_especie):
                    especie = self.especie_repo.obtener_por_id(id_especie)
                    raise BusinessRuleError(
                        code="ESPECIE_CON_ACTIVOS_ALOJADOS",
                        message=(
                            f"Operación denegada: el área '{infra.nombre.valor}' tiene "
                            f"{activos_por_especie[id_especie]} activos biológicos de la especie "
                            f"'{especie.nombre.valor if especie else id_especie}'. Traslade o desvincule "
                            "los activos antes de retirar la especie del área."
                        ),
                        field="especies",
                    )

        # H-12.3: el techo se evalúa sobre el estado resultante; nunca se expulsa a lo alojado.
        if agregadas or dto.superficie != infra.superficie.valor:
            carga = self.dependency_port.calcular_carga(id_infraestructura)
            if carga:
                validar_capacidad(
                    nombre_area=infra.nombre.valor,
                    superficie=dto.superficie,
                    especies=[a_especie_del_area(e) for e in especies],
                    carga_resultante=carga,
                )

        snapshot_anterior = infra._snapshot()
        cambia_modelo = dto.tipo_modelo_asignado != infra.tipo_modelo_asignado

        nombre = NombreInfraestructura(dto.nombre_infraestructura)
        superficie = Superficie(dto.superficie)

        infra.actualizar(
            nombre=nombre,
            tipo=tipo_area.nombre,
            superficie=superficie,
            descripcion=dto.descripcion_infraestructura,
            fecha_actualizacion=datetime.now(timezone.utc),
            id_especies=dto.especies,
            tipo_modelo_asignado=dto.tipo_modelo_asignado,
            nivel_criticidad=dto.nivel_criticidad,
        )

        try:
            infra_actualizada = self.infra_repo.actualizar(infra)
            self.auditoria_repo.registrar(
                id_infraestructura=infra_actualizada.id_infraestructura,
                id_usuario=usuario_actual.id_usuario,
                tipo_operacion="UPDATE",
                valores_nuevos=infra_actualizada._snapshot(),
                valores_anteriores=snapshot_anterior,
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        # DEV-10 (D-06): solo si cambió el modelo; editar el nombre no reinicia el nodo.
        if cambia_modelo:
            self.propagador_tipo_modelo.propagar(infra_actualizada, usuario_actual.id_usuario)
        return infra_actualizada
