# | Fecha      | Nombre      | Que se hizo |
# |------------|-------------|-------------|
# | 2026-11-17 | Laura López | TC-M07-G054: rollback auditoría bloqueante vs continuidad no bloqueante. |
"""Pruebas controladas RF-102 ante fallo de persistencia de auditoría (sin BD TEST).

Clasificación (código):
  BLOQUEANTE — M07.auditoria (misma Session) + commit/rollback en caso de uso
               RF-101 clientes, RF-98 contratos/anexos.
  NO BLOQUEANTE — M07.auditar_aparte = registrador_aparte (sesión propia; traga excepción + alerta)
               RF-95 gateway/vista, RF-97 vía consulta AAEF, RF-101 emisión token canal.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.accounting_integration.application.use_cases.canal.emitir_token_canal_use_case import EmitirTokenCanalUseCase
from src.accounting_integration.application.use_cases.clientes.gestionar_cliente_externo_use_case import (
    GestionarClienteExternoUseCase,
)
from src.accounting_integration.application.use_cases.clientes.registrar_cliente_externo_use_case import (
    RegistrarClienteExternoUseCase,
    SolicitudCliente,
)
from src.accounting_integration.application.use_cases.contratos.gestionar_contratos_use_case import (
    GestionarContratosUseCase,
    SolicitudContrato,
)
from src.accounting_integration.domain.entities.cliente_externo import ClienteExterno
from src.accounting_integration.domain.entities.contrato import AnexoMapeo, VersionContrato
from src.accounting_integration.domain.entities.evento_integracion import EventoIntegracion
from src.accounting_integration.infrastructure.repositories.auditoria_integracion_repository import (
    registrador_aparte,
)
from src.shared.errors import InfrastructureError

AHORA = datetime(2026, 11, 17, 22, 0, tzinfo=timezone.utc)
VENC = date(2027, 12, 31)


def _fallo_auditoria(*_a, **_k):
    raise InfrastructureError(code="AUDITORIA_FALLIDA_QA", message="Fallo controlado de persistencia de auditoría (G054).")


class TestE1AuditoriaBloqueante:
    def test_registrar_cliente_rollback_si_falla_auditoria(self):
        clientes = MagicMock()
        clientes.obtener_por_identificador.return_value = None
        cliente = ClienteExterno(42, "QA54", "Cliente QA G054", "qa-g054-client", canales={"CONSULTA_AAEF": 10})
        clientes.guardar.return_value = cliente
        auditoria = MagicMock()
        auditoria.registrar.side_effect = _fallo_auditoria
        db = MagicMock()
        uc = RegistrarClienteExternoUseCase(clientes, auditoria, db)

        with pytest.raises(InfrastructureError) as exc:
            uc.execute(SolicitudCliente("QA54", "Cliente QA G054", "qa-g054-client", VENC,
                                        canales={"CONSULTA_AAEF": 10}, secreto="TEST_SECRET_G054_FICTICIO"), 7)

        assert exc.value.code == "AUDITORIA_FALLIDA_QA"
        assert clientes.guardar.called
        assert auditoria.registrar.called
        assert db.rollback.called
        assert not db.commit.called

    def test_suspender_cliente_rollback_si_falla_auditoria(self):
        cliente = ClienteExterno(9, "QA", "QA", "qa-g054", estado="ACTIVO", canales={"TOKEN": 5})
        clientes = MagicMock()
        clientes.obtener.return_value = cliente
        clientes.guardar.side_effect = lambda c: c
        auditoria = MagicMock()
        auditoria.registrar.side_effect = _fallo_auditoria
        db = MagicMock()
        uc = GestionarClienteExternoUseCase(clientes, auditoria, db)

        with pytest.raises(InfrastructureError):
            uc.cambiar_estado(9, "suspender", "fallo auditoría controlado G054", 1)

        assert cliente.estado == "SUSPENDIDO"  # mutación en memoria antes del commit
        assert db.rollback.called
        assert not db.commit.called

    def test_registrar_contrato_rollback_si_falla_auditoria(self):
        anexo = AnexoMapeo(3, "ANX-QA", "1.0", "/tmp/qa.pdf", "a" * 64, estado="APROBADO")
        contratos = MagicMock()
        contratos.obtener_anexo.return_value = anexo
        contratos.listar_contratos.return_value = []
        contratos.guardar_contrato.side_effect = lambda c: VersionContrato(
            11, c.contrato_version, c.tipo_cambio, c.fecha_vigencia, c.id_mapeo_anexo_aaef, c.mapeadores,
            periodo_gracia_dias=c.periodo_gracia_dias, descripcion=c.descripcion, estado=c.estado)
        auditoria = MagicMock()
        auditoria.registrar.side_effect = _fallo_auditoria
        db = MagicMock()
        uc = GestionarContratosUseCase(contratos, auditoria, db, lambda: False, lambda *_: None)

        with pytest.raises(InfrastructureError):
            uc.registrar(SolicitudContrato("9.9", "MINOR", date(2026, 12, 1), 3, ["COMPRAS"]), 1)

        assert contratos.guardar_contrato.called
        assert db.rollback.called
        assert not db.commit.called


class TestE2AuditoriaNoBloqueante:
    def test_registrador_aparte_traga_error_y_alerta(self):
        db = MagicMock()
        factory = MagicMock(return_value=db)
        alertas = []

        with patch(
            "src.accounting_integration.infrastructure.repositories.auditoria_integracion_repository."
            "SqlAlchemyAuditoriaIntegracionRepository.registrar",
            side_effect=_fallo_auditoria,
        ):
            registrar = registrador_aparte(factory, lambda m, d: alertas.append((m, d)))
            registrar(EventoIntegracion(
                tipo_evento="TOKEN_CANAL_EMITIDO", tipo_actor="CLIENTE_EXTERNO",
                id_cliente_externo=1, id_usuario=2, codigo_http=200, codigo_resultado="OK"))

        assert alertas, "debe alertar al Administrador (RF-95 FA-9 / RF-102 4.1)"
        assert "No se pudo guardar" in alertas[0][0]
        assert db.rollback.called
        assert not db.commit.called
        assert db.close.called

    def test_emitir_token_continua_si_auditar_aparte_falla(self):
        """Producción cablea auditar_aparte=registrador_aparte; aquí se simula el mismo contrato."""
        clientes = MagicMock()
        cliente = ClienteExterno(5, "AF", "Agro", "qa-g054-tok", canales={"IDENTIDAD_M2M": 30, "CONSULTA_AAEF": 60})
        clientes.obtener_por_identificador.return_value = cliente
        cred = MagicMock()
        cred.hash_secreto = "x"
        cred.fecha_expiracion = AHORA + timedelta(days=30)
        clientes.credencial_activa.return_value = cred
        usuarios = MagicMock()
        usuarios.obtener_por_correo.return_value = MagicMock(id_usuario=8, id_rol=1, es_activo=True)

        db_aparte = MagicMock()
        alertas = []

        with patch(
            "src.accounting_integration.application.use_cases.canal.emitir_token_canal_use_case.secreto_cliente.coincide",
            return_value=True,
        ), patch(
            "src.accounting_integration.application.use_cases.canal.emitir_token_canal_use_case.limitar_cliente",
        ), patch(
            "src.accounting_integration.infrastructure.repositories.auditoria_integracion_repository."
            "SqlAlchemyAuditoriaIntegracionRepository.registrar",
            side_effect=_fallo_auditoria,
        ):
            auditar = registrador_aparte(lambda: db_aparte, lambda m, d: alertas.append((m, d)))
            uc = EmitirTokenCanalUseCase(
                clientes, usuarios, lambda *_a, **_k: ("token-ficticio-g054", 900), MagicMock(), auditar)
            token, segundos = uc.execute("qa-g054-tok", "TEST_SECRET_G054_FICTICIO", "contador@example.com", "203.0.113.10")

        assert token == "token-ficticio-g054"
        assert segundos == 900
        assert alertas
        assert db_aparte.rollback.called

    def test_registrador_aparte_exito_hace_commit_aparte(self):
        db = MagicMock()
        with patch(
            "src.accounting_integration.infrastructure.repositories.auditoria_integracion_repository."
            "SqlAlchemyAuditoriaIntegracionRepository.registrar",
        ) as reg:
            registrar = registrador_aparte(lambda: db, lambda *_: None)
            registrar(EventoIntegracion(tipo_evento="INTENTO_MODIFICACION_AUDITORIA", severidad="CRITICAL",
                                        tipo_actor="USUARIO", codigo_http=405, codigo_resultado="METODO_NO_PERMITIDO"))
            assert reg.called
            assert db.commit.called
            assert not db.rollback.called
