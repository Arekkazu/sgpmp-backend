# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-20 | Arekkazu | QA-M07 CU04 H-02/H-03/S-02 y CU07 H-01: cupo, avisos de bloqueo y días del filtro |
"""Reporte de QA de M07 del 2026-11-19 (CU04 y CU07), sin base de datos."""
from datetime import date, datetime, timezone
from unittest.mock import MagicMock

import pytest

from src.accounting_integration.application.use_cases.contratos.gestionar_contratos_use_case import (
    GestionarContratosUseCase,
)
from src.accounting_integration.domain.entities.contrato import AnexoMapeo, VersionContrato, exigir_cupo
from src.accounting_integration.domain.repositories.auditoria_integracion_repository import FiltrosAuditoria
from src.accounting_integration.infrastructure.repositories import auditoria_integracion_repository as repo_mod
from src.shared.errors import AppError

RETIRO_2_1 = datetime(2027, 2, 16, 15, 0, tzinfo=timezone.utc)


def _version(id_, version, estado="PENDIENTE", tipo="MINOR", anexo=1, fecha_inactivacion=None):
    return VersionContrato(id_, version, tipo, date(2026, 11, 1), anexo, ["COMPRAS"],
                           periodo_gracia_dias=90 if tipo == "MAJOR" else None, estado=estado,
                           fecha_inactivacion=fecha_inactivacion)


def _test_estado():
    """TEST del 19-11: 3.0 activa, 2.1 en retiro, 4.0 pendiente con anexo aprobado y 5.0 con anexo en borrador."""
    return [_version(30, "3.0", "ACTIVO", "MAJOR"), _version(21, "2.1", "DEPRECADO", fecha_inactivacion=RETIRO_2_1),
            _version(40, "4.0", tipo="MAJOR"), _version(50, "5.0", anexo=2)]


def _caso(contratos, avisados_hoy=0):
    repo = MagicMock()
    repo.listar_contratos.return_value = contratos
    repo.obtener_anexo.side_effect = lambda id_: AnexoMapeo(
        id_, "AAEF", "3.0", "doc", "a" * 64, estado="APROBADO" if id_ == 1 else "BORRADOR")
    auditoria = MagicMock()
    auditoria.consultar.return_value = ([], avisados_hoy)
    alertar = MagicMock()
    return GestionarContratosUseCase(repo, auditoria, MagicMock(), lambda: True, alertar), auditoria, alertar


def test_h02_con_una_version_en_retiro_dice_cuando_se_libera_el_cupo(en_colombia):
    with pytest.raises(AppError) as e:
        exigir_cupo(_version(82, "8.2"), _test_estado())
    assert e.value.code == "LIMITE_VERSIONES_EXCEDIDO"
    assert "2.1 ya está en retiro hasta el 16/02/2027" in e.value.message
    assert "Retire primero" not in e.value.message


def test_h02_con_dos_activas_nombra_la_que_debe_pasar_a_retiro():
    with pytest.raises(AppError) as e:
        exigir_cupo(_version(82, "8.2"), [_version(30, "3.0", "ACTIVO"), _version(40, "4.0", "ACTIVO")])
    assert "Retire primero la versión 3.0" in e.value.message


def test_h03_cada_version_bloqueada_se_audita_con_su_codigo_y_se_avisa():
    caso, auditoria, alertar = _caso(_test_estado())
    assert caso.procesar_vigencias(date(2026, 11, 20)) == 0
    eventos = {e.args[0].version_contrato: e.args[0] for e in auditoria.registrar.call_args_list}
    assert eventos["4.0"].codigo_resultado == "LIMITE_VERSIONES_EXCEDIDO"
    assert eventos["5.0"].codigo_resultado == "CONTRATO_NO_VALIDO"
    assert "anexo de mapeo aprobado" in eventos["5.0"].json_detalle["motivo"]
    avisos = [c.args[0] for c in alertar.call_args_list]
    assert len(avisos) == 2 and "4.0" in avisos[0] and "5.0" in avisos[1] and "anexo" in avisos[1]


def test_s02_el_aviso_diario_se_cuenta_en_la_auditoria_y_sobrevive_al_reinicio():
    caso, auditoria, alertar = _caso(_test_estado(), avisados_hoy=1)
    caso.procesar_vigencias(date(2026, 11, 20))
    alertar.assert_not_called()
    auditoria.registrar.assert_not_called()
    filtros = {c.args[0] for c in auditoria.consultar.call_args_list}
    assert FiltrosAuditoria(("CONTRATO_ACTIVACION_BLOQUEADA",), desde=date(2026, 11, 20), hasta=date(2026, 11, 20),
                            version_contrato="5.0") in filtros


def test_h01_cu07_desde_y_hasta_son_dias_del_usuario(monkeypatch, en_colombia):
    capturados = {}
    monkeypatch.setattr(repo_mod, "filas", lambda db, sql, params: capturados.update(sql=sql, **params) or [])
    repo_mod.SqlAlchemyAuditoriaIntegracionRepository(MagicMock()).consultar(
        FiltrosAuditoria(desde=date(2026, 11, 19), hasta=date(2026, 11, 19)), 1, 50)
    assert capturados["desde"] == datetime(2026, 11, 19, 5, 0, tzinfo=timezone.utc)
    assert capturados["hasta"] == datetime(2026, 11, 20, 4, 59, 59, 999999, tzinfo=timezone.utc)
    assert "CAST(:desde AS date)" not in capturados["sql"]
