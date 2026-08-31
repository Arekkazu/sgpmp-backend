"""Caso de uso: exportación del historial de auditoría a CSV (RF-10).

Existe porque paginar el log para exportarlo salía carísimo: con el tope de 50
registros por página, una descarga completa costaba 200 peticiones, cada una con
su ``COUNT(*)``, su verificación de hashes y **su propio evento de auditoría**.
El log terminaba contaminado con el ruido de leerlo. Aquí todo eso ocurre una
sola vez y deja un único evento ``EXPORTACION_AUDITORIA``.

El CSV se transmite en streaming, pero la integridad se verifica antes de emitir
el primer byte: un registro ``MANIPULADO`` debe poder abortar con 500, y una vez
enviadas las cabeceras del 200 eso ya no es posible.
"""
from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Iterator, Optional

from sqlalchemy.orm import Session

from src.identity_access.application.use_cases.auditoria.consultar_auditoria_use_case import (
    UMBRAL_SATURACION,
)
from src.identity_access.domain.repositories.evento_repository import EventoRepository
from src.identity_access.domain.repositories.usuario_repository import UsuarioRepository
from src.identity_access.domain.value_objects.evento_categoria import (
    EventoCategoria,
    nombre_para_tipo_evento,
)
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import InfrastructureError, ValidationError

TIPO_EXPORTACION_AUDITORIA = 26

# Mismo corte que declara saturada una consulta paginada: por encima de este
# volumen el RF pide refinar los filtros, no entregar un archivo más grande.
LIMITE_EXPORTACION = UMBRAL_SATURACION

CABECERA_CSV = [
    "ID",
    "Usuario",
    "Tipo evento",
    "Módulo",
    "Descripción",
    "Resultado",
    "IP",
    "Fecha/Hora",
    "Integridad",
]


class ExportarAuditoriaUseCase:
    """Genera el CSV del historial de auditoría completo para los filtros dados."""

    def __init__(
        self,
        eventos_repo: EventoRepository,
        db: Session,
        usuarios_repo: Optional[UsuarioRepository] = None,
    ):
        self.eventos_repo = eventos_repo
        self.db = db
        self.usuarios_repo = usuarios_repo

    def execute(
        self,
        usuario_actual: UsuarioActual,
        id_usuario: Optional[int],
        tipo_evento: Optional[int],
        fecha_desde: Optional[datetime],
        fecha_hasta: Optional[datetime],
        categoria: Optional[EventoCategoria] = None,
        archivados: bool = False,
    ) -> tuple[Iterator[str], int, int]:
        """Prepara la exportación y devuelve el generador del CSV.

        Returns:
            Tupla ``(lineas_csv, total_disponible, total_exportado)``. El primer
            elemento es un generador: al retornarlo, la validación de filtros y
            la verificación de integridad ya ocurrieron, así que cualquier error
            se levantó antes de que el router arme la respuesta.

        Raises:
            ValidationError: Filtros inconsistentes. HTTP 400.
            InfrastructureError: Algún registro del conjunto fue manipulado. HTTP 500.
        """
        self._validar_filtros(id_usuario, fecha_desde, fecha_hasta)

        filtros = {
            "id_usuario": id_usuario,
            "tipo_evento": tipo_evento,
            "fecha_desde": fecha_desde,
            "fecha_hasta": fecha_hasta,
            "categoria": categoria,
            "archivados": archivados,
        }

        total_disponible = self.eventos_repo.contar_eventos(**filtros)
        total_exportado = min(total_disponible, LIMITE_EXPORTACION)

        # Pasada 1: integridad de todo el conjunto, antes de emitir nada.
        clasificacion = self.eventos_repo.clasificar_conjunto(
            limite=LIMITE_EXPORTACION, **filtros
        )
        manipulados = [
            id_evento
            for id_evento, clase in clasificacion.items()
            if clase == "MANIPULADO"
        ]
        if manipulados:
            raise InfrastructureError(
                code="INTEGRIDAD_AUDITORIA_VIOLADA",
                message=(
                    "Alerta de seguridad: Se ha detectado una violación de integridad "
                    f"en el registro de auditoría {', '.join(str(i) for i in sorted(manipulados))}. "
                    "Los datos han sido manipulados o están corruptos. Se ha notificado "
                    "al oficial de seguridad."
                ),
            )

        self._registrar_exportacion(
            usuario_actual, filtros, total_disponible, total_exportado
        )

        return (
            self._lineas_csv(filtros, clasificacion, total_exportado),
            total_disponible,
            total_exportado,
        )

    def _validar_filtros(
        self,
        id_usuario: Optional[int],
        fecha_desde: Optional[datetime],
        fecha_hasta: Optional[datetime],
    ) -> None:
        """Mismas reglas que la consulta paginada, para que no diverjan."""
        inconsistentes = bool(fecha_desde and fecha_hasta and fecha_desde > fecha_hasta)
        if not inconsistentes and id_usuario is not None and self.usuarios_repo:
            inconsistentes = self.usuarios_repo.obtener_por_id(id_usuario) is None

        if inconsistentes:
            raise ValidationError(
                code="FILTROS_INCONSISTENTES",
                message=(
                    "Error de consulta: Los parámetros de filtrado son inconsistentes. "
                    "Verifique el rango de fechas y los identificadores de usuario seleccionados."
                ),
            )

    def _lineas_csv(
        self, filtros: dict, clasificacion: dict[int, str], total_exportado: int
    ) -> Iterator[str]:
        """Emite el CSV línea a línea (pasada 2), sin armarlo entero en memoria.

        El corte en ``total_exportado`` no es decorativo: entre el conteo y esta
        pasada pueden entrar eventos nuevos —empezando por el de esta misma
        exportación— y el archivo tendría más filas de las que anuncia la
        cabecera ``X-Registros-Exportados``.
        """
        # El BOM hace que Excel abra el archivo como UTF-8; sin él, "Módulo" y
        # "Descripción" salen con los acentos rotos.
        yield "﻿" + self._fila(CABECERA_CSV)

        emitidas = 0
        for evento in self.eventos_repo.iterar_eventos(
            limite=LIMITE_EXPORTACION, **filtros
        ):
            if emitidas >= total_exportado:
                break
            emitidas += 1
            yield self._fila([
                evento.id_evento,
                evento.nombre_usuario or evento.id_usuario,
                nombre_para_tipo_evento(evento.tipo_evento),
                evento.modulo,
                evento.descripcion or "",
                evento.resultado,
                evento.direccion_ip or "",
                evento.fecha_evento.isoformat() if evento.fecha_evento else "",
                clasificacion.get(evento.id_evento, ""),
            ])

    @staticmethod
    def _fila(valores: list) -> str:
        """Serializa una fila con las reglas de comillas del CSV estándar."""
        buffer = io.StringIO()
        # `csv` ya usa CRLF por defecto, que es lo que Excel espera.
        csv.writer(buffer).writerow(valores)
        return buffer.getvalue()

    def _registrar_exportacion(
        self,
        usuario_actual: UsuarioActual,
        filtros: dict,
        total_disponible: int,
        total_exportado: int,
    ) -> None:
        """Deja el único evento de la exportación.

        Si la auditoría del propio export falla, se revierte y se sigue: el
        archivo ya está listo y negárselo al administrador no arregla nada.
        """
        try:
            self.eventos_repo.registrar(
                tipo_evento=TIPO_EXPORTACION_AUDITORIA,
                exitoso=True,
                id_usuario=usuario_actual.id_usuario,
                detalle={
                    "filtros": {
                        "id_usuario": filtros["id_usuario"],
                        "tipo_evento": filtros["tipo_evento"],
                        "categoria": (
                            filtros["categoria"].value if filtros["categoria"] else None
                        ),
                        "fecha_desde": (
                            filtros["fecha_desde"].isoformat()
                            if filtros["fecha_desde"]
                            else None
                        ),
                        "fecha_hasta": (
                            filtros["fecha_hasta"].isoformat()
                            if filtros["fecha_hasta"]
                            else None
                        ),
                    },
                    "archivados": filtros["archivados"],
                    "total_disponible": total_disponible,
                    "total_exportado": total_exportado,
                    "truncado": total_exportado < total_disponible,
                },
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
