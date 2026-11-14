# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-26 | Leandro | INC-M03-125-G12 RF-53/63: confirmar evidencias FIFO solo después del commit con identidad estable entre reintentos. |
from src.telemetry.application.use_cases.auditoria.registrar_evento_auditoria_iot_use_case import _calcular_hash
from src.telemetry.domain.repositories.respaldo_auditoria_iot_port import RespaldoAuditoriaIotPort, DestinoRespaldoAuditoriaIotPort


class SincronizarRespaldoAuditoriaIotUseCase:
    def __init__(self, db, destino: DestinoRespaldoAuditoriaIotPort, respaldo: RespaldoAuditoriaIotPort):
        self.db, self.destino, self.respaldo = db, destino, respaldo

    def execute(self, limite: int = 100) -> int:
        try:
            if not self.destino.bloquear_respaldo():
                self.db.rollback()
                return 0
            eventos = self.respaldo.listar(limite)
            for evento in eventos:
                if _calcular_hash(evento) != evento.hash_integridad:
                    raise ValueError('Integridad del respaldo de auditoría comprometida.')
                self.destino.registrar_respaldo(evento)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        # Si falla esta confirmación, la siguiente vuelta repite los UUID sin duplicar en PostgreSQL.
        self.respaldo.confirmar([e.id_evento for e in eventos])
        return len(eventos)
