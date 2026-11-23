# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-06 | Arekkazu | M07 RF-95..102: ensamblado de repositorios y casos de uso de la integración |
# | 2026-11-19 | LuisfNarvaez01 | INC-M07-375 RF-98: los rechazos del ciclo de vida del contrato se auditan aparte |
# | 2026-11-19 | Arekkazu | INC-M07-373-G37 RF-98: período de gracia leído de los parámetros de M09 |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Fábrica de M07: arma los casos de uso con sus repositorios SQL para una sesión."""
from __future__ import annotations

from functools import cached_property

from sqlalchemy.orm import Session

from src.accounting_integration.application.use_cases.auditoria.consultar_auditoria_integracion_use_case import (
    ConsultarAuditoriaIntegracionUseCase,
)
from src.accounting_integration.application.use_cases.canal.emitir_token_canal_use_case import EmitirTokenCanalUseCase
from src.accounting_integration.application.use_cases.canal.verificar_acceso_canal_use_case import VerificarAccesoCanalUseCase
from src.accounting_integration.application.use_cases.clientes.gestionar_cliente_externo_use_case import (
    GestionarClienteExternoUseCase,
)
from src.accounting_integration.application.use_cases.clientes.registrar_cliente_externo_use_case import (
    RegistrarClienteExternoUseCase,
)
from src.accounting_integration.application.use_cases.contratos.gestionar_anexos_use_case import GestionarAnexosUseCase
from src.accounting_integration.application.use_cases.contratos.gestionar_contratos_use_case import GestionarContratosUseCase
from src.accounting_integration.application.use_cases.exportacion.consultar_aaef_use_case import ConsultarAaefUseCase
from src.accounting_integration.infrastructure import configuracion
from src.accounting_integration.infrastructure.adapters.alerta_administrador_adapter import alertador_administrador
from src.accounting_integration.infrastructure.repositories.auditoria_integracion_repository import (
    SqlAlchemyAuditoriaIntegracionRepository,
    registrador_aparte,
)
from src.accounting_integration.infrastructure.repositories.cliente_externo_repository import SqlAlchemyClienteExternoRepository
from src.accounting_integration.infrastructure.repositories.contrato_repository import SqlAlchemyContratoRepository
from src.accounting_integration.infrastructure.repositories.fuente_contable_repository import SqlAlchemyFuenteContableRepository
from src.accounting_integration.infrastructure.repositories.usuario_canal_repository import SqlAlchemyUsuarioCanalRepository
from src.configuration.application.use_cases.configuracion_global.parametros_integracion_contable_use_case import (
    ParametrosIntegracionContableUseCase,
)
from src.prediction.infrastructure.repositories.parametros_mlops_repository import SqlAlchemyParametrosMLOpsRepository
from src.shared.database import sesion_sistema
from src.shared.fechas import hoy_usuario
from src.shared.jwt import create_token_canal, verify_token_canal
from src.shared.rate_limit import registrar_llamada


class M07:
    """Fábrica de repositorios y casos de uso de la integración contable."""
    def __init__(self, db: Session):
        self.db = db

    @cached_property
    def alertar(self):
        """Función de alerta al Administrador."""
        return alertador_administrador(sesion_sistema)

    @cached_property
    def auditar_aparte(self):
        """RF-102 para lecturas y rechazos: sesión propia, nunca bloquea la respuesta."""
        return registrador_aparte(sesion_sistema, self.alertar)

    @cached_property
    def auditoria(self) -> SqlAlchemyAuditoriaIntegracionRepository:
        """RF-102 para RF-101 y RF-98: misma transacción que la operación (si falla, rollback)."""
        return SqlAlchemyAuditoriaIntegracionRepository(self.db)

    @cached_property
    def clientes(self) -> SqlAlchemyClienteExternoRepository:
        """Repositorio de clientes externos."""
        return SqlAlchemyClienteExternoRepository(self.db)

    @cached_property
    def contratos(self) -> SqlAlchemyContratoRepository:
        """Repositorio de contratos y anexos."""
        return SqlAlchemyContratoRepository(self.db)

    @cached_property
    def usuarios(self) -> SqlAlchemyUsuarioCanalRepository:
        """Repositorio de usuarios del canal."""
        return SqlAlchemyUsuarioCanalRepository(self.db)

    def emitir_token(self) -> EmitirTokenCanalUseCase:
        """Caso de uso de emisión de token de canal."""
        return EmitirTokenCanalUseCase(self.clientes, self.usuarios, create_token_canal, registrar_llamada, self.auditar_aparte)

    def verificar_acceso(self) -> VerificarAccesoCanalUseCase:
        """Caso de uso de verificación de acceso al canal."""
        return VerificarAccesoCanalUseCase(self.clientes, self.usuarios, verify_token_canal, registrar_llamada)

    def consultar_aaef(self) -> ConsultarAaefUseCase:
        """Caso de uso de la exportación contable."""
        return ConsultarAaefUseCase(SqlAlchemyFuenteContableRepository(self.db), self.contratos,
                                    configuracion.SISTEMA_ORIGEN, configuracion.LIMITE_BYTES, hoy_usuario)

    def registrar_cliente(self) -> RegistrarClienteExternoUseCase:
        """Caso de uso de registro de clientes."""
        return RegistrarClienteExternoUseCase(self.clientes, self.auditoria, self.db)

    def gestionar_cliente(self) -> GestionarClienteExternoUseCase:
        """Caso de uso de gestión de clientes."""
        return GestionarClienteExternoUseCase(self.clientes, self.auditoria, self.db)

    def gestionar_anexos(self) -> GestionarAnexosUseCase:
        """Caso de uso de gestión de anexos."""
        return GestionarAnexosUseCase(self.contratos, self.auditoria, self.db)

    def gracia(self) -> tuple[int, int]:
        """(mínimo, por defecto) del período de gracia, tal como los configuró M09 (RNF-98.10)."""
        return ParametrosIntegracionContableUseCase(self.db, SqlAlchemyParametrosMLOpsRepository(self.db)).gracia()

    def gestionar_contratos(self) -> GestionarContratosUseCase:
        """Caso de uso de gestión de contratos."""
        return GestionarContratosUseCase(self.contratos, self.auditoria, self.db, configuracion.es_produccion, self.alertar,
                                         configuracion.COMPROBANTE_NIC41_HABILITADO, self.auditar_aparte, self.gracia)

    def consultar_auditoria(self) -> ConsultarAuditoriaIntegracionUseCase:
        """Caso de uso de consulta de la auditoría."""
        return ConsultarAuditoriaIntegracionUseCase(self.auditoria, self.alertar)
