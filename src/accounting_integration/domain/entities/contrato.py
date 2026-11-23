# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-06 | Arekkazu | M07 RF-98/RF-AE02: versiones del contrato AAEF, anexo y resolución de versión |
# | 2026-11-19 | LuisfNarvaez01 | INC-M07-375 RF-98: estado antes que anexo al activar y solo una versión pendiente se modifica |
# | 2026-11-19 | Arekkazu | INC-M07-373-G37 RF-98: el mínimo de gracia lo fija M09 |
# | 2026-11-20 | Arekkazu | QA-M07 CU04 H-02 RF-98: el límite de versiones no manda a retirar una que ya está en retiro |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
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
from src.configuration.domain.entities.parametro_mlops import RF98_GRACIA_DEFECTO_BASE, RF98_GRACIA_MINIMA_BASE
from src.shared.errors import BusinessRuleError, FlowError, GoneError, NotFoundError, ValidationError
from src.shared.fechas import fecha_usuario

# Valores base de RF-98; los efectivos se configuran en M09 (RNF-98.10).
GRACIA_MINIMA_DIAS = RF98_GRACIA_MINIMA_BASE
GRACIA_DEFECTO_DIAS = RF98_GRACIA_DEFECTO_BASE
LIMITE_VIGENTES = 2
_FORMATO_VERSION = re.compile(r"^(\d{1,3})\.(\d{1,3})$")


@dataclass
class AnexoMapeo:
    """Anexo de mapeo contable de la exportación con su estado de aprobación."""
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
        """Pasa el anexo de borrador a revisión.

        Raises:
            FlowError: Si el anexo no está en borrador.
        """
        if self.estado != "BORRADOR":
            raise FlowError(code="TRANSICION_NO_PERMITIDA", message="Solo un anexo en borrador puede pasar a revisión.")
        self.estado, self.fecha_aprobacion_interna = "EN_REVISION", ahora

    def aprobar(self, ahora: datetime, evidencia: dict) -> None:
        """Aprueba el anexo en revisión con su evidencia.

        Raises:
            FlowError: Si el anexo no está en revisión.
        """
        if self.estado != "EN_REVISION":
            raise FlowError(code="TRANSICION_NO_PERMITIDA",
                            message="Solo un anexo en revisión, con la aprobación del Contador, puede aprobarse.")
        self.estado, self.fecha_aprobacion, self.evidencia = "APROBADO", ahora, evidencia


@dataclass
class VersionContrato:
    """Versión del contrato de la exportación contable con su ciclo de vida."""
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
        """Número de versión como tupla (mayor, menor)."""
        return numero_version(self.contrato_version)

    def exigir_activable(self) -> None:
        """RF-98 CA-12/FA-13: el estado se valida antes que el anexo o los transformadores, para que una
        versión inactiva responda que no se reactiva y no que le falta el anexo."""
        self._exigir("PENDIENTE", "activar")

    def activar(self, ahora: datetime) -> None:
        """Activa la versión pendiente."""
        self._exigir("PENDIENTE", "activar")
        self.estado, self.fecha_activacion = "ACTIVO", ahora

    def modificar(self, *, fecha_vigencia: Optional[date] = None, id_mapeo_anexo_aaef: Optional[int] = None,
                  mapeadores: Optional[list[str]] = None, periodo_gracia_dias: Optional[int] = None,
                  descripcion: Optional[str] = None, minimo_dias: int = GRACIA_MINIMA_DIAS) -> None:
        """RF-98 5.12 / CA-20 / FA-12: solo una versión PENDIENTE cambia sus datos; la versión y el tipo
        de cambio son su identidad y no se modifican nunca."""
        if self.estado != "PENDIENTE":
            raise FlowError(code="MODIFICACION_NO_PERMITIDA", message=(
                f"La versión {self.contrato_version} está {self.estado.lower()} y ya no puede modificarse."))
        if periodo_gracia_dias is not None:
            if self.tipo_cambio != "MAJOR":
                raise ValidationError(code="PERIODO_GRACIA_INVALIDO", field="periodo_gracia_dias",
                                      message="Solo una versión de cambio mayor tiene período de gracia.")
            if periodo_gracia_dias < minimo_dias:
                raise ValidationError(code="PERIODO_GRACIA_INVALIDO", field="periodo_gracia_dias",
                                      message=f"El período de gracia debe ser de al menos {minimo_dias} días.")
            self.periodo_gracia_dias = periodo_gracia_dias
        if mapeadores is not None:
            if not mapeadores or any(m not in MAPPERS_DISPONIBLES for m in mapeadores):
                raise ValidationError(code="MAPPERS_INVALIDOS", field="mapeadores",
                                      message="Indique transformadores válidos: compras y, si aplica, comprobante NIC 41.")
            self.mapeadores = sorted(set(mapeadores))
        if fecha_vigencia is not None:
            self.fecha_vigencia = fecha_vigencia
        if id_mapeo_anexo_aaef is not None:
            self.id_mapeo_anexo_aaef = id_mapeo_anexo_aaef
        if descripcion is not None:
            self.descripcion = descripcion

    def deprecar(self, ahora: datetime, dias_gracia: int, minimo_dias: int = GRACIA_MINIMA_DIAS) -> None:
        """Depreca la versión activa con su periodo de gracia.

        Raises:
            ValidationError: Si el periodo de gracia es menor al mínimo.
        """
        self._exigir("ACTIVO", "deprecar")
        if dias_gracia < minimo_dias:
            raise ValidationError(code="PERIODO_GRACIA_INVALIDO", field="dias_gracia",
                                  message=f"El período de gracia debe ser de al menos {minimo_dias} días.")
        self.estado, self.fecha_deprecacion = "DEPRECADO", ahora
        self.fecha_inactivacion = ahora + timedelta(days=dias_gracia)

    def inactivar(self, ahora: datetime) -> None:
        """Inactiva la versión deprecada una vez vencida la gracia.

        Raises:
            FlowError: Si la gracia sigue vigente.
        """
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
    """Convierte una versión ``mayor.menor`` en tupla de enteros."""
    mayor, menor = _FORMATO_VERSION.match(version).groups()
    return int(mayor), int(menor)


def validar_formato_version(version: str, campo: str = "contrato_version") -> str:
    """Valida el formato ``mayor.menor`` de la versión.

    Raises:
        ValidationError: Si el formato es inválido.
    """
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
    """RF-98 5.3 / CA-29: máximo dos versiones ACTIVO o DEPRECADO; dice cómo se libera el cupo.

    Una versión en retiro sigue contando hasta que termina su plazo, así que retirar otra no libera cupo
    mientras haya una en retiro: entonces se informa cuándo termina ese retiro (CU04 H-02)."""
    vigentes = [c for c in contratos if c.estado in ("ACTIVO", "DEPRECADO")
                and c.id_version_contrato_aaef != contrato.id_version_contrato_aaef]
    if len(vigentes) < LIMITE_VIGENTES:
        return
    en_retiro = [c for c in vigentes if c.estado == "DEPRECADO"]
    if en_retiro:
        proxima = min(en_retiro, key=lambda c: (c.fecha_inactivacion is None, c.fecha_inactivacion or datetime.max))
        hasta = f" hasta el {fecha_usuario(proxima.fecha_inactivacion):%d/%m/%Y}" if proxima.fecha_inactivacion else ""
        mensaje = (f"Ya hay {len(vigentes)} versiones vigentes y la versión {proxima.contrato_version} ya está en "
                   f"retiro{hasta}. Podrá activar una nueva versión cuando termine ese retiro.")
    else:
        candidata = min(vigentes, key=lambda c: c.numero)
        mensaje = (f"Ya hay {len(vigentes)} versiones vigentes. Retire primero la versión {candidata.contrato_version}; "
                   "podrá activar una nueva cuando termine su plazo de retiro.")
    raise BusinessRuleError(code="LIMITE_VERSIONES_EXCEDIDO", message=mensaje)


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
