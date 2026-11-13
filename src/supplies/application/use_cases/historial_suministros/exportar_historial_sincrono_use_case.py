# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-81: PDF/Excel, 202 > 10.000, firma     |
# | 2026-11-09 | LuisfNarvaez01   | INC-M05-284-G43 RF-81: el evento guarda filtros aplicados y total retornado |
# | 2026-11-10 | Arekkazu         | CP088 RF-81: PDF y Excel con encabezados, fechas, montos y catálogos en palabras; sin recorte |
# | 2026-11-12 | LuisfNarvaez01 | INC-M05-358-G43 RF-81: activo ajeno → 403 de E2, no 404 |
"""Caso de uso: exportar el historial de suministros a PDF o Excel (RF-81 Fase 6).

- ≤ 10.000 registros: archivo síncrono (≤ 10 s).
- > 10.000: se encola un trabajo EXPORTACION y se responde 202 con
  ``id_exportacion`` (E3); máximo 3 exportaciones asíncronas en curso por
  usuario (E6, 429). El worker genera el archivo, lo deja disponible 72 h y
  avisa al usuario.

El archivo trae encabezado del activo, todos los campos de cada registro,
subtotales por tipo de suministro y por ciclo, y firma (SHA-256 de las filas)
con el timestamp del sistema. Registra ``EXPORTACION_HISTORIAL_GENERADA`` en la
bitácora de M05 (RF-80) sin bloquear la respuesta si la auditoría falla.
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Optional, Union

from sqlalchemy.orm import Session

from src.shared.errors import AuthorizationError, BusinessRuleError, NotFoundError
from src.supplies.application.use_cases.exportacion.generador_archivos import (
    Documento,
    fecha,
    generar_excel,
    generar_pdf,
    legible,
    moneda,
    numero,
)
from src.supplies.domain.entities.historial_suministro import FiltrosHistorialSuministro, LineaHistorialSuministro
from src.supplies.domain.entities.trabajo_historial_suministro import TrabajoHistorialSuministro
from src.supplies.domain.repositories.activo_consulta_port import ActivoConsultaPort
from src.supplies.domain.repositories.alcance_activo_port import AlcanceActivoPort
from src.supplies.domain.repositories.auditoria_suministro_port import (
    AuditoriaSuministroPort,
    EventoAuditoriaSuministro,
)
from src.supplies.domain.repositories.configuracion_batch_historial_repository import (
    ConfiguracionBatchHistorialRepository,
)
from src.supplies.domain.repositories.historial_suministro_read_port import HistorialSuministroReadPort
from src.supplies.domain.value_objects.historial_suministro_enums import TipoTrabajoHistorial

logger = logging.getLogger(__name__)

FORMATOS = {"PDF": ".pdf", "EXCEL": ".xlsx"}
_COLUMNAS = [
    "id_registro_suministro",
    "tipo_suministro",
    "tipo_operacion",
    "descripcion",
    "fecha_aplicacion",
    "cantidad",
    "unidad_medida",
    "precio_unitario",
    "costo_registro",
    "origen_precio",
    "nombre_activo",
    "especie",
    "nombre_ciclo",
    "estado_ciclo",
    "observacion",
]


# Lo que lee una persona en el PDF y el Excel; la firma se calcula sobre los valores originales.
_ETIQUETAS = [
    "Id. del registro", "Tipo", "Operación", "Descripción", "Fecha", "Cantidad", "Unidad", "Precio unitario",
    "Costo", "Origen del precio", "Activo", "Especie", "Ciclo", "Estado del ciclo", "Observación",
]
_TIPO = {"ALIMENTO": "Alimento", "MEDICAMENTO": "Medicamento", "SERVICIO_VETERINARIO": "Servicio veterinario",
         "INSEMINACION": "Inseminación", "TODOS": "Todos"}
_OPERACION = {"REGISTRO": "Registro", "CORRECCION": "Corrección"}
_ORIGEN = {"MANUAL": "Precio manual", "M40_AUTOMATICO": "Precio automático", "CATALOGO": "Catálogo", "TODOS": "Todos"}


def _fila_legible(l: LineaHistorialSuministro) -> list:
    return [
        l.id_registro_suministro, legible(l.tipo_suministro, _TIPO), legible(l.tipo_operacion, _OPERACION), l.descripcion,
        fecha(l.fecha_aplicacion), numero(l.cantidad, 3), l.unidad_medida, moneda(l.precio_unitario), moneda(l.costo_registro),
        legible(l.origen_precio, _ORIGEN), l.nombre_activo or "", l.especie or "", l.nombre_ciclo or "",
        legible(l.estado_ciclo), l.observacion or "",
    ]


def _fila(l: LineaHistorialSuministro) -> list:
    return [
        l.id_registro_suministro, l.tipo_suministro, l.tipo_operacion, l.descripcion,
        l.fecha_aplicacion.isoformat(), l.cantidad, l.unidad_medida, l.precio_unitario, l.costo_registro,
        l.origen_precio, l.nombre_activo, l.especie, l.nombre_ciclo, l.estado_ciclo, l.observacion,
    ]


@dataclass(frozen=True)
class ArchivoHistorial:
    contenido: bytes
    nombre_archivo: str
    formato: str
    total_registros: int


class ExportarHistorialSincronoUseCase:
    def __init__(
        self,
        historial_port: HistorialSuministroReadPort,
        alcance_port: AlcanceActivoPort,
        activo_port: ActivoConsultaPort,
        config_repo: ConfiguracionBatchHistorialRepository,
        db: Session,
        auditoria_port: AuditoriaSuministroPort,
        solicitar: Optional[object] = None,
    ) -> None:
        self.historial_port = historial_port
        self.alcance_port = alcance_port
        self.activo_port = activo_port
        self.config_repo = config_repo
        self.db = db
        self.auditoria_port = auditoria_port
        self.solicitar = solicitar

    def execute(
        self, filtros: FiltrosHistorialSuministro, formato: str, *, id_usuario: int, id_rol: int
    ) -> Union[ArchivoHistorial, TrabajoHistorialSuministro]:
        ids_permitidos = self._validar(filtros, formato, id_usuario, id_rol)
        config = self.config_repo.obtener()
        resultado = self.historial_port.consultar(
            replace(filtros, pagina=1, registros_por_pagina=config.umbral_exportacion_async), ids_permitidos
        )
        if resultado.total_registros_filtrados > config.umbral_exportacion_async:
            return self.solicitar.execute(
                TipoTrabajoHistorial.EXPORTACION.value, filtros, id_usuario, id_rol, formato_exportacion=formato
            )
        return self._archivo(filtros, formato, resultado, id_usuario)

    def exportar_forzado(
        self, filtros: FiltrosHistorialSuministro, formato: str, *, id_usuario: int, id_rol: int
    ) -> ArchivoHistorial:
        """Worker del motor async (trabajo EXPORTACION): todo el volumen, sin umbral síncrono."""
        ids_permitidos = self._validar(filtros, formato, id_usuario, id_rol)
        resultado = self.historial_port.consultar(
            replace(filtros, pagina=1, registros_por_pagina=5_000_000), ids_permitidos
        )
        return self._archivo(filtros, formato, resultado, id_usuario)

    # ── Auxiliares ───────────────────────────────────────────────────────────
    def _validar(self, filtros: FiltrosHistorialSuministro, formato: str, id_usuario: int, id_rol: int):
        if formato not in FORMATOS:
            raise BusinessRuleError(
                code="FORMATO_EXPORTACION_INVALIDO",
                message="El formato de exportación del historial debe ser PDF o EXCEL.",
                field="formato_exportacion",
            )
        activo = self.activo_port.obtener(filtros.id_activo_biologico)
        if activo is None:
            if self.activo_port.existe(filtros.id_activo_biologico):
                # E2: existe pero está fuera de las unidades productivas del usuario (la RLS lo oculta).
                raise AuthorizationError(
                    code="ACCESO_DENEGADO",
                    message=(
                        f"No tiene permisos para consultar el historial del activo {filtros.id_activo_biologico}. "
                        "Verifique su rol y unidades productivas asignadas."
                    ),
                )
            raise NotFoundError(
                code="ACTIVO_NO_ENCONTRADO",
                message=f"El activo biológico {filtros.id_activo_biologico} no existe.",
                field="id_activo_biologico",
            )
        ids_permitidos = self.alcance_port.listar_ids_activos_permitidos(id_usuario, id_rol)
        if ids_permitidos is not None and filtros.id_activo_biologico not in ids_permitidos:
            raise AuthorizationError(
                code="ACCESO_DENEGADO",
                message=(
                    f"No tiene permisos para consultar el historial del activo {filtros.id_activo_biologico}. "
                    "Verifique su rol y unidades productivas asignadas."
                ),
            )
        return ids_permitidos

    def _archivo(self, filtros, formato: str, resultado, id_usuario: int) -> ArchivoHistorial:
        ahora = datetime.now(timezone.utc)
        filas = [_fila(l) for l in resultado.lineas]
        firma = hashlib.sha256("\n".join("|".join(map(str, f)) for f in filas).encode("utf-8")).hexdigest()
        primera = resultado.lineas[0] if resultado.lineas else None
        ciclos = {l.id_ciclo_productivo: l.nombre_ciclo for l in resultado.lineas if l.nombre_ciclo}
        rango = (f"{fecha(filtros.fecha_inicio_filtro) or 'el inicio'} a {fecha(filtros.fecha_fin_filtro) or 'hoy'}"
                 if filtros.fecha_inicio_filtro or filtros.fecha_fin_filtro else "todas")
        documento = Documento(
            titulo="Historial de Suministros",
            columnas=_ETIQUETAS,
            filas=[_fila_legible(l) for l in resultado.lineas],
            encabezado=[
                "Activo: " + (f"{primera.nombre_activo} ({primera.especie})" if primera and primera.nombre_activo
                              else f"N.º {filtros.id_activo_biologico}"),
                f"Filtros · ciclo: {ciclos.get(filtros.id_ciclo_productivo, 'todos') if filtros.id_ciclo_productivo else 'todos'}"
                f" · fechas: {rango} · tipo: {legible(filtros.tipo_suministro_filtro, _TIPO).lower()}"
                f" · origen del precio: {legible(filtros.origen_precio_filtro, _ORIGEN).lower()}",
                f"Total de registros: {resultado.total_registros_filtrados} · "
                f"Monto total: {moneda(resultado.monto_total_filtrado)}",
            ],
            pie=[
                *(f"Subtotal {legible(tipo, _TIPO).lower()}: {moneda(d['monto'])} ({d['total']} registros)"
                  for tipo, d in resultado.desglose_por_tipo_suministro.items()),
                *(f"Subtotal del ciclo {ciclos.get(ciclo, 'sin nombre')}: {moneda(d['monto'])} ({d['total']} registros)"
                  for ciclo, d in resultado.desglose_por_ciclo.items()),
                f"Firma del sistema (SHA-256): {firma}",
                "Generado por SIGAB",
            ],
        )
        contenido = generar_pdf(documento, ahora) if formato == "PDF" else generar_excel(documento)
        nombre = (
            f"Historial_Suministros_{filtros.id_activo_biologico}_"
            f"{filtros.fecha_inicio_filtro or 'inicio'}_{filtros.fecha_fin_filtro or 'fin'}{FORMATOS[formato]}"
        )
        self._auditar_exportacion(filtros, id_usuario, formato, resultado.total_registros_filtrados)
        return ArchivoHistorial(
            contenido=contenido, nombre_archivo=nombre, formato=formato,
            total_registros=resultado.total_registros_filtrados,
        )

    def _auditar_exportacion(self, filtros: FiltrosHistorialSuministro, id_usuario: int, formato: str,
                             total: int) -> None:
        # RF-81 Fase 7 / CA-8 / Postcondición 2: filtros aplicados y total de registros exportados.
        datos = {"filtros_aplicados": filtros.para_auditoria(), "formato_exportacion": formato,
                 "total_registros_retornados": total}
        try:
            self.auditoria_port.registrar(
                EventoAuditoriaSuministro(
                    entidad_afectada="historial_suministros",
                    tipo_operacion="EXPORTACION_HISTORIAL_GENERADA",
                    id_usuario=id_usuario,
                    resultado="EXITOSO",
                    id_activo_biologico=filtros.id_activo_biologico,
                    id_ciclo_productivo=filtros.id_ciclo_productivo,
                    datos_nuevos=datos,
                )
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            logger.exception("Error al auditar EXPORTACION_HISTORIAL_GENERADA para activo %s", filtros.id_activo_biologico)
