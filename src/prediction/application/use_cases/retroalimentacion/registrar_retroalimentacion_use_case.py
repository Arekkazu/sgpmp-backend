from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from src.prediction.domain.entities.retroalimentacion_clinica import RetroalimentacionClinica, _ESTADOS_CON_DIAGNOSTICO
from src.prediction.domain.repositories.evento_auditoria_m04_repository import EventoAuditoriaM04Repository
from src.prediction.domain.repositories.patologia_m04_repository import PatologiaM04Repository
from src.prediction.domain.repositories.resultado_inferencia_port import ResultadoInferenciaPort
from src.prediction.domain.repositories.retroalimentacion_clinica_repository import RetroalimentacionClinicaRepository
from src.prediction.infrastructure.dto.registrar_retroalimentacion_dto import RegistrarRetroalimentacionDTO
from src.shared.errors import BusinessRuleError, ConflictError, NotFoundError

VENTANA_RETROALIMENTACION_DIAS = 90

_GRUPO_SIN_PROBLEMA = frozenset({"CORRECTO", "SIN_EVENTO"})
_GRUPO_CON_PROBLEMA = frozenset({"PARCIAL", "INCORRECTO"})


class RegistrarRetroalimentacionUseCase:

    def __init__(
        self,
        *,
        db: Session,
        repo: RetroalimentacionClinicaRepository,
        resultado_port: ResultadoInferenciaPort,
        patologia_repo: PatologiaM04Repository,
        auditoria_repo: EventoAuditoriaM04Repository,
    ) -> None:
        self._db = db
        self._repo = repo
        self._resultado_port = resultado_port
        self._patologia_repo = patologia_repo
        self._auditoria_repo = auditoria_repo

    def execute(
        self, dto: RegistrarRetroalimentacionDTO, id_usuario_veterinario: int
    ) -> RetroalimentacionClinica:
        # FA-01: verificar que el resultado de inferencia existe
        resultado = self._resultado_port.obtener_por_id(dto.id_resultado_inferencia)
        if resultado is None:
            raise NotFoundError(
                code="RESULTADO_INFERENCIA_NO_ENCONTRADO",
                message="El resultado de inferencia no existe o no está disponible.",
            )

        fecha_inferencia: datetime = resultado["fecha_inferencia"]
        ahora = datetime.now(tz=timezone.utc)

        # FA-09: ventana temporal
        if fecha_inferencia.tzinfo is None:
            fecha_inferencia = fecha_inferencia.replace(tzinfo=timezone.utc)
        dias_transcurridos = (ahora - fecha_inferencia).days
        if dias_transcurridos > VENTANA_RETROALIMENTACION_DIAS:
            fecha_limite = fecha_inferencia + timedelta(days=VENTANA_RETROALIMENTACION_DIAS)
            raise BusinessRuleError(
                code="FUERA_DE_VENTANA_TEMPORAL",
                message=(
                    f"La retroalimentación no puede registrarse. Han transcurrido más de "
                    f"{VENTANA_RETROALIMENTACION_DIAS} días desde el resultado de inferencia "
                    f"{dto.id_resultado_inferencia}. La ventana válida para este resultado venció el "
                    f"{fecha_limite.strftime('%Y-%m-%d')}. Contacte al administrador si requiere "
                    f"registrar retroalimentación fuera de este plazo."
                ),
            )

        # FA-10: consistencia de activo biológico
        if resultado["id_activo_biologico"] != dto.id_activo_biologico:
            raise BusinessRuleError(
                code="ACTIVO_BIOLOGICO_INCONSISTENTE",
                message="El activo biológico no corresponde al resultado de inferencia indicado.",
                field="id_activo_biologico",
            )

        # FA-07: consistencia temporal (retroalimentación no puede ser anterior a la inferencia)
        if ahora < fecha_inferencia:
            raise BusinessRuleError(
                code="TIMESTAMP_INVALIDO",
                message="La fecha de retroalimentación es inválida.",
            )

        # FA-02: unicidad por usuario + resultado
        existente = self._repo.obtener_por_resultado_y_usuario(
            dto.id_resultado_inferencia, id_usuario_veterinario
        )
        if existente is not None:
            raise ConflictError(
                code="RETROALIMENTACION_DUPLICADA",
                message="Ya existe una retroalimentación registrada por este usuario para este resultado.",
            )

        # FA-04 / FA-05: validación de diagnósticos
        estado = (dto.estado_retroalimentacion or "").upper()
        diags = dto.diagnosticos_reales or []
        if estado in _ESTADOS_CON_DIAGNOSTICO:
            if not diags:
                raise BusinessRuleError(
                    code="DIAGNOSTICO_REQUERIDO",
                    message="El diagnóstico clínico es obligatorio para este tipo de retroalimentación.",
                    field="diagnosticos_reales",
                )
            for id_pat in diags:
                patologia = self._patologia_repo.obtener_por_id(id_pat)
                if patologia is None or not patologia.es_activo:
                    raise BusinessRuleError(
                        code="DIAGNOSTICO_NO_VALIDO",
                        message=f"La patología con id {id_pat} no es válida o no está activa en el sistema.",
                        field="diagnosticos_reales",
                    )

        # Detectar conflicto antes de guardar para crear la entidad con el flag correcto
        otras_existentes = self._repo.listar_por_resultado(dto.id_resultado_inferencia)
        hay_conflicto = self._calcular_conflicto(estado, id_usuario_veterinario, otras_existentes)

        entidad = RetroalimentacionClinica.crear(
            id_resultado_inferencia=dto.id_resultado_inferencia,
            id_activo_biologico=dto.id_activo_biologico,
            estado_retroalimentacion=estado,
            diagnosticos_reales=diags if diags else None,
            fuente_diagnostico=dto.fuente_diagnostico,
            observaciones_clinicas=dto.observaciones_clinicas,
            id_usuario_veterinario=id_usuario_veterinario,
            es_conflicto_retroalimentacion=hay_conflicto,
        )

        correlacion = uuid.uuid4()
        try:
            entidad_guardada = self._repo.guardar(entidad)
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise

        self._auditoria_repo.registrar(
            tipo_evento="RETROALIMENTACION_REGISTRADA",
            tipo_actor="USUARIO",
            id_usuario=id_usuario_veterinario,
            id_referencia=str(entidad_guardada.id_retroalimentacion),
            entidad_referencia="retroalimentacion_clinica",
            resultado_operacion="EXITOSO",
            severidad_evento="INFO",
            correlacion_id=correlacion,
            payload_evento=entidad_guardada._snapshot(),
        )
        if hay_conflicto:
            self._auditoria_repo.registrar(
                tipo_evento="CONFLICTO_RETROALIMENTACION",
                tipo_actor="SISTEMA",
                id_usuario=id_usuario_veterinario,
                id_referencia=str(dto.id_resultado_inferencia),
                entidad_referencia="resultado_inferencia",
                resultado_operacion="DETECTADO",
                severidad_evento="WARNING",
                correlacion_id=correlacion,
                payload_evento={
                    "id_resultado_inferencia": str(dto.id_resultado_inferencia),
                    "nueva_retroalimentacion": str(entidad_guardada.id_retroalimentacion),
                    "total_retroalimentaciones": len(otras_existentes) + 1,
                },
            )
        try:
            self._db.commit()
        except Exception:
            self._db.rollback()

        return entidad_guardada

    @staticmethod
    def _calcular_conflicto(
        nuevo_estado: str,
        id_usuario_nuevo: int,
        existentes: list[RetroalimentacionClinica],
    ) -> bool:
        if not existentes:
            return False
        estados_otros = {r.estado_retroalimentacion for r in existentes if r.id_usuario_veterinario != id_usuario_nuevo}
        if not estados_otros:
            return False
        todos = estados_otros | {nuevo_estado}
        return bool(todos & _GRUPO_SIN_PROBLEMA) and bool(todos & _GRUPO_CON_PROBLEMA)
