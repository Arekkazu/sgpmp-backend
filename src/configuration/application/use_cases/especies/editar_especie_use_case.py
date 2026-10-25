# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-20 | Arekkazu | DEV-19 RF-15: edita esperanza_vida_dias (omitida conserva); snapshot desde la entidad |
# | 2026-10-20 | Arekkazu | DEV-21 RF-15: bajar la densidad que deja un área excedida → 422 (RFC-012) |
"""Caso de uso: Editar especie existente del catálogo (Flujo B — RF-15).

Administrador e Ingeniero de Campo pueden editar. Concurrencia optimista
mediante ``fecha_actualizacion``: si el valor enviado difiere del almacenado,
la especie fue modificada por otro usuario y se rechaza la operación (412).
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.configuration.domain.entities.especie import Especie
from src.configuration.domain.repositories.auditoria_especie_repository import AuditoriaEspecieRepository
from src.configuration.domain.repositories.especie_repository import EspecieRepository
from src.configuration.domain.value_objects.nombre_especie import NombreEspecie
from src.configuration.infrastructure.dto.editar_especie_dto import EditarEspecieDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import BusinessRuleError, ConflictError, NotFoundError, PreconditionFailedError
from src.configuration.domain.services.capacidad_area import validar_reduccion_densidad
from src.shared.tipo_modelo import tipo_modelo_de_grupo



class EditarEspecieUseCase:
    """Modifica nombre y/o descripción de una especie activa."""

    def __init__(
        self,
        db: Session,
        especies_repo: EspecieRepository,
        auditoria_repo: AuditoriaEspecieRepository,
    ) -> None:
        self.db = db
        self.especies_repo = especies_repo
        self.auditoria_repo = auditoria_repo

    def execute(self, id_especie: int, dto: EditarEspecieDTO, usuario_actual: UsuarioActual) -> Especie:
        especie = self.especies_repo.obtener_por_id(id_especie, bloquear=True)
        if especie is None:
            raise NotFoundError(
                code="ESPECIE_NO_ENCONTRADA",
                message=f"No existe una especie con ID {id_especie}.",
            )

        if not especie.es_activo:
            raise BusinessRuleError(
                code="ESPECIE_INACTIVA",
                message="No se puede editar una especie inactiva. Reactívela primero.",
            )

        # Concurrencia optimista: rechazar si la especie fue modificada desde que el cliente la cargó.
        # Normalizar ambas a UTC para comparar con seguridad aunque varíe el tzinfo.
        ts_actual = especie.fecha_actualizacion
        ts_dto = dto.fecha_actualizacion
        if ts_actual is not None and ts_dto is not None:
            if ts_actual.astimezone(timezone.utc) != ts_dto.astimezone(timezone.utc):
                raise PreconditionFailedError(
                    code="CONFLICTO_CONCURRENCIA",
                    message="La especie fue modificada por otro usuario. Recargue los datos e intente de nuevo.",
                )
        elif ts_actual != ts_dto:
            raise PreconditionFailedError(
                code="CONFLICTO_CONCURRENCIA",
                message="La especie fue modificada por otro usuario. Recargue los datos e intente de nuevo.",
            )

        nombre_nuevo = NombreEspecie(dto.nombre)
        if nombre_nuevo.normalizado() != especie.nombre.normalizado():
            duplicado = self.especies_repo.obtener_por_nombre(nombre_nuevo)
            if duplicado is not None and duplicado.id_especie != especie.id_especie:
                raise ConflictError(
                    code="ESPECIE_DUPLICADA",
                    message=f"El nombre '{nombre_nuevo.valor}' ya pertenece a otra especie del catálogo.",
                    field="nombre",
                )

        snapshot_anterior = especie._snapshot()

        densidad_maxima = especie.densidad_maxima_por_especie
        if "densidad_maxima_por_especie" in dto.model_fields_set:
            densidad_maxima = dto.densidad_maxima_por_especie
            anterior = especie.densidad_maxima_por_especie
            # RFC-012: no se reduce (ni se define por primera vez) por debajo de lo que
            # dejaría un área donde la especie está con más individuos que su techo.
            if densidad_maxima is not None and (anterior is None or densidad_maxima < anterior):
                validar_reduccion_densidad(
                    especie.nombre.valor, id_especie, densidad_maxima,
                    self.especies_repo.listar_areas_ocupadas(id_especie),
                )
        esperanza_vida = especie.esperanza_vida_dias
        if "esperanza_vida_dias" in dto.model_fields_set:
            esperanza_vida = dto.esperanza_vida_dias
        # Omitido conserva el grupo actual (el DTO no acepta vaciarlo).
        grupo_manejo = dto.grupo_manejo if "grupo_manejo" in dto.model_fields_set else especie.grupo_manejo
        if grupo_manejo != especie.grupo_manejo:
            # RF-20 v1.1: el cambio no puede dejar áreas con un modelo incoherente.
            cantidad = self.especies_repo.contar_areas_con_modelo_distinto(
                id_especie, tipo_modelo_de_grupo(grupo_manejo)
            )
            if cantidad:
                raise BusinessRuleError(
                    code="ESPECIE_CON_AREAS_DE_OTRO_MODELO",
                    message=(
                        f"Operación denegada: la especie '{especie.nombre.valor}' tiene {cantidad} áreas "
                        "productivas con un modelo de IA que no corresponde al nuevo grupo de manejo. "
                        "Reasigne o quite el modelo de esas áreas antes de cambiar el grupo de la especie."
                    ),
                    field="grupo_manejo",
                )
            # RF-15 v1.1: tampoco con activos alojados. Asignar el primer grupo a una
            # especie que no lo tenía no es un cambio y no se bloquea.
            if especie.grupo_manejo is not None:
                activos = self.especies_repo.contar_activos_alojados(id_especie)
                if activos:
                    raise BusinessRuleError(
                        code="ESPECIE_CON_ACTIVOS_ALOJADOS",
                        message=(
                            f"Operación denegada: la especie '{especie.nombre.valor}' tiene {activos} "
                            "activos biológicos alojados. Trasládelos o cierre su ciclo antes de cambiar "
                            "el grupo de manejo."
                        ),
                        field="grupo_manejo",
                    )

        especie.actualizar(
            nombre=nombre_nuevo,
            descripcion=dto.descripcion,
            densidad_maxima_por_especie=densidad_maxima,
            fecha_actualizacion=datetime.now(timezone.utc),
            grupo_manejo=grupo_manejo,
            esperanza_vida_dias=esperanza_vida,
        )

        try:
            especie_actualizada = self.especies_repo.actualizar(especie)
            self.auditoria_repo.registrar(
                id_especie=especie_actualizada.id_especie,
                id_usuario=usuario_actual.id_usuario,
                tipo_operacion="UPDATE",
                valores_anteriores=snapshot_anterior,
                valores_nuevos=especie_actualizada._snapshot(),
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return especie_actualizada
