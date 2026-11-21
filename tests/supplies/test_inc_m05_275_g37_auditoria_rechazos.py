# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-11-08 | Leandro | INC-M05-275-G37 RF-80: verificar auditoría de rechazos, idempotencia y fallos controlados con fakes. |
# | 2026-11-10 | Arekkazu | Lote M05/M06 RF-78 R9: intento inicial + 3 reintentos (4 llamadas) tras #1024 |
"""Regresión de #960; persistencia y rollback se verifican aparte en PostgreSQL."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from src.shared.errors import BusinessRuleError, ConflictError
from src.shared.fechas import hoy_usuario
from src.supplies.application.use_cases.costeo_suministros.registrar_suministro_directo_use_case import (
    RegistrarSuministroDirectoUseCase,
)
from src.supplies.domain.repositories.ciclo_abierto_port import CicloAbierto
from src.supplies.infrastructure.dto.registrar_suministro_directo_dto import RegistrarSuministroDirectoDTO


def escenario():
    db, repo, ciclo, auditoria, movimiento, activos = (Mock() for _ in range(6))
    repo.existe_idempotente.return_value = None
    repo.existe_duplicado_contenido.return_value = False
    repo.guardar.side_effect = lambda registro: registro
    ciclo.obtener_abierto.return_value = CicloAbierto(
        19, datetime.now(timezone.utc) - timedelta(days=30), 23,
    )
    activos.obtener.return_value = SimpleNamespace(id_activo_biologico=8)
    uc = RegistrarSuministroDirectoUseCase(db, repo, ciclo, auditoria, movimiento, activos)
    dto = RegistrarSuministroDirectoDTO(
        id_activo_biologico=8, tipo_suministro='SERVICIO_VETERINARIO', id_idempotencia=uuid4(),
        cantidad=Decimal('2'), precio_unitario=Decimal('10'), unidad_medida='servicio',
        fecha_aplicacion=hoy_usuario(),
        justificacion_precio='Precio acordado y documentado con el profesional',
    )
    return SimpleNamespace(
        uc=uc, db=db, repo=repo, ciclo=ciclo, auditoria=auditoria, movimiento=movimiento,
        activos=activos, dto=dto, usuario=SimpleNamespace(id_usuario=7, id_rol=1),
    )


@pytest.mark.parametrize('caso,codigo', [
    ('ciclo', 'CICLO_NO_ACTIVO'),
    ('duplicado', 'SUMINISTRO_DUPLICADO'),
    ('justificacion', 'JUSTIFICACION_PRECIO_REQUERIDA'),
])
def test_rechazo_de_negocio_conserva_error_y_emite_un_evento(caso, codigo):
    e = escenario()
    if caso == 'ciclo':
        e.ciclo.obtener_abierto.return_value = None
    elif caso == 'duplicado':
        e.repo.existe_duplicado_contenido.return_value = True
    else:
        e.dto.justificacion_precio = None
    with pytest.raises((BusinessRuleError, ConflictError)) as rechazo:
        e.uc.execute(e.dto, e.usuario)
    assert rechazo.value.code == codigo
    e.auditoria.registrar.assert_called_once()
    evento = e.auditoria.registrar.call_args.args[0]
    assert evento.resultado == 'RECHAZADO' and evento.tipo_operacion == 'REGISTRO_FALLIDO'
    assert evento.id_usuario == 7 and evento.id_activo_biologico == 8 and evento.numero_reintentos == 0
    e.repo.guardar.assert_not_called()
    e.movimiento.registrar.assert_not_called()


@pytest.mark.parametrize('cambios,codigo', [
    ({'tipo_suministro': 'NO_CATALOGADO'}, 'TIPO_SUMINISTRO_NO_CONFIGURADO'),
    ({'cantidad': None}, 'DATOS_SUMINISTRO_INCOMPLETOS'),
    ({'fecha_aplicacion': hoy_usuario() + timedelta(days=1)}, 'FECHA_FUERA_DE_RANGO'),
    ({'cantidad': Decimal('0')}, 'COSTO_REGISTRO_INVALIDO'),
    ({'precio_unitario': Decimal('-1')}, 'COSTO_REGISTRO_INVALIDO'),
    ({'tipo_suministro': 'ALIMENTO'}, 'REGISTRO_RF75_INVALIDO'),
    ({'tipo_suministro': 'MEDICAMENTO'}, 'REGISTRO_RF76_INVALIDO'),
    ({'justificacion_precio': 'a' * 501}, 'JUSTIFICACION_PRECIO_MUY_LARGA'),
])
def test_otras_reglas_rechazadas_son_auditadas(cambios, codigo):
    e = escenario()
    e.dto = e.dto.model_copy(update=cambios)
    with pytest.raises(BusinessRuleError) as rechazo:
        e.uc.execute(e.dto, e.usuario)
    assert rechazo.value.code == codigo
    evento, = e.auditoria.registrar.call_args.args
    assert evento.resultado == 'RECHAZADO'
    assert str(e.dto.id_idempotencia) in evento.detalle_causa
    assert not any(t in evento.detalle_causa for t in ('M02', 'M09', 'RF75', 'RF76'))
    e.db.commit.assert_called_once()
    e.movimiento.registrar.assert_not_called()


def test_conflicto_despues_de_guardar_revierte_antes_de_auditar():
    e = escenario()
    orden = []
    e.movimiento.registrar.side_effect = ConflictError(code='CONFLICTO', message='Detalle interno')
    e.db.rollback.side_effect = lambda: orden.append('rollback')
    e.auditoria.registrar.side_effect = lambda evento: orden.append('rechazo')
    e.db.commit.side_effect = lambda: orden.append('commit')
    with pytest.raises(ConflictError):
        e.uc.execute(e.dto, e.usuario)
    assert orden == ['rollback', 'rollback', 'rechazo', 'commit']
    e.repo.guardar.assert_called_once()
    evento = e.auditoria.registrar.call_args.args[0]
    assert (evento.id_ciclo_productivo, evento.id_gestion_fases) == (19, 23)
    assert not evento.registro_incompleto
    assert 'Detalle interno' not in evento.detalle_causa


@pytest.mark.parametrize('punto', ['activo', 'auditoria', 'commit', 'rollback'])
def test_fallo_al_auditar_no_reemplaza_el_rechazo(punto, caplog):
    e = escenario()
    e.ciclo.obtener_abierto.return_value = None
    destino = {'activo': e.activos.obtener, 'auditoria': e.auditoria.registrar,
               'commit': e.db.commit, 'rollback': e.db.rollback}[punto]
    destino.side_effect = RuntimeError('SQL y secretos que no deben registrarse')
    with pytest.raises(ConflictError) as rechazo:
        e.uc.execute(e.dto, e.usuario)
    assert rechazo.value.code == 'CICLO_NO_ACTIVO'
    assert 'No se pudo auditar' in caplog.text
    assert 'SQL y secretos' not in caplog.text


def test_activo_no_visible_no_produce_referencia_ajena():
    e = escenario()
    e.activos.obtener.return_value = None
    e.ciclo.obtener_abierto.return_value = None
    with pytest.raises(ConflictError):
        e.uc.execute(e.dto, e.usuario)
    evento = e.auditoria.registrar.call_args.args[0]
    assert evento.id_activo_biologico is None and evento.id_gestion_fases is None
    assert evento.registro_incompleto
    assert 'Activo solicitado: 8' in evento.detalle_causa


def test_idempotencia_conserva_prioridad_sin_evento_de_rechazo():
    e = escenario()
    existente = object()
    e.repo.existe_idempotente.return_value = existente
    e.ciclo.obtener_abierto.return_value = None
    resultado = e.uc.execute(e.dto, e.usuario)
    assert resultado.estado == 'YA_PROCESADO' and resultado.registro is existente
    e.auditoria.registrar.assert_not_called()
    e.ciclo.obtener_abierto.assert_not_called()
    e.db.rollback.assert_not_called()


def test_registro_valido_conserva_movimiento_y_un_commit():
    e = escenario()
    resultado = e.uc.execute(e.dto, e.usuario)
    assert resultado.estado == 'REGISTRADO'
    assert resultado.registro.costo_registro == Decimal('20')
    e.movimiento.registrar.assert_called_once()
    e.auditoria.registrar.assert_not_called()
    e.db.commit.assert_called_once()
    e.db.rollback.assert_not_called()


def test_fallo_tecnico_conserva_reintentos_y_evento_fallido(monkeypatch):
    from src.shared.errors import InfrastructureError
    e = escenario()
    e.repo.guardar.side_effect = InfrastructureError(code='ERROR_INTERNO', message='No disponible')
    monkeypatch.setattr('src.supplies.application.use_cases.costeo_suministros.registrar_suministro_directo_use_case.time.sleep', lambda _: None)
    with pytest.raises(InfrastructureError):
        e.uc.execute(e.dto, e.usuario)
    assert e.repo.guardar.call_count == 4  # intento inicial + 3 reintentos (RF-78 restricción 9)
    e.auditoria.registrar.assert_called_once()
    evento = e.auditoria.registrar.call_args.args[0]
    assert evento.resultado == 'FALLIDO' and evento.numero_reintentos == 3
    e.activos.obtener.assert_not_called()


def test_error_tecnico_de_lectura_no_se_presenta_como_rechazo():
    from src.shared.errors import ServiceUnavailableError
    e = escenario()
    e.repo.existe_idempotente.side_effect = ServiceUnavailableError(code='SERVICIO_NO_DISPONIBLE', message='No disponible')
    with pytest.raises(ServiceUnavailableError):
        e.uc.execute(e.dto, e.usuario)
    e.auditoria.registrar.assert_not_called()
