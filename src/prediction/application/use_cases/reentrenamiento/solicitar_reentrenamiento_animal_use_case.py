# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-02 | Arekkazu | AJF-14 RF-71 BE-1: solicitar el reentrenamiento de un animal abre un proceso PENDIENTE |
"""BE-1: la solicitud por animal deja el evento en la bitácora (como hasta ahora) y además
abre el proceso que el motor de IA va a tomar.

A diferencia de la solicitud por tipo de modelo, no exige las retroalimentaciones mínimas:
el pipeline de ET-02 entrena con las lecturas del animal y el generador sintético, y la
procedencia (SINTETICA, MIXTA, REAL) la decide el entrenamiento; una versión SINTETICA o
MIXTA solo puede quedar en sombra (regla de RF-69 ya en el backend).
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from src.prediction.application.use_cases.versiones_modelo.consultar_estado_reentrenamiento_use_case import (
    ConsultarEstadoReentrenamientoUseCase,
)
from src.prediction.domain.entities.estado_reentrenamiento import TIPOS_MODELO_INDIVIDUAL, EstadoReentrenamiento
from src.prediction.domain.entities.proceso_reentrenamiento import ProcesoReentrenamiento
from src.prediction.domain.repositories.evento_auditoria_m04_repository import EventoAuditoriaM04Repository
from src.prediction.domain.repositories.proceso_reentrenamiento_repository import ProcesoReentrenamientoRepository
from src.shared.errors import BusinessRuleError, ConflictError, InfrastructureError, NotFoundError

#: ET-02 v5 (Tabla 6.1): ``dias_minimos`` de calibración. En DEV los animales tienen horas,
#: no días, de lecturas: se baja con la variable (y el motor anota en ``motivos`` que calibró con menos).
DIAS_MINIMOS_LECTURAS = float(os.getenv("REENTRENAMIENTO_DIAS_MINIMOS_LECTURAS", "7"))


class SolicitarReentrenamientoAnimalUseCase:
    def __init__(self, *, db: Session, procesos: ProcesoReentrenamientoRepository,
                 estado_use_case: ConsultarEstadoReentrenamientoUseCase,
                 auditoria_repo: EventoAuditoriaM04Repository, dias_minimos: Optional[float] = None) -> None:
        self._db = db
        self._procesos = procesos
        self._estado = estado_use_case
        self._auditoria = auditoria_repo
        self._dias_minimos = DIAS_MINIMOS_LECTURAS if dias_minimos is None else dias_minimos

    def execute(self, *, id_activo_biologico: int, motivo: Optional[str], id_usuario: int,
                ahora: Optional[datetime] = None) -> tuple[EstadoReentrenamiento, UUID, ProcesoReentrenamiento]:
        ahora = ahora or datetime.now(timezone.utc)
        datos = self._procesos.datos_animal(id_activo_biologico)
        if datos is None:
            raise NotFoundError("ACTIVO_NO_ENCONTRADO", "El animal no existe o no está en tus fincas.", field="id_activo_biologico")
        if datos.tipo_modelo not in TIPOS_MODELO_INDIVIDUAL:
            raise BusinessRuleError(
                "ACTIVO_SIN_MODELO_INDIVIDUAL",
                "El área del animal no usa un modelo individual: no tiene un modelo propio que reentrenar.",
                field="id_activo_biologico",
            )
        if self._procesos.abierto_de(id_activo_biologico) is not None:
            raise ConflictError("REENTRENAMIENTO_EN_CURSO", "Ya hay un reentrenamiento pendiente o en curso para este animal.",
                                field="id_activo_biologico")
        dias = datos.horas_de_lecturas / 24
        if dias < self._dias_minimos:
            raise BusinessRuleError(
                "LECTURAS_INSUFICIENTES",
                f"El animal tiene {dias:.1f} días de lecturas; el reentrenamiento necesita al menos {self._dias_minimos:g}.",
                field="id_activo_biologico",
            )
        estado = next(e for e in self._estado.execute() if e.tipo_modelo == datos.tipo_modelo)
        try:
            proceso = self._procesos.crear(ProcesoReentrenamiento.solicitar(
                tipo_modelo=datos.tipo_modelo, id_activo_biologico=id_activo_biologico, id_usuario=id_usuario, ahora=ahora))
            resultado = self._auditoria.registrar(
                tipo_evento="REENTRENAMIENTO_SOLICITADO",
                tipo_actor="USUARIO",
                id_usuario=id_usuario,
                id_referencia=str(id_activo_biologico),
                entidad_referencia="activo_biologico",
                resultado_operacion="EXITOSO",
                payload_evento={
                    "tipo_modelo": datos.tipo_modelo,
                    "id_activo_biologico": id_activo_biologico,
                    "id_proceso_reentrenamiento": str(proceso.id_proceso_reentrenamiento),
                    "registros_nuevos": estado.registros_nuevos,
                    "minimo_solicitud": estado.minimo_solicitud,
                    "minimo_reentrenamiento": estado.minimo_reentrenamiento,
                    "dias_lecturas": round(dias, 2),
                    "id_usuario_solicitante": id_usuario,
                    "motivo": motivo,
                },
            )
            if not resultado.aceptado:
                raise InfrastructureError("SOLICITUD_NO_REGISTRADA", "No se pudo registrar la solicitud de reentrenamiento.")
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise
        return estado, resultado.id_evento, proceso
