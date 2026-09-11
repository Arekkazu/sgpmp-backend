"""Casos de uso de la exportación asíncrona de auditoría (RF-10).

La exportación síncrona mantiene la petición abierta mientras arma el archivo.
Por encima del umbral configurable eso deja de ser razonable: el trabajo se
encola, un poller lo procesa y el cliente consulta el estado hasta descargar.

Los tres casos de uso viven juntos porque son las tres caras de la misma cola y
ninguno tiene sentido sin los otros dos.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from src.identity_access.application.use_cases.auditoria.exportar_auditoria_use_case import (
    ExportarAuditoriaUseCase,
)
from src.identity_access.domain.entities.exportacion_auditoria import (
    ResultadoExportacion,
    TrabajoExportacion,
)
from src.identity_access.domain.repositories.exportacion_auditoria_repository import (
    ExportacionAuditoriaRepository,
)
from src.identity_access.domain.value_objects.evento_categoria import EventoCategoria
from src.shared.errors import NotFoundError, BusinessRuleError, TooManyRequestsError

logger = logging.getLogger(__name__)


class SolicitarExportacionAuditoriaUseCase:
    """Encola una exportación grande y devuelve su identificador de seguimiento."""

    def __init__(self, db: Session, cola_repo: ExportacionAuditoriaRepository):
        self.db = db
        self.cola_repo = cola_repo

    def execute(self, filtros: dict, id_usuario: int) -> TrabajoExportacion:
        config = self.cola_repo.obtener_configuracion()

        if self.cola_repo.contar_activos() >= config.limite_concurrencia:
            raise TooManyRequestsError(
                code="LIMITE_EXPORTACIONES_EXCEDIDO",
                message=(
                    "Límite de exportaciones simultáneas alcanzado. Espere a que "
                    "alguna finalice antes de solicitar otra."
                ),
            )

        trabajo = TrabajoExportacion(
            parametros=serializar_filtros(filtros),
            id_usuario_solicitante=id_usuario,
        )
        try:
            trabajo = self.cola_repo.encolar(trabajo)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return trabajo


class ConsultarExportacionAuditoriaUseCase:
    """Estado de un trabajo encolado, para que el cliente sepa cuándo descargar."""

    def __init__(self, cola_repo: ExportacionAuditoriaRepository):
        self.cola_repo = cola_repo

    def execute(self, id_cola: int) -> TrabajoExportacion:
        trabajo = self.cola_repo.obtener(id_cola)
        if trabajo is None:
            raise NotFoundError(
                code="EXPORTACION_NO_ENCONTRADA",
                message="La exportación solicitada no existe.",
            )
        return trabajo


class DescargarExportacionAuditoriaUseCase:
    """Entrega el CSV de un trabajo ya completado."""

    def __init__(self, cola_repo: ExportacionAuditoriaRepository):
        self.cola_repo = cola_repo

    def execute(self, id_cola: int) -> ResultadoExportacion:
        trabajo = self.cola_repo.obtener(id_cola)
        if trabajo is None:
            raise NotFoundError(
                code="EXPORTACION_NO_ENCONTRADA",
                message="La exportación solicitada no existe.",
            )
        if not trabajo.descargable:
            raise BusinessRuleError(
                code="EXPORTACION_NO_DISPONIBLE",
                message=(
                    f"La exportación está en estado {trabajo.estado}. "
                    "Solo se puede descargar una exportación completada."
                ),
            )
        resultado = self.cola_repo.obtener_resultado(id_cola)
        if resultado is None:
            raise NotFoundError(
                code="EXPORTACION_NO_ENCONTRADA",
                message="El archivo de la exportación ya no está disponible.",
            )
        return resultado


class ProcesarColaExportacionesUseCase:
    """Worker: toma trabajos pendientes y genera su CSV.

    Reusa `ExportarAuditoriaUseCase` sin tope de volumen: el corte síncrono
    existe para no dejar una petición HTTP colgada, y aquí no hay ninguna
    esperando.
    """

    def __init__(
        self,
        db: Session,
        cola_repo: ExportacionAuditoriaRepository,
        exportar_use_case: ExportarAuditoriaUseCase,
    ):
        self.db = db
        self.cola_repo = cola_repo
        self.exportar_use_case = exportar_use_case

    def ejecutar(self) -> int:
        """Procesa los pendientes disponibles. Devuelve cuántos completó."""
        config = self.cola_repo.obtener_configuracion()
        if not config.es_activo:
            return 0

        procesados = 0
        for _ in range(config.num_workers_max):
            trabajo = self._tomar()
            if trabajo is None:
                break
            if self._procesar(trabajo, config.max_reintentos):
                procesados += 1
        return procesados

    def _tomar(self) -> Optional[TrabajoExportacion]:
        try:
            trabajo = self.cola_repo.tomar_pendiente()
            self.db.commit()
            return trabajo
        except Exception:
            self.db.rollback()
            raise

    def _procesar(self, trabajo: TrabajoExportacion, max_reintentos: int) -> bool:
        try:
            lineas, total_disponible, total_exportado = self.exportar_use_case.execute(
                usuario_actual=_Solicitante(trabajo.id_usuario_solicitante),
                **deserializar_filtros(trabajo.parametros),
            )
            fecha = datetime.now(timezone.utc).date().isoformat()
            self.cola_repo.completar(
                trabajo.id_cola,
                ResultadoExportacion(
                    contenido_csv="".join(lineas),
                    nombre_archivo=f"auditoria-{fecha}.csv",
                    total_exportado=total_exportado,
                    total_disponible=total_disponible,
                ),
            )
            self.db.commit()
            return True
        except Exception as exc:
            self.db.rollback()
            logger.exception("Falló la exportación de auditoría %s.", trabajo.id_cola)
            reintentable = trabajo.intentos < max_reintentos
            try:
                self.cola_repo.fallar(trabajo.id_cola, str(exc), reintentable)
                self.db.commit()
            except Exception:
                self.db.rollback()
            return False


class _Solicitante:
    """Portador del `id_usuario` para auditar la exportación diferida.

    El use case síncrono espera un `UsuarioActual`, pero fuera de un request no
    hay ninguno: el trabajo ya pasó por RBAC cuando se encoló.
    """

    def __init__(self, id_usuario: int):
        self.id_usuario = id_usuario


def serializar_filtros(filtros: dict) -> dict:
    """Deja los filtros en JSON plano para guardarlos en la cola."""
    return {
        "id_usuario": filtros.get("id_usuario"),
        "tipo_evento": filtros.get("tipo_evento"),
        "categoria": (
            filtros["categoria"].value if filtros.get("categoria") else None
        ),
        "fecha_desde": (
            filtros["fecha_desde"].isoformat() if filtros.get("fecha_desde") else None
        ),
        "fecha_hasta": (
            filtros["fecha_hasta"].isoformat() if filtros.get("fecha_hasta") else None
        ),
        "archivados": bool(filtros.get("archivados", False)),
    }


def deserializar_filtros(parametros: dict) -> dict:
    """Reconstruye los filtros tipados desde lo guardado en la cola."""
    return {
        "id_usuario": parametros.get("id_usuario"),
        "tipo_evento": parametros.get("tipo_evento"),
        "categoria": (
            EventoCategoria(parametros["categoria"])
            if parametros.get("categoria")
            else None
        ),
        "fecha_desde": (
            datetime.fromisoformat(parametros["fecha_desde"])
            if parametros.get("fecha_desde")
            else None
        ),
        "fecha_hasta": (
            datetime.fromisoformat(parametros["fecha_hasta"])
            if parametros.get("fecha_hasta")
            else None
        ),
        "archivados": bool(parametros.get("archivados", False)),
    }
