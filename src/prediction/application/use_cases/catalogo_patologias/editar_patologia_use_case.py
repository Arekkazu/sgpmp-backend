from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.prediction.domain.entities.patologia_variable import PatologiaVariable
from src.prediction.domain.repositories.evento_auditoria_m04_repository import EventoAuditoriaM04Repository
from src.prediction.domain.repositories.historial_catalogo_repository import HistorialCatalogoRepository
from src.prediction.domain.repositories.modelo_activo_port import ModeloActivoPort
from src.prediction.domain.repositories.patologia_m04_repository import PatologiaM04Repository
from src.prediction.domain.repositories.variable_i3p1_port import VariableI3P1Port
from src.prediction.infrastructure.dto.editar_patologia_dto import EditarPatologiaDTO
from src.shared.errors import BusinessRuleError, ConflictError, NotFoundError, PreconditionFailedError


class EditarPatologiaUseCase:
    def __init__(
        self,
        *,
        db: Session,
        repo: PatologiaM04Repository,
        historial_repo: HistorialCatalogoRepository,
        auditoria_repo: EventoAuditoriaM04Repository,
        variable_port: VariableI3P1Port,
        modelo_activo_port: ModeloActivoPort,
    ) -> None:
        self._db = db
        self._repo = repo
        self._historial_repo = historial_repo
        self._auditoria_repo = auditoria_repo
        self._variable_port = variable_port
        self._modelo_activo_port = modelo_activo_port

    def execute(self, id_patologia: int, dto: EditarPatologiaDTO, id_usuario: int):
        entidad = self._repo.obtener_por_id(id_patologia)
        if not entidad:
            raise NotFoundError(code="PATOLOGIA_NO_ENCONTRADA", message="Patología no encontrada.")

        # FA-06: no editar patología base
        if entidad.es_base:
            raise BusinessRuleError(
                code="PATOLOGIA_BASE_INMUTABLE",
                message="Las patologías base del sistema no pueden ser modificadas.",
            )

        # concurrencia optimista
        if dto.fecha_actualizacion is not None and entidad.fecha_actualizacion is not None:
            if entidad.fecha_actualizacion.astimezone(timezone.utc) != dto.fecha_actualizacion.astimezone(timezone.utc):
                raise PreconditionFailedError(
                    code="CONFLICTO_CONCURRENCIA",
                    message="El registro fue modificado por otro usuario. Recarga y reintenta.",
                )

        # FA-07: sin modelos activos
        if self._modelo_activo_port.tiene_modelos_activos(id_patologia):
            raise ConflictError(
                code="PATOLOGIA_EN_USO_POR_MODELO",
                message="La patología está en uso por un modelo activo y no puede ser modificada.",
            )

        # validaciones de creación
        ids_solicitados = list(dict.fromkeys(dto.variables_sensoricas_asociadas))
        if not (2 <= len(ids_solicitados) <= 6):
            raise BusinessRuleError(
                code="CANTIDAD_VARIABLES_INVALIDA",
                message="La patología debe tener entre 2 y 6 variables sensóricas asociadas.",
            )
        if len(dto.descripcion_clinica.strip()) < 50:
            raise BusinessRuleError(
                code="DESCRIPCION_CLINICA_INSUFICIENTE",
                message="La descripcion_clinica debe tener al menos 50 caracteres.",
                field="descripcion_clinica",
            )
        ids_validos = self._variable_port.obtener_ids_activos(ids_solicitados)
        ids_invalidos = [i for i in ids_solicitados if i not in ids_validos]
        if ids_invalidos:
            raise BusinessRuleError(
                code="VARIABLE_NO_EN_I3P1",
                message=f"Las siguientes variables no están en el catálogo I3P-1: {ids_invalidos}.",
                field="variables_sensoricas_asociadas",
            )

        # unicidad de nombre (excluir la propia patología)
        existente = self._repo.obtener_por_nombre(dto.nombre_patologia)
        if existente and existente.id_patologia != id_patologia:
            raise ConflictError(
                code="NOMBRE_PATOLOGIA_DUPLICADO",
                message=f"Ya existe una patología con el nombre '{dto.nombre_patologia}'.",
                field="nombre_patologia",
            )

        # unicidad de combinación de variables (excluir la propia)
        if self._repo.obtener_por_combinacion_variables(ids_solicitados, entidad.especie_aplicable, excluir_id=id_patologia):
            raise ConflictError(
                code="COMBINACION_VARIABLES_DUPLICADA",
                message="Ya existe una patología con la misma combinación de variables para esta especie.",
                field="variables_sensoricas_asociadas",
            )

        snapshot_anterior = entidad._snapshot()
        entidad.actualizar(
            nombre=dto.nombre_patologia,
            descripcion_clinica=dto.descripcion_clinica.strip(),
            variables=[PatologiaVariable(id_variable_ambiental=i) for i in ids_solicitados],
            fecha_actualizacion=datetime.now(timezone.utc),
        )

        try:
            entidad = self._repo.actualizar(entidad)
            self._historial_repo.registrar(
                id_patologia=entidad.id_patologia,
                version_catalogo=entidad.version_catalogo,
                accion="MODIFICADA",
                datos_nuevos=entidad._snapshot(),
                datos_anteriores=snapshot_anterior,
                id_usuario=id_usuario,
            )
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise

        self._auditoria_repo.registrar(
            tipo_evento="CATALOGO_PATOLOGIA_MODIFICADA",
            tipo_actor="USUARIO",
            id_usuario=id_usuario,
            id_referencia=str(entidad.id_patologia),
            entidad_referencia="patologia",
            resultado_operacion="EXITOSO",
            payload_evento={"anterior": snapshot_anterior, "nuevo": entidad._snapshot()},
        )
        try:
            self._db.commit()
        except Exception:
            self._db.rollback()

        return entidad
