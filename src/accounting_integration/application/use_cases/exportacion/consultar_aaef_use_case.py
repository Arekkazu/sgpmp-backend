# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-06 | Arekkazu | M07 RF-95 Fases 3-5 / RF-97: alcance por fincas, versión y envelope AAEF del titular |
# | 2026-11-19 | LuisfNarvaez01 | TC-M07-381 RF-97: el detalle del error AAEF (Mapper, documento) llega a la respuesta y a la auditoría |
# | 2026-11-19 | LuisfNarvaez01 | TC-M07-379 RF-97: TRAZABILIDAD_INCOMPLETA nombra los hechos afectados y los trae en el detalle |
# | 2026-11-19 | LuisfNarvaez01 | TC-M07-380 RF-97: ERROR_DATOS_FINANCIEROS para fallas al leer los datos financieros y ERROR_INTERNO_RF97 para lo inesperado |
# | 2026-11-19 | Arekkazu | TC-M07-G019 RF-96 CA-6: LineType validado contra la matriz contable |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
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
from src.financial_valuation.domain.value_objects.nic41 import ETIQUETA_HECHO
from src.shared.errors import AppError, AuthorizationError, BusinessRuleError, InfrastructureError, NotFoundError


_HECHOS_EN_MENSAJE = 5
_ERROR_DATOS_FINANCIEROS = ("No se pudo leer la información financiera del productor para la exportación contable. "
                            "Intente de nuevo en unos minutos; si continúa, contacte al administrador del SGPMP.")
_ERROR_INTERNO = ("Ocurrió un error inesperado al generar la información contable. "
                  "Contacte al administrador del SGPMP.")


def _financieros(leer: Callable, *args):
    """RF-97 Fase 3 / FA-7: una falla al leer los datos financieros sale como ERROR_DATOS_FINANCIEROS
    (la causa original queda encadenada para el log y para reconocer el tiempo máximo agotado)."""
    try:
        return leer(*args)
    except AppError:
        raise
    except Exception as exc:
        raise InfrastructureError(code="ERROR_DATOS_FINANCIEROS", message=_ERROR_DATOS_FINANCIEROS,
                                  original_error=exc) from exc


def _trazabilidad_incompleta(lineas: list[dict]) -> AaefError:
    """RF-97 FA-3: bloquea «con el detalle de los hechos afectados». El mensaje nombra los primeros y el
    ``detalle`` los trae todos, para que el Contador los ubique en Finanzas."""
    hechos = [{**ln, "hecho": ETIQUETA_HECHO.get(ln["tipo_hecho"], "Hecho contable"),
               "fecha_hecho": ln["fecha_hecho"].isoformat() if ln.get("fecha_hecho") else None} for ln in lineas]
    nombrados = "; ".join(
        h["hecho"] + (f" del activo {h['activo']}" if h.get("activo") else "")
        + (f" del {h['fecha_hecho']}" if h["fecha_hecho"] else "") for h in hechos[:_HECHOS_EN_MENSAJE])
    resto = len(hechos) - _HECHOS_EN_MENSAJE
    return AaefError(
        "TRAZABILIDAD_INCOMPLETA",
        f"{len(hechos)} asientos del rango no tienen la trazabilidad completa: {nombrados}"
        + (f" y {resto} más" if resto > 0 else "") + ". El Contador debe revisarlos en Finanzas antes de exportar.",
        detalle={"hechos": hechos})


@dataclass(frozen=True)
class SolicitudAaef:
    """Parámetros de la consulta de la exportación contable."""
    nit: str
    desde: date
    hasta: date
    id_usuario: int
    correo_usuario: str
    version_solicitada: Optional[str] = None


@dataclass(frozen=True)
class ResultadoAaef:
    """Archivo generado con su hash y el contrato aplicado."""
    cuerpo: bytes
    hash_contenido: str
    contrato: VersionContrato
    id_intercambio: str
    documentos: int


class ConsultarAaefUseCase:
    """Genera la exportación contable de un titular para un rango de fechas."""
    def __init__(self, fuente: FuenteContableRepository, contratos: ContratoRepository, sistema: SistemaOrigen,
                 limite_bytes: int, hoy: Callable[[], date]):
        self.fuente = fuente
        self.contratos = contratos
        self.sistema = sistema
        self.limite_bytes = limite_bytes
        self.hoy = hoy

    def execute(self, s: SolicitudAaef) -> ResultadoAaef:
        """Genera el archivo de la exportación.

        Raises:
            NotFoundError: Si el titular no existe.
        """
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
            validar_rango(_financieros(self.fuente.periodos, s.nit), s.desde, s.hasta)
            sin_traza = _financieros(self.fuente.lineas_sin_trazabilidad, s.nit, s.desde, s.hasta)
            if sin_traza:  # RF-97 FA-3; el cierre de M06 ya lo impide, esto es la última defensa
                raise _trazabilidad_incompleta(sin_traza)
            subtipos, hechos = _financieros(self.fuente.linetypes_catalogados)
            compras = (mapear_compras(_financieros(self.fuente.costos_factura, s.nit, s.desde, s.hasta), subtipos)
                       if MAPPER_COMPRAS in contrato.mapeadores else [])
            comprobantes = (mapear_comprobantes(_financieros(self.fuente.comprobantes, s.nit, s.desde, s.hasta), titular,
                                                hechos)
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
            # RNF-96.4: el Mapper y el documento que fallaron viajan estructurados, no solo en el mensaje
            raise BusinessRuleError(code=exc.codigo, message=exc.mensaje, field=exc.campo,
                                    detalle=exc.detalle or None) from exc
        except AppError:
            raise
        except Exception as exc:  # RF-97 FA-10: error inesperado de la transformación (Fases 5-7)
            raise InfrastructureError(code="ERROR_INTERNO_RF97", message=_ERROR_INTERNO, original_error=exc) from exc
        return ResultadoAaef(cuerpo, hash_contenido(envelope["invoices"]), contrato,
                             envelope["metadata"]["ExchangeId"], len(envelope["invoices"]))
