# | Fecha      | Nombre   | Que se hizo                                                             |
# |------------|----------|-------------------------------------------------------------------------|
# | 2026-11-18 | Arekkazu | M08 RF-104: validación común, armado y partición en archivos de 50 MB   |
"""Pasos comunes de RF-104 que comparten la vista previa, la generación inmediata y el proceso en segundo plano.

1. Permiso por tipo de reporte (Fase 1, 403) — ``Solicitante.permitidos`` sale de ``modulo1.permisos``.
2. Filtros obligatorios y de catálogo (400), referencias del usuario: 404 si no existe, 403 si es de otra finca.
3. Períodos: 404, 403 si no es del alcance, 422 si no está CERRADO o si el de comparación no es anterior al base.
4. Armado del contenido dentro de la instantánea.
"""
from __future__ import annotations

import math
import re
import unicodedata
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Callable, Optional

from src.reporting.application.use_cases.reportes.armadores import ARMADORES, Contexto
from src.reporting.domain.repositories.fuente_reportes_repository import FuenteReportesRepository
from src.reporting.domain.repositories.solicitud_reporte_repository import RenderizadorReportePort
from src.reporting.domain.reportes.catalogo import (
    CATALOGO,
    ETIQUETAS,
    FINCA,
    PERIODO,
    DefinicionReporte,
    filtros_serializables,
    validar_filtros,
)
from src.reporting.domain.reportes.contenido import ContenidoReporte, Tabla
from src.reporting.domain.reportes.solicitud import ArchivoReporte, sha256
from src.shared.errors import AuthorizationError, BusinessRuleError, NotFoundError
from src.shared.fechas import en_zona_usuario, hoy_usuario

LIMITE_PARTE = 50 * 1024 * 1024  # RF-104 restricción: 50 MB por archivo
SIN_DATOS = ("No hay datos para los filtros elegidos. Prueba con otro rango de fechas o quita algún filtro.")
_REFERENCIAS = {"finca": "La finca", "activo": "El animal o lote", "lote": "El lote", "infraestructura": "El área",
                "sensor": "El sensor", "especie": "La especie"}

AbrirFuente = Callable[[int, str], AbstractContextManager[FuenteReportesRepository]]


@dataclass
class Solicitante:
    """Quién pide el reporte: sus tipos permitidos (RBAC) y sus fincas (``None`` = todas)."""
    id_usuario: int
    nombre: str
    permitidos: set[str]
    fincas: Optional[list[int]]
    zona_horaria: str = "UTC"


@dataclass
class Preparado:
    definicion: DefinicionReporte
    filtros: dict[str, Any]
    contenido: ContenidoReporte
    id_finca_logo: Optional[int] = None
    fecha_snapshot: Optional[datetime] = None


def exigir_permiso(tipo: str, solicitante: Solicitante) -> DefinicionReporte:
    definicion = CATALOGO.get(tipo)
    if definicion is None:
        raise NotFoundError(code="REPORTE_INEXISTENTE", message="Ese reporte no existe.", field="tipo_reporte")
    if tipo not in solicitante.permitidos:
        raise AuthorizationError(code="REPORTE_NO_AUTORIZADO", field="tipo_reporte",
                                 message="Tu rol no tiene permiso para generar este reporte.")
    return definicion


def _validar_referencias(fuente: FuenteReportesRepository, definicion: DefinicionReporte, filtros: dict[str, Any],
                         fincas: Optional[list[int]]) -> Optional[int]:
    """404 / 403 de cada referencia. Devuelve la finca del reporte si una referencia la fija (para el logo)."""
    finca_logo = None
    for filtro in definicion.filtros:
        valor = filtros.get(filtro.nombre)
        if valor is None or filtro.tipo not in _REFERENCIAS:
            continue
        ubicacion = fuente.ubicar(filtro.tipo, valor)
        if ubicacion is None:
            raise NotFoundError(code="REFERENCIA_INEXISTENTE", field=f"filtros.{filtro.nombre}",
                                message=f"{_REFERENCIAS[filtro.tipo]} elegido en «{ETIQUETAS[filtro.nombre]}» no existe.")
        id_finca = ubicacion.get("id_finca")
        if id_finca is not None and fincas is not None and id_finca not in fincas:
            raise AuthorizationError(code="FINCA_NO_AUTORIZADA", field=f"filtros.{filtro.nombre}",
                                     message="No tienes permisos para esta finca.")
        if id_finca is not None and (filtro.tipo != FINCA or finca_logo is None):
            finca_logo = id_finca
    return finca_logo


def _validar_periodos(fuente: FuenteReportesRepository, definicion: DefinicionReporte,
                      filtros: dict[str, Any]) -> dict[str, dict[str, Any]]:
    periodos: dict[str, dict[str, Any]] = {}
    for filtro in definicion.filtros:
        if filtro.tipo != PERIODO or filtros.get(filtro.nombre) is None:
            continue
        periodo = fuente.periodo(filtros[filtro.nombre])
        if periodo is None:
            raise NotFoundError(code="PERIODO_INEXISTENTE", field=f"filtros.{filtro.nombre}",
                                message="El período contable elegido no existe.")
        if not periodo["accesible"]:
            raise AuthorizationError(code="PERIODO_NO_AUTORIZADO", field=f"filtros.{filtro.nombre}",
                                     message="No tienes acceso a ese período contable.")
        if definicion.periodo_cerrado and periodo["estado"] != "CERRADO":
            raise BusinessRuleError(
                code="PERIODO_NO_CERRADO", field=f"filtros.{filtro.nombre}",
                message=(f"El período del {periodo['fecha_inicio']:%d/%m/%Y} al {periodo['fecha_fin']:%d/%m/%Y} no "
                         "está cerrado. Solo se pueden generar reportes sobre períodos contables cerrados."))
        periodos[filtro.nombre] = periodo
    base, comparacion = periodos.get("periodo_contable_base"), periodos.get("periodo_contable_comparacion")
    if definicion.compara_periodos and base and comparacion and comparacion["fecha_fin"] >= base["fecha_inicio"]:
        raise BusinessRuleError(code="PERIODOS_FUERA_DE_ORDEN", field="filtros.periodo_contable_comparacion",
                                message="El período de comparación debe ser anterior al período base.")
    return periodos


def preparar(fuente: FuenteReportesRepository, tipo: str, crudos: Optional[dict[str, Any]],
             solicitante: Solicitante, ahora: Optional[datetime] = None) -> Preparado:
    """Valida todo y arma el contenido. Corre dentro de la instantánea (``fuente``)."""
    definicion = exigir_permiso(tipo, solicitante)
    hoy: date = hoy_usuario()
    filtros = validar_filtros(definicion, crudos, hoy)
    finca_logo = _validar_referencias(fuente, definicion, filtros, solicitante.fincas)
    periodos = _validar_periodos(fuente, definicion, filtros)
    fincas = solicitante.fincas
    if finca_logo is None and fincas is not None and len(fincas) == 1:
        finca_logo = fincas[0]
    ctx = Contexto(fuente=fuente, tipo=tipo, filtros=filtros, fincas=fincas, hoy=hoy, nombre_usuario=solicitante.nombre,
                   incluir_nic41="REPORTE_VALORACION_NIC41" in solicitante.permitidos, periodos=periodos)
    if ahora is not None:
        ctx.generado = ahora
    contenido = ARMADORES[tipo](ctx)
    if contenido.firma:
        # Firma del Contador: nombre, rol, fecha y huella del contenido firmado (no hay certificados digitales).
        huella = sha256(repr([(t.titulo, t.filas) for t in contenido.resumen + ([contenido.detalle]
                                                                                 if contenido.detalle else [])])
                        .encode())
        contenido.firma = (f"Firmado electrónicamente por {contenido.firma}, Contador, el "
                           f"{dict(contenido.encabezado).get('Fecha de generación', '')}. "
                           f"Huella SHA-256 del contenido: {huella}.")
    return Preparado(definicion, filtros, contenido, finca_logo, ctx.generado)


def exigir_datos(contenido: ContenidoReporte) -> None:
    """FA-2: sin datos para los filtros no se genera archivo."""
    if not contenido.tiene_datos:
        raise BusinessRuleError(code="SIN_DATOS", message=SIN_DATOS, field="filtros")


def _slug(texto: str) -> str:
    plano = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", plano.lower()).strip("_") or "reporte"


def partir_en_archivos(contenido: ContenidoReporte, formato: str, renderizador: RenderizadorReportePort,
                       ruta_logo: Optional[str], generado: datetime) -> list[ArchivoReporte]:
    """El reporte en partes de hasta 50 MB, sin ZIP (RF-104 restricción, RNF-03).

    Se divide el cuerpo de registros en partes iguales y se vuelve a generar cada una; los reportes por secciones
    (ficha del animal, ejecutivo) no tienen volumen para llegar al límite.
    """
    extension = renderizador.extension(formato)
    base = f"{_slug(contenido.titulo)}_{en_zona_usuario(generado):%Y%m%d_%H%M}"
    datos = renderizador.renderizar(contenido, formato, ruta_logo)
    if len(datos) <= LIMITE_PARTE or contenido.detalle is None or len(contenido.detalle.filas) < 2:
        return [_archivo(1, f"{base}.{extension}", renderizador.tipo_contenido(formato), datos)]
    filas = contenido.detalle.filas
    partes = math.ceil(len(datos) / LIMITE_PARTE) + 1
    while True:
        tamano = math.ceil(len(filas) / partes)
        trozos = [filas[i:i + tamano] for i in range(0, len(filas), tamano)]
        archivos = []
        for numero, trozo in enumerate(trozos, start=1):
            parte = ContenidoReporte(**{**contenido.__dict__, "titulo": f"{contenido.titulo} (parte {numero} de "
                                                                        f"{len(trozos)})",
                                        "detalle": Tabla(contenido.detalle.titulo, contenido.detalle.columnas, trozo)})
            archivos.append(_archivo(numero, f"{base}_parte_{numero}_de_{len(trozos)}.{extension}",
                                     renderizador.tipo_contenido(formato),
                                     renderizador.renderizar(parte, formato, ruta_logo)))
        if all(a.tamano_bytes <= LIMITE_PARTE for a in archivos) or tamano == 1:
            return archivos
        partes *= 2


def _archivo(numero: int, nombre: str, tipo: str, datos: bytes) -> ArchivoReporte:
    return ArchivoReporte(numero_parte=numero, nombre_archivo=nombre, tipo_contenido=tipo, contenido=datos,
                          tamano_bytes=len(datos), checksum_sha256=sha256(datos))


def detalle_auditoria(preparado: Preparado, formato: str, estado: str, checksum: Optional[str],
                      numero_registros: Optional[int], id_reporte: Any) -> dict[str, Any]:
    """Campos de auditoría de CA-15 (y la exportación contable incluida, para la trazabilidad de M07)."""
    detalle: dict[str, Any] = {
        "id_reporte": str(id_reporte), "tipo_reporte": preparado.definicion.tipo,
        "filtros_aplicados": filtros_serializables(preparado.filtros), "formato": formato,
        "fecha_snapshot": preparado.fecha_snapshot.isoformat() if preparado.fecha_snapshot else None, "estado_final": estado, "checksum": checksum,
        "numero_registros": numero_registros,
    }
    if preparado.definicion.tipo in ("REPORTE_VALORACION_NIC41", "REPORTE_ESTADO_EXPORTACIONES"):
        detalle["exportacion_contable"] = dict(preparado.contenido.encabezado).get("Exportación contable")
    return detalle


def json_seguro(valor: Any) -> Any:
    """Valores de la vista previa listos para JSON: montos como número, fechas en ISO."""
    if isinstance(valor, Decimal):
        return float(valor)
    if isinstance(valor, (date, datetime)):
        return valor.isoformat()
    return valor
