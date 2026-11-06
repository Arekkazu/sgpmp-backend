# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-06 | Arekkazu | M07 RF-95 Fases 3-5 / RF-97: alcance por fincas, versión y envelope AAEF del titular |
"""Genera el envelope AAEF de un titular para un rango de períodos cerrados (RF-97 v3.0).

Lo invoca el Gateway (RF-95) con el usuario ya autenticado y con permiso; aquí se resuelve lo que
depende de los datos: el titular existe (404), el usuario tiene **todas** sus fincas activas (403,
RF-95 5.3 d), la versión del contrato (RF-98) y las reglas de negocio de RF-97 (422). No guarda nada."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Callable, Optional

from pydantic import ValidationError as ErrorEsquema

from src.accounting_integration.domain.entities.contrato import VersionContrato, resolver_version
from src.accounting_integration.domain.repositories.contrato_repository import ContratoRepository
from src.accounting_integration.domain.repositories.fuente_contable_repository import FuenteContableRepository
from src.accounting_integration.domain.services.aaef import (
    MAPPER_COMPRAS,
    MAPPER_COMPROBANTE_NIC41,
    AaefError,
    SistemaOrigen,
    construir_envelope,
    controlar_tamano,
    hash_contenido,
    mapear_comprobantes,
    mapear_compras,
    serializar,
    validar_rango,
    verificar_cuadre,
)
from src.accounting_integration.domain.services.esquema_agrofusion import AccountingConsultResponse
from src.shared.errors import AuthorizationError, BusinessRuleError, NotFoundError


@dataclass(frozen=True)
class SolicitudAaef:
    nit: str
    desde: date
    hasta: date
    id_usuario: int
    correo_usuario: str
    version_solicitada: Optional[str] = None


@dataclass(frozen=True)
class ResultadoAaef:
    cuerpo: bytes
    hash_contenido: str
    contrato: VersionContrato
    id_intercambio: str
    documentos: int


class ConsultarAaefUseCase:
    def __init__(self, fuente: FuenteContableRepository, contratos: ContratoRepository, sistema: SistemaOrigen,
                 limite_bytes: int, hoy: Callable[[], date]):
        self.fuente = fuente
        self.contratos = contratos
        self.sistema = sistema
        self.limite_bytes = limite_bytes
        self.hoy = hoy

    def execute(self, s: SolicitudAaef) -> ResultadoAaef:
        titular = self.fuente.titular(s.nit)
        if titular is None:  # RF-95 FA-7
            raise NotFoundError(code="TITULAR_NO_ENCONTRADO", field="nit",
                                message=f"No hay fincas activas registradas con el NIT {s.nit}.")
        if self.fuente.fincas_titular(s.nit) - self.fuente.fincas_usuario(s.id_usuario):  # RF-95 FA-6
            raise AuthorizationError(code="ALCANCE_INSUFICIENTE", message=(
                f"Su usuario no tiene asignadas todas las fincas del titular {s.nit}. "
                "Solicite al administrador la asignación completa."))
        contrato = resolver_version(self.contratos.listar_contratos(), s.version_solicitada)
        try:
            validar_rango(self.fuente.periodos(s.nit), s.desde, s.hasta)
            sin_traza = self.fuente.lineas_sin_trazabilidad(s.nit, s.desde, s.hasta)
            if sin_traza:  # RF-97 FA-3; el cierre de M06 ya lo impide, esto es la última defensa
                raise AaefError("TRAZABILIDAD_INCOMPLETA", f"{sin_traza} asientos del rango no tienen la trazabilidad "
                                "completa. El Contador debe revisarlos en Finanzas antes de exportar.")
            compras = (mapear_compras(self.fuente.costos_factura(s.nit, s.desde, s.hasta))
                       if MAPPER_COMPRAS in contrato.mapeadores else [])
            comprobantes = (mapear_comprobantes(self.fuente.comprobantes(s.nit, s.desde, s.hasta), titular)
                            if MAPPER_COMPROBANTE_NIC41 in contrato.mapeadores else [])
            envelope = construir_envelope(titular, s.desde, s.hasta, self.sistema, s.correo_usuario, self.hoy(),
                                          compras, comprobantes)
            verificar_cuadre(envelope)
            cuerpo = serializar(envelope)
            try:  # última verificación: lo que AgroFusion rechazaría con 502 no sale de aquí
                AccountingConsultResponse.model_validate_json(cuerpo)
            except ErrorEsquema as exc:
                raise AaefError("MAPPER_FALLIDO", "La información generada no cumple el formato que espera AgroFusion. "
                                "Contacte al administrador del SGPMP.", detalle={"errores": exc.error_count()}) from exc
            controlar_tamano(cuerpo, self.limite_bytes)
        except AaefError as exc:
            raise BusinessRuleError(code=exc.codigo, message=exc.mensaje, field=exc.campo) from exc
        return ResultadoAaef(cuerpo, hash_contenido(envelope["invoices"]), contrato,
                             envelope["metadata"]["ExchangeId"], len(envelope["invoices"]))
