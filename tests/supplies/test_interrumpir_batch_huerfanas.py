# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-10 | Arekkazu | INC-M05-511 RF-74: al arrancar se interrumpen las corridas del batch ICA que quedaron huérfanas |
# | 2026-11-12 | Leandro | INC-M05-350/351-G05 RF-74: cubrir causa, motivo y aviso de interrupción manual. |
"""Una corrida EN_EJECUCION que sobrevive a un reinicio bloqueaba el batch de todas las noches."""
from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from src.shared.errors import FlowError

from src.supplies.application.use_cases.eficiencia.interrumpir_batch_ica_use_case import InterrumpirBatchICAUseCase
from src.supplies.domain.entities.ejecucion_batch_ica import EjecucionBatchICA
from src.supplies.domain.value_objects.eficiencia_enums import EstadoEjecucionBatch


class _Repo:
    def __init__(self, ejecuciones):
        self.ejecuciones = {e.id_ejecucion: e for e in ejecuciones}

    def obtener(self, id_ejecucion, *, para_actualizar=False):
        return self.ejecuciones.get(id_ejecucion)

    def obtener_en_ejecucion(self):
        vivas = [e for e in self.ejecuciones.values() if e.esta_en_ejecucion]
        return max(vivas, key=lambda e: e.id_ejecucion) if vivas else None

    def guardar(self, ejecucion):
        return ejecucion


class _Db:
    def commit(self): pass
    def rollback(self): pass


def _corrida(id_ejecucion, estado=EstadoEjecucionBatch.EN_EJECUCION):
    return EjecucionBatchICA(tipo_disparo="AUTOMATICO", hora_inicio=datetime(2026, 11, 10, 2, tzinfo=timezone.utc),
                             num_workers=4, estado=estado, id_ejecucion=id_ejecucion)


def test_interrumpe_todas_las_huerfanas_y_deja_las_terminadas():
    repo = _Repo([_corrida(52), _corrida(61, EstadoEjecucionBatch.COMPLETADO), _corrida(62)])
    assert InterrumpirBatchICAUseCase(_Db(), repo).interrumpir_huerfanas() == [62, 52]
    assert repo.obtener(62).estado == EstadoEjecucionBatch.INTERRUMPIDO
    assert repo.obtener(62).causa_interrupcion == "REINICIO_SERVIDOR"
    assert repo.obtener(61).estado == EstadoEjecucionBatch.COMPLETADO
    assert repo.obtener_en_ejecucion() is None


def test_sin_huerfanas_no_hace_nada():
    assert InterrumpirBatchICAUseCase(_Db(), _Repo([_corrida(61, EstadoEjecucionBatch.COMPLETADO)])).interrumpir_huerfanas() == []


def test_interrupcion_manual_separa_motivo_y_avisa_una_vez_despues_del_commit():
    corrida = _corrida(62)
    db = Mock()
    notificador = Mock()
    notificador.a_roles.side_effect = lambda *_: db.commit.assert_called_once()
    uc = InterrumpirBatchICAUseCase(db, _Repo([corrida]), notificador)

    resultado = uc.execute(62, 137, "REINICIO_SERVIDOR")

    assert resultado.estado == EstadoEjecucionBatch.INTERRUMPIDO
    assert resultado.causa_interrupcion == "MANUAL"
    assert resultado.motivo_interrupcion == "REINICIO_SERVIDOR"
    assert resultado.id_usuario_interrupcion == 137 and resultado.hora_corte
    roles, tipo, _, detalle = notificador.a_roles.call_args.args
    assert roles == ("Administrador", "Productor")
    assert tipo == "BATCH_ICA_INTERRUMPIDO"
    assert detalle == {"id_ejecucion": 62, "causa_interrupcion": "MANUAL"}
    with pytest.raises(FlowError, match="no está en ejecución"):
        uc.execute(62, 137, "Otro intento")
    notificador.a_roles.assert_called_once()


def test_interrupcion_no_avisa_si_falla_la_confirmacion():
    db = Mock()
    db.commit.side_effect = RuntimeError("BD no disponible")
    notificador = Mock()
    uc = InterrumpirBatchICAUseCase(db, _Repo([_corrida(62)]), notificador)

    with pytest.raises(RuntimeError, match="BD no disponible"):
        uc.execute(62, 137)

    db.rollback.assert_called_once()
    notificador.a_roles.assert_not_called()
