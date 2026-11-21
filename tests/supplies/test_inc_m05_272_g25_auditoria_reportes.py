# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-11-07 | Leandro | INC-M05-272-G25 RF-77: verificar auditoría de generación, regeneración y exportación con fakes. |
"""Regresiones de #958; las garantías de persistencia se prueban aparte con PostgreSQL."""
from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from src.supplies.application.use_cases.reporte_gastos.generar_reporte_gastos_use_case import GenerarReporteGastosUseCase
from src.supplies.application.use_cases.reporte_gastos.exportar_reporte_gastos_use_case import ExportarReporteGastosUseCase
from src.supplies.application.use_cases.reporte_gastos.consultar_reporte_gastos_use_case import ConsultarReporteGastosUseCase
from src.supplies.domain.entities.reporte_gasto import FiltrosReporteGasto, ReporteGasto


def reporte():
    return ReporteGasto(fecha_inicio=date(2026,1,1),fecha_fin=date(2026,1,2),tipo_periodo='CICLO_COMPLETO',
        gasto_total_acumulado=Decimal('25'),id_activo_biologico=8,id_usuario=7,
        id_reporte_gasto_acumulado=31,fecha_generacion=datetime.now(timezone.utc),
        parametros={'fecha_inicio':'2026-01-01','fecha_fin':'2026-01-02','id_activo_biologico':8})


def generador(db,auditoria):
    repo=Mock()
    repo.guardar.side_effect=lambda r:r
    g=GenerarReporteGastosUseCase(db,Mock(),Mock(),repo,Mock(),Mock(),Mock(),auditoria)
    return g


def test_generacion_persistida_emite_evento_antes_del_commit():
    db,auditoria=Mock(),Mock()
    g=generador(db,auditoria)
    orden=[]
    auditoria.registrar.side_effect=lambda e:orden.append('auditoria')
    db.commit.side_effect=lambda:orden.append('commit')
    g._persistir(reporte())
    auditoria.registrar.assert_called_once()
    e=auditoria.registrar.call_args.args[0]
    assert e.id_usuario==7 and e.resultado=='EXITOSO'
    assert e.entidad_afectada=='reporte_gastos_acumulados'
    assert orden==['auditoria','commit']


@pytest.mark.parametrize('formato',['CSV','PDF'])
def test_exportacion_exitosa_audita_archivo_y_actor(formato):
    db,auditoria,archivos=Mock(),Mock(),Mock()
    def guardar(a):
        a.id_archivo=uuid4()
        return a
    archivos.guardar.side_effect=guardar
    e=ExportarReporteGastosUseCase(db,Mock(),Mock(),archivos,SimpleNamespace(ruta_logo=lambda **_:None),auditoria)
    archivo=e.exportar(reporte(),formato,7)
    auditoria.registrar.assert_called_once()
    evento=auditoria.registrar.call_args.args[0]
    assert evento.id_usuario==7 and evento.resultado=='EXITOSO'
    assert evento.entidad_afectada=='archivos_exportacion_suministros'
    assert evento.datos_nuevos['id_archivo']==str(archivo.id_archivo)


@pytest.mark.parametrize('etapa',['guardar','auditar','commit'])
def test_generacion_revierte_si_falla_la_transaccion(etapa):
    db,auditoria=Mock(),Mock()
    g=generador(db,auditoria)
    if etapa=='guardar':
        g.reporte_repo.guardar.side_effect=RuntimeError('guardar')
    elif etapa=='auditar':
        auditoria.registrar.side_effect=RuntimeError('auditar')
    else:
        db.commit.side_effect=RuntimeError('commit')
    with pytest.raises(RuntimeError,match=etapa):
        g._persistir(reporte())
    db.rollback.assert_called_once()
    if etapa=='guardar':
        auditoria.registrar.assert_not_called()


def test_generacion_forzada_conserva_usuario_solicitante():
    db,auditoria=Mock(),Mock()
    g=generador(db,auditoria)
    g._validar=Mock(return_value=None)
    def construir(filtros,id_usuario,*args):
        r=reporte()
        r.id_usuario=id_usuario
        return r
    g.construir=construir
    g.generar_forzado(FiltrosReporteGasto(date(2026,1,1),date(2026,1,2),id_activo_biologico=8),17,[8])
    assert auditoria.registrar.call_args.args[0].id_usuario==17
    auditoria.registrar.assert_called_once()


def test_encolar_no_anuncia_un_reporte_aun_no_generado():
    db,auditoria=Mock(),Mock()
    g=generador(db,auditoria)
    g.trabajo_repo.encolar.side_effect=lambda t:t
    g._encolar(FiltrosReporteGasto(date(2024,1,1),date(2026,1,2),id_activo_biologico=8),7,[8],'CSV')
    auditoria.registrar.assert_not_called()
    g.reporte_repo.guardar.assert_not_called()
    db.commit.assert_called_once()


@pytest.mark.parametrize('etapa',['guardar','auditar','commit'])
def test_exportacion_revierte_si_falla_la_transaccion(etapa):
    db,auditoria,archivos=Mock(),Mock(),Mock()
    def guardar(a):
        a.id_archivo=uuid4()
        return a
    archivos.guardar.side_effect=guardar if etapa!='guardar' else RuntimeError('guardar')
    if etapa=='auditar':
        auditoria.registrar.side_effect=RuntimeError('auditar')
    if etapa=='commit':
        db.commit.side_effect=RuntimeError('commit')
    uc=ExportarReporteGastosUseCase(db,Mock(),Mock(),archivos,Mock(),auditoria)
    with pytest.raises(RuntimeError,match=etapa):
        uc.exportar(reporte(),'CSV',7)
    db.rollback.assert_called_once()
    if etapa=='guardar':
        auditoria.registrar.assert_not_called()


def test_exportar_reconstruye_sin_emitir_otra_generacion():
    db,auditoria,archivos,g=Mock(),Mock(),Mock(),Mock()
    r=reporte()
    g.construir_desde_parametros.return_value=r
    repo=Mock(obtener=Mock(return_value=r))
    archivos.guardar.side_effect=lambda a:a
    uc=ExportarReporteGastosUseCase(db,repo,g,archivos,Mock(),auditoria)
    uc.execute(31,'CSV',SimpleNamespace(id_usuario=9))
    g.construir_desde_parametros.assert_called_once()
    g.execute.assert_not_called()
    auditoria.registrar.assert_called_once()
    assert auditoria.registrar.call_args.args[0].id_usuario==9


def test_regeneracion_audita_actor_y_referencia_original():
    db,auditoria,g=Mock(),Mock(),Mock()
    original=reporte()
    nuevo=reporte()
    nuevo.id_reporte_gasto_acumulado=None
    g.construir_desde_parametros.return_value=nuevo
    uc=ConsultarReporteGastosUseCase(Mock(obtener=Mock(return_value=original)),db,auditoria,g)
    r,aviso=uc.regenerar(31,SimpleNamespace(id_usuario=9))
    assert r is nuevo and aviso and nuevo.id_reporte_gasto_acumulado is None
    e=auditoria.registrar.call_args.args[0]
    assert e.tipo_operacion=='SELECT' and e.id_usuario==9
    assert e.datos_nuevos['accion']=='REGENERACION' and e.datos_nuevos['id_reporte_gasto_acumulado']==31
    db.commit.assert_called_once()


def test_consulta_sin_regenerar_no_emite_evento_de_generacion():
    db,auditoria=Mock(),Mock()
    uc=ConsultarReporteGastosUseCase(Mock(obtener=Mock(return_value=reporte())),db,auditoria)
    uc.execute(31)
    auditoria.registrar.assert_not_called()
    db.commit.assert_not_called()


def test_regeneracion_fallida_no_confirma_auditoria():
    db,auditoria,g=Mock(),Mock(),Mock()
    g.construir_desde_parametros.return_value=reporte()
    auditoria.registrar.side_effect=RuntimeError('auditar')
    uc=ConsultarReporteGastosUseCase(Mock(obtener=Mock(return_value=reporte())),db,auditoria,g)
    with pytest.raises(RuntimeError,match='auditar'):
        uc.regenerar(31,SimpleNamespace(id_usuario=9))
    db.rollback.assert_called_once()
    db.commit.assert_not_called()


@pytest.mark.parametrize('limite',['PDF','CSV'])
def test_exportacion_rechazada_por_limites_no_anuncia_exito(monkeypatch,limite):
    from src.shared.errors import AppError
    from src.supplies.application.use_cases.reporte_gastos import exportar_reporte_gastos_use_case as modulo
    db,auditoria,archivos=Mock(),Mock(),Mock()
    r=reporte()
    if limite=='PDF':
        monkeypatch.setattr(modulo,'MAX_REGISTROS_PDF',-1)
    else:
        monkeypatch.setattr(modulo,'MAX_BYTES_CSV',0)
    uc=ExportarReporteGastosUseCase(db,Mock(),Mock(),archivos,Mock(),auditoria)
    with pytest.raises(AppError):
        uc.exportar(r,limite,7)
    auditoria.registrar.assert_not_called()
    archivos.guardar.assert_not_called()


def test_fallo_pdf_audita_solo_el_fallo(monkeypatch):
    from src.shared.errors import InfrastructureError
    from src.supplies.application.use_cases.reporte_gastos import exportar_reporte_gastos_use_case as modulo
    db,auditoria,archivos=Mock(),Mock(),Mock()
    monkeypatch.setattr(modulo,'generar_pdf',Mock(side_effect=RuntimeError('motor')))
    uc=ExportarReporteGastosUseCase(db,Mock(),Mock(),archivos,SimpleNamespace(ruta_logo=lambda **_:None),auditoria)
    with pytest.raises(InfrastructureError):
        uc.exportar(reporte(),'PDF',7)
    e=auditoria.registrar.call_args.args[0]
    assert e.resultado=='FALLIDO' and e.tipo_operacion=='REGISTRO_FALLIDO'
    auditoria.registrar.assert_called_once()
    archivos.guardar.assert_not_called()
