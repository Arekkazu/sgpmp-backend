# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-06 | Arekkazu | M07 RF-98/RF-AE02: versiones del contrato AAEF, anexo y resolución de versión |
"""Contrato AAEF (RF-98 v1.1) y anexo de mapeo (RF-AE02 v3.0).

El contrato avanza PENDIENTE → ACTIVO → DEPRECADO → INACTIVO, sin retrocesos ni saltos. Un MAJOR
depreca las versiones activas anteriores y fija su fecha de inactivación al final de la gracia
(``fecha_inactivacion`` es la fecha prevista mientras está DEPRECADO y la real después)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Iterable, Optional

from src.accounting_integration.domain.services.aaef import MAPPERS_DISPONIBLES
from src.shared.errors import BusinessRuleError, FlowError, GoneError, NotFoundError, ValidationError

GRACIA_MINIMA_DIAS = 30
GRACIA_DEFECTO_DIAS = 90
LIMITE_VIGENTES = 2
_FORMATO_VERSION = re.compile(r"^(\d{1,3})\.(\d{1,3})$")


@dataclass
class AnexoMapeo:
    id_mapeo_anexo_aaef: Optional[int]
    codigo_anexo: str
    version_anexo: str
    ruta_documento: str
    sha256_documento: str
    estado: str = "BORRADOR"
    fecha_aprobacion_interna: Optional[datetime] = None
    fecha_aprobacion: Optional[datetime] = None
    evidencia: Optional[dict] = None

    def usable(self, es_produccion: bool) -> bool:
        """RF-98 5.2 exige el anexo APROBADO. Fuera de producción basta EN_REVISION: la prueba de
        interoperabilidad que lo aprueba (RF-AE02 5.11) necesita un contrato activo en TEST."""
        return self.estado == "APROBADO" or (not es_produccion and self.estado == "EN_REVISION")

    def enviar_a_revision(self, ahora: datetime) -> None:
        if self.estado != "BORRADOR":
            raise FlowError(code="TRANSICION_NO_PERMITIDA", message="Solo un anexo en borrador puede pasar a revisión.")
        self.estado, self.fecha_aprobacion_interna = "EN_REVISION", ahora

    def aprobar(self, ahora: datetime, evidencia: dict) -> None:
        if self.estado != "EN_REVISION":
            raise FlowError(code="TRANSICION_NO_PERMITIDA",
                            message="Solo un anexo en revisión, con la aprobación del Contador, puede aprobarse.")
        self.estado, self.fecha_aprobacion, self.evidencia = "APROBADO", ahora, evidencia


@dataclass
class VersionContrato:
    id_version_contrato_aaef: Optional[int]
    contrato_version: str
    tipo_cambio: str
    fecha_vigencia: date
    id_mapeo_anexo_aaef: Optional[int]
    mapeadores: list[str] = field(default_factory=list)
    endpoint_asociado: str = "/integracion/aaef/productores/{nit}"
    periodo_gracia_dias: Optional[int] = None
    descripcion: Optional[str] = None
    estado: str = "PENDIENTE"
    fecha_activacion: Optional[datetime] = None
    fecha_deprecacion: Optional[datetime] = None
    fecha_inactivacion: Optional[datetime] = None

    @property
    def numero(self) -> tuple[int, int]:
        return numero_version(self.contrato_version)

    def activar(self, ahora: datetime) -> None:
        self._exigir("PENDIENTE", "activar")
        self.estado, self.fecha_activacion = "ACTIVO", ahora

    def deprecar(self, ahora: datetime, dias_gracia: int) -> None:
        self._exigir("ACTIVO", "deprecar")
        if dias_gracia < GRACIA_MINIMA_DIAS:
            raise ValidationError(code="PERIODO_GRACIA_INVALIDO", field="dias_gracia",
                                  message=f"El período de gracia debe ser de al menos {GRACIA_MINIMA_DIAS} días.")
        self.estado, self.fecha_deprecacion = "DEPRECADO", ahora
        self.fecha_inactivacion = ahora + timedelta(days=dias_gracia)

    def inactivar(self, ahora: datetime) -> None:
        self._exigir("DEPRECADO", "inactivar")
        if self.fecha_inactivacion and ahora < self.fecha_inactivacion:
            raise FlowError(code="PERIODO_GRACIA_VIGENTE", message=(
                f"La versión {self.contrato_version} sigue en período de gracia hasta "
                f"{self.fecha_inactivacion.date().isoformat()}."))
        self.estado, self.fecha_inactivacion = "INACTIVO", ahora

    def _exigir(self, estado: str, accion: str) -> None:
        if self.estado == "INACTIVO":
            raise FlowError(code="REACTIVACION_NO_PERMITIDA",
                            message=f"La versión {self.contrato_version} está inactiva y no puede cambiar de estado.")
        if self.estado != estado:
            raise FlowError(code="TRANSICION_NO_PERMITIDA", message=(
                f"No se puede {accion} la versión {self.contrato_version}: está {self.estado.lower()}."))


def numero_version(version: str) -> tuple[int, int]:
    mayor, menor = _FORMATO_VERSION.match(version).groups()
    return int(mayor), int(menor)


def validar_formato_version(version: str, campo: str = "contrato_version") -> str:
    version = (version or "").strip()
    if not _FORMATO_VERSION.match(version):
        raise ValidationError(code="VERSION_FORMATO_INVALIDO", field=campo,
                              message="La versión debe tener el formato MAYOR.MENOR, por ejemplo 3.0.")
    return version


def motivo_bloqueo_activacion(contrato: VersionContrato, anexo: Optional[AnexoMapeo], es_produccion: bool) -> Optional[str]:
    """RF-98 5.2 / FA-5: motivo legible por el que el contrato no puede activarse, o ``None``."""
    if anexo is None or not anexo.usable(es_produccion):
        return f"La versión {contrato.contrato_version} no tiene un anexo de mapeo aprobado."
    if not contrato.mapeadores or any(m not in MAPPERS_DISPONIBLES for m in contrato.mapeadores):
        return f"La versión {contrato.contrato_version} no tiene transformadores válidos asociados."
    return None


def versiones_a_deprecar(contrato: VersionContrato, contratos: Iterable[VersionContrato]) -> list[VersionContrato]:
    """RF-98 5.4: un MAJOR depreca las versiones activas de MAJOR menor; un MINOR no depreca nada."""
    if contrato.tipo_cambio != "MAJOR":
        return []
    return [c for c in contratos if c.estado == "ACTIVO" and c.numero[0] < contrato.numero[0]]


def exigir_cupo(contrato: VersionContrato, contratos: Iterable[VersionContrato]) -> None:
    """RF-98 5.3 / CA-29: máximo dos versiones ACTIVO o DEPRECADO; dice cuál retirar primero."""
    vigentes = [c for c in contratos if c.estado in ("ACTIVO", "DEPRECADO")
                and c.id_version_contrato_aaef != contrato.id_version_contrato_aaef]
    if len(vigentes) >= LIMITE_VIGENTES:
        candidata = min(vigentes, key=lambda c: (c.estado != "DEPRECADO", c.numero))
        raise BusinessRuleError(code="LIMITE_VERSIONES_EXCEDIDO", message=(
            f"Ya hay {len(vigentes)} versiones vigentes. Retire primero la versión {candidata.contrato_version} "
            "antes de activar una nueva."))


def resolver_version(contratos: Iterable[VersionContrato], solicitada: Optional[str]) -> VersionContrato:
    """RF-98 5.11: la versión pedida si está ACTIVO o DEPRECADO; sin pedir, la ACTIVO de mayor número."""
    contratos = list(contratos)
    if solicitada:
        version = validar_formato_version(solicitada, "Accept-Version")
        encontrada = next((c for c in contratos if c.numero == numero_version(version)), None)
        if encontrada is None or encontrada.estado == "PENDIENTE":
            raise NotFoundError(code="VERSION_NO_REGISTRADA", field="Accept-Version",
                                message=f"La versión {version} del contrato contable no está disponible.")
        if encontrada.estado == "INACTIVO":
            raise GoneError(code="VERSION_INACTIVA", field="Accept-Version",
                            message=f"La versión {version} del contrato contable ya no está disponible.")
        return encontrada
    activos = [c for c in contratos if c.estado == "ACTIVO"]
    if not activos:
        raise BusinessRuleError(code="CONTRATO_NO_ACTIVO",
                                message="No hay una versión vigente del contrato contable. Contacte al administrador.")
    return max(activos, key=lambda c: c.numero)
