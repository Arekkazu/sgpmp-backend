# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-11-07 | Leandro | INC-M05-270-G14 RF-76: probar límites decimal(10,4) y traducciones seguras del trigger. |
"""Contrato de dosis y errores acotados de RF-76."""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.exc import InternalError

from src.shared.db_error_translator import raise_from_db_error
from src.shared.errors import InfrastructureError,ValidationError
from src.supplies.infrastructure.dto.registrar_medicamento_dto import RegistrarMedicamentoDTO
from src.supplies.infrastructure.models.registro_medicamento_model import RegistroMedicamentoModel


def dto(dosis):
    return RegistrarMedicamentoDTO(id_activo_biologico=1,nombre_medicamento='Oxitetraciclina',
        fecha_aplicacion=date(2026,11,7),hora_aplicacion='09:03',via_administracion='INTRAMUSCULAR',
        dosis_aplicada=dosis,unidad_dosis='ml',periodo_retiro_dias=0,
        motivo_aplicacion='Tratamiento de infeccion respiratoria',costo_unitario=500,nombre_veterinario='Dr. Perez')


@pytest.mark.parametrize('valor',['0.0001','0.0004','0.0005','0.0015','0.001','10','999999.9999','0.00010','1.23450','1e-4'])
def test_valores_exactos_no_se_redondean(valor):
    assert dto(valor).dosis_aplicada==Decimal(valor)


@pytest.mark.parametrize('valor',['0.00001','0.00049','1.23456','1000000','9999999.999','1e-5','NaN','Infinity','0','-1'])
def test_valores_fuera_del_contrato_se_rechazan(valor):
    with pytest.raises(PydanticValidationError):dto(valor)


def test_orm_coincide_con_el_tipo_del_contrato():
    tipo=RegistroMedicamentoModel.__table__.c.cantidad.type
    assert (tipo.precision,tipo.scale)==(10,4)


def error(funcion,etiqueta,sqlstate='P0001'):
    diagnostico=SimpleNamespace(sqlstate=sqlstate,context='PL/pgSQL function '+funcion+'() line 5 at RAISE',
        message_primary=etiqueta+': SQL secreto y datos privados',column_name=None,constraint_name=None,table_name=None)
    clase=type('ErrorControlado',(Exception,),{'diag':diagnostico,'pgcode':sqlstate})
    return InternalError('INSERT secreto',{'secreto':'no revelar'},clase())


@pytest.mark.parametrize('etiqueta,campo',[('CANTIDAD_INVALIDA','dosis_aplicada'),('COSTO_INVALIDO','costo_unitario')])
def test_rechazos_conocidos_se_traducen_a_400_sin_sql(etiqueta,campo):
    with pytest.raises(ValidationError) as exc:
        raise_from_db_error(error('modulo5.fn_trg_calcular_costo_total_medicamento',etiqueta))
    assert exc.value.status_code==400 and exc.value.code=='VAL_ENTRADA' and exc.value.field==campo
    assert 'secreto' not in exc.value.message and 'privados' not in exc.value.message


@pytest.mark.parametrize('funcion,etiqueta,sqlstate',[
    ('otro_esquema.fn_trg_calcular_costo_total_medicamento','CANTIDAD_INVALIDA','P0001'),
    ('modulo5.fn_trg_calcular_costo_total_medicamento','OTRO_FALLO','P0001'),
    ('modulo5.fn_trg_calcular_costo_total_medicamento','CANTIDAD_INVALIDA','XX000'),
])
def test_fallos_desconocidos_no_se_convierten_en_errores_del_cliente(funcion,etiqueta,sqlstate):
    with pytest.raises(InfrastructureError):raise_from_db_error(error(funcion,etiqueta,sqlstate))
