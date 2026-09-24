"""RF-52 E5: reconciliación diaria entre el historial RF-46 y la bitácora RF-52.

Cada corrida deja una marca (``RECONCILIACION_RF46_RF52``) con el último id de
cada tabla del historial, y revisa lo creado entre las dos marcas anteriores:
- La primera corrida solo fija el punto de partida. Lo anterior a la llave
  ``registros_rf46`` no tiene con qué cruzarse, y marcarlo sería un falso positivo.
- Revisar con una corrida de retraso da a cada fila al menos un día para que su
  registro llegue a la bitácora, aunque haya pasado por el buffer (E1) o por la
  cola de alta carga (E3).

Lo que falte se registra como ``INCONSISTENCIA_RF46_RF52`` (CRITICAL) con los
identificadores, sin tocar el historial. El aviso al administrador lo dispara la
tarea de ``main.py`` con ``NotificarInconsistenciaAuditoriaUseCase``, en una
sesión propia, igual que la alerta de RF-10.
"""
from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from src.biological_assets.domain.entities.activo_biologico import EventoAuditoria, RegistroRf46
from src.biological_assets.domain.repositories.bitacora_auditoria_repository import BitacoraAuditoriaRepository
from src.biological_assets.domain.repositories.reconciliacion_auditoria_repository import (
    ReconciliacionAuditoriaRepository,
)

logger = logging.getLogger(__name__)

# Margen sobre la hora de la marca: un evento emitido entre la lectura de los ids
# y la escritura de la marca quedaría fuera de una ventana exacta.
_MARGEN_BITACORA = timedelta(hours=1)


@dataclass
class ResultadoReconciliacion:
    turno_adquirido: bool
    ventana_revisada: bool = False
    inconsistencias: list[RegistroRf46] = field(default_factory=list)


class ReconciliarBitacoraHistorialUseCase:

    def __init__(
        self,
        db: Session,
        repo: ReconciliacionAuditoriaRepository,
        bitacora_repo: BitacoraAuditoriaRepository,
    ) -> None:
        self.db = db
        self.repo = repo
        self.bitacora_repo = bitacora_repo

    def execute(self) -> ResultadoReconciliacion:
        try:
            if not self.repo.adquirir_turno():
                self.db.rollback()
                return ResultadoReconciliacion(turno_adquirido=False)

            marcas = self.repo.ultimas_marcas(2)
            hasta_actual = self.repo.ids_maximos()
            resultado = ResultadoReconciliacion(turno_adquirido=True, ventana_revisada=len(marcas) == 2)

            ahora = datetime.now(timezone.utc)
            if resultado.ventana_revisada:
                ultima, penultima = marcas
                resultado.inconsistencias = self.repo.registros_sin_bitacora(
                    desde=penultima.hasta,
                    hasta=ultima.hasta,
                    bitacora_desde=penultima.registrada_en - _MARGEN_BITACORA,
                )
                if resultado.inconsistencias:
                    self.bitacora_repo.registrar(EventoAuditoria(
                        rf_origen='RF52',
                        tipo_evento='INCONSISTENCIA_RF46_RF52',
                        clasificacion_biologica='GESTION_OPERATIVA',
                        resultado='FALLIDO',
                        severidad_log='CRITICAL',
                        timestamp_evento=ahora,
                        descripcion=(
                            f'{len(resultado.inconsistencias)} registros del historial RF-46 sin su '
                            'registro en la bitácora RF-52.'
                        ),
                        detalle_tecnico={
                            'registros_rf46': [asdict(r) for r in resultado.inconsistencias],
                            'ventana': {'desde': penultima.hasta, 'hasta': ultima.hasta},
                        },
                    ))

            # Escritura directa, no registrar_evento_bitacora: la marca no puede
            # quedar encolada (E3) porque la siguiente corrida la necesita.
            self.bitacora_repo.registrar(EventoAuditoria(
                rf_origen='RF52',
                tipo_evento='RECONCILIACION_RF46_RF52',
                clasificacion_biologica='GESTION_OPERATIVA',
                resultado='EXITOSO',
                severidad_log='INFO',
                timestamp_evento=ahora,
                descripcion='Reconciliación diaria entre el historial RF-46 y la bitácora RF-52.',
                detalle_tecnico={
                    'hasta': hasta_actual,
                    'ventana_revisada': resultado.ventana_revisada,
                    'inconsistencias': len(resultado.inconsistencias),
                },
            ))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        if resultado.inconsistencias:
            logger.critical(
                'RF-52 E5: %d registros del historial RF-46 sin su registro en la bitácora: %s',
                len(resultado.inconsistencias),
                [(r.tabla, r.id) for r in resultado.inconsistencias],
            )
        return resultado
