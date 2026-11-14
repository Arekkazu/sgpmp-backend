# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-11-08 | Leandro | INC-M05-278-G39 RF-80: validar causa de incompletitud, UUID estable e intentos de modificación. |
"""Regresión de auditoría; persistencia, concurrencia y HTTP se verifican aparte."""
from uuid import UUID
from unittest.mock import Mock

import pytest

from src.supplies.application.use_cases.auditoria.registrar_intento_modificacion_auditoria_use_case import (
    RegistrarIntentoModificacionAuditoriaUseCase,
)

from src.supplies.domain.repositories.auditoria_suministro_port import EventoAuditoriaSuministro


def evento(**cambios):
    return EventoAuditoriaSuministro(**(dict(entidad_afectada='registro_suministro',
        tipo_operacion='REGISTRO_FALLIDO', id_usuario=7, resultado='FALLIDO') | cambios))


def test_incompleto_sin_causa_identifica_datos_ausentes():
    e = evento(registro_incompleto=True)
    assert e.detalle_causa and 'Campos faltantes:' in e.detalle_causa
    assert 'activo biológico' in e.detalle_causa and 'ciclo productivo' in e.detalle_causa


def test_evento_emite_un_uuid_estable():
    e = evento()
    assert isinstance(getattr(e, 'id_evento_m05', None), UUID)
    assert e.id_evento_m05 == e.id_evento_m05 and e.id_evento_m05 != evento().id_evento_m05



@pytest.mark.parametrize('detalle', [None, '', '   '])
def test_incompleto_sin_datos_faltantes_no_inventa_causa(detalle):
    e = evento(id_activo_biologico=8, id_ciclo_productivo=4, registro_incompleto=True, detalle_causa=detalle)
    assert 'detalle de la causa' in e.detalle_causa
    assert 'no identificó otros datos ausentes' in e.detalle_causa


def test_causa_existente_se_conserva_y_agrega_solo_ausencias_acreditadas():
    e = evento(id_activo_biologico=8, registro_incompleto=True, detalle_causa='Fuente indisponible.')
    assert e.detalle_causa.startswith('Fuente indisponible.')
    assert 'ciclo productivo' in e.detalle_causa and 'activo biológico' not in e.detalle_causa


def test_evento_completo_no_se_marca_incompleto_por_no_tener_contexto_opcional():
    e = evento()
    assert not e.registro_incompleto and e.detalle_causa is None


@pytest.mark.parametrize('metodo,tipo', [('PUT', 'UPDATE'), ('PATCH', 'UPDATE'), ('DELETE', 'DELETE'), ('POST', 'INSERT')])
def test_intento_de_modificacion_emite_un_rechazo_sin_repositorio_de_lectura(metodo, tipo):
    db, puerto = Mock(), Mock()
    RegistrarIntentoModificacionAuditoriaUseCase(db, puerto).execute(
        id_usuario=7, id_registro_solicitado=35, metodo=metodo)
    puerto.registrar.assert_called_once()
    emitido = puerto.registrar.call_args.args[0]
    assert emitido.tipo_operacion == tipo and emitido.resultado == 'RECHAZADO'
    assert emitido.id_usuario == 7 and '35' in emitido.detalle_causa
    assert emitido.id_activo_biologico is None
    db.commit.assert_called_once()
    db.rollback.assert_not_called()


@pytest.mark.parametrize('fallo', ['registrar', 'commit', 'rollback'])
def test_fallo_de_auditoria_no_habilita_modificacion_ni_expone_sql(fallo, caplog):
    db, puerto = Mock(), Mock()
    if fallo == 'registrar':
        puerto.registrar.side_effect = RuntimeError('SQL y secretos')
    else:
        db.commit.side_effect = RuntimeError('SQL y secretos')
        if fallo == 'rollback':
            db.rollback.side_effect = RuntimeError('SQL y secretos')
    RegistrarIntentoModificacionAuditoriaUseCase(db, puerto).execute(
        id_usuario=7, id_registro_solicitado=35, metodo='DELETE')
    assert 'No se pudo auditar' in caplog.text and 'SQL y secretos' not in caplog.text
