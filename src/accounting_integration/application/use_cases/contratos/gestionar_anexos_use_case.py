# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-06 | Arekkazu | M07 RF-AE02: registro, revisión (validación automática) y aprobación del anexo |
"""Anexo de mapeo AAEF (RF-AE02 v3.0): BORRADOR → EN_REVISION → APROBADO, sin vuelta atrás.

- Pasar a revisión es la aprobación interna del Contador (5.9) y exige la validación automática con
  datos de prueba (5.10): estructura contra el esquema de AgroFusion, cuadre, cuentas y fechas.
- Aprobar exige la evidencia de la prueba de interoperabilidad en TEST (5.11).
Un anexo aprobado no se edita: un cambio es un anexo nuevo."""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from src.accounting_integration.domain.entities.contrato import AnexoMapeo
from src.accounting_integration.domain.entities.evento_integracion import EventoIntegracion
from src.accounting_integration.domain.repositories.auditoria_integracion_repository import AuditoriaIntegracionRepository
from src.accounting_integration.domain.repositories.contrato_repository import ContratoRepository
from src.accounting_integration.domain.services.aaef import (
    ComprobanteNic41,
    CostoFactura,
    SistemaOrigen,
    Titular,
    construir_envelope,
    mapear_comprobantes,
    mapear_compras,
    serializar,
    verificar_cuadre,
)
from src.accounting_integration.domain.services.esquema_agrofusion import AccountingConsultResponse
from src.shared.errors import BusinessRuleError, NotFoundError, ValidationError

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_FECHA = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def validar_con_datos_de_prueba() -> list[str]:
    """RF-AE02 5.10: corre los Mappers sobre datos de prueba y devuelve los controles que fallan."""
    titular = Titular("900000001", "Titular de prueba SAS")
    compra = CostoFactura(1, "800000001", "Proveedor de prueba SAS", "FE", "1", date(2026, 1, 15), date(2026, 2, 14),
                          "ALIMENTO", Decimal("1000.505"), "51350501", "PRUEBA-1")
    comprobante = ComprobanteNic41("NIC-900000001-202601-VARIACION_VR_TB-1", "VARIACION_VR_TB", "Especie de prueba",
                                   date(2026, 1, 31), [{"cuenta_debito": "15120501", "cuenta_credito": "42950501", "valor": "2500"}])
    envelope = construir_envelope(titular, date(2026, 1, 1), date(2026, 1, 31), SistemaOrigen("SGPMP", "SIGAB", "PRUEBA"),
                                  "validacion@sgpmp.local", date(2026, 2, 1), mapear_compras([compra]),
                                  mapear_comprobantes([comprobante], titular))
    fallas = []
    try:
        AccountingConsultResponse.model_validate(json.loads(serializar(envelope)))
    except Exception:
        fallas.append("estructura")
    try:
        verificar_cuadre(envelope)
    except Exception:
        fallas.append("cuadre")
    if any(len(ln["accounting_account"]) != (1 if d["Header"]["Type"]["Code"] == "02" else 2)
           for d in envelope["invoices"] for ln in d["Lines"]):
        fallas.append("cuentas")
    if not all(_FECHA.match(d["Header"][c]) for d in envelope["invoices"] for c in ("IssueDate", "DueDate", "UpdatedAt")):
        fallas.append("fechas")
    return fallas


class GestionarAnexosUseCase:
    def __init__(self, contratos: ContratoRepository, auditoria: AuditoriaIntegracionRepository, db: Session):
        self.contratos = contratos
        self.auditoria = auditoria
        self.db = db

    def _confirmar(self, anexo: AnexoMapeo, tipo_evento: str, id_usuario: int, detalle: dict) -> AnexoMapeo:
        try:
            anexo = self.contratos.guardar_anexo(anexo)
            self.auditoria.registrar(EventoIntegracion(
                tipo_evento=tipo_evento, tipo_actor="USUARIO", id_usuario=id_usuario, codigo_resultado="OK",
                json_detalle={"codigo_anexo": anexo.codigo_anexo, "version_anexo": anexo.version_anexo, **detalle}))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return anexo

    def _anexo(self, id_mapeo_anexo_aaef: int) -> AnexoMapeo:
        anexo = self.contratos.obtener_anexo(id_mapeo_anexo_aaef)
        if anexo is None:
            raise NotFoundError(code="ANEXO_NO_ENCONTRADO", message="El anexo de mapeo no existe.")
        return anexo

    def registrar(self, codigo_anexo: str, version_anexo: str, ruta_documento: str, sha256_documento: str,
                  id_usuario: int) -> AnexoMapeo:
        sha = sha256_documento.strip().lower()
        if not _SHA256.match(sha):
            raise ValidationError(code="HASH_DOCUMENTO_INVALIDO", field="sha256_documento",
                                  message="El hash del documento debe ser un SHA-256 en hexadecimal (64 caracteres).")
        return self._confirmar(AnexoMapeo(None, codigo_anexo, version_anexo, ruta_documento, sha),
                               "ANEXO_REGISTRADO", id_usuario, {"sha256_documento": sha})

    def enviar_a_revision(self, id_mapeo_anexo_aaef: int, id_usuario: int) -> AnexoMapeo:
        anexo = self._anexo(id_mapeo_anexo_aaef)
        fallas = validar_con_datos_de_prueba()
        if fallas:  # FA-2: no avanza
            self.auditoria.registrar(EventoIntegracion(
                tipo_evento="ANEXO_VALIDACION_FALLIDA", severidad="ERROR", tipo_actor="USUARIO", id_usuario=id_usuario,
                codigo_resultado="ANEXO_VALIDACION_FALLIDA", json_detalle={"codigo_anexo": anexo.codigo_anexo, "fallas": fallas}))
            self.db.commit()
            raise BusinessRuleError(code="ANEXO_VALIDACION_FALLIDA", message=(
                f"La validación automática del anexo falló ({', '.join(fallas)}). Corrija el mapeo antes de enviarlo a revisión."))
        anexo.enviar_a_revision(datetime.now(timezone.utc))
        return self._confirmar(anexo, "ANEXO_EN_REVISION", id_usuario, {"validacion_automatica": "OK"})

    def aprobar(self, id_mapeo_anexo_aaef: int, evidencia: dict, id_usuario: int) -> AnexoMapeo:
        anexo = self._anexo(id_mapeo_anexo_aaef)
        anexo.aprobar(datetime.now(timezone.utc), evidencia)
        return self._confirmar(anexo, "ANEXO_APROBADO", id_usuario, {"evidencia": evidencia})
