"""Caso de uso: consulta paginada del historial de auditoría (solo administradores).

Aplica filtros opcionales por usuario, tipo, categoría y rango de fechas.
Registra el propio acceso como un evento de auditoría, incluso si el acceso
fue denegado, para mantener trazabilidad completa.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from src.identity_access.domain.repositories.evento_repository import EventoRepository
from src.identity_access.domain.repositories.usuario_repository import UsuarioRepository
from src.identity_access.domain.value_objects.evento_categoria import EventoCategoria
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import InfrastructureError, ValidationError

TIPO_CONSULTA_AUDITORIA = 16

# Umbral del FA "Exceso de resultados en consulta (Saturación)".
UMBRAL_SATURACION = 10_000
TAMANO_MAXIMO_PAGINA = 50


class ConsultarAuditoriaUseCase:
    """Orquesta la consulta del log de auditoría con validación de acceso y filtros."""

    def __init__(
        self,
        eventos_repo: EventoRepository,
        db: Session,
        usuarios_repo: Optional[UsuarioRepository] = None,
    ):
        """Inicializa el use case.

        Args:
            eventos_repo: Repositorio de dominio de eventos (consulta y registro).
            db: Sesión SQLAlchemy activa del request.
            usuarios_repo: Repositorio de usuarios, para rechazar un filtro con un
                ``id_usuario`` inexistente. Si no se inyecta, ese filtro no se valida.
        """
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
            Diccionario con ``total``, ``pagina``, ``tamano``, ``items``,
            ``saturada`` y ``mensaje``. Cada ítem es una tupla
            ``(Evento, clasificacion_integridad)``.

        Raises:
            ValidationError: Si el rango de fechas es inconsistente o el
                ``id_usuario`` del filtro no existe. HTTP 400.
            InfrastructureError: Si algún registro devuelto fue manipulado. HTTP 500.
        """
        # La autorización es RBAC y vive en el router (`verificar_acceso_auditoria`),
        # que además audita el intento denegado como exige el flujo alterno.

        # 1. Validar filtros: rango de fechas y existencia del usuario filtrado.
        filtros_inconsistentes = bool(
            fecha_desde and fecha_hasta and fecha_desde > fecha_hasta
        )
        if not filtros_inconsistentes and id_usuario is not None and self.usuarios_repo:
            filtros_inconsistentes = self.usuarios_repo.obtener_por_id(id_usuario) is None

        if filtros_inconsistentes:
            raise ValidationError(
                code="FILTROS_INCONSISTENTES",
                message=(
                    "Error de consulta: Los parámetros de filtrado son inconsistentes. "
                    "Verifique el rango de fechas y los identificadores de usuario seleccionados."
                ),
            )

        # 2. Limitar tamaño de página
        tamano = min(tamano, TAMANO_MAXIMO_PAGINA)
        offset = (pagina - 1) * tamano

        # 3. Consultar eventos con verificación de integridad
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

        # 4. FA "Fallo de integridad del registro": un registro alterado es un
        # incidente de seguridad, no un dato más de la respuesta.
        manipulados = [
            evento.id_evento for evento, clase in items if clase == "MANIPULADO"
        ]
        if manipulados:
            raise InfrastructureError(
                code="INTEGRIDAD_AUDITORIA_VIOLADA",
                message=(
                    "Alerta de seguridad: Se ha detectado una violación de integridad "
                    f"en el registro de auditoría {', '.join(str(i) for i in manipulados)}. "
                    "Los datos han sido manipulados o están corruptos. Se ha notificado "
                    "al oficial de seguridad."
                ),
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

        # 6. FA "Exceso de resultados en consulta": la paginación ya protege el
        # rendimiento, pero el RF exige avisar explícitamente que la respuesta es
        # parcial para que el administrador refine la búsqueda.
        saturada = total > UMBRAL_SATURACION
        mensaje = (
            f"Consulta extensa: Se muestran los primeros {tamano} resultados. "
            "Utilice los parámetros de paginación o filtros adicionales para "
            "refinar la búsqueda."
            if saturada
            else None
        )

        return {
            "total": total,
            "pagina": pagina,
            "tamano": tamano,
            "items": items,
            "saturada": saturada,
            "mensaje": mensaje,
        }
