# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-11-14 | destroyerban     | INC-M05-353-G37 RF-80: rechazos de RF-79/RF-81 auditados y campos mínimos por tipo |
"""Regresión de INC-M05-353-G37 (TC-M05-G37, checkpoints A02c, A02d y A04).

- A02c: consolidar con el ciclo activo → 409 y un evento ``RECHAZADO``.
- A02d: historial con filtros inválidos → 422 y un evento ``RECHAZADO``.
- A04: cada evento trae los campos mínimos de su tipo (Restricción 8) o queda
  ``registro_incompleto`` con ``detalle_causa`` nombrando cada campo faltante.
"""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from src.shared.errors import (
    AuthorizationError,
    BusinessRuleError,
    ConflictError,
    InfrastructureError,
    NotFoundError,
    ValidationError,
)
from src.supplies.application.use_cases.costeo_suministros.movimiento_ledger import RegistradorMovimientoLedger
from src.supplies.application.use_cases.historial_suministros.auditoria_historial import ciclo_del_resultado
from src.supplies.application.use_cases.historial_suministros.consultar_historial_suministros_use_case import (
    ConsultarHistorialSuministrosUseCase,
)
from src.supplies.application.use_cases.historial_suministros.exportar_historial_sincrono_use_case import (
    ExportarHistorialSincronoUseCase,
)
from src.supplies.application.use_cases.provision_nic41.consolidar_ciclo_use_case import ConsolidarCicloUseCase
from src.supplies.application.use_cases.provision_nic41.corregir_provision_use_case import CorregirProvisionUseCase
from src.supplies.domain.entities.evento_auditoria_suministro import EventoAuditoriaSuministroConsulta
from src.supplies.domain.entities.historial_suministro import FiltrosHistorialSuministro
from src.supplies.domain.repositories.auditoria_suministro_port import EventoAuditoriaSuministro
from src.supplies.domain.repositories.ciclo_abierto_port import FaseProductiva
from src.supplies.infrastructure.repositories.auditoria_suministro_repository import (
    SqlAlchemyAuditoriaSuministroRepository,
)
from src.supplies.infrastructure.schema.auditoria_suministro_schema import EventoAuditoriaSuministroResponse

USUARIO = SimpleNamespace(id_usuario=7, id_rol=1)


def _evento(**cambios):
    base = dict(entidad_afectada='registro_suministro', tipo_operacion='SUMINISTRO_REGISTRADO',
                id_usuario=7, resultado='EXITOSO')
    return EventoAuditoriaSuministro(**(base | cambios))


def _emitidos(puerto):
    return [c.args[0] for c in puerto.registrar.call_args_list]


# ── A04: campos mínimos por tipo (Restricción 8) ────────────────────────────────
@pytest.mark.parametrize('tipo,campos,faltantes', [
    ('SUMINISTRO_REGISTRADO', {'costo_afectado': Decimal('5'), 'origen_precio': 'MANUAL'},
     ['registro de suministro', 'tipo de suministro']),
    ('PRECIO_MANUAL_INGRESADO', {'origen_precio': 'MANUAL'}, ['registro de suministro']),
    ('ACUMULADO_ACTUALIZADO', {'costo_afectado': Decimal('5')}, ['registro de suministro']),
    ('REGISTRO_FALLIDO', {'numero_reintentos': 0}, ['tipo de suministro']),
    ('CICLO_CONSOLIDADO', {}, ['costo afectado']),
    ('PROVISION_INCREMENTAL_FALLIDA', {'id_registro_suministro': uuid4()},
     ['número de reintentos', 'fechas de los intentos']),
    ('PROVISION_PENDIENTE', {}, ['número de reintentos']),
])
def test_falta_un_minimo_del_tipo_marca_incompleto_y_lo_nombra(tipo, campos, faltantes):
    e = _evento(tipo_operacion=tipo, id_activo_biologico=8, id_ciclo_productivo=4, **campos)
    assert e.registro_incompleto is True
    assert e.detalle_causa.endswith('Campos faltantes: ' + ', '.join(faltantes) + '.')


def test_consulta_sin_ciclo_queda_incompleta():
    e = _evento(tipo_operacion='CONSULTA_HISTORIAL_EJECUTADA', id_activo_biologico=8)
    assert e.registro_incompleto and 'Campos faltantes: ciclo productivo.' in e.detalle_causa


def test_evento_con_todos_sus_minimos_queda_completo():
    e = _evento(id_activo_biologico=8, id_ciclo_productivo=4, id_registro_suministro=uuid4(),
                id_tipo_suministro='SERVICIO_VETERINARIO', costo_afectado=Decimal('5'), origen_precio='MANUAL')
    assert e.registro_incompleto is False and e.detalle_causa is None


def test_causa_del_emisor_se_conserva_antes_de_los_faltantes():
    e = _evento(tipo_operacion='REGISTRO_FALLIDO', numero_reintentos=0, id_activo_biologico=8,
                detalle_causa='Registro de suministro rechazado.')
    assert e.detalle_causa == (
        'Registro de suministro rechazado. Campos faltantes: ciclo productivo, tipo de suministro.')


def test_detalle_sin_nombres_de_columna():
    e = _evento(tipo_operacion='PROVISION_INCREMENTAL_FALLIDA')
    assert not any(c in e.detalle_causa for c in ('id_', 'numero_reintentos', 'fecha_intentos', 'costo_afectado'))


# ── Registro y tipo de suministro: escritura y lectura ──────────────────────────
def test_registro_y_tipo_viajan_en_datos_nuevos_sin_pisar_el_contexto():
    id_registro = uuid4()
    e = _evento(datos_nuevos={'formato': 'PDF'}, id_registro_suministro=id_registro, id_tipo_suministro='ALIMENTO')
    assert e.datos_nuevos_con_referencias() == {
        'formato': 'PDF', 'id_registro_suministro': str(id_registro), 'id_tipo_suministro': 'ALIMENTO'}
    assert _evento(datos_nuevos={'a': 1}).datos_nuevos_con_referencias() == {'a': 1}
    assert _evento().datos_nuevos_con_referencias() is None


def test_el_repositorio_escribe_las_referencias_en_datos_nuevos():
    db = Mock()
    SqlAlchemyAuditoriaSuministroRepository(db).registrar(
        _evento(id_registro_suministro='abc', id_tipo_suministro='ALIMENTO'))
    valores = db.execute.call_args.args[0].compile().params
    assert valores['datos_nuevos'] == {'id_registro_suministro': 'abc', 'id_tipo_suministro': 'ALIMENTO'}


def _consulta(datos_nuevos):
    return EventoAuditoriaSuministroConsulta(
        id_auditoria_suministro=1, entidad_afectada='registro_suministro', tipo_operacion='SUMINISTRO_REGISTRADO',
        id_usuario=7, resultado='EXITOSO', fecha_evento=datetime.now(timezone.utc), datos_anteriores=None,
        datos_nuevos=datos_nuevos, ip_origen=None, id_sesion=None, fecha_emision=None, id_activo_biologico=8,
        id_ciclo_productivo=4, costo_afectado=None, origen_precio=None, clasificacion_registro='NIC41',
        retencion_aplicable='5 años', hash_integridad='a' * 64, registro_incompleto=False, detalle_causa=None,
        numero_reintentos=None, fecha_intentos=None, id_gestion_fases=None, id_evento_m05=uuid4(),
    )


def test_la_respuesta_expone_registro_y_tipo_en_primer_nivel():
    r = EventoAuditoriaSuministroResponse.model_validate(
        _consulta({'id_registro_suministro': 'abc', 'id_tipo_suministro': 'ALIMENTO'}))
    assert (r.id_registro_suministro, r.id_tipo_suministro) == ('abc', 'ALIMENTO')
    vacio = EventoAuditoriaSuministroResponse.model_validate(_consulta(None))
    assert (vacio.id_registro_suministro, vacio.id_tipo_suministro) == (None, None)


def test_movimiento_del_ledger_emite_registro_y_tipo_en_sus_tres_eventos():
    auditoria, acumulados, outbox = Mock(), Mock(), Mock()
    acumulados.obtener.return_value = SimpleNamespace(acumulado_total_ciclo=Decimal('20'),
                                                      acumulado_por_categoria={})
    registro = SimpleNamespace(
        id_registro_suministro=uuid4(), tipo_suministro='SERVICIO_VETERINARIO', tipo_operacion='REGISTRO',
        id_activo_biologico=8, id_ciclo_productivo=4, id_gestion_fases=23, costo_registro=Decimal('20'),
        origen_precio='MANUAL', fecha_aplicacion=date.today(),
    )
    RegistradorMovimientoLedger(acumulados, auditoria, outbox).registrar(registro, id_usuario=7, precio_manual=True)
    eventos = _emitidos(auditoria)
    assert [e.tipo_operacion for e in eventos] == [
        'SUMINISTRO_REGISTRADO', 'PRECIO_MANUAL_INGRESADO', 'ACUMULADO_ACTUALIZADO']
    for e in eventos:
        assert e.id_registro_suministro == str(registro.id_registro_suministro)
        assert e.id_tipo_suministro == 'SERVICIO_VETERINARIO'
        assert e.registro_incompleto is False, e.detalle_causa


# ── A02c: rechazos de RF-79 ─────────────────────────────────────────────────────
def _fase(activa=True):
    return FaseProductiva(id_gestion_fases=834, id_activo_biologico=1850, id_ciclo_productivo=12,
                          fecha_inicio=datetime.now(timezone.utc), fecha_finalizacion=None if activa else
                          datetime.now(timezone.utc), es_activa=activa)


def _consolidar():
    db, ciclo, auditoria = Mock(), Mock(), Mock()
    ciclo.obtener_por_id.return_value = _fase()
    uc = ConsolidarCicloUseCase(db, ciclo, Mock(), Mock(), Mock(), auditoria, Mock())
    return SimpleNamespace(uc=uc, db=db, ciclo=ciclo, auditoria=auditoria)


def test_consolidar_con_ciclo_activo_deja_un_evento_rechazado():
    c = _consolidar()
    orden = []
    c.db.rollback.side_effect = lambda: orden.append('rollback')
    c.auditoria.registrar.side_effect = lambda e: orden.append('evento')
    c.db.commit.side_effect = lambda: orden.append('commit')
    with pytest.raises(ConflictError) as rechazo:
        c.uc.execute(834, USUARIO)
    assert rechazo.value.code == 'CICLO_ACTIVO'
    assert orden == ['rollback', 'evento', 'commit']
    (evento,) = _emitidos(c.auditoria)
    assert (evento.tipo_operacion, evento.resultado, evento.id_usuario) == ('CICLO_CONSOLIDADO', 'RECHAZADO', 7)
    assert (evento.id_activo_biologico, evento.id_ciclo_productivo, evento.id_gestion_fases) == (1850, 12, 834)
    assert 'sigue activo' in evento.detalle_causa and 'CICLO_ACTIVO' not in evento.detalle_causa
    # Restricción 8: un rechazo no movió costo, así que lo declara faltante.
    assert evento.registro_incompleto and 'Campos faltantes: costo afectado.' in evento.detalle_causa


def test_consolidar_ciclo_inexistente_no_enlaza_claves():
    c = _consolidar()
    c.ciclo.obtener_por_id.return_value = None
    with pytest.raises(NotFoundError):
        c.uc.execute(999, USUARIO)
    (evento,) = _emitidos(c.auditoria)
    assert evento.resultado == 'RECHAZADO' and evento.id_activo_biologico is None and evento.id_gestion_fases is None
    assert 'Instancia de ciclo solicitada: 999.' in evento.detalle_causa


def test_error_interno_al_consolidar_queda_como_fallido():
    c = _consolidar()
    c.ciclo.obtener_por_id.side_effect = [InfrastructureError(code='ERROR_BD', message='x'), _fase()]
    with pytest.raises(InfrastructureError):
        c.uc.execute(834, USUARIO)
    (evento,) = _emitidos(c.auditoria)
    assert evento.resultado == 'FALLIDO' and 'error interno' in evento.detalle_causa


def test_si_la_auditoria_falla_se_conserva_el_rechazo(caplog):
    c = _consolidar()
    c.auditoria.registrar.side_effect = RuntimeError('secreto')
    with pytest.raises(ConflictError) as rechazo:
        c.uc.execute(834, USUARIO)
    assert rechazo.value.code == 'CICLO_ACTIVO'
    assert 'No se pudo auditar' in caplog.text and 'secreto' not in caplog.text


@pytest.mark.parametrize('caso,error', [
    ('inexistente', NotFoundError), ('motivo', ValidationError), ('activo', ConflictError)])
def test_corregir_provision_rechazada_deja_reporte_costos_rechazado(caso, error):
    c = _consolidar()
    provisiones = Mock()
    provisiones.obtener.return_value = None if caso == 'inexistente' else SimpleNamespace(id_gestion_fases=834)
    uc = CorregirProvisionUseCase(c.db, provisiones, c.uc)
    motivo = 'corto' if caso == 'motivo' else 'Se corrige el monto por un consumo mal registrado en el ciclo.'
    with pytest.raises(error):
        uc.execute(5, motivo, USUARIO)
    (evento,) = _emitidos(c.auditoria)
    assert (evento.tipo_operacion, evento.resultado) == ('REPORTE_COSTOS_GENERADO', 'RECHAZADO')
    assert evento.detalle_causa.startswith('Corrección del reporte consolidado rechazada:')
    assert (evento.id_gestion_fases is None) == (caso == 'inexistente')


# ── A02d: rechazos de RF-81 ─────────────────────────────────────────────────────
def _historial(clase):
    db, historial, alcance, activos, config, auditoria = (Mock() for _ in range(6))
    activos.obtener.return_value = SimpleNamespace(id_activo_biologico=1850)
    alcance.listar_ids_activos_permitidos.return_value = None
    historial.ciclo_pertenece_a_activo.return_value = True
    uc = clase(historial, alcance, activos, config, db, auditoria)
    return SimpleNamespace(uc=uc, db=db, historial=historial, activos=activos, auditoria=auditoria)


def _filtros(**cambios):
    return FiltrosHistorialSuministro(**({'id_activo_biologico': 1850} | cambios))


def test_historial_con_fechas_invertidas_deja_un_evento_rechazado():
    h = _historial(ConsultarHistorialSuministrosUseCase)
    hoy = date.today()
    with pytest.raises(BusinessRuleError) as rechazo:
        h.uc.execute(_filtros(fecha_inicio_filtro=hoy, fecha_fin_filtro=hoy - timedelta(days=5)),
                     id_usuario=7, id_rol=1)
    assert rechazo.value.code == 'COMBINACION_FILTROS_INVALIDA'
    (evento,) = _emitidos(h.auditoria)
    assert (evento.tipo_operacion, evento.resultado, evento.id_usuario) == (
        'CONSULTA_HISTORIAL_EJECUTADA', 'RECHAZADO', 7)
    assert evento.id_activo_biologico == 1850
    assert 'la fecha final del filtro es anterior a la fecha inicial' in evento.detalle_causa
    assert 'fecha_fin_filtro' not in evento.detalle_causa
    assert evento.datos_nuevos['filtros_aplicados']['fecha_fin_filtro'] == (hoy - timedelta(days=5)).isoformat()
    assert evento.registro_incompleto and 'Campos faltantes: ciclo productivo.' in evento.detalle_causa
    h.db.commit.assert_called_once()


def test_historial_de_activo_ajeno_no_enlaza_el_activo():
    h = _historial(ConsultarHistorialSuministrosUseCase)
    h.activos.obtener.return_value = None
    h.activos.existe.return_value = True
    with pytest.raises(AuthorizationError):
        h.uc.execute(_filtros(), id_usuario=7, id_rol=1)
    (evento,) = _emitidos(h.auditoria)
    assert evento.id_activo_biologico is None and 'Activo solicitado: 1850.' in evento.detalle_causa


def test_ciclo_ajeno_al_activo_no_se_enlaza():
    h = _historial(ConsultarHistorialSuministrosUseCase)
    h.historial.ciclo_pertenece_a_activo.return_value = False
    with pytest.raises(BusinessRuleError):
        h.uc.execute(_filtros(id_ciclo_productivo=99), id_usuario=7, id_rol=1)
    (evento,) = _emitidos(h.auditoria)
    assert evento.id_ciclo_productivo is None
    assert evento.datos_nuevos['filtros_aplicados']['id_ciclo_productivo'] == 99


def test_exportacion_rechazada_deja_su_evento_con_el_formato():
    h = _historial(ExportarHistorialSincronoUseCase)
    with pytest.raises(BusinessRuleError):
        h.uc.execute(_filtros(), 'CSV', id_usuario=7, id_rol=1)
    (evento,) = _emitidos(h.auditoria)
    assert (evento.tipo_operacion, evento.resultado) == ('EXPORTACION_HISTORIAL_GENERADA', 'RECHAZADO')
    assert evento.datos_nuevos['formato_exportacion'] == 'CSV'
    assert 'el formato de exportación no es PDF ni Excel' in evento.detalle_causa


# ── Ciclo del evento exitoso del historial ──────────────────────────────────────
def _resultado(ciclos):
    return SimpleNamespace(lineas=[SimpleNamespace(id_ciclo_productivo=c) for c in ciclos],
                           desglose_por_ciclo={f'c{c}': {} for c in set(ciclos)})


@pytest.mark.parametrize('filtro,ciclos,esperado', [
    (5, [7, 8], 5),     # el filtrado manda
    (None, [7, 7], 7),  # un solo ciclo en el resultado
    (None, [7, 8], None),  # varios: no hay uno solo que registrar
    (None, [], None),
])
def test_ciclo_del_resultado(filtro, ciclos, esperado):
    assert ciclo_del_resultado(_filtros(id_ciclo_productivo=filtro), _resultado(ciclos)) == esperado
