"""Caso de uso: consulta paginada del historial de auditoría (solo administradores).

Aplica filtros opcionales por usuario, tipo, categoría y rango de fechas.
Registra el propio acceso como un evento de auditoría, incluso si el acceso
fue denegado, para mantener trazabilidad completa.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from src.identity_access.domain.repositories.evento_repository import EventoRepository
from src.identity_access.domain.value_objects.evento_categoria import EventoCategoria
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import AuthorizationError, ValidationError

ROL_ADMINISTRADOR = 1
TIPO_CONSULTA_AUDITORIA = 16


class ConsultarAuditoriaUseCase:
    """Orquesta la consulta del log de auditoría con validación de acceso y filtros."""

    def __init__(self, eventos_repo: EventoRepository, db: Session):
        """Inicializa el use case.

        Args:
            eventos_repo: Repositorio de dominio de eventos (consulta y registro).
            db: Sesión SQLAlchemy activa del request.
        """
        self.eventos_repo = eventos_repo
        self.db = db

    def execute(
        self,
        usuario_actual: UsuarioActual,
        id_usuario: Optional[int],
        tipo_evento: Optional[int],
        fecha_desde: Optional[datetime],
        fecha_hasta: Optional[datetime],
        pagina: int,
        tamano: int,
        categoria: Optional[EventoCategoria] = None,
        archivados: bool = False,
    ) -> dict:
        """Consulta el historial de auditoría con los filtros indicados.

        Args:
            usuario_actual: Usuario autenticado que realiza la consulta.
            id_usuario: Filtrar eventos del usuario con este ID.
            tipo_evento: Filtrar por tipo de evento específico.
            fecha_desde: Inicio del rango temporal (inclusive).
            fecha_hasta: Fin del rango temporal (inclusive).
            pagina: Número de página (base 1).
            tamano: Cantidad de ítems por página (máximo efectivo: 50).
            categoria: Filtrar por categoría funcional.
            archivados: Consultar el archivo histórico de RF-10 (eventos con más
                de 12 meses) en vez del log activo. Los mismos filtros, la misma
                paginación y las mismas reglas de acceso aplican a ambos.

        Returns:
            Diccionario con ``total``, ``pagina``, ``tamano`` e ``items``, donde
            cada ítem es una tupla ``(Evento, integridad_ok)``.

        Raises:
            AuthorizationError: Si el actor no tiene rol de administrador. HTTP 403.
            ValidationError: Si ``fecha_desde`` es posterior a ``fecha_hasta``. HTTP 400.
        """
        # 1. Solo administradores
        if usuario_actual.id_rol != ROL_ADMINISTRADOR:
            try:
                self.eventos_repo.registrar(
                    tipo_evento=TIPO_CONSULTA_AUDITORIA,
                    exitoso=False,
                    id_usuario=usuario_actual.id_usuario,
                    detalle={"razon": "ACCESO_DENEGADO", "archivados": archivados},
                )
                self.db.commit()
            except Exception:
                self.db.rollback()
            raise AuthorizationError(
                code="ACCESO_DENEGADO",
                message=(
                    "Acceso denegado: No posee privilegios de administrador para consultar "
                    "el historial de auditoría. Este incidente ha sido registrado."
                ),
            )

        # 2. Validar rango de fechas
        if fecha_desde and fecha_hasta and fecha_desde > fecha_hasta:
            raise ValidationError(
                code="RANGO_FECHAS_INVALIDO",
                message=(
                    "Error de consulta: Los parámetros de filtrado son inconsistentes. "
                    "Verifique el rango de fechas y los identificadores de usuario seleccionados."
                ),
            )

        # 3. Limitar tamaño de página
        tamano = min(tamano, 50)
        offset = (pagina - 1) * tamano

        # 4. Consultar eventos con verificación de integridad
        total = self.eventos_repo.contar_eventos(
            id_usuario=id_usuario,
            tipo_evento=tipo_evento,
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta,
            categoria=categoria,
            archivados=archivados,
        )
        items = self.eventos_repo.listar_eventos(
            id_usuario=id_usuario,
            tipo_evento=tipo_evento,
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta,
            offset=offset,
            limit=tamano,
            categoria=categoria,
            archivados=archivados,
        )

        # 5. Registrar evento de consulta
        try:
            self.eventos_repo.registrar(
                tipo_evento=TIPO_CONSULTA_AUDITORIA,
                exitoso=True,
                id_usuario=usuario_actual.id_usuario,
                detalle={
                    "filtros": {
                        "id_usuario": id_usuario,
                        "tipo_evento": tipo_evento,
                        "categoria": categoria.value if categoria else None,
                        "fecha_desde": fecha_desde.isoformat() if fecha_desde else None,
                        "fecha_hasta": fecha_hasta.isoformat() if fecha_hasta else None,
                    },
                    "archivados": archivados,
                    "total_resultados": total,
                },
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return {
            "total": total,
            "pagina": pagina,
            "tamano": tamano,
            "items": items,
        }
