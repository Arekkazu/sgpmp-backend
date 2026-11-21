# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-27 | Leandro | INC-M03-133-G170 RF-62: reproducir falta de sustitutas y validar atomicidad de la reevaluacion. |
from datetime import datetime,timezone,timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4
import pytest
from src.telemetry.application.use_cases.calidad.solicitar_reevaluacion_use_case import SolicitarReevaluacionUseCase
from src.telemetry.infrastructure.dto.solicitar_reevaluacion_dto import SolicitarReevaluacionDTO
from tests.telemetry.test_inc_m03_104_g165_motor_calidad import escenario


def test_reevaluacion_crea_sustituta_antes_de_confirmar():
    s=escenario([19.8,20.2]*10,20,offset=3.5294)
    anterior=s.uc.execute(**s.datos)
    s.db.reset_mock()
    s.calidad.obtener_por_lectura.return_value=anterior
    s.calidad.listar_vigentes_por_sensor_rango.return_value=[anterior]
    s.uc.telemetria_repo.obtener_por_id.return_value=SimpleNamespace(**{
        **s.datos,'valor_crudo':s.datos['valor'],'estado_calidad':'LECTURA_VALIDA',
        'version_calibracion':None,'metadatos':{},'reloj_desincronizado':False})
    dto=SolicitarReevaluacionDTO(id_sensor=7,fecha_desde=anterior.timestamp_evaluacion-timedelta(seconds=1),
        fecha_hasta=anterior.timestamp_evaluacion+timedelta(seconds=1),
        causa_documentada='Error documentado de calibracion que genero drift falso',
        parametros_correctos={'offset':0,'ganancia':1})
    uc=SolicitarReevaluacionUseCase(s.db,s.calidad,s.uc.telemetria_repo,s.uc.parametros_port,s.auditoria,s.uc.contexto_port)
    resultado=uc.execute(dto,1,'Administrador de prueba')
    assert resultado.evaluaciones_creadas==resultado.evaluaciones_superadas==1
    nueva=s.calidad.guardar.call_args.args[0]
    assert nueva.id_evaluacion_superada==anterior.id_evaluacion
    assert nueva.parametros_calibracion_aplicados=={'offset':0,'ganancia':1}
    assert nueva.motivo_reevaluacion==dto.causa_documentada
    assert nueva.version_evaluacion
    s.db.commit.assert_called_once()


@pytest.mark.parametrize('valores',[
    {'ganancia':0},{'ganancia':-1},{'k':0},{'M':0},{'N':1},{'P':0},{'N':3,'M':4},{'N':3,'P':4},
    {'k':True},{'offset':'0'},{'ganancia':float('inf')},{'umbral_drift':-1},{'desconocido':1},
])
def test_correcciones_invalidas_no_se_aplican(valores):
    from src.telemetry.domain.entities.parametros_reevaluacion import validar_correcciones,corregir_estadisticos
    from src.telemetry.domain.repositories.parametros_calidad_port import ParametrosCalidad
    from src.shared.errors import BusinessRuleError
    with pytest.raises(BusinessRuleError):
        corregir_estadisticos(ParametrosCalidad(),validar_correcciones(valores))


def test_motor_sin_confirmar_conserva_operacion_pendiente_para_lote():
    s=escenario([19.8,20.2]*10,20,offset=3.5294)
    ev=s.uc.execute(**s.datos,confirmar=False,motivo_reevaluacion='Error de configuracion confirmado',
        correcciones={'k':4},version_calibracion='cal-prueba')
    assert ev.parametros_aplicados['k']==4
    assert ev.motivo_reevaluacion=='Error de configuracion confirmado'
    assert ev.version_evaluacion.startswith('rf62:') and len(ev.version_evaluacion)==69
    assert ev.parametros_aplicados['version_evaluacion_componentes']['version_calibracion']=='cal-prueba'
    s.auditoria.registrar.assert_called_once()
    s.db.commit.assert_not_called()


def test_version_depende_de_parametros_aplicados_no_del_instante():
    s=escenario([19.8,20.2]*10,20)
    a=s.uc.execute(**s.datos,motivo_reevaluacion='Error de configuracion confirmado')
    b=s.uc.execute(**s.datos,motivo_reevaluacion='Otra causa documentada')
    c=s.uc.execute(**s.datos,motivo_reevaluacion='Otra causa documentada',correcciones={'k':4})
    assert a.version_evaluacion==b.version_evaluacion
    assert a.version_evaluacion!=c.version_evaluacion
