# | Fecha      | Nombre  | Que se hizo                                      |
# |------------|---------|--------------------------------------------------|
# | 2026-10-21 | Leandro | DEV-41 RF-53/57: confirma alerta y correlacion juntas |
"""Cada etapa confirma sus efectos y su evidencia juntos; las demás pueden avanzar."""
import logging

from src.shared.errors import AppError
from src.telemetry.domain.repositories.postcommit_port import EtapaPostcommit

logger = logging.getLogger(__name__)


class ProcesarPostcommitUseCase:
    def __init__(self, unidad_factory, acciones, limite=50, reintento_seg=60):
        if limite <= 0 or reintento_seg <= 0:
            raise ValueError('Límite y espera de reintento deben ser positivos.')
        self.unidad_factory = unidad_factory
        self.acciones = acciones
        self.limite = limite
        self.reintento_seg = reintento_seg

    def execute(self):
        resultado = {'completados': 0, 'fallidos': 0}
        for etapa in EtapaPostcommit:
            with self.unidad_factory() as unidad:
                ids = unidad.pendientes(etapa, self.limite, self.reintento_seg)
            for identificador in ids:
                try:
                    with self.unidad_factory() as unidad:
                        if not unidad.reclamar(etapa, identificador):
                            continue
                        detalle = self.acciones[etapa](unidad.db, identificador)
                        if isinstance(detalle, dict):
                            unidad.registrar(etapa, identificador, detalle=detalle)
                        else:
                            unidad.registrar(etapa, identificador)
                        unidad.confirmar()
                    resultado['completados'] += 1
                except Exception as exc:
                    resultado['fallidos'] += 1
                    # Ni SQL crudo ni payloads/credenciales en la bitácora de reintento.
                    codigo = exc.code if isinstance(exc, AppError) else type(exc).__name__
                    logger.warning('Postcommit pendiente: etapa=%s id=%s error=%s', etapa.value, identificador, codigo)
                    try:
                        with self.unidad_factory() as unidad:
                            if unidad.reclamar(etapa, identificador):
                                unidad.registrar(etapa, identificador, codigo)
                                unidad.confirmar()
                    except Exception:
                        logger.error('No se pudo persistir el reintento: etapa=%s id=%s', etapa.value, identificador)
        return resultado
