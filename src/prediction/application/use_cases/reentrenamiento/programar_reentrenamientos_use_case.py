# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-03 | Arekkazu | AJF-14 RF-71 BE-6: disparador PROGRAMADO de reentrenamientos por antigüedad de la versión |
"""BE-6: abre procesos PROGRAMADO para los animales cuya versión vigente es más vieja que
``dias_reentrenamiento_programado`` (parámetro MLOps, patrón RF-57). Con 0 (valor base) no hace nada.

Solo abre el proceso; lo corre el motor de IA como cualquier otro. Un animal sin días suficientes
de lecturas se salta (sin evento: se vuelve a mirar en la siguiente pasada).
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from src.configuration.domain.entities.parametro_mlops import (
    RF71_DIAS_PROGRAMADO, RF71_DIAS_PROGRAMADO_BASE, numero_configurado,
)
from src.configuration.domain.repositories.parametros_mlops_port import ParametrosMLOpsPort
from src.prediction.application.use_cases.reentrenamiento.solicitar_reentrenamiento_animal_use_case import (
    DIAS_MINIMOS_LECTURAS,
)
from src.prediction.domain.entities.proceso_reentrenamiento import ProcesoReentrenamiento
from src.prediction.domain.repositories.evento_auditoria_m04_repository import EventoAuditoriaM04Repository
from src.prediction.domain.repositories.proceso_reentrenamiento_repository import ProcesoReentrenamientoRepository

SISTEMA = "reentrenamiento-programado"
#: Tope por pasada: el motor corre uno a la vez; no se llena la cola de golpe.
MAXIMO_POR_PASADA = int(os.getenv("REENTRENAMIENTO_PROGRAMADO_MAXIMO", "5"))


class ProgramarReentrenamientosUseCase:
    def __init__(self, *, db: Session, procesos: ProcesoReentrenamientoRepository, parametros: ParametrosMLOpsPort,
                 auditoria_repo: EventoAuditoriaM04Repository, dias_minimos_lecturas: Optional[float] = None) -> None:
        self._db = db
        self._procesos = procesos
        self._parametros = parametros
        self._auditoria = auditoria_repo
        self._dias_lecturas = DIAS_MINIMOS_LECTURAS if dias_minimos_lecturas is None else dias_minimos_lecturas

    def dias_configurados(self) -> int:
        valores = self._parametros.obtener([RF71_DIAS_PROGRAMADO])
        if RF71_DIAS_PROGRAMADO not in valores:
            return RF71_DIAS_PROGRAMADO_BASE
        return numero_configurado(valores, RF71_DIAS_PROGRAMADO, minimo=0, entero=True)

    def execute(self, ahora: Optional[datetime] = None) -> int:
        """Cuántos procesos PROGRAMADO abrió."""
        dias = self.dias_configurados()
        if dias <= 0:
            return 0
        ahora = ahora or datetime.now(timezone.utc)
        abiertos = 0
        try:
            for id_activo, tipo_modelo in self._procesos.candidatos_programados(dias):
                if abiertos >= MAXIMO_POR_PASADA:
                    break
                if self._procesos.horas_de_lecturas(id_activo) / 24 < self._dias_lecturas:
                    continue
                proceso = self._procesos.crear(ProcesoReentrenamiento.solicitar(
                    tipo_modelo=tipo_modelo, id_activo_biologico=id_activo, id_usuario=None, ahora=ahora,
                    disparador="PROGRAMADO"))
                self._auditoria.registrar(
                    tipo_evento="REENTRENAMIENTO_SOLICITADO", tipo_actor="SISTEMA", id_sistema=SISTEMA,
                    id_referencia=str(id_activo), entidad_referencia="activo_biologico", resultado_operacion="EXITOSO",
                    payload_evento={
                        "tipo_modelo": tipo_modelo, "id_activo_biologico": id_activo,
                        "id_proceso_reentrenamiento": str(proceso.id_proceso_reentrenamiento),
                        "disparador": "PROGRAMADO", "dias_version": dias,
                        # Campos de RF-73 para este evento; en un disparo del sistema no aplican.
                        "registros_nuevos": None, "minimo_solicitud": None, "id_usuario_solicitante": None,
                    },
                )
                abiertos += 1
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise
        return abiertos
