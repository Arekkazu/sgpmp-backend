"""Caso de uso: Registrar etapa del ciclo productivo (Flujo A — RF-16)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.configuration.domain.entities.ciclo_biologico import CicloBiologico
from src.configuration.domain.repositories.auditoria_ciclo_repository import AuditoriaCicloRepository
from src.configuration.domain.repositories.ciclo_biologico_repository import CicloBiologicoRepository
from src.configuration.domain.repositories.especie_repository import EspecieRepository
from src.configuration.domain.value_objects.duracion_dias import DuracionDias
from src.configuration.domain.value_objects.nombre_etapa import NombreEtapa
from src.configuration.infrastructure.dto.registrar_ciclo_dto import RegistrarCicloDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import BusinessRuleError, ConflictError, NotFoundError


def _snapshot(ciclo: CicloBiologico) -> dict:
    return {
        "id_ciclo_biologico": ciclo.id_ciclo_biologico,
        "nombre": ciclo.nombre.valor,
        "descripcion": ciclo.descripcion,
        "duracion_dias": ciclo.duracion_dias.valor,
        "id_especie": ciclo.id_especie,
        "es_activo": ciclo.es_activo,
        "fecha_actualizacion": ciclo.fecha_actualizacion.isoformat() if ciclo.fecha_actualizacion else None,
    }


class RegistrarCicloUseCase:

    def __init__(
        self,
        db: Session,
        ciclos_repo: CicloBiologicoRepository,
        especies_repo: EspecieRepository,
        auditoria_repo: AuditoriaCicloRepository,
    ) -> None:
        self.db = db
        self.ciclos_repo = ciclos_repo
        self.especies_repo = especies_repo
        self.auditoria_repo = auditoria_repo

    def execute(self, dto: RegistrarCicloDTO, usuario_actual: UsuarioActual) -> CicloBiologico:
        especie = self.especies_repo.obtener_por_id(dto.id_especie)
        if especie is None:
            raise NotFoundError(
                code="ESPECIE_NO_ENCONTRADA",
                message=f"No existe una especie con ID {dto.id_especie}.",
            )
        if not especie.es_activo:
            raise BusinessRuleError(
                code="ESPECIE_INACTIVA",
                message=f"La especie con ID {dto.id_especie} está inactiva. No se pueden agregar etapas.",
            )

        nombre = NombreEtapa(dto.nombre)
        duracion = DuracionDias(dto.duracion_dias)

        existente = self.ciclos_repo.obtener_por_nombre_y_especie(nombre, dto.id_especie)
        if existente is not None:
            raise ConflictError(
                code="ETAPA_DUPLICADA",
                message=f"Ya existe una etapa con el nombre '{nombre.valor}' para esta especie.",
                field="nombre",
            )

        ciclo = CicloBiologico.crear(
            nombre=nombre,
            duracion_dias=duracion,
            id_especie=dto.id_especie,
            descripcion=dto.descripcion,
        )

        try:
            ciclo_guardado = self.ciclos_repo.guardar(ciclo)
            self.auditoria_repo.registrar(
                id_ciclo_biologico=ciclo_guardado.id_ciclo_biologico,
                id_usuario=usuario_actual.id_usuario,
                tipo_operacion="CREATE",
                valores_nuevos=_snapshot(ciclo_guardado),
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return ciclo_guardado
