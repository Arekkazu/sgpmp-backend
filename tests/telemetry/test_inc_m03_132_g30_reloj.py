# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-27 | Leandro | INC-M03-132-G30 RF-53/54/62: reproducir contrato de reloj por lectura y exclusion oficial sin alterar indice. |
"""Pruebas con dobles de los contratos nuevos; PostgreSQL se acredita aparte."""
import pytest
from pydantic import ValidationError

from tests.telemetry.test_dev05_ingesta_bplus import entrada, construir
from tests.telemetry.test_inc_m03_104_g165_motor_calidad import escenario
from src.telemetry.domain.repositories.ingesta_telemetria_port import ResultadoPersistenciaIngesta
from datetime import datetime, timezone


@pytest.mark.parametrize('sincronizado',[True,False,None])
def test_dto_recibe_estado_original_del_reloj(sincronizado):
    dto = entrada(reloj_sincronizado=sincronizado)
    assert dto.model_dump()['reloj_sincronizado'] is sincronizado
    uc = construir(ResultadoPersistenciaIngesta(1,'LECTURA_VALIDA','OK',datetime.now(timezone.utc),1))
    uc.execute(dto)
    meta = uc.ingesta_port.ingerir.call_args.args[0]['metadatos']
    if sincronizado is None:
        assert 'reloj_sincronizado' not in meta
    else:
        assert meta['reloj_sincronizado'] is sincronizado


@pytest.mark.parametrize('valor',[0,1,'false','true',{},[]])
def test_dto_rechaza_estado_del_reloj_que_no_es_booleano(valor):
    with pytest.raises(ValidationError):
        entrada(reloj_sincronizado=valor)


@pytest.mark.parametrize('cambios,indice,clase',[
    ({},100,'APTO'),
    ({'estado_calidad_rf53':'FUERA_DE_RANGO'},0,'NO_APTO'),
])
def test_time_desync_restringe_aptitud_sin_inventar_descuento(cambios,indice,clase):
    s = escenario([19.8,20.2]*10,20)
    s.datos.update(cambios)
    ev = s.uc.execute(**s.datos,reloj_desincronizado=True,
                      evidencia_reloj={'fuente':'HEARTBEAT','id_heartbeat':3})
    assert ev.indice_calidad == indice
    assert ev.clasificacion_calidad.value == clase
    assert (ev.apto_para_ia,ev.apto_para_nic41) == (False,False)
    assert ev.flags_detectados['reloj_desincronizado']['activo'] is True
    assert ev.flags_detectados['reloj_desincronizado']['codigo'] == 'TIME_DESYNC'
    assert ev.parametros_aplicados['restriccion_temporal']['codigo'] == 'TIME_DESYNC'
    assert ev.parametros_aplicados['reloj_rf53']['id_heartbeat'] == 3
    s.db.commit.assert_called_once()


def test_reloj_sin_marca_conserva_aptitud_existente():
    s = escenario([19.8,20.2]*10,20)
    ev = s.uc.execute(**s.datos,reloj_desincronizado=False)
    assert ev.indice_calidad == 100
    assert (ev.apto_para_ia,ev.apto_para_nic41) == (True,True)
    assert 'reloj_desincronizado' not in ev.flags_detectados
