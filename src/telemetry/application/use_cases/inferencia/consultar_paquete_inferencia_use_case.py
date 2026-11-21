# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-27 | destroyerban | INC-M03-116-G59 RF-56: consulta del paquete por id con alcance por finca |
"""RF-56 Postcondición 3 y 5, CA-8: consultar un paquete de inferencia y su ciclo de vida.

El paquete trae su trazabilidad (sensor → evento Edge → paquete → versión de modelo) y su
ciclo de vida, que son los eventos que la bitácora RF-63 tiene de él (generación, contexto
incompleto, reintentos, envío o fallo), en orden cronológico. Fuera de las fincas del usuario
el paquete "no existe" (404), igual que en la bitácora y en Alertas.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from src.shared.errors import NotFoundError
from src.telemetry.domain.entities.evento_auditoria_iot import EntidadAfectadaTipo, EventoAuditoriaIot
from src.telemetry.domain.entities.telemetria import PaqueteInferencia
from src.telemetry.domain.repositories.bitacora_auditoria_iot_repository import BitacoraAuditoriaIotRepository
from src.telemetry.domain.repositories.paquete_inferencia_repository import PaqueteInferenciaRepository

# Un paquete deja pocos eventos (generación, hasta 5 intentos, envío o fallo); el tope evita
# que un dato anómalo devuelva una lista sin límite.
MAX_EVENTOS_CICLO_VIDA = 200


@dataclass
class PaqueteConCicloVida:
    paquete: PaqueteInferencia
    ciclo_vida: list[EventoAuditoriaIot] = field(default_factory=list)


class ConsultarPaqueteInferenciaUseCase:

    def __init__(
        self,
        paquete_repo: PaqueteInferenciaRepository,
        auditoria_repo: BitacoraAuditoriaIotRepository,
    ) -> None:
        self.paquete_repo = paquete_repo
        self.auditoria_repo = auditoria_repo

    def execute(
        self, id_paquete: int, *, ids_fincas_permitidas: Optional[list[int]] = None,
    ) -> PaqueteConCicloVida:
        paquete = self.paquete_repo.obtener(id_paquete, ids_fincas_permitidas=ids_fincas_permitidas)
        if paquete is None:
            raise NotFoundError(
                code='PAQUETE_INFERENCIA_NO_ENCONTRADO',
                message=f'No existe el paquete de inferencia {id_paquete}.',
                field='id_paquete',
            )
        # El alcance ya se validó con el paquete: sus eventos se leen sin volver a filtrar.
        eventos, _ = self.auditoria_repo.listar(
            entidad_afectada_tipo=EntidadAfectadaTipo.PAQUETE_IA.value,
            entidad_afectada_id=str(id_paquete),
            por_pagina=MAX_EVENTOS_CICLO_VIDA,
        )
        return PaqueteConCicloVida(paquete=paquete, ciclo_vida=sorted(eventos, key=lambda e: e.fecha_hora))
