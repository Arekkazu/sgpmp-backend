# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-25 | Arekkazu | RF-63: un timeout en pendientes de una etapa no detiene a las demás |
# | 2026-10-25 | Arekkazu | USAB-M03 M3-12 RF-63: el fake acepta el tope de reintento |
"""RF-63: la consulta de pendientes de una etapa que falla no bloquea al resto."""
from contextlib import contextmanager

from src.telemetry.application.use_cases.ingesta.procesar_postcommit_use_case import ProcesarPostcommitUseCase
from src.telemetry.domain.repositories.postcommit_port import EtapaPostcommit


class _Unidad:
    db = None

    def __init__(self, registro):
        self.registro = registro

    def pendientes(self, etapa, limite, reintento_seg, reintento_max_seg=None):
        if etapa is EtapaPostcommit.RF53_AUDITORIA:
            raise TimeoutError('canceling statement due to statement timeout')
        return [1]

    def reclamar(self, etapa, identificador):
        return True

    def registrar(self, etapa, identificador, error=None, *, detalle=None):
        self.registro.append((etapa, error))

    def confirmar(self):
        pass


def test_timeout_en_pendientes_no_detiene_las_etapas_siguientes():
    registro = []

    @contextmanager
    def unidad():
        yield _Unidad(registro)

    acciones = {e: (lambda db, i: None) for e in
                (EtapaPostcommit.RF53_AUDITORIA, EtapaPostcommit.RF62, EtapaPostcommit.HEARTBEAT_ESTADO)}
    resultado = ProcesarPostcommitUseCase(unidad, acciones).execute()

    assert resultado == {'completados': 2, 'fallidos': 1}
    assert registro == [(EtapaPostcommit.RF62, None), (EtapaPostcommit.HEARTBEAT_ESTADO, None)]
