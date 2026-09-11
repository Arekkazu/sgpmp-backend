from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from src.prediction.domain.entities.patologia_m04 import PatologiaM04
from src.prediction.domain.entities.patologia_variable import PatologiaVariable
from src.prediction.domain.repositories.especie_port import EspeciePort
from src.prediction.domain.repositories.evento_auditoria_m04_repository import EventoAuditoriaM04Repository
from src.prediction.domain.repositories.historial_catalogo_repository import HistorialCatalogoRepository
from src.prediction.domain.repositories.patologia_m04_repository import PatologiaM04Repository
from src.prediction.domain.repositories.variable_i3p1_port import VariableI3P1Port
from src.prediction.infrastructure.dto.registrar_patologia_dto import RegistrarPatologiaDTO
from src.shared.errors import BusinessRuleError, ConflictError, NotFoundError


class RegistrarPatologiaUseCase:
    def __init__(
        self,
        *,
        db: Session,
        repo: PatologiaM04Repository,
        historial_repo: HistorialCatalogoRepository,
        auditoria_repo: EventoAuditoriaM04Repository,
        variable_port: VariableI3P1Port,
        especie_port: EspeciePort,
    ) -> None:
        self._db = db
        self._repo = repo
        self._historial_repo = historial_repo
        self._auditoria_repo = auditoria_repo
        self._variable_port = variable_port
        self._especie_port = especie_port

    def execute(self, dto: RegistrarPatologiaDTO, id_usuario: int) -> PatologiaM04:
        # FA-01: especie válida
        if not self._especie_port.especie_activa(dto.especie_aplicable):
            raise NotFoundError(
                code="ESPECIE_NO_ACTIVA",
                message=f"La especie '{dto.especie_aplicable}' no existe o no está activa.",
            )

        # FA-02: mínimo 2, máximo 6 variables + descripción clínica ≥50 chars
        if not (2 <= len(dto.variables_sensoricas_asociadas) <= 6):
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

        # FA-03: todas las variables existen en I3P-1
        ids_solicitados = list(dict.fromkeys(dto.variables_sensoricas_asociadas))  # deduplica preservando orden
        ids_validos = self._variable_port.obtener_ids_activos(ids_solicitados)
        ids_invalidos = [i for i in ids_solicitados if i not in ids_validos]
        if ids_invalidos:
            raise BusinessRuleError(
                code="VARIABLE_NO_EN_I3P1",
                message=f"Las siguientes variables no están en el catálogo I3P-1: {ids_invalidos}.",
                field="variables_sensoricas_asociadas",
            )

        # FA-04: nombre único (case-insensitive) global
        if self._repo.obtener_por_nombre(dto.nombre_patologia):
            raise ConflictError(
                code="NOMBRE_PATOLOGIA_DUPLICADO",
                message=f"Ya existe una patología con el nombre '{dto.nombre_patologia}'.",
                field="nombre_patologia",
            )

        # FA-05: combinación de variables única por especie
        if self._repo.obtener_por_combinacion_variables(ids_solicitados, dto.especie_aplicable):
            raise ConflictError(
                code="COMBINACION_VARIABLES_DUPLICADA",
                message="Ya existe una patología con la misma combinación de variables para esta especie.",
                field="variables_sensoricas_asociadas",
            )

        variables = [PatologiaVariable(id_variable_ambiental=i) for i in ids_solicitados]
        entidad = PatologiaM04.crear(
            nombre=dto.nombre_patologia,
            especie_aplicable=dto.especie_aplicable,
            descripcion_clinica=dto.descripcion_clinica.strip(),
            variables=variables,
            id_usuario_creador=id_usuario,
        )

        try:
            entidad = self._repo.guardar(entidad)
            self._historial_repo.registrar(
                id_patologia=entidad.id_patologia,
                version_catalogo=entidad.version_catalogo,
                accion="CREADA",
                datos_nuevos=entidad._snapshot(),
                id_usuario=id_usuario,
            )
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise

        self._auditoria_repo.registrar(
            tipo_evento="CATALOGO_PATOLOGIA_AGREGADA",
            tipo_actor="USUARIO",
            id_usuario=id_usuario,
            id_referencia=str(entidad.id_patologia),
            entidad_referencia="patologia",
            resultado_operacion="EXITOSO",
            payload_evento=entidad._snapshot(),
        )
        try:
            self._db.commit()
        except Exception:
            self._db.rollback()

        return entidad
